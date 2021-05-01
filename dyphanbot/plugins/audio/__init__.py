from functools import partial

import discord
from discord.errors import ConnectionClosed
from dyphanbot import Plugin, utils

from .controller import AudioController
from .player import YTDLPlaylist
from .extractor import AudioExtractionError, YTDLExtractor

HELP_TEXT = """*aliases: `audio`, `voice`, `music`, `m`*
Connects to a voice channel and plays audio.
Supports playing from YouTube and various other sites, as well as any file format FFMPEG supports.
See the [list of supported sites](https://ytdl-org.github.io/youtube-dl/supportedsites.html) for all the sites this plugin can play from."""

class Audio(Plugin):
    """ Handles the 'audio' commands for DyphanBot """

    def __init__(self, dyphanbot):
        super().__init__(dyphanbot)
        self.controller = AudioController(dyphanbot)
        self._persist_fn = "persistence.json"
        self._persistence_data = self.load_json(self._persist_fn)
    
    def _save_persistence(self):
        return self.save_json(self._persist_fn, self._persistence_data)
    
    async def help(self, message, args):
        prefix = self.get_local_prefix(message)
        command = args[0] if args else 'audio'
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
                "value": "Joins and plays a URL or searches YouTube. "
                         "Resumes a paused audio if called by itself.",
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
                "name": "> {} repeat".format(invocation),
                "value": "Toggles repeat for the current or next song.",
                "inline": False
            }, {
                "name": "> {} volume `(+/-)1-100`".format(invocation),
                "value": ("Sets the volume. Can be either number from 1 to 100, "
                          "or a change preceeded by `+` or `-`.\n"
                          "Displays the current volume if called by itself.\n"
                          "e.g:\n"
                          "    `{0} volume 75` sets volume to *75%*\n"
                          "    `{0} volume +10` increases volume by *10%*\n"
                          "    `{0} volume -5` decreases volume by *5%*\n"
                          "    `{0} volume` displays current volume (*80%* after "
                          "running the previous commands)\n").format(invocation),
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

    async def playonjoin(self, message, args):
        # Highly experimental, doesn't even work... might scrap
        if message.author.id not in self.dyphanbot.get_bot_masters():
            return
        
        guild_id = str(message.guild.id)
        query = " ".join(args).strip()
        if not query:
            return await message.channel.send("You haven't specified a query.")
        
        if not message.author.voice or not message.author.voice.channel:
            return await message.channel.send("You're not in a voice channel.")
        
        if guild_id not in self._persistence_data:
            self._persistence_data[guild_id] = {
                "playonjoin": {}
            }
        
        msg = await message.channel.send("Preparing requested source(s)...")
        try:
            ytdl_extractor = YTDLExtractor()
            info = await ytdl_extractor.process_entries(query)
            if isinstance(info, YTDLPlaylist) and not info.title:
                info.title = "*Untitled Playlist*"
            
            vchannel = message.author.voice.channel
            vch_id = str(vchannel.id)
            poj = self._persistence_data[guild_id]['playonjoin']
            if vch_id not in poj:
                poj[vch_id] = {}
            poj[vch_id]['query'] = query
            poj[vch_id]['text_channel'] = str(message.channel.id)
            self._persistence_data[guild_id]['playonjoin'] = poj
            self._save_persistence()

            await msg.edit(
                content="Play-on-join was successfully set for `{}`.".format(
                    vchannel.name),
                embed=discord.Embed(
                    title=info.title or "*Untitled*",
                    url=info.web_url if info.web_url and info.web_url.startswith("http") else discord.Embed.Empty
                ))
        except AudioExtractionError as err:
            self.logger.error(err.message)
            return await msg.edit(content=err.display_message)
        except ValueError:
            pass
        except Exception as e:
            await message.channel.send("Whoops! Something went wrong... ```py\n{}: {}\n```".format(type(e).__name__, e))
            raise
    
    @Plugin.event
    async def on_voice_state_update(self, member, before, after):
        # Highly experimental, doesn't even work... might scrap
        if member.id not in self.dyphanbot.get_bot_masters():
            return
        
        v_client = member.guild.voice_client
        if member != member.guild.me:
            try:
                vchannel = None
                guild_id = str(member.guild.id)
                poj = self._persistence_data[guild_id]['playonjoin']
                if after.channel != before.channel:
                    if after.channel and str(after.channel.id) in poj:
                        self.logger.info("PoJ Voice join: %s", str(member))
                        vchannel = after.channel

                        if v_client and v_client.is_connected():
                            # bot is busy now... we'll get em next time
                            return
                        
                        poj_channel = poj[str(vchannel.id)]
                        query = poj_channel['query']
                        text_channel = poj_channel['text_channel']

                        try:
                            await self.controller.join(vchannel.guild, vchannel, reconnect=False)
                            player = self.controller.get_player(self.dyphanbot, None, vchannel.guild)
                            after_playback = partial(self.controller.stab_player_to_death, vchannel.guild)
                            await player.prepare_entries(query, None,
                                silent=True,
                                requester=member,
                                custom_data={
                                    "after_playback": after_playback
                                }
                            )
                        except ConnectionClosed:
                            await self.controller.stab_player_to_death(vchannel.guild)
                    elif before.channel and str(before.channel.id) in poj:
                        self.logger.info("PoJ Voice leave: %s", str(member))
                        vchannel = before.channel
                        if not v_client or (v_client and not v_client.is_connected()):
                            return
                        if len(vchannel.members) > 1:
                            return
                        if v_client.channel == vchannel:
                            await v_client.disconnect(force=True)
                            # K I L L
                            await self.controller.stab_player_to_death(vchannel.guild)
                        return
            except KeyError:
                pass
    
    async def join(self, message, args):
        if not message.author.voice or not message.author.voice.channel:
            return await message.channel.send(
                "You're not in a voice channel... ~~dummy~~")
        
        return await self.controller.join(
            message.guild, message.author.voice.channel)

    async def play(self, message, args):
        query = " ".join(args)
        if len(args) <= 0 or query.strip() == "":
            resumed = await self.controller.resume(message.guild, message)
            if not resumed:
                await message.channel.send("Nothing was paused, bruh.")
            return
        
        if not message.author.voice or not message.author.voice.channel:
            return await message.channel.send(
                "You're not in a voice channel... ~~dummy~~")
        
        return await self.controller.play(
            message.guild, message.author.voice.channel, query, message)


    async def pause(self, message, args):
        paused = await self.controller.pause(message.guild, message)
        if paused is False:
            return await message.channel.send(
                "I wasn't even playing anything~~, baka~~!")
        if paused is None:
            return await message.channel.send("Already paused, bruh.")
        
        return paused

    async def stop(self, message, args):
        stopped = await self.controller.stop(message.guild, message)
        if not stopped:
            return await message.channel.send("I wasn't even playing anything!")
        
        return await message.channel.send("Stopped the playlist.")
    
    async def repeat(self, message, args):
        repeat_toggle = await self.controller.repeat(message.guild, message)
        if repeat_toggle is None:
            return await message.channel.send("I need to be in a voice channel...")
        
        return await message.channel.send(
            "**`{0}`**: Turned {1} repeat.".format(
                message.author,
                "ON" if repeat_toggle else "OFF"
            ))

    async def volume(self, message, args):
        current_volume = await self.controller.volume(message.guild, message=message)
        if current_volume is False:
            return await message.channel.send("I ain't in a voice chat, bruh..")
        if len(args) <= 0:
            return await message.channel.send(
                "Volume: **{0:.0f}%**\n"
                "Use `{1}{2} volume <amount>` where `<amount>` is either a "
                "number from 1 to 100 or an increment/decrement.\n"
                "To increase or decrease the volume by an amount, preceed the "
                "number with a `+` or `-` respectively.".format(
                    current_volume, self.get_local_prefix(message), "audio"
                ))
        
        volume_in: str = args[0].strip()
        delta = volume_in and (volume_in.startswith("+") or volume_in.startswith("-"))
        try:
            volume = int(volume_in)
            change_volume = await self.controller.volume(
                message.guild, volume, delta, message=message)
            if change_volume is False:
                return await message.channel.send(
                    "I ain't in a voice channel, bruh..")
            if change_volume is None:
                return await message.channel.send(
                    "Volume goes from 1 to 100...")
            
            return await message.channel.send(
                "**`{0}`**: Set the volume to **{1:.0f}%**".format(
                    message.author, change_volume))
        except ValueError:
            return await message.channel.send(
                "... What? Volume has to be set by a number from 1 to 100 or "
                "an increment/decrement with `+`/`-` respectively.")

    async def skip(self, message, args):
        skipped = await self.controller.skip(message.guild, message)
        if skipped is False:
            return await message.channel.send("I'm not even in a voice channel!")
        if skipped is None:
            return await message.channel.send("I wasn't playing anything!")
        
        return skipped

    async def status(self, message, args):
        status = await self.controller.status(message.guild, message)
        if status is False:
            return await message.channel.send(
                "I'm not even connected to a voice channel, dude!!")
        if status is None:
            return await message.channel.send("I'm not playing anything...")
        
        return status

    async def queue(self, message, args):
        status = await self.controller.status(message.guild)
        queue = await self.controller.queue(message.guild, message)
        if queue is False:
            return await message.channel.send(
                "I'm not even connected to a voice channel, dude!!")
        
        queue_str = ""
        if status:
            progress_str = utils.secs_to_hms(status.get_progress())
            duration_str = utils.secs_to_hms(status.duration) if status.duration else "?"
            queue_str += "{0} **{1}:**\n **`{2}`**{3}\n\n".format(
                "\u25B6\uFE0E" if status.is_playing else "\u23F8\uFE0E",
                status.np_str if status.np_str else "Now Playing",
                status.title,
                "\n[ {} / {} ]".format(progress_str, duration_str)
            )
        
        if queue['is_empty'] and not queue['next_source']:
            queue_str += "Playlist queue is empty..."
        elif queue['size'] <= 0 and not queue['next_source']:
            queue_str += "Playlist queue has no songs."
        else:
            queue_str += "**Next Up:**\n"
            queue_str += "» *`{0}`*\n".format(queue['next_source'].title) if queue['next_source'] else ""
            for entry in queue['entries']:
                queue_str += "• `{0}`\n".format(entry.title)
            if queue['next_count'] > 0:
                queue_str += "*+ {} more...*".format(queue['next_count'])
        
        return await message.channel.send(embed=discord.Embed(
            title="Queue",
            description=queue_str,
            colour=discord.Colour(0x7289DA)
        ))

    async def leave(self, message, args):
        leaving = await self.controller.leave(message.guild)
        if leaving is False:
            return await message.channel.send(
                "I'm not connected to a voice channel, bruh...")

    async def reset(self, message, args):
        await self.controller.reset(message.guild)
        return await message.channel.send("Reset player. Maybe it works now?")
    
    @Plugin.command
    async def audio(self, client, message, args, _cmd='audio'):
        """ The Voice command.
        Handles subcommands for playing and controlling audio.
        """
        sub_cmds = ['join', 'play', 'fplay', 'pause', 'stop', 'repeat',
                    'volume', 'skip', 'status', 'queue', 'leave', 'reset']

        if len(args) > 0:
            scmd = args[0].strip()
            if scmd in sub_cmds:
                if not hasattr(self, scmd):
                    return await message.channel.send("Not implemented yet...")
                await getattr(self, scmd)(message, args[1:])
            elif scmd == 'playonjoin':
                await self.playonjoin(message,args[1:])
            elif scmd == 'help':
                await self.dyphanbot.bot_controller.help(message, [_cmd])
            else:
                await message.channel.send("lol wut?")
        else:
            await message.channel.send("La la la!!")
    
    @Plugin.command
    async def voice(self, client, message, args):
        return await self.audio(client, message, args, _cmd='voice')
    
    @Plugin.command(cmd='music')
    async def music_cmd(self, client, message, args):
        return await self.audio(client, message, args, _cmd='music')
    
    @Plugin.command(cmd='m')
    async def m_cmd(self, client, message, args):
        return await self.audio(client, message, args, _cmd='m')
