""" DyphanBot Per-Server Extensions implementation """
import os
import json
import posixpath
import requests
from pprint import pprint
from dyphanbot.constants import DEFAULT_DATA_DIR

DB_FILENAME = os.path.join(DEFAULT_DATA_DIR, "extensions.json")

class ExtensionLoader(object):
    """docstring for ExtensionLoader."""
    def __init__(self, dyphanbot):
        self.dyphanbot = dyphanbot
        self.initial_data = {}
        self.db = self.load_db()

    def save_db(self, data):
        with open(DB_FILENAME, 'w') as fd:
            json.dump(data, fd)

    def load_db(self):
        try:
            with open(DB_FILENAME, 'r') as fd:
                returned = json.load(fd)
                #pprint(fd.read())
            return returned
        except (OSError, IOError) as e:
            return self.save_db(self.initial_data)

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
        except Exception as e:
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
        return "Successfully registerd `%s`" % ext['name']

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
            return "Extension not found on this server."
        req_url = ext['url-format'].format(args, message=message)
        try:
            r = requests.get(req_url)
            r.raise_for_status()
            res = r.json()
            if res["status"] == "failure":
                return "Failed: %s" % res["error"]
            if "dyphan-output" in res:
                return res["dyphan-output"]["text"]
        except Exception as e:
            return "Whoops! Something went wrong... ```py\n{}: {}\n```".format(type(e).__name__, e)

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
    """docstring for ELHandlers."""
    def __init__(self, dyphanbot):
        self.dyphanbot = dyphanbot
        self.extloader = ExtensionLoader(dyphanbot)

    async def add(self, client, message, args):
        if len(args) < 1:
            return await message.channel.send("Bruh.. What extension? `Usage: @Dyphan add-ext <url>`")
        url = args[0]
        await message.channel.send(self.extloader.register(message.guild, url))

    async def call(self, client, message, args):
        if len(args) < 1:
            return await message.channel.send("Bruh.. What extension? `Usage: @Dyphan ext <command> [args]`")
        cmd = args[0]
        #ext_args = args[1:]
        mentionless = message.content.replace(self.dyphanbot.bot_mention(message), "", 1).strip()
        ext_args = mentionless.partition(cmd)[2].strip()
        await message.channel.send(self.extloader.call(message, cmd, ext_args))

    async def help(self, client, message, args):
        if len(args) < 1:
            return await message.channel.send("Bruh.. What extension? `Usage: @Dyphan ext-help <command>`")
        cmd = args[0]
        ext = self.extloader.find(message.guild, cmd)
        if not ext:
            return await message.channel.send("Can't find that extension, bruh. It's probably not registered. `Usage: @Dyphan ext-help <command>`")
        if 'help' not in ext:
            return await message.channel.send("Extension has no `help` text.")
        await message.channel.send("*`{0}`*: {1}".format(ext['command'], ext['help']))

    async def list(self, client, message, args):
        await message.channel.send(self.extloader.list(message.guild))


def plugin_init(dyphanbot):
    el = ELHandlers(dyphanbot)

    dyphanbot.add_command_handler("add-ext", el.add)
    dyphanbot.add_command_handler("ext", el.call)
    dyphanbot.add_command_handler("ext-help", el.help)
    dyphanbot.add_command_handler("ext-list", el.list)
