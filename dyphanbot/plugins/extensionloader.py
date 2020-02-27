""" DyphanBot Per-Server Extensions implementation """
import os
import io
import json
import traceback
import posixpath
from pprint import pprint
from base64 import b64decode

import requests
import discord

import dyphanbot.utils as utils
from dyphanbot import Plugin
from dyphanbot.exceptions import DyphanBotError

EXT_REPO_URL = "https://dyphanbot.github.io/repo"

HELP_MSG = """
**Extensions Help**
`{0}add <url>`: Registers an extension to this server.
`{0}remove <extension_command>`: Unregisters an extension from this server.
`{0}update <extension_command>`: Re-registers an extension on this server.
`{0}list`: Lists extensions registered on this server.
`{0}help [extension_command]`: Displays extension help text.
`{0}<extension_command>`: Calls an extension.
"""

class InvalidExtensionError(DyphanBotError):
    """ Raised when extension verification fails """
    pass

class ELCore(object):
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
        out_files = []
        if 'files' in output:
            # Get files from datauris
            for jfo in output['files']:
                data_uri = jfo.get('datauri', "")
                filename = jfo.get('filename')
                spoiler = jfo.get('spoiler', False)
                _, encoded = data_uri.split(",", 1)
                if not data_uri:
                    continue

                # Get binary from base64 and make it a discord File object
                fio = io.BytesIO(b64decode(encoded))
                out_files.append(discord.File(fio, filename=filename, spoiler=spoiler))
        else:
            out_files = None
        
        return {
            "content": (output['text'] if 'text' in output else None),
            "embed": (discord.Embed.from_dict(output['embed']) if 'embed' in output else None),
            "tts": (output['tts'] if 'tts' in output else False),
            "files": out_files,
            "file": None, # Only allow list of files to prevent exceptions
            "delete_after": (output['delete_after'] if 'delete_after' in output else None)
        }

    def verify(self, url):
        """ Checks if url or extension name is provided, looks up manifest.json,
            verifies if the manifest is valid by checking for required keys,
            then returns extension info. If validation fails, raises
            `InvalidExtensionError` with an appropriate message.
        """
        if "://" in url:
            if not url.startswith("https://"):
                raise InvalidExtensionError("Extension URLs must start with `https://`")
        elif url.isalnum():
            ext_name = url
            url = posixpath.join(EXT_REPO_URL, ext_name)
        else:
            raise InvalidExtensionError("Invalid URL or extension name.")

        required_keys = ['id', 'name', 'author', 'command', 'request-url']
        try:
            r = requests.get(posixpath.join(url, "manifest.json"))
            r.raise_for_status()
            manifest = r.json()
            if 'dyphan-extension' not in manifest:
                raise InvalidExtensionError("Not a valid extension.")
            if not any(x in manifest['dyphan-extension'] for x in required_keys):
                raise InvalidExtensionError("Broken extension manifest. Contact developer.")
            return manifest['dyphan-extension']
        except requests.HTTPError:
            raise InvalidExtensionError("Extension not found or cannot be accessed.")
        except requests.ConnectionError:
            raise InvalidExtensionError("Could not request extension (ConnectionError).")
        except ValueError:
            raise InvalidExtensionError("Unable to parse extension.")
    
    def _register(self, guild, ext, update=False):
        """ Registers extension.
            If a conflicting extension is found, appends a number.
        """
        guild_id = str(guild.id)
        ext_id = ext['id']

        conflicting_cmd_warn = ""
        cmd_list = self.get_command_list(guild)
        if ext['command'] in cmd_list and not update:
            # there has to be a better way to do this.... right?
            count = 1
            new_cmd = "{0}:{1}".format(ext['command'], count)
            while new_cmd in cmd_list:
                count += 1
                new_cmd = "{0}:{1}".format(ext['command'], count)
            conflicting_cmd_warn = ", but found conflicting commands."
            ext['command'] = new_cmd
        
        self.db[guild_id][ext_id] = ext
        self.save_db(self.db)
        return "Successfully registered `{0}`{1}".format(ext['name'], conflicting_cmd_warn)

    def register(self, guild, url):
        """ Verifies and registers extension """
        try:
            ext = self.verify(url)
        except InvalidExtensionError as err:
            return err

        guild_id = str(guild.id)
        ext_id = ext['id']
        self.db = self.load_db()
        if guild_id not in self.db:
            self.db[guild_id] = {}
        if ext_id in self.db[guild_id]:
            return "Extension already registered in this server."
        
        ext['ext-url'] = url
        return self._register(guild, ext)
    
    def unregister(self, guild, cmd):
        """ Removes a registered extension from the guild """
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
    
    def reregister(self, guild, cmd, force=False):
        """ Updates extension manifest """
        ext = self.find(guild, cmd)
        if not ext:
            return "Extension `{0}` not found on this server.".format(cmd)
        
        guild_id = str(guild.id)
        ext_id = ext['id']
        self.db = self.load_db()
        if ext_id not in self.db.get(guild_id, {}) or {}:
            return "Extension not found on this server. (2)"
        
        if "ext-url" in ext:
            url = ext['ext-url']
            try:
                ext = self.verify(url)
            except InvalidExtensionError as err:
                return err
            
            if ext['id'] != ext_id and not force:
                return "Extension ID changed. Is this the same extension?"
            
            ext['ext-url'] = url
            return self._register(guild, ext, update=True)
        
        return "Extension URL not found. Try removing and adding it again."

    def find(self, guild, cmd):
        """ Looks up a registered extension and returned it if found, or
            `False` if not found.
        """
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
        """ Calls the extension by sending a JSON POST request with the relevent
            message object parameters and returns a dict of the message to send.
        """
        ext = self.find(message.guild, cmd)
        if not ext:
            return { "content": "Extension `{0}` not found on this server.".format(cmd) }
        
        time_fmt = "%Y-%m-%dT%H:%M:%S"

        # HUGE PAYLOAD!! #
        req_payload = {
            "query": args,
            "message": {
                "id": message.id,
                "author": {
                    "id": message.author.id,
                    "name": message.author.name,
                    "discriminator": message.author.discriminator,
                    "display_name": message.author.display_name,
                    "avatar_url": str(message.author.avatar_url),
                    "color": message.author.color.value,
                    "activity": str(message.author.activity) or None,
                    "mention": message.author.mention,
                    "channel_permissions": message.author.permissions_in(message.channel).value,
                    "guild_permissions": message.author.guild_permissions.value,
                    "bot": message.author.bot,
                    "joined_at": message.author.joined_at.strftime(time_fmt),
                    "created_at": message.author.created_at.strftime(time_fmt)
                },
                "content": message.content,
                "clean_content": message.clean_content,
                "channel": {
                    "id": message.channel.id,
                    "name": message.channel.name,
                    "topic": message.channel.topic,
                    "mention": message.channel.mention,
                    "last_message_id": message.channel.last_message_id,
                    "slowmode_delay": message.channel.slowmode_delay,
                    "is_nsfw": message.channel.is_nsfw(),
                    "is_news": message.channel.is_news(),
                    "created_at": message.channel.created_at.strftime(time_fmt)
                },
                "guild": {
                    "id": message.guild.id,
                    "name": message.guild.name,
                    "icon_url": str(message.guild.icon_url),
                    "owner_id": message.guild.owner_id,
                    "max_presences": message.guild.max_presences,
                    "max_members": message.guild.max_members,
                    "description": message.guild.description,
                    "mfa_level": message.guild.mfa_level,
                    "features": message.guild.features,
                    "premium_tier": message.guild.premium_tier,
                    "premium_subscription_count": message.guild.premium_subscription_count,
                    "large": message.guild.large,
                    "emoji_limit": message.guild.emoji_limit,
                    "filesize_limit": message.guild.filesize_limit,
                    "member_count": message.guild.member_count,
                    "created_at": message.guild.created_at.strftime(time_fmt)
                },
                "mention_everyone": message.mention_everyone,
                "jump_url": message.jump_url,
                "created_at": message.created_at.strftime(time_fmt)
            }
        }
        req_headers = {"Content-Type": "application/json"}
        print(req_payload)
        try:
            req_url = ext['request-url']
            if "no-params" in ext and ext.get("no-params", "false"):
                r = requests.get(req_url, headers=req_headers)
            else:
                r = requests.post(req_url, data=json.dumps(req_payload), headers=req_headers)
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
        """ Returns a string containing a list of registered extensions in the
            guild
        """
        guild_id = str(guild.id)
        if guild_id not in self.db:
            return "No extensions are registered on this server."
        ext_dict = self.db[guild_id]
        returned = "Found {} registered extensions for this server:\n".format(len(ext_dict))
        for key in ext_dict:
            ext = ext_dict[key]
            returned += "*`{0}`*: {1}\n".format(ext['command'], ext['help'])
        return returned
    
    def get_ext_dict(self, guild):
        """ Returns a dict of registered extensions in a guild """
        guild_id = str(guild.id)
        if guild_id not in self.db:
            return {}
        ext_dict = self.db[guild_id]
        return ext_dict
    
    def get_command_list(self, guild):
        """ Returns a list of extension commands """
        ext_dict = self.get_ext_dict(guild)
        cmd_list = []
        for ext in ext_dict.values():
            cmd_list.append(ext['command'])
        return cmd_list

class ExtensionLoader(Plugin):
    """ Command handlers for the extension loader """
    def __init__(self, dyphanbot):
        super().__init__(dyphanbot)
        self.dyphanbot = dyphanbot
        self.extloader = ELCore(dyphanbot)
        self.reserved_cmds = [ "add", "remove", "update", "help", "list" ]
        self.ext_prefix = '+'

    def _help_embed(self, ext):
        """ Generates and returns an embed with the extension's help info
            and usage
        """
        embed = discord.Embed(
            title=ext['name'],
            colour=discord.Colour(0x7289da),
            description=ext.get("help", "*No help provided.*")
        )
        embed.set_author(name="Extension Help")

        if "website" in ext:
            embed.url = ext.get("website")
        
        embed.add_field(name="Usage", value=self._parse_usage(ext), inline=False)
        
        return embed
    
    def _list_embed(self, ext_dict):
        """ Generates and returns an embed containing a list of registered
            extensions and their descriptions.
        """
        if len(ext_dict) < 1:
            return discord.Embed(
                colour=discord.Colour(0x7289da),
                description="No extensions are registered on this server."
            )
        embed_text = "Found {0} extensions registered on this server.\nType `{1}help <command>` for usage info."
        embed = discord.Embed(
            colour=discord.Colour(0x7289da),
            description=embed_text.format(len(ext_dict), self.ext_prefix)
        )
        embed.set_author(name="Extension List")

        for key in ext_dict:
            ext = ext_dict[key]
            embed.add_field(
                name="`{0}`".format(ext['command']),
                value=ext.get("help", "*No help provided.*"),
                inline=True
            )
        
        return embed
    
    def _parse_usage(self, ext):
        """ Formats the extension's usage strings if found. Otherwise, return
            the command call as default.
        """
        return ext.get("usage", "Default: `{command}`").format(
            prefix=self.ext_prefix,
            command="%s%s" % (self.ext_prefix, ext.get('command')),
            command_name=ext.get('command')
        )

    async def add(self, client, message, args):
        """ Command handler for registering extensions to the server """
        if not message.author.guild_permissions.manage_guild:
            return await message.channel.send("You don't have permission to add extensions to this server.")
        if len(args) < 1:
            return await message.channel.send("Bruh.. What extension? `Usage: @{0} {1}add <url>`".format(self.dyphanbot.user.name, self.ext_prefix))
        url = args[0]
        await message.channel.send(self.extloader.register(message.guild, url))
    
    async def remove(self, client, message, args):
        """ Command handler for unregistering extensions from the server """
        if not message.author.guild_permissions.manage_guild:
            return await message.channel.send("You don't have permission to remove extensions from this server.")
        if len(args) < 1:
            return await message.channel.send("Bruh.. What extension? `Usage: @{0} {1}remove <command>`".format(self.dyphanbot.user.name, self.ext_prefix))
        cmd = args[0]
        await message.channel.send(self.extloader.unregister(message.guild, cmd))
    
    async def update(self, client, message, args):
        """ Command handler for reloading an extension """
        if not message.author.guild_permissions.manage_guild:
            return await message.channel.send("You don't have permission to update extensions on this server.")
        if len(args) < 1:
            return await message.channel.send("Bruh.. What extension? `Usage: @{0} {1}update <command> [force]`".format(self.dyphanbot.user.name, self.ext_prefix))
        cmd = args[0]
        force = False
        if len(args) > 1:
            force = True if args[1].strip() == "force" else False
        await message.channel.send(self.extloader.reregister(message.guild, cmd, force))

    async def call(self, client, message, args):
        """ Handles extension command calls """
        if len(args) < 1:
            return await message.channel.send("Bruh.. What extension? `Usage: @{0} {1}<command> [args]`".format(self.dyphanbot.user.name, self.ext_prefix))
        cmd = args[0]
        #ext_args = args[1:]
        mentionless = message.content.replace(self.dyphanbot.bot_mention(message), "", 1).strip()
        ext_args = mentionless.partition(cmd)[2].strip()
        await message.channel.send(**self.extloader.call(message, cmd, ext_args))

    async def help(self, client, message, args):
        """ Sends back the requested extension's help embed, if an extension
            was provided; otherwise sends command help message.
        """
        if len(args) < 1:
            return await message.channel.send(HELP_MSG.format(self.ext_prefix))
        cmd = args[0]
        ext = self.extloader.find(message.guild, cmd)
        if not ext:
            return await message.channel.send("Can't find that extension, bruh. It's probably not registered. `Usage: @{0} {1}help <command>`".format(self.dyphanbot.user.name, self.ext_prefix))
        
        #await message.channel.send("*`{0}`*: {1}\n{2}".format(ext['command'], ext['help'], ext.get('website', "")))
        await message.channel.send(embed=self._help_embed(ext))

    async def list(self, client, message, args):
        """ Sends back an embed of a list of registered extensions """
        #await message.channel.send(self.extloader.list(message.guild))
        await message.channel.send(embed=self._list_embed(self.extloader.get_ext_dict(message.guild)))

    async def _reserved(self, client, message, args):
        """ Placeholder for unimplemented commands """
        await message.channel.send("Reserved command. Not yet implemented.")
    
    @Plugin.on_message(raw=True)
    async def ext_command_handler(self, client, message):
        """ Message handler for extension calls and related commands """
        self.ext_prefix = self.dyphanbot.bot_controller._get_ext_prefix(message.guild)
        parsed_cmd = utils.parse_command(self.dyphanbot, message, self.ext_prefix, True)
        if not parsed_cmd:
            return
        cmd, args = parsed_cmd
        if cmd[0] in self.reserved_cmds:
            await getattr(self, cmd[0], self._reserved)(client, message, args)
        else:
            await self.call(client, message, cmd)

#def plugin_init(dyphanbot):
#    el = ELHandlers(dyphanbot)
#    dyphanbot.add_message_handler(el.ext_command_handler, True)
