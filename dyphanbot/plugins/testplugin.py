import logging
import random

import discord

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

dbot = None

class TestPlugin(object):
    """docstring for TestPlugin."""
    def __init__(self, dyphanbot):
        self.dyphanbot = dyphanbot

    async def test(self, client, message, args):
        if 'self' in args:
            await message.channel.send(self.dyphanbot.bot_mention(message) + " test")
        else:
            await message.channel.send("Tested!!")

    async def anime(self, client, message=None, args=None):
        # TODO: Make this run automatically instead of on command.
        # TODO: Maybe randomly choose from a list of anime to watch from as an easter egg?
        activity = discord.Activity(
            name="anime",
            state="Watching an anime episode",
            details="It's a very exciting anime!",
            type=discord.ActivityType.watching
        )
        await client.change_presence(activity=activity, status=discord.Status.dnd)
        if message:
            await message.channel.send("Imma watch some anime... ~~brb~~ but I'll still be here. I can multitask... literally.")

    async def handle_message(self, client, message):
        if "Dyphan" in message.content:
            await message.channel.send("sup bitch")
        elif any(omaeshin in message.content for omaeshin in OMAEWAMOUSHINDEIRU):
            await message.channel.send(random.choice(NANI))

    async def handle_raw_message(self, client, message):
        if "Dyphan likes it raw" in message.content:
            await message.channel.send("I LIKE IT RAWW!!!!")
        elif any(bgrill in message.content.lower() for bgrill in BESTGIRL):
            await message.channel.send(":heart:")

def plugin_init(dyphanbot):
    testplugin = TestPlugin(dyphanbot)
    dyphanbot.add_ready_handler(testplugin.anime)

    dyphanbot.add_command_handler("test", testplugin.test)
    dyphanbot.add_command_handler("anime", testplugin.anime)
    dyphanbot.add_message_handler(testplugin.handle_message)
    dyphanbot.add_message_handler(testplugin.handle_raw_message, raw=True)
