import traceback

import random
import discord

from dyphanbot import Plugin, utils

from .autorole import AutoRole
from .farewell import Farewell

"""
gsettings.json structure:
-------------------------
{
    "guilds": {
        "12345678987654321": {
            "farewell": {
                "enabled": true,
                "message": ["...", ],
                "channel_id": "98765432123456789"
            },
            "autorole": {
                "enabled": true,
                "roles": [
                    "0864213579086421", ...
                ]
            }
        },
        ...
    }
}
"""

class Moderation(Plugin):
    """
    Commands and tools for Discord server moderation and administration.
    """
    
    def __init__(self, dyphanbot):
        super().__init__(dyphanbot)

        self._gsettings_fn = "gsettings.json"
        self._gsettings = self._load_gsettings()

        self.autorole = AutoRole(dyphanbot, self)
        self.farewell = Farewell(dyphanbot, self)

    def _save_gsettings(self):
        return self.save_json(self._gsettings_fn, self._gsettings)
    
    def _load_gsettings(self):
        return self.load_json(self._gsettings_fn, initial_data={
            "guilds": {}
        })
    
    def get_template_defs(self, member, channel, guild):
        return {
            "user.name": member.name,
            "user.discrim": member.discriminator,
            "user.mention": member.mention,
            "channel.name": channel.name,
            "channel.mention": channel.mention,
            "guild.name": guild.name
        }
    
    def parse_message_template(self, text, member, channel, guild):
        template_defs = self.get_template_defs(member, channel, guild)
        for key, val in template_defs.items():
            text = text.replace(f"{{{key}}}", val)
        return text
    
    def get_guild_settings(self, guild, reload=True):
        if reload:
            self._gsettings = self._load_gsettings()
        return self._gsettings.get("guilds", {}).get(str(guild.id), {})

    def get_gsettings(self, guild, setting, reload=True):
        gsettings = self.get_guild_settings(guild, reload)
        return gsettings.get(setting, {})
    
    def set_gsettings(self, guild, setting, key, value):
        guild_id = str(guild.id)
        if not self.get_guild_settings(guild, False):
            self._gsettings["guilds"][guild_id] = {}
        
        if not self.get_gsettings(guild, setting, False):
            self._gsettings["guilds"][guild_id][setting] = {}
        
        self._gsettings["guilds"][guild_id][setting][key] = value
        return self._gsettings["guilds"][guild_id][setting][key]
    
    async def help(self, message, args):
        try:
            submod = getattr(self, args[0], None)
            if submod and hasattr(submod, "help"):
                return await submod.help(message, args)
        except:
            traceback.print_exc()
        
        return {
            "helptext": "Various commands tools for Discord server management.\nType `help` after the command for usage info.",
            "shorthelp": "Commands and tools for server management.",
            "sections": [
                {
                    "name": "Available commands:",
                    "value": "`{0}autorole`\n`{0}farewell`".format(self.get_local_prefix(message))
                }
            ]
        }
    
    @Plugin.event
    async def on_member_join(self, member):
        await self.autorole.on_join(member)

    @Plugin.event
    async def on_member_remove(self, member):
        await self.farewell.on_leave(member)
    
    @Plugin.command(cmd="autorole", perms=["manage_roles"])
    async def autorole_cmd(self, client, message, args):
        return await self.autorole.invoke(message, args)
    
    @Plugin.command(cmd="farewell", perms=["manage_guild"])
    async def farewell_cmd(self, client, message, args):
        return await self.farewell.invoke(message, args)
