import os
import json
import random
import logging
import discord

from dyphanbot.pluginloader import PluginLoader

CONFIG_FN = "dyphan_token.json"

# Configure the logging module
logging.basicConfig(
    format='%(asctime)s - %(name)s [%(levelname)s]: %(message)s',
    level=logging.INFO)

class DyphanBot(object):
    """
    Main class for DyphanBot
    """
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.token = self.load_config()["token"]
        self.client = discord.Client()
        self.pluginloader = PluginLoader(self)

        self.commands = {}
        self.msg_handlers = []
        self.events = [self.on_ready, self.on_message]

    def start(self):
        self.pluginloader.load_plugins()
        self.register_events()
        self.client.run(self.token)

    def load_config(self):
        configfilepath = os.path.join(os.path.expanduser('~'), CONFIG_FN)
        with open(configfilepath) as fd:
            return json.load(fd)

    def register_events(self):
        for event in self.events:
            self.client.async_event(event)

    def add_command_handler(self, command, handler):
        self.commands[command] = handler;

    def add_message_handler(self, handler, raw=False):
        # This is the only way that setting attributes to a function actually fucking works... fuck python
        handler.__dict__['raw'] = raw
        self.msg_handlers.append(handler)

    def bot_mention(self, msg):
        server = msg.server
        return '{0.mention}'.format(server.me if server is not None else self.client.user)

    def on_ready(self):
        print("Initializing {0} ({1}) running DyphanBot".format(self.client.user.name, self.client.user.id))

    async def on_message(self, message):
        if self.bot_mention(message) in message.content:
            cmd = message.content.replace(self.bot_mention(message), "").strip().split()
            args = cmd[1:]
            self.logger.info("Got command `%s` with args `%s`", cmd[0], ' '.join(args))
            for key in self.commands:
                if key == cmd[0]:
                    await self.commands[key](self.client, message, args)
        for handler in self.msg_handlers:
            if handler.raw or (not handler.raw and self.bot_mention(message) in message.content):
                await handler(self.client, message)
