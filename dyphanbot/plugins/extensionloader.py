""" DyphanBot Per-Server Extensions implementation """
import os
import json
import traceback
import posixpath
from pprint import pprint

import requests
import discord

import dyphanbot.utils as utils

HELP_MSG = """
**Extensions Help**
`{0}add <url>`: Registers an extension to this server.
`{0}remove <extension_command>`: Unregisters an extension from this server.
`{0}list`: Lists extensions registered on this server.
`{0}help [extension_command]`: Displays extension help text.
`{0}<extension_command>`: Calls an extension.
"""

class ExtensionLoader(object):
    """ Handles per-server extension loading """
    def __init__(self, dyphanbot):
        self.dyphanbot = dyphanbot
        self.db_filename = "extensions.json"
        self.db = self.load_db()

    def save_db(self, data):
        return self.dyphanbot.data.save_json(self.db_filename, data)

    def load_db(self):
        return self.dyphanbot.data.load_json(self.db_filename)

    def parse_output(self, output):
        """ Parses JSON output to `send()` parameters. """
        return {
            "content": (output['text'] if 'text' in output else None),
            "embed": (discord.Embed.from_dict(output['embed']) if 'embed' in output else None),
            "tts": (output['tts'] if 'tts' in output else False),
            "files": (output['files'] if 'files' in output else None),
            "file": None, # Only allow list of files to prevent exceptions
            "delete_after": (output['delete_after'] if 'delete_after' in output else None)
        }

    def verify(self, url):
        if not url.startswith("https"):
            return False

        required_keys = ['id', 'name', 'author', 'command', 'url-format']
        try:
            r = requests.get(posixpath.join(url, "manifest.json"))
            r.raise_for_status()
            manifest = r.json()
            if 'dyphan-extension' not in manifest:
                return False
            if not any(x in manifest['dyphan-extension'] for x in required_keys):
                return False
            return manifest['dyphan-extension']
        except Exception:
            return False

    def register(self, guild, url):
        ext = self.verify(url)
        if not ext:
            return "Invalid extension."

        guild_id = str(guild.id)
        ext_id = ext['id']
        self.db = self.load_db()
        if guild_id not in self.db:
            self.db[guild_id] = {}
        if ext_id in self.db[guild_id]:
            return "Extension already registered in this server."

        self.db[guild_id][ext_id] = ext
        self.save_db(self.db)
        return "Successfully registered `%s`" % ext['name']
    
    def unregister(self, guild, cmd):
        ext = self.find(guild, cmd)
        if not ext:
            return "Extension `{0}` not found on this server.".format(cmd)

        guild_id = str(guild.id)
        ext_id = ext['id']
        self.db = self.load_db()
        if ext_id not in self.db.get(guild_id, {}) or {}:
            return "Extension not found on this server. (2)"

        self.db[guild_id].pop(ext_id, None)
        self.save_db(self.db)
        return "Successfully unregistered `%s`" % ext['name']

    def find(self, guild, cmd):
        self.db = self.load_db()
        guild_id = str(guild.id)
        if guild_id not in self.db:
            print("ID not found...")
            return False
        ext_dict = self.db[guild_id]
        for key in ext_dict:
            if cmd == ext_dict[key]['command']:
                return ext_dict[key]
        print("Extension not found...")
        return False

    def call(self, message, cmd, args):
        ext = self.find(message.guild, cmd)
        if not ext:
            return { "content": "Extension `{0}` not found on this server.".format(cmd) }
        req_url = ext['url-format'].format(args, message=message)
        try:
            r = requests.get(req_url)
            r.raise_for_status()
            res = r.json()
            if res["status"] == "failure":
                return { "content": ("Failed: %s" % res["error"]) }
            if "dyphan-output" in res:
                return self.parse_output(res["dyphan-output"])
        except Exception as e:
            traceback.print_exc()
            return { "content": "Whoops! Something went wrong... ```py\n{}: {}\n```".format(type(e).__name__, e) }

    def list(self, guild):
        guild_id = str(guild.id)
        if guild_id not in self.db:
            return "No extensions are registered on this server."
        ext_dict = self.db[guild_id]
        returned = "Found {} registered extensions for this server:\n".format(len(ext_dict))
        for key in ext_dict:
            ext = ext_dict[key]
            returned += "*`{0}`*: {1}\n".format(ext['command'], ext['help'])
        return returned

class ELHandlers(object):
    """ Command handlers for extensions """
    def __init__(self, dyphanbot):
        self.dyphanbot = dyphanbot
        self.extloader = ExtensionLoader(dyphanbot)
        self.reserved_cmds = [ "add", "remove", "help", "list" ]
        self.ext_prefix = '+'

    async def add(self, client, message, args):
        if not message.author.guild_permissions.manage_guild:
            return await message.channel.send("You don't have permission to add extensions to this server.")
        if len(args) < 1:
            return await message.channel.send("Bruh.. What extension? `Usage: @{0} {1}add <url>`".format(self.dyphanbot.user.name, self.ext_prefix))
        url = args[0]
        await message.channel.send(self.extloader.register(message.guild, url))
    
    async def remove(self, client, message, args):
        if not message.author.guild_permissions.manage_guild:
            return await message.channel.send("You don't have permission to remove extensions from this server.")
        if len(args) < 1:
            return await message.channel.send("Bruh.. What extension? `Usage: @{0} {1}remove <command>`".format(self.dyphanbot.user.name, self.ext_prefix))
        cmd = args[0]
        await message.channel.send(self.extloader.unregister(message.guild, cmd))

    async def call(self, client, message, args):
        if len(args) < 1:
            return await message.channel.send("Bruh.. What extension? `Usage: @{0} {1}<command> [args]`".format(self.dyphanbot.user.name, self.ext_prefix))
        cmd = args[0]
        #ext_args = args[1:]
        mentionless = message.content.replace(self.dyphanbot.bot_mention(message), "", 1).strip()
        ext_args = mentionless.partition(cmd)[2].strip()
        await message.channel.send(**self.extloader.call(message, cmd, ext_args))

    async def help(self, client, message, args):
        if len(args) < 1:
            return await message.channel.send(HELP_MSG.format(self.ext_prefix))
        cmd = args[0]
        ext = self.extloader.find(message.guild, cmd)
        if not ext:
            return await message.channel.send("Can't find that extension, bruh. It's probably not registered. `Usage: @{0} {1}help <command>`".format(self.dyphanbot.user.name, self.ext_prefix))
        if 'help' not in ext:
            return await message.channel.send("Extension has no `help` text.")
        await message.channel.send("*`{0}`*: {1}\n{2}".format(ext['command'], ext['help'], ext.get('website', "")))

    async def list(self, client, message, args):
        await message.channel.send(self.extloader.list(message.guild))

    async def _reserved(self, client, message, args):
        await message.channel.send("Reserved command. Not yet implemented.")

    async def ext_command_handler(self, client, message):
        self.ext_prefix = self.dyphanbot.bot_controller._get_ext_prefix(message.guild)
        parsed_cmd = utils.parse_command(self.dyphanbot, message, self.ext_prefix, True)
        if not parsed_cmd:
            return
        cmd, args = parsed_cmd
        if cmd[0] in self.reserved_cmds:
            await getattr(self, cmd[0], self._reserved)(client, message, args)
        else:
            await self.call(client, message, cmd)

def plugin_init(dyphanbot):
    el = ELHandlers(dyphanbot)
    dyphanbot.add_message_handler(el.ext_command_handler, True)
