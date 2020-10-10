import io
import re
import logging
import aiohttp
from pprint import pprint

import discord
from dyphanbot import Plugin

class Echo(Plugin):
    """ Echo and Emoji plugin """
    def __init__(self, dyphanbot):
        self.dyphanbot = dyphanbot
    
    async def help(self, message, args):
        prefix = self.get_local_prefix(message)
        botname = self.dyphanbot.user.name
        return {
            "title": "Emojify",
            "helptext": "Posts emoji and can make 'em big for you!\nWill also work with animated emotes for non-nitro users.",
            "shorthelp": "Posts emoji and bigmoji, even animated ones!",
            "sections": [{
                "name": "Usage",
                "value": """> {0}emoji `emojiname`\n> {0}bigmoji `emojiname`
                `emojiname` is the emote's name without the colons.
                
                You could also use `:emojiname:` and `;emojiname;` (for bigmoji) to post emoji that {1} has access to (as well as animated ones).""".format(
                    prefix, botname
                )
            }]
        }
    
    @Plugin.command(botmaster=True)
    async def echo(self, client, message, args):
        #inputtext = " ".join(args)
        inputtext = message.content.replace(self.dyphanbot.bot_mention(message), "", 1).strip()
        inputtext = inputtext.partition(" ")[2]
        await message.channel.send(inputtext)

    @Plugin.command
    async def bigmoji(self, client, message, args):
        inputtext = " ".join(args)
        #pprint(message.guild.emojis)
        emoji = self.find_emoji(client, message, inputtext)
        if emoji:
            data = await self.get_bytes_from_url(str(emoji.url))
            if not data:
                return await message.channel.send("Can't get emoji...")
            await message.channel.send(file=discord.File(data, filename=emoji.name+"."+str(emoji.url).split(".")[-1]))
    
    @Plugin.command
    async def emoji(self, client, message, args):
        inputtext = " ".join(args)
        #pprint(message.guild.emojis)
        await self.send_emoji(client, message, inputtext)
    
    @Plugin.on_message(raw=True)
    async def emojify(self, client, message):
        if message.author is not (message.guild.me or client.user):
            inputtext = message.content
            output = ""
            rawemojis = re.findall(r"(?![^<][A-Za-z0-9:_-]+>):([^:\s]*(?:::[^:\s]*)*):", inputtext)
            rawbigmoji = re.search(r"\;(\w+)\;", inputtext)
            if rawbigmoji:
                print("bigmoji: "+rawbigmoji.group(1))
                return await self.bigmoji(client, message, [rawbigmoji.group(1)])
            for rawemoji in rawemojis:
                output += str(self.find_emoji(client, message, rawemoji))
            if output:
                await message.channel.send(output)

    async def send_emoji(self, client, message, name):
        emoji = self.find_emoji(client, message, name)
        if emoji:
            await message.channel.send(emoji)

    def find_emoji(self, client, message, name):
        for emoji in client.emojis:
            if name == emoji.name:
                return emoji
        return None or ""

    async def get_bytes_from_url(self, url):
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return None
                return io.BytesIO(await resp.read())

#def plugin_init(dyphanbot):
#    echo = Echo(dyphanbot)

#    dyphanbot.add_command_handler(
#        "echo", echo.echo,
#        permissions={
#            "botmaster": True, # botmaster overrides guild_params (for botmasters)...
#            "guild_perms": ["manage_guild", "manage_roles"]
#        }
#    )
#    dyphanbot.add_command_handler("emoji", echo.emoji)
#    dyphanbot.add_command_handler("bigmoji", echo.bigmoji)
#    dyphanbot.add_message_handler(echo.emojify, raw=True)
