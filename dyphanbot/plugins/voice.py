import asyncio
import textwrap
import datetime
import logging

from async_timeout import timeout
from functools import partial

import discord
import dyphanbot.utils as utils
from dyphanbot import Plugin

import youtube_dl

HELP_TEXT = """*aliases: `voice`, `audio`, `music`, `m`*
Connects to a voice channel and plays audio.
Supports playing from YouTube and various other sites, as well as any file format FFMPEG supports.
See the [list of supported sites](https://ytdl-org.github.io/youtube-dl/supportedsites.html) for all the sites this plugin can play from."""

YTDL_OPTS = {
    'format': 'webm[abr>0]/bestaudio/best',
    'prefer_ffmpeg': True,
    'ignoreerrors': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'  # ipv6 addresses cause issues sometimes
}

FFMPEG_OPTS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

ytdl = youtube_dl.YoutubeDL(YTDL_OPTS)

class YTDLObject(object):
    def __init__(self, loop=None):
        self.loop = loop or asyncio.get_event_loop()

class YTDLPlaylist(YTDLObject):

    def __init__(self, data: dict, requester: discord.Member, loop=None):
        super().__init__(loop)
        self.requester = requester

        self._data = data
        self._entries = data.get('entries')
        self.id = data.get('id')
        self.title = data.get('title')
        self.uploader = data.get('uploader')
        self.uploader_id = data.get('uploader_id')
        self.web_url = data.get('webpage_url')
        self.extractor = data.get('extractor')
        self.extractor_key = data.get('extractor_key')
    
    def _get_video_id_from_url(self):
        # a 'hacky' way to get videos with playlists to start from the current
        # video instead of the beginning of the playlist
        if not self.web_url:
            return None
        video_opts = {'noplaylist':True, 'ignoreerrors':True}
        video_info = youtube_dl.YoutubeDL(video_opts).extract_info(
            url=self.web_url,
            download=False,
            process=False)
        if not video_info or 'playlist' in video_info.get('_type', '') or video_info.get('id') == self.id:
            return None # url is actually a playlist instead of a video in a playlist
        return video_info.get('id')
    
    def entries(self):
        """ Generates a list of YTDLPlaylistEntry objects to be processed later """
        entries = []
        found = False
        v_id = self._get_video_id_from_url()
        for i, entry in enumerate(self._entries, 1):
            if v_id and v_id != entry.get('id') and not found:
                continue # skip till we get to the current id
            found = True # we found the video, stop skipping and add the rest
            entries.append(YTDLPlaylistEntry(self, entry, self.requester,
                index=i, loop=self.loop))
        return entries

class YTDLPlaylistEntry(YTDLObject):
    """ Represents an unprocessed playlist entry """
    def __init__(self, playlist: YTDLPlaylist, data: dict, requester: discord.Member, index=0, loop=None):
        super().__init__(loop)
        self._data = data
        self.id = data.get('id')
        self.title = data.get('title', "*N/A*") or "*Untitled*"
        self.playlist = playlist
        self.playlist_index = index
        self.requester = requester
    
    async def process(self):
        """ Processes this playlist entry into a YTDLEntry """
        if 'on_process' in self._data:
            data = self._data['on_process']()
            if data.get('_complete'):
                return YTDLEntry(data, self.requester, loop=self.loop)
            self._data.update(data)
        weburl_base = None
        if self.playlist.web_url:
            weburl_base = youtube_dl.utils.url_basename(self.playlist.web_url)
        extra_info = {
            'playlist': self.playlist._data,
            'playlist_id': self.playlist.id,
            'playlist_title': self.playlist.title,
            'playlist_uploader': self.playlist.uploader,
            'playlist_uploader_id': self.playlist.uploader_id,
            'playlist_index': self.playlist_index,
            'webpage_url': self.playlist.web_url,
            'webpage_url_basename': weburl_base,
            'extractor': self.playlist.extractor,
            'extractor_key': self.playlist.extractor_key,
        }
        to_run = partial(
            ytdl.process_ie_result,
            ie_result=self._data,
            download=False,
            extra_info={k: v for k, v in extra_info.items() if v}
        )
        entry_result = await self.loop.run_in_executor(None, to_run)
        if not entry_result:
            return None
        return YTDLEntry(entry_result, self.requester, loop=self.loop)

class YTDLEntry(YTDLObject):
    """ Represents a youtube-dl entry """
    def __init__(self, data: dict, requester: discord.Member, custom_data={}, loop=None):
        super().__init__(loop)
        self.requester = requester

        self._data = data
        self._custom_data = custom_data
        self._update_data(data, custom_data)
    
    def _update_data(self, data: dict, custom_data={}):
        data.update(custom_data)
        self._data = data
        self.id = data.get('id')
        self.title = data.get('title', "*No Title*") or "*Untitled*"
        self.description = data.get('description', "")
        self.web_url = data.get('webpage_url')
        self.views = data.get('view_count')
        self.is_live = bool(data.get('is_live'))
        self.likes = data.get('like_count')
        self.dislikes = data.get('dislike_count')
        self.duration = data.get('duration')
        self.uploader = data.get('uploader')
        self.thumbnail = data.get('thumbnail')

        # upload date handling
        date = data.get('upload_date')
        if date:
            try:
                date = datetime.datetime.strptime(date, '%Y%M%d').date()
            except ValueError:
                date = None

        self.upload_date = date
    
    def create_source(self):
        """ Generates a playable source from the entry data """
        return YTDLSource(discord.FFmpegPCMAudio(ytdl.prepare_filename(self._data), **FFMPEG_OPTS), entry=self)
    
    async def regather_source(self):
        if 'on_regather' in self._data:
            regathered_data = self._data['on_regather']()
            self._update_data(self._data, regathered_data)
            return YTDLSource(discord.FFmpegPCMAudio(self._data['url'], **FFMPEG_OPTS), entry=self)
        to_run = partial(ytdl.extract_info, url=self.web_url, download=False)
        regathered_data = await self.loop.run_in_executor(None, to_run)
        if self._data.get('_custom_playlist'):
            self._custom_data = self._data
        regathered_data.update(self._custom_data)
        self._update_data(self._data, regathered_data)
        return YTDLSource(discord.FFmpegPCMAudio(self._data['url'], **FFMPEG_OPTS), entry=self)

class YTDLSource(discord.PCMVolumeTransformer):
    """ Playable source object for YTDL """
    def __init__(self, source, *, entry: YTDLEntry):
        super().__init__(source)
        self.entry = entry
        self.requester = entry.requester

        # get these attributes from the entry (pls tell me there's a better way...)
        for attr in ['title', 'description', 'web_url', 'views', 'is_live',
                     'likes', 'dislikes', 'duration', 'uploader', 'thumbnail',
                     'upload_date']:
            setattr(self, attr, getattr(self.entry, attr))

class MusicPlayer(object):
    """ Handles fetching and parsing media from URLs using youtube-dl, as well
    as the playlist queue.
    """
    def __init__(self, client: discord.Client, message: discord.Message):
        self._logger = logging.getLogger(__name__)
        self._dead = False
        self.client = client
        self.message = message
        self.guild = message.guild
        self.vclient = self.guild.voice_client
        self.channel = message.channel

        self.queue = asyncio.Queue()
        self.next = asyncio.Event()

        self.now_playing = None
        self.volume = 0.5
        self.current = None
        self.next_source = None

        # TODO: Make webhook embeds actually optional...
        self.can_use_webhooks = False

        self.loop = self.vclient.loop
        self.audio_player = self.loop.create_task(self.player_loop())
    
    async def _send_message(self, message: discord.Message, silent, *args, **kwargs):
        """ Sends or edits discord message if not `silent` """
        if not silent:
            if message.author == self.client.user:
                return await message.edit(**kwargs)
            return await message.channel.send(*args, **kwargs)
        return None
    
    async def _process_data(self, data, depth=0):
        # Processes the data until data['_type'] is either 'video' or 'playlist'
        # This references a portion of youtube-dl's own code, except it only
        # handles 'url' or 'url_transparent' result types since we do playlist
        # and video processing later on.
        # This method shouldn't be called on playlist entries!
        result_type = data.get('_type', 'video')

        if result_type in ('url', 'url_transparent'):
            data['url'] = youtube_dl.utils.sanitize_url(data['url'])
        
        if result_type == 'url':
            to_run = partial(ytdl.extract_info,
                url=data['url'], ie_key=data.get('ie_key'),
                download=False, process=False)
            return await self.loop.run_in_executor(None, to_run)
        elif result_type == 'url_transparent':
            to_run = partial(ytdl.extract_info,
                url=data['url'], ie_key=data.get('ie_key'),
                download=False, process=False)
            info = await self.loop.run_in_executor(None, to_run)

            if not info:
                return info
            
            fprops = {(k, v) for k, v in data.items() if v is not None}
            for f in ('_type', 'url', 'id', 'extractor', 'extractor_key', 'ie_key'):
                if f in fprops:
                    del fprops[f]
            new_data = info.copy()
            new_data.update(fprops)

            if new_data.get('_type') == 'url':
                new_data['_type'] = 'url_transparent'
            
            if depth <= 3:
                return await self._process_data(new_data, depth+1)
            return new_data # we've gone too deep...
        else:
            return data
    
    async def _generate_playlist_data(self, message, data: dict, silent=False):
        if not 'entries' in data:
            return None
        new_data = {
            '_type': 'playlist',
            'id': data.get('id', "custom-playlist"),
            'title': data.get('title', "Untitled Custom Playlist"),
            'entries': []
        }

        for entry in data['entries']:
            if 'url' in entry:
                try:
                    to_run = partial(ytdl.extract_info, url=entry['url'], download=False, process=False)
                    entry_info = await self.loop.run_in_executor(None, to_run)
                    if entry_info.get('_type') == 'playlist':
                        # too much hassle in handling playlists inside of each other
                        continue
                    if 'data' in entry:
                        entry_info.update(entry['data'])
                    entry_info['_custom_playlist'] = True
                    new_data['entries'].append(entry_info)
                except youtube_dl.utils.YoutubeDLError:
                    await self._send_message(message, silent,
                        content="Skipped `{}` due to an error.".format(
                            entry.get('data', {}).get('title', entry['url'])))
                    continue
            elif 'id' in entry:
                entry_info = {}
                entry_info['id'] = entry['id']
                if 'data' in entry:
                    entry_info.update(entry['data'])
                new_data['entries'].append(entry_info)
        
        return new_data

    async def prepare_entries(self, message, search, *, custom_data={}, silent=False):
        msg = await self._send_message(message, silent, "Preparing requested source(s)...")
        if isinstance(search, dict):
            data = await self._generate_playlist_data(message, search, silent)
            if not data:
                self._logger.error(
                    "Custom playlist data missing required values.")
                return await self._send_message(msg, silent,
                    content="Unable to generate playlist... :c")
            if not data['entries']:
                return await self._send_message(msg, silent,
                    content="The playlist is empty... :c")
        else:
            try:
                to_run = partial(ytdl.extract_info, url=search, download=False, process=False)
                data = await self.loop.run_in_executor(None, to_run)
                
                # Process the result till we get a playlist or a video
                data = await self._process_data(data)
            except youtube_dl.utils.YoutubeDLError:
                return await self._send_message(msg, silent,
                    content="Unable to retrieve content... :c")

        # If it's a playlist with more than one video, put it in a YTDLPlaylist
        # object and queue them as playlist entries to process them in the
        # player loop. Otherwise, if it's a single video, use `data` as its
        # entry and queue it.
        if 'entries' in data:
            playlist = YTDLPlaylist(data, message.author, loop=self.loop)
            loading_notice = "\nThis might take a while depending on the playlist size." if playlist.title else ""
            fpname = " from `{}`".format(playlist.title) if playlist.title else ""
            await self._send_message(msg, silent, content="Queuing playlist entries{}...{}".format(fpname, loading_notice))
            entry_count = 0
            last_entry = None
            entries = await self.loop.run_in_executor(None, playlist.entries)
            for entry in entries:
                await self.queue.put(entry)
                last_entry = entry
                entry_count += 1
            if last_entry and entry_count == 1:
                await self._send_message(msg, silent, content="Added to queue: `{}`".format(last_entry.title))
            else:
                await self._send_message(msg, silent, content="Added {} playlist entries{}.".format(entry_count, fpname))
        else:
            # Not a playlist, so the entry data is in `data`
            entry = YTDLEntry(data, message.author, custom_data, loop=self.loop)
            await self.queue.put(entry)
            await self._send_message(msg, silent, content="Added to queue: `{}`".format(entry.title))

    def np_embed(self, source, webhook=False):
        """ Generates 'Now Playing'/'Now Streaming'/'Paused' status embed. """
        embed = discord.Embed(
            title=source.title,
            colour=discord.Colour(0x7289DA),
            url=source.web_url if not source.entry._data.get('no_url') else discord.Embed.Empty,
            description=source.description if source.entry._data.get('full_desc') else textwrap.shorten(source.description, 157, placeholder="..."),
            timestamp=self.message.created_at
        )

        if source.thumbnail:
            embed.set_thumbnail(url=source.thumbnail)
        
        if not webhook:
            embed.set_author(
                name=("Now Streaming" if source.is_live else "Now Playing") if self.vclient.is_playing() else "Paused",
                url="https://github.com/buzzbyte/DyphanBot",
                icon_url=utils.get_user_avatar_url(self.message.guild.me)
            )

        embed.set_footer(text="Requested by: {0.display_name}".format(source.requester), icon_url=utils.get_user_avatar_url(source.requester))
        if source.uploader:
            embed.add_field(name="Uploaded by", value=source.uploader, inline=True)

        duration = source.duration
        if duration:
            min, sec = divmod(int(duration), 60)
            hrs, min = divmod(min, 60)
            dfmtstr = "{0:d}:{1:02d}:{2:02d}" if hrs > 0 else "{1:02d}:{2:02d}"
            embed.add_field(name="Duration", value=dfmtstr.format(hrs, min, sec), inline=True)

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
        
        return source

    async def player_loop(self):
        """ Main player loop """
        await self.client.wait_until_ready()

        while not self.client.is_closed():
            self.next.clear()

            source = self.next_source
            if not source:
                try:
                    source = await self.get_queued_source()
                except asyncio.TimeoutError:
                    return await self.destroy()
                except Exception  as e:
                    await self.channel.send("There was an error processing your requested audio source...```py\n{}: {}\n```".format(type(e).__name__, e))
                    continue
            
            if source and self.vclient:
                source.volume = self.volume
                self.current = source

                if source.entry._data.get('before_playback'):
                    await source.entry._data['before_playback']()
                
                self.vclient.play(source, after=self.play_finalize)
                await self.update_now_playing()

                try:
                    self.next_source = await self.get_queued_source(wait_for_queue=False)
                except Exception  as e:
                    # we'll get 'em next time...
                    self.next_source = None
                
                await self.next.wait()
                if source.entry._data.get('after_playback'):
                    await source.entry._data['after_playback']()

                await self.update_last_playing(source)
                source.cleanup()
            
            self.current = None

    async def find_or_create_webhook(self):
        if self.guild.me.permissions_in(self.channel).manage_webhooks and self.can_use_webhooks:
            for webhook in await self.channel.webhooks():
                if "DyphanBot" in webhook.name:
                    return webhook
            return await self.channel.create_webhook(name="DyphanBot Webhook")
        return None

    async def update_now_playing(self):
        """ Deletes previous playing status embed and sends a new one. """
        webhook = await self.find_or_create_webhook()
        if webhook:
            self.now_playing = await webhook.send(
                embed=self.np_embed(self.current, webhook=True),
                avatar_url=utils.get_user_avatar_url(self.message.guild.me),
                username=("Now Streaming" if self.current.is_live else "Now Playing") if self.vclient.is_playing() else "Paused"
            )
        else:
            await self.update_last_playing()
            self.now_playing = await self.channel.send(embed=self.np_embed(self.current))

    async def update_last_playing(self, last_source=None):
        """ Replaces last "Now Playing" status with a "Played" embed """
        if self.now_playing:
            if last_source:
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
    
    def stop(self):
        """ Stops playing and clears queue """
        if self.next_source:
            self.next_source.cleanup()
        self.next_source = None
        if self.vclient.is_paused():
            self.vclient.resume()
        self.vclient.stop()
        self.clear_queue()

    async def cleanup(self):
        """ Disconnects from the voice client and clears the playlist queue. """
        self.stop()
        try:
            await self.vclient.disconnect()
        except AttributeError:
            pass

    async def destroy(self):
        """ Uninitializes this player (basically disconnects from voice and
        clears the queue).
        """
        self._dead = True
        return await self.cleanup()

class Music(object):
    """ Commands for playing and controlling music playback.
    Acts as an interface for youtube-dl, basically.
    """

    def __init__(self, dyphanbot):
        self.dyphanbot = dyphanbot
        self.players = {}

    def get_player(self, client, message):
        """Retrieve the guild player, or generate one."""
        guild_id = message.guild.id
        if guild_id in self.players and not self.players[guild_id]._dead:
            return self.players[guild_id]
        
        player = MusicPlayer(client, message)
        self.players[message.guild.id] = player

        return player
    
    async def stab_player_to_death(self, guild: discord.Guild): # cause 'kill' sounds boring
        """ Kills the music player... obviously. """
        guild_id = guild.id
        if guild_id in self.players:
            player = self.players[guild_id]
            await player.destroy()
            player = None
            del self.players[guild_id]

    async def join(self, client, message, args):
        """ Connects to the user's voice channel. """
        if not message.author.voice or not message.author.voice.channel:
            await message.channel.send("You're not in a voice channel... ~~dummy~~")
            return False
        
        v_channel = message.author.voice.channel
        v_client = message.guild.voice_client
        if v_client:
            await v_client.move_to(v_channel)
        else:
            await v_channel.connect()
        return message.guild.voice_client

    async def play(self, client, message, args, **kwargs):
        """ Plays audio from a URL, if provided. Otherwise, resumes paused
        audio.
        This will also call `join` if the bot is not already connected to a
        voice channel.
        """
        if isinstance(args, list):
            song = " ".join(args)
        else:
            song = args

        v_client = message.guild.voice_client
        if not v_client:
            v_client = await self.join(client, message, [])
            if not v_client:
                return

        player = self.get_player(client, message)
        if isinstance(song, str) and song.strip() == "":
            if v_client.is_paused():
                v_client.resume()
                if player.current:
                    await player.update_now_playing()
            else:
                await message.channel.send("Nothing was paused, bruh.")
            return

        await player.prepare_entries(message, song, **kwargs)

    async def pause(self, client, message, args):
        """ Pause currently playing audio, if any. """
        v_client = message.guild.voice_client
        if not v_client or not v_client.is_playing():
            return await message.channel.send("I wasn't even playing anything~~, baka~~!")
        elif v_client.is_paused():
            return await message.channel.send("Already paused, bruh.")

        v_client.pause()
        player = self.get_player(client, message)
        if player.current:
            await player.update_now_playing()

    async def stop(self, client, message, args):
        """ Stops playing audio and clears the playlist queue. """
        v_client = message.guild.voice_client
        if not v_client or not v_client.is_connected():
            return await message.channel.send("I wasn't even playing anything!")
        player = self.get_player(client, message)
        player.stop()
        await message.channel.send("Stopped the playlist.")

    async def playlist(self, client, message, args):
        """ Adds a specified list of searches/URLs to the queue. """
        await message.channel.send("Not implemented yet...")

    async def volume(self, client, message, args):
        """ Sets, increases, or decreases the volume. """
        v_client = message.guild.voice_client
        if not v_client or not v_client.is_connected():
            return await message.channel.send("I ain't in a voice chat, bruh..")

        player = self.get_player(client, message)
        vol = player.volume * 100
        vol_mod = 5
        if len(args) > 0:
            if args[0].strip() == "up":
                vol += vol_mod
                if vol > 100:
                    vol = 100
            elif args[0].strip() == "down":
                vol -= vol_mod
                if vol < 1:
                    vol = 1
            else:
                try:
                    vol = int(args[0])
                    if not 0 < vol < 101:
                        return await message.channel.send("Volume goes from 1 to 100 ...")
                except ValueError:
                    return await message.channel.send(".. What? Use either `up`, `down`, or a number between 1 to 100.")
        else:
            return await message.channel.send("Volume: **{0:.1f}%**\nVolume can be either `up`, `down`, or a number from 1 to 100.".format(vol))

        if v_client.source:
            v_client.source.volume = vol / 100
        player.volume = vol / 100
        await message.channel.send("**`{0}`**: Set the volume to **{1:.1f}%**".format(message.author, vol))

    async def skip(self, client, message, args):
        """ Skip the currently playing audio. """
        v_client = message.guild.voice_client
        if not v_client or not v_client.is_connected():
            return await message.channel.send("I wasn't even playing anything!")

        if v_client.is_paused():
            pass
        elif not v_client.is_playing():
            return

        v_client.stop()

    async def status(self, client, message, args):
        """ Displays the 'Now Playing'/'Now streaming'/'Paused' embed status
        containing the audio info.
        """
        v_client = message.guild.voice_client
        if not v_client or not v_client.is_connected():
            return await message.channel.send("I'm not even connected to a voice channel, dude!!")

        player = self.get_player(client, message)
        if not player.current:
            return await message.channel.send("I'm not playing anything...")

        await player.update_now_playing()
    
    async def queue(self, client, message, args):
        """ Displays the current playlist queue """
        v_client = message.guild.voice_client
        if not v_client or not v_client.is_connected():
            return await message.channel.send("I'm not even connected to a voice channel, dude!!")
        
        player = self.get_player(client, message)
        if player.queue.empty():
            return await message.channel.send("Playlist queue is empty...")
        
        max_listing = 10
        song_count = 1 if player.next_source else 0
        queue_str = "• **`{0}`**\n".format(player.next_source.title) if player.next_source else ""
        for entry in player.queue._queue:
            if isinstance(entry, YTDLEntry) or isinstance(entry, YTDLPlaylistEntry):
                song_count += 1
                if song_count <= max_listing:
                    queue_str += "• `{0}`\n".format(entry.title)
        if song_count > max_listing:
            queue_str += "*+ {} more...*".format(song_count-max_listing)
        if song_count <= 0:
            return await message.channel.send("Playlist queue has no songs.")
        
        embed = discord.Embed(
            title="Up Next",
            description=queue_str,
            colour=discord.Colour(0x7289DA)
        )
        
        await message.channel.send(embed=embed)

    async def leave(self, client, message, args):
        """ Disconnects from the voice client. """
        v_client = message.guild.voice_client
        if not v_client or not v_client.is_connected():
            return await message.channel.send("I'm not connected to a voice channel, bruh...")
        
        await self.stab_player_to_death(message.guild)
    
    async def reset(self, client, message, args):
        """ Removes the guild's player to regenerate a new one later """
        await self.stab_player_to_death(message.guild)
        await message.channel.send("Reset player. Maybe it works now?")
    

class Voice(Plugin):
    """ Contains the Voice command which handles the Music sub-commands """

    def __init__(self, dyphanbot):
        super().__init__(dyphanbot)
        self.music = Music(dyphanbot)
    
    async def help(self, message, args):
        prefix = self.get_local_prefix(message)
        command = args[0] if args else 'voice'
        invocation = "{}{}".format(prefix, command)
        return {
            "helptext": HELP_TEXT,
            "shorthelp": "Plays audio in voice channels.",
            "sections": [{
                "name": "> {} join".format(invocation),
                "value": "Joins the voice channel the user is in.",
                "inline": False
            }, {
                "name": "> {} play `URL or search query`".format(invocation),
                "value": "Joins and plays a URL or searches YouTube. Resumes a paused audio if called by itself.",
                "inline": False
            }, {
                "name": "> {} pause".format(invocation),
                "value": "Pauses the currently playing audio.",
                "inline": False
            }, {
                "name": "> {} stop".format(invocation),
                "value": "Stops playing audio and clears the playlist queue.",
                "inline": False
            }, {
                "name": "> {} volume `up/down/1-100`".format(invocation),
                "value": "Sets the volume. Can be either up, down, or a number from 1 to 100. Displays the volume if called by itself.",
                "inline": False
            }, {
                "name": "> {} skip".format(invocation),
                "value": "Skips to the next queued audio source.",
                "inline": False
            }, {
                "name": "> {} status".format(invocation),
                "value": "Displays the currently playing/paused audio.",
                "inline": False
            }, {
                "name": "> {} queue".format(invocation),
                "value": "Lists the queued playlist.",
                "inline": False
            }, {
                "name": "> {} leave".format(invocation),
                "value": "Disconnects from the voice channel.",
                "inline": False
            }]

        }
    
    @Plugin.command
    async def voice(self, client, message, args, _cmd='voice'):
        """ The Voice command.
        Handles subcommands for playing and controlling audio.
        """
        sub_cmds = ['join', 'play', 'fplay', 'pause', 'stop', 'playlist',
                    'volume', 'skip', 'status', 'queue', 'leave', 'reset']

        if len(args) > 0:
            scmd = args[0].strip()
            if scmd in sub_cmds:
                if not hasattr(self.music, scmd):
                    return await message.channel.send("Not implemented yet...")
                await getattr(self.music, scmd)(client, message, args[1:])
            elif scmd == 'help':
                await self.dyphanbot.bot_controller.help(message, [_cmd])
            else:
                await message.channel.send("lol wut?")
        else:
            await message.channel.send("La la la!!")
    
    @Plugin.command
    async def audio(self, client, message, args):
        return await self.voice(client, message, args, _cmd='audio')
    
    @Plugin.command(cmd='music')
    async def music_cmd(self, client, message, args):
        return await self.voice(client, message, args, _cmd='music')
    
    @Plugin.command(cmd='m')
    async def m_cmd(self, client, message, args):
        return await self.voice(client, message, args, _cmd='m')
