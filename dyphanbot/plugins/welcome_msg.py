import re
import discord

from dyphanbot import Plugin
import dyphanbot.utils as utils

'''
Local JSON setup:
    {
        "guild_id": {
            "enabled": true/false,
            "welcomemsgs": [
                {
                    "channel_id": ["..."],
                    "messages": ["..."]
                }
                ...
            ]
        }
        ...
    }
'''

class ParseHelper:
    """ Class methods for parsing welcome messages. """

    @classmethod
    def get_emoji(cls, client, name):
        """ Finds and returns an emoji from the given
            name (e.g. happyface), or the plain string (e.g. :happyface:)
            if the emoji is not found.
        """
        for emoji in client.emojis:
            if name == emoji.name:
                return str(emoji)
        return None or ":{}:".format(name)
    
    @classmethod
    def get_role_mention(cls, member, name):
        """ Finds and returns a role mention string from the given
            role name (e.g. Admins), or the plain string
            if the role is not found or not mentionable.
        """
        role = discord.utils.get(member.guild.roles, name=name)
        return role.mention if role and role.mentionable else "@{}".format(name)
    
    @classmethod
    def get_channel_mention(cls, member, name):
        """ Finds and returns a channel mention string from the given
            channel name (e.g. channel-name), or the plain string
            if the channel is not found.
        """
        channel = discord.utils.find(lambda c: c.name in name, member.guild.channels)
        #channel = discord.utils.get(member.guild.channels, name=name)
        return channel.mention if channel else "#{}".format(name)
    
    @classmethod
    def get_member_mention(cls, member, name):
        """ Finds and returns a member mention string from the given
            username and descriminator (e.g. Username#1234), or the plain string
            if the member is not found.
        """
        member = discord.utils.find(lambda m: str(m) == name, member.guild.members)
        return member.mention if member else "@{}".format(name)
    
    @classmethod
    def find_channels(cls, text):
        """ Finds and returns a list of mentioned channel names """
        matches = re.findall(r'#([^\s!-,\.\/:-@[-^`{-~]+)', text)
        return matches
    
    @classmethod
    def find_members(cls, text):
        """ Finds and returns a list of mentioned member names """
        matches = re.findall(r'@([^#@:]+#\d{4})', text)
        return matches

    @classmethod
    def find_tags(cls, tagname, text):
        """ Finds and returns a list of tags matching <tagname:value> """
        matches = re.findall("<{}:[^>]+>".format(tagname), text)
        return matches
    
    @classmethod
    def parse_tag(cls, tagname, tag):
        """ Returns the value of a tag that matches <tagname:value> """
        matches = re.search("<{}:([^>]+)>".format(tagname), tag)
        return matches.group(1)

    @classmethod
    def parse_tags(cls, client, member, text):
        """ Finds and replaces tags that match <tagname:value> with the proper
            mention/emoji strings so Discord can render them properly.
        """

        # Find and parse tags for emoji, role, and channel
        emoji_matches = cls.find_tags("emoji", text)
        for match in emoji_matches:
            value = cls.parse_tag('emoji', match)
            text = re.sub(match, cls.get_emoji(client, value), text)
        
        role_matches = cls.find_tags("role", text)
        for match in role_matches:
            value = cls.parse_tag('role', match)
            text = re.sub(match, cls.get_role_mention(member, value), text)
        
        channel_matches = cls.find_tags("channel", text)
        for match in channel_matches:
            value = cls.parse_tag('channel', match)
            text = re.sub(match, cls.get_channel_mention(member, value), text)
        
        return text
    
    @classmethod
    def parse_mentions(cls, member, text):
        """ Finds and replaces raw mention strings with mentionable strings
            for Discord to render.
        """

        # Find raw channel mentions and replace them with real mentions
        raw_channel_mentions = cls.find_channels(text)
        for raw_mention in raw_channel_mentions:
            text = re.sub("#{}".format(raw_mention), cls.get_channel_mention(member, raw_mention), text)
        
        # Find raw member mentions and replace them with real mentions
        raw_member_mentions = cls.find_members(text)
        for raw_mention in raw_member_mentions:
            raw_mention = raw_mention.strip()
            text = re.sub("@{}".format(raw_mention), cls.get_member_mention(member, raw_mention), text)
        
        return text
    
    @classmethod
    def parse_message(cls, client, member, text):
        """ Short-hand for parse_tags() and parse_mentions() """
        text = cls.parse_tags(client, member, text)
        text = cls.parse_mentions(member, text)
        return text

class WelcomeMsg(Plugin):
    """ Plugin for guilds to welcome users on join """

    def start(self):
        self.intents.members = True
        self.db_filename = "welcomemsgs"
        self.data = self.load_json(self.db_filename)
    
    def save_data(self, data):
        return self.save_json(self.db_filename, data)
        
    async def add(self, message):
        guild_id = str(message.guild.id)
        channels = message.channel_mentions
        textblocks = utils.parse_codeblock(message.content)
        if len(channels) <= 0:
            return await message.channel.send("You have not mentioned any channels.")
        if len(textblocks) <= 0:
            return await message.channel.send("No welcome message specified. Specify one in a code block (between \``` and \```).")
        if not self.data.get(guild_id):
            self.data[guild_id] = {
                "enabled": False,
                "welcomemsgs": []
            }
        try:
            self.data[guild_id]["welcomemsgs"].append({
                "channel_id": [str(channel.id) for channel in channels],
                "messages": textblocks
            })

            self.save_data(self.data)
            success_msg = "Welcome messages successfully set."
            if not self.data[guild_id]['enabled']:
                success_msg += " Type `{0}welcomemsg enable` to enable.".format(self.get_local_prefix(message))
            return await message.channel.send(success_msg)
        except Exception as e:
            return await message.channel.send("Whoops! Something went wrong... ```py\n{}: {}\n```".format(type(e).__name__, e))

    async def remove(self, message):
        guild_id = str(message.guild.id)
        channels = message.channel_mentions
        if len(channels) <= 0:
            return await message.channel.send("You have not mentioned any channels.")
        
        try:
            rchan_ids = [str(x.id) for x in channels]
            for wmsg in self.data[guild_id]["welcomemsgs"]:
                chan_ids = wmsg['channel_id']
                chan_ids = [x for x in chan_ids if x not in rchan_ids]
                wmsg['channel_id'] = chan_ids
            
            # Clean up entries with empty channel ids...
            wmsgs = self.data[guild_id]["welcomemsgs"]
            wmsgs = [x for x in wmsgs if not len(x['channel_id']) <= 0]
            self.data[guild_id]["welcomemsgs"] = wmsgs
        except KeyError:
            return await message.channel.send("No welcome messages were set for the given {}.".format("channels" if channels > 1 else "channel"))
        else:
            self.save_data(self.data)
            return await message.channel.send("Removed welcome messages from selected channels successfully.")

    async def clear(self, message):
        guild_id = str(message.guild.id)
        try:
            if len(self.data[guild_id]["welcomemsgs"]) <= 0:
                return await message.channel.send("No welcome messages set for this server.")
            self.data[guild_id]["welcomemsgs"] = []
            self.data[guild_id]["enabled"] = False
        except KeyError:
            return await message.channel.send("No welcome messages defined in this server.")
        else:
            self.save_data(self.data)
            return await message.channel.send("Successfully cleared all welcome messages from this server.")

    async def enable(self, message, enabled):
        guild_id = str(message.guild.id)
        try:
            if self.data[guild_id].get("enabled") and self.data[guild_id]["enabled"] == enabled:
                return await message.channel.send("Welcome messages are already {0} on this server.".format(
                    "enabled" if enabled else "disabled"
                ))
            self.data[guild_id]["enabled"] = enabled
        except KeyError:
            return await message.channel.send("No welcome messages defined in this server.")
        else:
            self.save_data(self.data)
            return await message.channel.send("Welcome messages successfully {0} on this server.".format(
                "enabled" if enabled else "disabled"
            ))

    async def show(self, message):
        guild_id = str(message.guild.id)
        
        enabledstr = "?"
        efields = []
        try:
            enabledstr = "enabled" if self.data[guild_id]["enabled"] else "disabled"
            for wmsg in self.data[guild_id]["welcomemsgs"]:
                chan_str = ", ".join(["`#{}`".format(message.guild.get_channel(int(chan_id)).name) for chan_id in wmsg['channel_id']])
                wmsgtxt = "\n".join(["```{}```".format(msg) for msg in wmsg["messages"]])
                efields.append({
                    "name": chan_str,
                    "value": wmsgtxt
                })
        except KeyError:
            return await message.channel.send("No welcome messages defined in this server.")
        else:
            return await message.channel.send(embed=discord.Embed.from_dict({
                "title": "Welcome Messages",
                "description": "Welcome messages are currently {0} for this server.".format(enabledstr),
                "fields": efields
            }))
    
    async def dry_run(self, message):
        await message.channel.send("Invoking dry run...")
        return await self.mjoin(self.dyphanbot, message.author)
    
    @Plugin.on_member_join
    async def mjoin(self, client, member):
        guild_id = str(member.guild.id)
        try:
            if self.data[guild_id]['enabled']:
                for wmsg in self.data[guild_id]["welcomemsgs"]:
                    channels = [member.guild.get_channel(int(cid)) for cid in wmsg['channel_id']]
                    for channel in channels:
                        for wmessage in wmsg["messages"]:
                            wmessage = ParseHelper.parse_message(client, member, wmessage)
                            await channel.send(wmessage.format(
                                name=member.display_name,
                                username=member.name,
                                discriminator=member.discriminator,
                                fullusername=str(member),
                                mention=member.mention,
                                channel=channel.mention,
                                channelname=channel.name,
                                servername=member.guild.name
                            ))
        except KeyError:
            pass

    @Plugin.command(perms=["manage_guild"])
    async def welcomemsg(self, client, message, args):
        if len(args) < 1:
            #return await message.channel.send("Sets welcome messages. Type `{0}welcomemsg help` for subcommands.".format(self.get_local_prefix(message)))
            return await self.show(message)
        subcmd = args[0]
        argtxt = message.content.replace(self.dyphanbot.bot_mention(message), "", 1).strip()
        argtxt = argtxt.partition(" ")[2][len(subcmd):]
        if subcmd == "add":
            await self.add(message)
        elif subcmd == "remove":
            await self.remove(message)
        elif subcmd == "clear":
            await self.clear(message)
        elif subcmd == "enable":
            await self.enable(message, True)
        elif subcmd == "disable":
            await self.enable(message, False)
        elif subcmd == "show":
            await self.show(message)
        elif subcmd == "dryrun":
            await self.dry_run(message)
        elif subcmd == "help":
            await message.channel.send("Subcommands: `add` `remove` `clear` `enable` `disable` `show` `help`")
        else:
            await message.channel.send("Unknown subcommand. Type `{0}welcomemsg help` for help.".format(self.get_local_prefix(message)))

    @Plugin.command
    async def parsetest(self, client, message, args):
        parsed = utils.parse_codeblock(message.content)
        output = "\n------\n".join(parsed)
        await message.channel.send(output if len(parsed) > 0 else "*No codeblock or codeblock is empty.*")

    @Plugin.on_message(raw=True)
    async def msgtest(self, client, message):
        if len(message.channel_mentions) > 0:
            print(message.channel_mentions)
