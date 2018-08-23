import logging
import random

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
            await client.send_message(message.channel, self.dyphanbot.bot_mention(message) + " test")
        else:
            await client.send_message(message.channel, "Tested!!")

    async def handle_message(self, client, message):
        if "Dyphan" in message.content:
            await client.send_message(message.channel, "sup bitch")
        elif any(omaeshin in message.content for omaeshin in OMAEWAMOUSHINDEIRU):
            await client.send_message(message.channel, random.choice(NANI))

    async def handle_raw_message(self, client, message):
        if "Dyphan likes it raw" in message.content:
            await client.send_message(message.channel, "I LIKE IT RAWW!!!!")
        elif any(bgrill in message.content for bgrill in BESTGIRL):
            await client.send_message(message.channel, ":heart:")

def plugin_init(dyphanbot):
    testplugin = TestPlugin(dyphanbot)
    dyphanbot.add_command_handler("test", testplugin.test)
    dyphanbot.add_message_handler(testplugin.handle_message)
    dyphanbot.add_message_handler(testplugin.handle_raw_message, raw=True)
