import logging
import random
import asyncio
import discord

class SongRequest(object):
    """docstring for SongRequest."""
    def __init__(self, message, player):
        self.player = player
        self.channel = message.channel
        self.requester = message.author

    def __str__(self):
        fmt = "*{0.title}*{2}\nUploaded by *{0.uploader}* and requested by *{1.display_name}*"
        duration = self.player.duration
        audiolength = " [length: {0[0]}:{0[1]}]".format(divmod(duration, 60)) if duration else ""
        return fmt.format(self.player, self.requester, audiolength)

class VoiceState(object):
    def __init__(self, client):
        self.client = client
        self.current = None
        self.voice_client = None
        self.playlist = asyncio.Queue()
        self.play_next = asyncio.Event()
        self.audio_player = self.client.loop.create_task(self.audio_player_task())

    @property
    def player(self):
        return self.current.player

    def is_playing(self):
        if self.voice_client is None or self.current is None:
            return False

        return self.player.is_playing()

    def skip(self):
        if self.is_playing():
            self.player.stop()

    def trigger_next(self):
        self.client.loop.call_soon_threadsafe(self.play_next.set)

    async def create_player(self, song):
        opts = { 'default_search': 'auto', "ignoreerrors": True }
        #delay_opt = " -ss -3" # Delays audio by 3 seconds to minimize lag for streamed videos
        delay_opt = ""
        return await self.voice_client.create_ytdl_player(
            song.strip(),
            ytdl_options=opts,
            after=self.trigger_next,
            before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5" + delay_opt,
        )

    """Audio player loop"""
    async def audio_player_task(self):
        logging.info("audio player task entered")
        while True:
            logging.info("player task loop start")
            self.play_next.clear()
            self.current = await self.playlist.get()
            await self.client.send_message(self.current.channel, "**Now Playing:** {0}".format(self.current))
            self.current.player.start()
            logging.info("player task loop end")
            await self.play_next.wait()

class VoicePlugin(object):
    """docstring for VoicePlugin."""
    def __init__(self, dyphanbot):
        self.dyphanbot = dyphanbot
        self.voice_states = {}

        if not discord.opus.is_loaded():
            discord.opus.load_opus('opus')

    def get_voice_state(self, client, server):
        state = self.voice_states.get(server.id)
        if state is None:
            state = VoiceState(client)
            self.voice_states[server.id] = state

        return state

    async def voice(self, client, message, args):
        # TODO: Do something better than this...
        if len(args) > 0:
            if args[0].strip() == "join":
                await self.join(client, message, args[1:])
            elif args[0].strip() == "play":
                await self.play(client, message, args[1:])
            elif args[0].strip() == "playlist":
                await self.playlist(client, message, args[1:])
            elif args[0].strip() == "pause":
                await self.pause(client, message, args[1:])
            elif args[0].strip() == "stop":
                await self.stop(client, message, args[1:])
            elif args[0].strip() == "skip":
                await self.skip(client, message, args[1:])
            elif args[0].strip() == "queue":
                await self.queue(client, message, args[1:])
            elif args[0].strip() == "status":
                await self.status(client, message, args[1:])
            elif args[0].strip() == "leave":
                await self.leave(client, message, args[1:])
            else:
                await client.send_message(message.channel, "lol wut?")
        else:
            await client.send_message(message.channel, "La la la!!")

    async def join(self, client, message, args):
        v_chat = message.author.voice_channel
        if v_chat is None:
            await client.send_message(message.channel, "You're not in a voice channel... ~~dummy~~")
            return False

        state = self.get_voice_state(client, message.server)
        if state.voice_client is None:
            state.voice_client = await client.join_voice_channel(message.author.voice_channel)
        else:
            await state.voice_client.move_to(v_chat)

        return True

    async def play(self, client, message, args):
        song = " ".join(args)

        state = self.get_voice_state(client, message.server)
        if state.voice_client is None:
            joined = await self.join(client, message, [])
            if not joined:
                return

        if song.strip() == "":
            if state.current and not state.is_playing():
                state.player.resume()
            else:
                await client.send_message(message.channel, "Nothing was paused, bruh.")
            return

        try:
            player = await state.create_player(song)
        except Exception as e:
            fmt = 'An error occurred while processing this request: ```py\n{}: {}\n```'
            await client.send_message(message.channel, fmt.format(type(e).__name__, e))
        else:
            entry = SongRequest(message, player)
            await state.playlist.put(entry)
            await client.send_message(message.channel, "Added *{0}* to the playlist queue.".format(player.title))

    async def playlist(self, client, message, args):
        argstr = " ".join(args)
        if not "|" in argstr:
            await client.send_message(message.channel, "Song list needs to be separated by the `|` character.")
            return

        addedsongs = []
        songlist = argstr.strip().split("|")

        state = self.get_voice_state(client, message.server)
        if state.voice_client is None:
            joined = await self.join(client, message, [])
            if not joined:
                return

        mtext = "Adding songs to playlist..."
        message = await client.send_message(message.channel, mtext)
        for song in songlist:
            try:
                player = await state.create_player(song)
            except Exception as e:
                fmt = 'An error occurred while processing song `{0}`: ```py\n{1}: {2}\n```'
                await client.send_message(message.channel, fmt.format(song, type(e).__name__, e))
                continue
            else:
                entry = SongRequest(message, player)
                await state.playlist.put(entry)
                mtext += "\n    **+** *{0}*".format(player.title)
                await client.edit_message(message, mtext)

        mtext += "\nAdded all requested songs to playlist."
        await client.edit_message(message, mtext)

    async def pause(self, client, message, args):
        state = self.get_voice_state(client, message.server)
        if state.is_playing():
            state.player.pause()

    async def stop(self, client, message, args):
        state = self.get_voice_state(client, message.server)
        if state.is_playing():
            state.player.stop()
        else:
            await client.send_message(message.channel, "I wasn't even playing anything....")

        state.audio_player.cancel()
        await client.send_message(message.channel, "Stopped the playlist.")

    async def skip(self, client, message, args):
        state = self.get_voice_state(client, message.server)
        if not state.is_playing():
            await client.send_message(message.channel, "I'm not even playing anything....")
            return

        await client.send_message(message.channel, "Skipping song...")
        state.skip()

    async def queue(self, client, message, args):
        state = self.get_voice_state(client, message.server)
        await client.send_message(message.channel, "{0} songs left in queue.".format(state.playlist.qsize()))

    async def status(self, client, message, args):
        state = self.get_voice_state(client, message.server)
        if state.current is None:
            await client.send_message(message.channel, "Nothing's playing.")
        else:
            await client.send_message(message.channel, "**Now {0}:** {1}".format("Playing" if state.is_playing() else "Paused", state.current))

    async def leave(self, client, message, args):
        state = self.get_voice_state(client, message.server)
        if state.is_playing():
            state.player.stop()

        try:
            state.audio_player.cancel()
            del self.voice_states[message.server.id]
            await state.voice_client.disconnect()
        except:
            pass

def plugin_init(dyphanbot):
    voiceplugin = VoicePlugin(dyphanbot)
    dyphanbot.add_command_handler("voice", voiceplugin.voice)
