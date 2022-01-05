import logging
import random
import discord

DEFAULT_FAREWELL = [
    "{user.mention} (`{user.name}#{user.discrim}`) has left the server. Please come back! :'c",
    "Oh no! {user.mention} (`{user.name}#{user.discrim}`) just left... I didn't even get to say goodbye!",
    "Sad days... {user.mention} (`{user.name}#{user.discrim}`) left."
]

# cause python... -_-
NL = "\n"

class Farewell(object):
    def __init__(self, dyphanbot, utils):
        self.logger = logging.getLogger(__name__)
        self.dyphanbot = dyphanbot
        self.utils = utils

    def channel_ids2obj(self, guild, channel_ids):
        return [guild.get_channel(int(cid)) for cid in channel_ids if cid is not None]
    
    def channel_list2str(self, channels):
        return ', '.join([f'{channel.mention}' for channel in channels])

    async def on_leave(self, member):
        guild = member.guild
        farewell_settings = self.utils.get_gsettings(guild, "farewell")
        farewell_messages = farewell_settings.get("message", DEFAULT_FAREWELL)
        channel_ids = farewell_settings.get("channel_id", [])
        if not farewell_settings or not farewell_settings.get('enabled', False):
            return

        if not channel_ids:
            self.logger.warn(f"Farewell settings for guild {guild.id} has no channel_id set. Farewell messages will not send.")
            return

        if not farewell_messages:
            farewell_messages = DEFAULT_FAREWELL
        
        for channel_id in channel_ids:
            channel = self.dyphanbot.get_channel(int(channel_id))
            if not channel:
                self.logger.warn(f"Farewell: There is no channel with id {channel_id}. Skipping.")
                continue

            farewell_msg = self.utils.parse_message_template(random.choice(farewell_messages), member, channel, guild)
            await channel.send(farewell_msg)
        
    def list_embed(self, enabled, channels, farewells):
        enabled_text = "enabled" if enabled else "disabled"
        farewellstr = ""
        for fw in farewells:
            farewellstr += f"> {fw}{NL}{NL}"
        return discord.Embed.from_dict({
            "title": "Farewell Messages",
            "description": f"Farewell messages are currently **{enabled_text}** for this server.",
            "fields": [
                {
                    "name": "Message texts (selected at random)",
                    "value": farewellstr.strip() or "*No messages set.*"
                },
                {
                    "name": "Channels",
                    "value": self.channel_list2str(channels) or "*No channels set.*"
                }
            ]
        })
    
    async def add(self, message, args):
        fmsg = " ".join(args)

        if not fmsg.strip():
            return await message.channel.send("No message given.")
        
        farewell_settings = self.utils.get_gsettings(message.guild, "farewell")
        farewells = farewell_settings.get("message", [])

        farewells.append(fmsg)
        
        self.utils.set_gsettings(message.guild, "farewell", "message", farewells)
        self.utils._save_gsettings()
        await message.channel.send(
            f"Farewell message added: `{fmsg}`{NL}"
            f"Enable with `{self.utils.get_local_prefix(message)}farewell enable` to activate.{NL}"
            f"Type `{self.utils.get_local_prefix(message)}farewell list` to list all farewell messages set for this server."
        )
    
    async def toggle(self, message, enable):
        farewell_settings = self.utils.get_gsettings(message.guild, "farewell")
        enabled = farewell_settings.get("enabled", False)
        channel_ids = farewell_settings.get("channel_id", [])
        farewell_channels = self.channel_ids2obj(message.guild, channel_ids)

        mentioned_channels = message.channel_mentions

        action_text = "enabled" if enable else "disabled"
        opposite_text = "disable" if enable else "enable"

        if (enable and enabled and not mentioned_channels) or (not enable and not enabled):
            return await message.channel.send(
                f"Farewell messages are already {action_text} in this server for channels: {self.channel_list2str(farewell_channels)}{NL}"
                f"Type `{self.utils.get_local_prefix(message)}farewell list` for a list of the farewell messages added.{NL}"
                f"Type `{self.utils.get_local_prefix(message)}farewell {opposite_text}` to {opposite_text}."
            )

        if enable:
            if not mentioned_channels and not farewell_channels:
                return await message.channel.send(
                    "There are no channels set for farewell messages. Type this command again and mention the channels you want messages to appear in.\n"
                    "When you have a channel already set, you can type this command to enable farewell messages without mentioning the channels again."
                )
            
            if mentioned_channels:
                mcids = [str(channel.id) for channel in mentioned_channels if channel is not None]
                channel_ids = self.utils.set_gsettings(message.guild, "farewell", "channel_id", mcids)
                farewell_channels = self.channel_ids2obj(message.guild, channel_ids)

        self.utils.set_gsettings(message.guild, "farewell", "enabled", enable)
        self.utils._save_gsettings()

        await message.channel.send(f"Farewell messages have been {action_text} for channels: {self.channel_list2str(farewell_channels)}")
    
    async def list_farewells(self, message):
        farewell_settings = self.utils.get_gsettings(message.guild, "farewell")
        enabled = farewell_settings.get("enabled", False)
        farewells = farewell_settings.get("message", [])
        channel_ids = farewell_settings.get("channel_id", [])
        farewell_channels = self.channel_ids2obj(message.guild, channel_ids)

        default_tag = ""
        if not farewells:
            default_tag = " (default)"
            farewells = DEFAULT_FAREWELL
        
        await message.channel.send(embed=self.list_embed(enabled, farewell_channels, farewells))
    
    async def clear_channels(self, message):
        self.utils.set_gsettings(message.guild, "farewell", "channel_id", [])
        self.utils.set_gsettings(message.guild, "farewell", "enabled", False)
        self.utils._save_gsettings()

        await message.channel.send("Farewell channel list has been cleared and disabled.")
    
    async def clear_messages(self, message):
        self.utils.set_gsettings(message.guild, "farewell", "message", [])
        self.utils._save_gsettings()

        await message.channel.send("Farewell message list has been reset to default.")
    
    async def test_run(self, message):
        await self.on_leave(message.author)
    
    async def help(self, message, args):
        prefix = self.utils.get_local_prefix(message)
        invocation = f"{prefix}{args[0]}"
        usage_text = """
        `{0} list` - Lists the farewell messages and channels currently set for the server.
        `{0} add` - Adds a new farewell message text that will get picked randomly.
        `{0} enable` - Activates the farewell messages on the channels mentioned.
        `{0} disable` - Deactivates the farewell messages.
        `{0} clear` - Clears the channels and deactivates farewell messages.
        `{0} reset` - Resets the farewell messages to the defaults.
        `{0} test` - Tests the farewell messages on the current member (still posts on the specified channels).
        `{0} help` - Shows this help.
        """.format(invocation)
        return {
            "title": "Farewell Messages",
            "helptext": "Set up randomly chosen messages that trigger on a specified channel when a member leaves the server or gets kicked.",
            "sections": [
                {
                    "name": "Usage",
                    "value": usage_text.strip()
                }
            ]
        }
    
    async def invoke(self, message, args):
        if len(args) > 0:
            scmd = args[0].strip()
            if scmd == 'add':
                await self.add(message, args[1:])
            elif scmd == 'enable':
                await self.toggle(message, True)
            elif scmd == 'disable':
                await self.toggle(message, False)
            elif scmd == 'list':
                await self.list_farewells(message)
            elif scmd == 'clear':
                await self.clear_channels(message)
            elif scmd == 'reset':
                await self.clear_messages(message)
            elif scmd == 'test':
                await self.test_run(message)
            elif scmd == 'help':
                await self.dyphanbot.bot_controller.help(message, ['farewell'])
            else:
                await message.channel.send(f"Unknown subcommand. Type `{self.utils.get_local_prefix(message)}farewell help` for available commands.")
        else:
            await self.list_farewells(message)