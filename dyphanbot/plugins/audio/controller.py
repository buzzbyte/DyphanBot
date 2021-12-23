from itertools import islice
import typing

import discord

from .player import AudioPlayer

class PlayerButton(discord.ui.Button):
    def __init__(self, controller, cb_func, label, emoji_id=None, **kwargs):
        self.cb_func = cb_func
        self.controller = controller
        self.client = controller.dyphanbot

        self.active = False

        emoji = self.client.get_emoji(emoji_id) if emoji_id else None
        if emoji:
            label = None
        
        super().__init__(label=label, emoji=emoji, **kwargs)
    
    async def callback(self, interaction: discord.Interaction):
        if not interaction.user and not interaction.guild:
            return
        
        return await self.cb_func(self, interaction)

class PlayerView(discord.ui.View):
    def __init__(self, controller, guild, emojis={}):
        super().__init__(timeout=None)
        self.controller = controller
        self.guild = guild
        self.emojis = emojis
    
    async def load_view(self):
        self.clear_items()

        self.status = await self.controller.status(self.guild)

        if self.status.is_paused:
            self.add_item(PlayerButton(self.controller, self.play,  "Play",  self.emojis.get("play"),  custom_id="audio:play"))
        else:
            self.add_item(PlayerButton(self.controller, self.pause, "Pause", self.emojis.get("pause"), custom_id="audio:pause"))
        
        self.add_item(PlayerButton(self.controller, self.stop, "Stop", self.emojis.get("stop"), custom_id="audio:stop"))
        self.add_item(PlayerButton(self.controller, self.skip, "Skip", self.emojis.get("skip"), custom_id="audio:skip"))

        self.add_item(PlayerButton(self.controller, self.repeat, "Repeat", self.emojis.get("repeat"), custom_id="audio:repeat",
                        style=discord.ButtonStyle.primary if self.status.is_repeating else discord.ButtonStyle.secondary))
    
    async def play(self, button: PlayerButton, interaction):
        author = interaction.guild.get_member(interaction.user.id)
        await self.controller.resume(interaction.guild, interaction.message)
        await interaction.response.send_message(f"*{author.display_name}* resumed playback.")
    
    async def pause(self, button: PlayerButton, interaction):
        author = interaction.guild.get_member(interaction.user.id)
        await self.controller.pause(interaction.guild, interaction.message)
        await interaction.response.send_message(f"*{author.display_name}* paused playback.")
    
    async def stop(self, button: PlayerButton, interaction):
        author = interaction.guild.get_member(interaction.user.id)
        stopping = await self.controller.stop(interaction.guild, interaction.message)
        if stopping:
            await interaction.response.send_message(f"*{author.display_name}* stopped playback and cleared queue.")
    
    async def skip(self, button: PlayerButton, interaction):
        author = interaction.guild.get_member(interaction.user.id)
        skipping = await self.controller.skip(interaction.guild, interaction.message)
        if skipping:
            await interaction.response.send_message(f"*{author.display_name}* skipped this playback.")
    
    async def repeat(self, button: PlayerButton, interaction):
        author = interaction.guild.get_member(interaction.user.id)
        repeat_toggle = await self.controller.repeat(interaction.guild, interaction.message)
        if repeat_toggle is not None:
            await self.controller.status(interaction.guild, interaction.message, interaction.channel)
            await interaction.response.send_message(f"*{author.display_name}* put it on repeat." if repeat_toggle else f"*{author.display_name}* turned off repeat.")

class AudioController(object):
    """ Commands for playing and controlling music playback.
    Acts as an interface for youtube-dl, basically.
    """

    def __init__(self, dyphanbot, config={}, **kwargs):
        self.dyphanbot = dyphanbot
        self.players = {}
        self.config = config
        self.kwargs = kwargs

    def get_player(self, client, message, guild=None):
        """Retrieve the guild player, or generate one."""
        if not guild:
            guild = message.guild
        
        guild_id = guild.id
        if guild_id in self.players and not self.players[guild_id]._dead:
            player = self.players[guild_id]
            return player
        
        player_view = PlayerView(self, guild, self.config.get('emoji', {}))
        
        player = AudioPlayer(client, guild, message, self.config, view=player_view, **self.kwargs)
        self.players[guild_id] = player

        return player
    
    async def stab_player_to_death(self, guild: discord.Guild): # cause 'kill' sounds boring
        """ Kills the music player... obviously. """
        guild_id = guild.id
        if guild_id in self.players:
            player = self.players[guild_id]
            await player.destroy()
            player = None
            del self.players[guild_id]

    async def join(self,
                   guild: discord.Guild,
                   vchannel: discord.VoiceChannel,
                   timeout: int=60, reconnect: bool=True):
        """ Connects to the user's voice channel. """

        vclient: discord.VoiceClient = guild.voice_client
        
        try:
            vclient = await vchannel.connect(timeout=timeout, reconnect=reconnect)
        except discord.ClientException:
            await vclient.move_to(vchannel)
        
        return vclient

    async def play(self,
                   guild: discord.Guild,
                   vchannel: discord.VoiceChannel,
                   query: typing.Any,
                   message:discord.Message=None,
                   timeout: int=60, reconnect: bool=True, **kwargs):
        """ Plays audio from a URL, if provided. Otherwise, resumes paused
        audio.
        This will also call `join` if the bot is not already connected to a
        voice channel.
        """

        vclient = await self.join(guild, vchannel, timeout, reconnect)
        if not vclient:
            return
        
        player = self.get_player(self.dyphanbot, message, guild)
        return await player.prepare_entries(query, message, **kwargs)
    
    async def resume(self, guild: discord.Guild, message: discord.Message=None):
        vclient = guild.voice_client
        if not vclient:
            return False

        player = self.get_player(self.dyphanbot, message, guild)
        if vclient.is_paused():
            vclient.resume()
            if message and player.current:
                await player.update_now_playing(message.channel)
            return True
        
        return False

    async def pause(self, guild: discord.Guild, message: discord.Message=None):
        """ Pause currently playing audio, if any. """
        vclient = guild.voice_client
        if not vclient or (vclient and not vclient.is_playing()):
            return False
        if vclient.is_paused():
            return None
        
        vclient.pause()

        player = self.get_player(self.dyphanbot, message, guild)
        if message and player.current:
            await player.update_now_playing(message.channel)
        
        return True

    async def stop(self, guild: discord.Guild, message: discord.Message=None):
        """ Stops playing audio and clears the playlist queue. """
        vclient = guild.voice_client
        if not vclient or not vclient.is_connected():
            return False
        
        player = self.get_player(self.dyphanbot, message, guild)
        player.stop()

        return True
    
    async def repeat(self, guild: discord.Guild, message: discord.Message=None):
        vclient = guild.voice_client
        if not vclient or not vclient.is_connected():
            return None
        
        player = self.get_player(self.dyphanbot, message, guild)
        player.repeat = not player.repeat
        return player.repeat

    async def playlist(self, client, message, args):
        """ Adds a specified list of searches/URLs to the queue. """
        raise NotImplementedError(
            "AudioController.playlist() has not been implemented... might consider remove it eventually")

    async def volume(self,
                     guild: discord.Guild,
                     volume: int=None,
                     delta: bool=False,
                     max_volume: int=100,
                     message: discord.Message=None):
        """ Sets, increases, or decreases the volume. """
        vclient = guild.voice_client
        if not vclient or not vclient.is_connected():
            return False
        
        player = self.get_player(self.dyphanbot, message, guild)
        current_volume = player.volume * 100
        if volume is None:
            return current_volume
        
        if delta:
            if current_volume + volume > max_volume:
                current_volume = max_volume
            elif current_volume + volume < 1:
                current_volume = 1
            else:
                current_volume += volume
        else:
            if not 0 < volume < max_volume+1:
                return None
            current_volume = volume
        
        if vclient.source:
            vclient.source.volume = current_volume / 100
        player.volume = current_volume / 100

        return current_volume

    async def skip(self, guild: discord.Guild, message: discord.Message=None):
        """ Skip the currently playing audio. """
        vclient = guild.voice_client
        if not vclient or not vclient.is_connected():
            return False
        
        if vclient.is_paused():
            pass
        elif not vclient.is_playing():
            return None
        
        player = self.get_player(self.dyphanbot, message, guild)
        player.skip()

        return True

    async def status(self,
                     guild: discord.Guild,
                     message: discord.Message=None,
                     channel: discord.TextChannel=None):
        """ Displays the 'Now Playing'/'Now streaming'/'Paused' embed status
        containing the audio info.
        """
        vclient = guild.voice_client
        if not vclient or not vclient.is_connected():
            return False
        
        player = self.get_player(self.dyphanbot, message, guild)
        if not player.current:
            return None
        
        if not message and not channel:
            source = player.current
            source.is_repeating = player.repeat
            source.is_playing   = vclient.is_playing()
            source.is_paused    = vclient.is_paused()
            source.np_str = player.np_status_str(source)
            return source
        
        if not channel:
            channel = message.channel
        
        await player.update_now_playing(channel)
        return True
    
    async def queue(self,
                    guild: discord.Guild,
                    message: discord.Message=None,
                    limit: int=10,
                    start_index: int=0):
        """ Displays the current playlist queue """
        vclient = guild.voice_client
        if not vclient or not vclient.is_connected():
            return False
        
        player = self.get_player(self.dyphanbot, message, guild)
        raw_queue = player.queue._queue
        
        if len(raw_queue) > 0 and start_index >= len(raw_queue):
            start_index = len(raw_queue) - 1
        if start_index < 0:
            start_index = 0
        
        prev_count = start_index
        queue_list = list(islice(raw_queue, start_index, start_index + limit))
        next_count = len(raw_queue) - (start_index + limit)
        if next_count < 0:
            next_count = 0

        return {
            "prev_count": prev_count,
            "next_source": player.next_source if player.next_source else None,
            "entries": queue_list,
            "next_count": next_count,
            "size": len(raw_queue) + 1 if player.next_source else len(raw_queue),
            "is_empty": player.queue.empty()
        }

    async def leave(self, guild: discord.Guild):
        """ Disconnects from the voice client. """
        vclient = guild.voice_client
        if not vclient or not vclient.is_connected():
            return False
        
        return await self.stab_player_to_death(guild)
    
    async def reset(self, guild: discord.Guild):
        """ Removes the guild's player to regenerate a new one later """
        return await self.stab_player_to_death(guild)
