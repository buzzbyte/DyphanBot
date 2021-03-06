import random
import discord

from dyphanbot import Plugin

OMAEWAMOUSHINDEIRU = [
    "おまえはもうしんでいる",
    "おまえはもう死んでいる",
    "お前はもうしんでいる",
    "お前はもう死んでいる"
]

NANI = [
    "**なに？！**",
    "**何？！**"
]

BESTGIRL = [
    "best girl dyphan",
    "best girl dyphanbot",
    "dyphan is best girl",
    "dyphanbot is best girl"
]

class ExamplePlugin(Plugin):
    """ Demonstrates new plugin structure. """

    def start(self):
        self.logger.info("Example Plugin started!")
        self.intents.members = True
    
    async def help(self, message, args):
        return {
            "title": "Hello World",
            "helptext": "A plugin created to demonstrate DyphanBot's plugin structure.",
            "shorthelp": "A simple example plugin.",
            "color": discord.Colour(0x00FF00),
            "sections": [
                {
                    "name": "What do I do?",
                    "value": "Responds to `i luv u` and a few other easter eggs, greets you, and accepts head pats!"
                },
                {
                    "name": "My Commands",
                    "value": "`hello`: Responds with a greeting.\n`headpat`: Accepts a head pat."
                }
            ]
        }

    @Plugin.on_ready
    async def ready(self, client):
        self.logger.info("Bot is ready!!")
    
    @Plugin.on_member_join
    async def mjoin(self, client, member):
        self.logger.info("Member ({0}) joined a guild ({1}).".format(str(member), str(member.guild)))

    @Plugin.command(cmd="hello")
    async def helloplugin(self, client, message, args):
        await message.channel.send("Hello you!")

    @Plugin.command
    async def headpat(self, client, message, args):
        await message.channel.send("<:kitsuneUwU:532777822775934986>")

    @Plugin.on_message
    async def luv_u(self, client, message):
        if "i luv u" in message.content.lower():
            await message.channel.send("i luv u too bby :heart:")

    @Plugin.on_message(raw=True)
    async def bestgirl(self, client, message):
        if any(bgrill in message.content.lower() for bgrill in BESTGIRL):
            await message.channel.send("no u :heart:")
        elif any(omaeshin in message.content for omaeshin in OMAEWAMOUSHINDEIRU):
            await message.channel.send(random.choice(NANI))

#def plugin_init(dyphanbot):
#    pass
