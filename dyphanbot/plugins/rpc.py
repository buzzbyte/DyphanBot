import traceback
import asyncio
import aio_msgpack_rpc as amprpc

class DyBotRPC(object):
    def __init__(self, dyphanbot):
        self.dyphanbot = dyphanbot

    def get_client(self):
        return self.dyphanbot

    def hello(self, str):
        return "Hello {0}!".format(str)

    async def send_message(self, channel_id, *args, **kwargs):
        channel = self.dyphanbot.get_channel(channel_id)
        if not channel:
            return "Error: Can't find channel."
        try:
            await channel.send(*args, **kwargs)
        except Exception as e:
            return traceback.format_exc()
        return "Sent message to channel '{0}' in guild '{1}' successfully.".format(channel.name, channel.guild.name)

async def run_server(dyphanbot):
    rpc_serv = amprpc.Server(DyBotRPC(dyphanbot))
    server = await asyncio.start_server(rpc_serv, host="localhost", port=18002)

def plugin_init(dyphanbot):
    loop = dyphanbot.loop
    loop.run_until_complete(run_server(dyphanbot))
