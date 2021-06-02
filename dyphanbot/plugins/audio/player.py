import copy
import asyncio
import logging
import textwrap

from async_timeout import timeout

import discord
import dyphanbot.utils as utils

from .extractor import (
    YTDLExtractor, YTDLEntry, YTDLPlaylist, YTDLPlaylistEntry, AudioExtractionError)


class AudioPlayer(object):
    """ Handles fetching and parsing media from URLs using youtube-dl, as well
    as the playlist queue.
    """
    def __init__(self, client: discord.Client, guild: discord.Guild,
            message: discord.Message=None, config: dict={}, **kwargs):
        self._logger = logging.getLogger(__name__)
        self._dead = False
        self._tasks = []
        self.client = client
        self.message = message
        self.guild = message.guild if message else guild
        self.vclient = self.guild.voice_client
        self.config = config
        self.kwargs = kwargs

        self.queue = asyncio.Queue()
        self.next = asyncio.Event()

        self.now_playing = None
        self.volume = 0.5
        self.current = None
        self.next_source = None
        self.last_source = None
        self._repeat = False

        # TODO: Make webhook embeds actually optional per-server...
        self.can_use_webhooks = self.config.get('use_webhooks', False)

        self.loop = self.vclient.loop
        self.ytdl_extractor = YTDLExtractor(self.loop)
        self.audio_player = self.loop.create_task(self.player_loop())
    
    async def _run_future(self, func):
        future = self.loop.run_in_executor(None, func)
        self._tasks.append(future)
        return await future
    
    async def _send_message(self, message: discord.Message, silent):
        """ Sends or edits discord message if not `silent` """
        async def send_message(content, message: discord.Message=message, **kwargs):
            if message and not silent:
                if message.author == self.client.user:
                    await message.edit(content=content, **kwargs)
                    return message
                return await message.channel.send(content, **kwargs)
            return None
        return send_message
    
    @property
    def repeat(self):
        """ Weather the current song will repeat after it's done """
        return self._repeat
    
    @repeat.setter
    def repeat(self, val):
        self._repeat = val

    async def prepare_entries(self, search, message=None, *, custom_data={},
                              silent=False, requester=None, channel=None):
        if message is not None:
            requester = message.author
            channel = message.channel
        
        send_message = await self._send_message(message, silent)
        msg = await send_message("Preparing requested source(s)...")
        
        try:
            entry_data = await self.ytdl_extractor.process_entries(
                search, custom_data=custom_data, channel=channel,
                requester=requester, message_callback=send_message)
            
            # If it's a playlist with more than one video, get each entry and
            # queue them one by one to process them later in the player loop.
            # Otherwise, if it's a single entry, just queue it as-is.
            if isinstance(entry_data, YTDLPlaylist):
                playlist = entry_data
                loading_notice = "\nThis might take a while depending on the playlist size." if playlist.title else ""
                fpname = " from `{}`".format(playlist.title) if playlist.title else ""
                msg = await send_message(
                    "Queuing playlist entries{}...{}".format(fpname, loading_notice),
                    message=msg)
                
                entry_count = 0
                last_entry = None
                entries = await self._run_future(playlist.entries)
                for entry in entries:
                    await self.queue.put(entry)
                    last_entry = entry
                    entry_count += 1
                
                if last_entry and entry_count == 1:
                    await send_message(
                        "Added to queue: `{}`".format(last_entry.title),
                        message=msg)
                else:
                    await send_message(
                        "Added {} playlist entries{}.".format(entry_count, fpname),
                        message=msg)
            elif isinstance(entry_data, YTDLEntry):
                await self.queue.put(entry_data)
                await send_message(
                    "Added to queue: `{}`".format(entry_data.title),
                    message=msg)
            else:
                # wait, wtf?
                raise AudioExtractionError(
                    "Processed entry data is neither of YTDLPlaylist nor YTDLEntry (which shouldn't happen)",
                    "An Onixpected error occurred... Dx"
                )
        except AudioExtractionError as err:
            self._logger.error(err.message)
            return await send_message(err.display_message, message=msg)
    
    def np_status_str(self, source):
        """ Return the proper "Now Playing" status for the embed title """
        status = ("Now Streaming" if source.is_live else "Now Playing") if self.vclient.is_playing() else "Paused"
        if self.repeat and not source.is_live:
            status += " (on repeat)"
        return status

    def np_embed(self, source, webhook=False):
        """ Generates 'Now Playing'/'Now Streaming'/'Paused' status embed. """
        embed = discord.Embed(
            title=source.title,
            colour=discord.Colour(0x7289DA),
            url=source.web_url if not source.entry._data.get('no_url') else discord.Embed.Empty,
            description=source.description if source.entry._data.get('full_desc') else textwrap.shorten(source.description, 157, placeholder="..."),
            timestamp=self.message.created_at if self.message else discord.Embed.Empty
        )

        if source.thumbnail:
            embed.set_thumbnail(url=source.thumbnail)
        
        if not webhook:
            embed.set_author(
                name=self.np_status_str(source),
                url="https://github.com/buzzbyte/DyphanBot",
                icon_url=utils.get_user_avatar_url(source.entry.channel.guild.me)
            )
        
        if source.requester:
            embed.set_footer(
                text="Requested by: {0.display_name}".format(source.requester),
                icon_url=utils.get_user_avatar_url(source.requester))
        
        if source.uploader:
            embed.add_field(name="Uploaded by", value=source.uploader, inline=True)

        duration = source.duration
        progress_time = source.get_progress()
        if duration:
            progress_str = utils.secs_to_hms(progress_time) if progress_time else None
            duration_str = utils.secs_to_hms(duration)
            field_name = "Progress" if progress_str else "Duration"
            field_val  = "{} / {}".format(progress_str, duration_str) if progress_str else duration_str
            embed.add_field(name=field_name, value=field_val, inline=True)
        else:
            if progress_time:
                progress_str = utils.secs_to_hms(progress_time)
                embed.add_field(name="Playing for", value=progress_str, inline=True)

        return embed

    def played_embed(self, source):
        """ Generates the 'Played' status embed for previously played audio. """
        embed = discord.Embed(
            title=source.title,
            colour=discord.Colour(0x7289DA),
            url=source.web_url if not source.entry._data.get('no_url') else discord.Embed.Empty,
        )

        embed.set_author(name="Played")

        return embed
    
    def play_finalize(self, error):
        """ Called after VoiceClient finishes playing source or error occured """
        if error:
            if getattr(self.client, 'dev_mode', False):
                raise error
            self._logger.error("%s: %s", type(error).__name__, error)
        
        return self.loop.call_soon_threadsafe(self.next.set)

    async def get_queued_source(self, wait_for_queue=True):
        """ Gets next queued entry, processes it, and returns its source """
        source = None

        if wait_for_queue:
            async with timeout(300): # 5 minutes
                entry = await self.queue.get()
        else:
            entry = self.queue.get_nowait()

        if isinstance(entry, YTDLPlaylistEntry):
            entry = await entry.process()
        
        if isinstance(entry, YTDLEntry):
            source = await entry.regather_source()
        
        return (entry, source)

    async def player_loop(self):
        """ Main player loop """
        await self.client.wait_until_ready()

        while not self.client.is_closed():
            self.next.clear()

            if self.repeat and self.last_source:
                new_source = await self.last_source.entry.regather_source()
                source = new_source
            else:
                source = self.next_source
                self.next_source = None
            
            if not source:
                try:
                    entry, source = await self.get_queued_source()
                except asyncio.TimeoutError:
                    return await self.destroy()
                except asyncio.CancelledError:
                    pass # assume cancellation was intentional
                except Exception:
                    continue
            
            if source and self.vclient:
                source.volume = self.volume
                self.current = source

                if source.entry._data.get('before_playback'):
                    await source.entry._data['before_playback']()
                
                self.vclient.play(source, after=self.play_finalize)
                await self.update_now_playing(source.entry.channel)

                if self.last_source:
                    self.last_source.cleanup()
                
                self.last_source = source
                
                if not self.next_source and not self.repeat:
                    try:
                        _, self.next_source = await self.get_queued_source(
                            wait_for_queue=False)
                    except Exception:
                        # we'll get 'em next time...
                        self.next_source = None
                
                await self.next.wait()
                if source.entry._data.get('after_playback'):
                    await source.entry._data['after_playback']()

                await self.update_last_playing(source)
                source.cleanup()
            
            self.current = None

    async def find_or_create_webhook(self, channel):
        if self.guild.me.permissions_in(channel).manage_webhooks and self.can_use_webhooks:
            for webhook in await channel.webhooks():
                if "DyphanBot" in webhook.name:
                    return webhook
            return await channel.create_webhook(name="DyphanBot Webhook")
        return None

    async def update_now_playing(self, channel):
        """ Deletes previous playing status embed and sends a new one. """
        if not channel:
            return None
        
        webhook = await self.find_or_create_webhook(channel)
        if webhook:
            self.now_playing = await webhook.send(
                embed=self.np_embed(self.current, webhook=True),
                avatar_url=utils.get_user_avatar_url(channel.guild.me),
                username=self.np_status_str(self.current)
            )
        else:
            await self.update_last_playing()
            if 'components' in self.config.get('enabled_experiments', []):
                from discord_components import (
                    DiscordComponents, Button, ButtonStyle)
                ddb: DiscordComponents = self.kwargs.get("ddb")
                if ddb:
                    self.now_playing = await ddb.send_component_msg(
                        channel,
                        content="Buttons experiment enabled",
                        embed=self.np_embed(self.current),
                        components=[
                            [
                                Button(label="\u275A\u275A" if self.vclient.is_playing() else "\u25B6\uFE0E", id="play-pause"),
                                Button(label="\u2B1B\uFE0E", id="stop"),
                                Button(label="\u25BA\u2759", id="skip"),
                                Button(label="\U0001f501\uFE0E", id="repeat", 
                                       style=ButtonStyle.blue if self.repeat else ButtonStyle.gray)
                            ]
                        ])
                    self.now_playing.__dict__["has_component"] = True
                    return
            self.now_playing = await channel.send(embed=self.np_embed(self.current))

    async def update_last_playing(self, last_source=None):
        """ Replaces last "Now Playing" status with a "Played" embed """
        if self.now_playing:
            if last_source and not self.repeat:
                if self.now_playing.__dict__.get("has_component"):
                    print("sending played component msg")
                    ddb = self.kwargs.get("ddb")
                    await ddb.edit_component_msg(
                        self.now_playing,
                        embed=self.played_embed(last_source),
                        components=[]
                    )
                else:
                    await self.now_playing.edit(embed=self.played_embed(last_source))
            else:
                try:
                    await self.now_playing.delete()
                except discord.HTTPException:
                    pass
            
            self.now_playing = None # reset reference

    def clear_queue(self):
        """ Clears the playlist queue. """
        self.queue._queue.clear()

    def skip(self):
        """ Skip currently playing audio source """
        # make sure we turn off repeat so we don't accidentally replay the song
        self.repeat = False
        self.vclient.stop()
    
    def stop(self):
        """ Stops playing and clears queue """
        self.repeat = False
        if self.next_source:
            self.next_source.cleanup()
        self.next_source = None
        if self.vclient.is_paused():
            self.vclient.resume()
        self.vclient.stop()
        if self.vclient.source:
            self.vclient.source.cleanup()
        self.clear_queue()

    async def cleanup(self):
        """ Disconnects from the voice client and clears the playlist queue. """
        try:
            self.stop()
            for task in self._tasks:
                task.cancel()
            self.vclient.cleanup()
            await self.vclient.disconnect()
        except AttributeError:
            pass

    async def destroy(self):
        """ Uninitializes this player (basically disconnects from voice and
        clears the queue).
        """
        self._dead = True
        self.ytdl_extractor.cleanup()
        await self.cleanup()
