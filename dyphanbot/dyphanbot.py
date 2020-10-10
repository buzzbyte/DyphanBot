import os
import json
import random
import logging
import discord

import dyphanbot.utils as utils
from dyphanbot.constants import CB_NAME
from dyphanbot.datamanager import DataManager
from dyphanbot.botcontroller import BotController
from dyphanbot.pluginloader import PluginLoader

# Configure the logging module
logging.basicConfig(
    format='%(asctime)s - %(name)s [%(levelname)s]: %(message)s',
    level=logging.INFO)

class DyphanBot(discord.Client):
    """
    Main class for DyphanBot
    """
    def __init__(self, debug=False, config_path=None):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        if debug:
            logging.getLogger("dyphanbot").setLevel(logging.DEBUG)
        self.data = DataManager(self, config_path)
        self.bot_controller = BotController(self)
        self.pluginloader = PluginLoader(self,
            disabled_plugins=self.data._get_key('disabled_plugins', []),
            user_plugin_dirs=self.data._get_key('plugin_dirs', []))

        self.commands = {}

        # TODO: make this into one dict with all the handlers
        self.msg_handlers = []
        self.ready_handlers = []
        self.mjoin_handlers = []

    def run(self):
        self.pluginloader.load_plugins()
        super().run(self.data._get_key('token'), bot=self.data._get_key('bot', True))

    def add_command_handler(self, command, handler, permissions=None, plugin=None):
        handler.__dict__['plugin'] = plugin
        handler.__dict__['permissions'] = permissions
        self.commands[command] = handler

    def add_message_handler(self, handler, raw=False):
        handler.__dict__['raw'] = raw
        self.msg_handlers.append(handler)

    def add_ready_handler(self, handler):
        self.logger.debug("On ready handler called for '%s'", handler.__name__)
        self.ready_handlers.append(handler)
    
    def add_mjoin_handler(self, handler):
        self.mjoin_handlers.append(handler)

    def bot_mention(self, msg):
        """Returns a mention string for the bot"""
        server = msg.guild
        return '{0.mention}'.format(server.me if server is not None else self.user)

    def get_avatar_url(self):
        """Returns a URL for the bot's avatar"""
        return utils.get_user_avatar_url(self.user)

    def get_bot_masters(self):
        """ Returns a list of configured Bot Masters' user IDs """
        return self.data._get_key('bot_masters', [])

    async def process_command(self, message, cmd, args, prefix=False):
        self.logger.info("Got command `%s` with args `%s`", cmd, ' '.join(args))
        if await self.bot_controller._process_command(message, cmd, args, prefix):
            return None
        if cmd in self.commands:
            # handle commands disabled by the guild settings
            disabled_commands = self.bot_controller._get_settings_for_guild(message.guild, "disabled_commands")
            if disabled_commands and (cmd in disabled_commands):# and not message.author.guild_permissions.manage_guild:
                return None
            
            if self.commands[cmd].permissions:
                # handle permissions (botmaster and guild)
                cmd_perms = self.commands[cmd].permissions
                self.logger.info("Command `%s` has permissions `%s`", cmd, cmd_perms)
                if "botmaster" in cmd_perms and cmd_perms["botmaster"]:
                    return (await self.commands[cmd](self, message, args) if str(message.author.id) in self.get_bot_masters() else None)
                if "guild_perms" in cmd_perms:
                    member_perms = message.author.permissions_in(message.channel)
                    for perms in cmd_perms["guild_perms"]:
                        if not getattr(member_perms, perms):
                            return None
            
            return await self.commands[cmd](self, message, args)
        return None

    async def on_ready(self):
        self.logger.debug("Found %d ready handlers: %s", len(self.ready_handlers), self.ready_handlers)
        for handler in self.ready_handlers:
            await handler(self)
        self.logger.info("Initializing %s (%s) running %s", self.user.name, self.user.id, CB_NAME)
    
    async def on_member_join(self, member):
        for handler in self.mjoin_handlers:
            await handler(self, member)

    async def on_message(self, message):
        # Disable DMs until we support them
        if isinstance(message.channel, discord.DMChannel):
            if message.author != self.user:
                return await message.channel.send("Direct messages are not fully supported yet.. Still have to work out bugs and stuff")
            return
        cmd_handler = None
        prefix = self.bot_controller._get_prefix(message.guild)
        full_cmd, args = utils.parse_command(self, message, prefix)
        if len(full_cmd) < 1:
            # don't process if there's no command (happens when bot gets mentioned without a command or only the prefix was sent)
            return
        if self.bot_mention(message) in message.content:
            cmd_handler = await self.process_command(message, full_cmd[0], args)
        elif prefix and message.content.startswith(prefix):
            cmd_handler = await self.process_command(message, full_cmd[0], args, True)
        if not cmd_handler:
            for handler in self.msg_handlers:
                # Good luck reading this! lol
                if handler.raw or (not handler.raw and ((prefix and message.content.startswith(prefix)) or (self.bot_mention(message) in message.content))):
                    await handler(self, message)
