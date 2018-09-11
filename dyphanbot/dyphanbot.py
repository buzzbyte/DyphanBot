import os
import json
import random
import logging
import discord

import dyphanbot.utils as utils
from dyphanbot.constants import CB_NAME
from dyphanbot.pluginloader import PluginLoader

CONFIG_FN = "testee_token.json"
#CONFIG_FN = "dyphan_token.json"

# Configure the logging module
logging.basicConfig(
    format='%(asctime)s - %(name)s [%(levelname)s]: %(message)s',
    level=logging.INFO)

class DyphanBot(discord.Client):
    """
    Main class for DyphanBot
    """
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.token = self.load_config()["token"]
        self.pluginloader = PluginLoader(self)

        self.commands = {}
        self.msg_handlers = []
        self.ready_handlers = []

    def run(self):
        self.pluginloader.load_plugins()
        super().run(self.token)

    def load_config(self):
        configfilepath = os.path.join(os.path.expanduser('~'), CONFIG_FN)
        with open(configfilepath) as fd:
            return json.load(fd)

    def add_command_handler(self, command, handler):
        self.commands[command] = handler;

    def add_message_handler(self, handler, raw=False):
        # This is the only way that setting attributes to a function actually fucking works... fuck python
        handler.__dict__['raw'] = raw
        self.msg_handlers.append(handler)

    def add_ready_handler(self, handler):
        self.ready_handlers.append(handler)

    def bot_mention(self, msg):
        """Returns a mention string for the bot"""
        server = msg.guild
        return '{0.mention}'.format(server.me if server is not None else self.user)

    def get_avatar_url(self):
        """Returns a URL for the bot's avatar"""
        return utils.get_user_avatar_url(self.user)

    async def on_ready(self):
        for handler in self.ready_handlers:
            await handler(self)
        self.logger.info("Initializing %s (%s) running %s", self.user.name, self.user.id, CB_NAME)

    async def on_message(self, message):
        if self.bot_mention(message) in message.content:
            cmd = message.content.replace(self.bot_mention(message), "").strip().split()
            args = cmd[1:]
            self.logger.info("Got command `%s` with args `%s`", cmd[0], ' '.join(args))
            for key in self.commands:
                if key == cmd[0]:
                    await self.commands[key](self, message, args)
        for handler in self.msg_handlers:
            if handler.raw or (not handler.raw and self.bot_mention(message) in message.content):
                await handler(self, message)
