from dyphanbot import Plugin

class ExamplePlugin(Plugin):
    """ Demonstrates new plugin structure. """

    def start(self):
        self.logger.info("Example Plugin started!")

    @Plugin.on_ready
    async def ready(self, client):
        self.logger.info("Bot is ready!!")

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
        if "best girl dyphan" in message.content.lower():
            await message.channel.send("no u :heart:")

#def plugin_init(dyphanbot):
#    pass
