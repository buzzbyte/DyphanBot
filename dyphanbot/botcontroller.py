import logging
import discord

class BotController:
    def __init__(self, dyphanbot):
        self.logger = logging.getLogger(__name__)
        self.dyphanbot = dyphanbot
        self._guildsettings_fn = "guildsettings.json"
        self.guildsettings = self.dyphanbot.data.load_json(self._guildsettings_fn, {})

    def _save_settings(self, data):
        return self.dyphanbot.data.save_json(self._guildsettings_fn, data)

    def _get_prefix(self, guild):
        guild_id = str(guild.id)
        prefix = None
        if self.guildsettings.get(guild_id):
            prefix = self.guildsettings[guild_id].get("prefix")
        return prefix

    def _get_ext_prefix(self, guild):
        guild_id = str(guild.id)
        ext_prefix = '+'
        if self.guildsettings.get(guild_id):
            ext_prefix = self.guildsettings[guild_id].get("ext-prefix", '+')
        return ext_prefix
    
    def _get_settings_for_guild(self, guild, key=None):
        guild_id = str(guild.id)
        if guild_id in self.guildsettings:
            return self.guildsettings[guild_id].get(key, None) if key else self.guildsettings[guild_id]
        return None

    async def _process_command(self, message, cmd, args, prefix=None):
        # Exclude commands trying to call hidden methods.
        # Additionally, make sure only the general/helper commands are allowed
        # to be called with a prefix.
        general_cmds = ['help', 'commands', 'plugins']
        if cmd.startswith('_') or (prefix and cmd not in general_cmds):
            return None
        try:
            return await getattr(self, cmd)(message, args)
        except AttributeError:
            return None

    async def plugins(self, message, args):
        """ Sends an embed listing available plugins """
        plugins = self.dyphanbot.pluginloader.get_plugins()
        pliststr = ""
        unlisted_count = 0
        for pname, plugin in plugins.items():
            try:
                phelp = await plugin.help(message, [pname]) # pass default args since we only want the title and short description
                if 'unlisted' in phelp and phelp['unlisted']:
                    unlisted_count += 1
                    continue

                if 'title' not in phelp or phelp['title'].strip() == pname:
                    pliststr += "• `{0}`".format(pname)
                else:
                    pliststr += "• {0} (`{1}`)".format(phelp['title'], pname)
                
                if 'shorthelp' in phelp:
                    pliststr += ": {0}".format(phelp['shorthelp'])
                
                pliststr += "\n"
            except:
                self.logger.warning("Skipped plugin '%s' due to an error in its help method.", pname)
                unlisted_count += 1
                continue
        
        if not pliststr.strip():
            pliststr = "No plugins provide help... :c\n"
        
        if unlisted_count > 0:
            pliststr += "\nUnlisted plugins: {0}".format(unlisted_count)

        embed = discord.Embed(
            title="Available Plugins",
            description=pliststr,
            colour=discord.Colour(0x7289DA)
        )
        await message.channel.send(embed=embed)

    async def help(self, message, args):
        """ Sends an embed providing general or plugin help """
        plugins = self.dyphanbot.pluginloader.get_plugins()
        release_info = self.dyphanbot.release_info()
        version = release_info["version"]
        
        if len(args) < 1:
            prefix = self._get_prefix(message.guild) or "@{0} ".format(self.dyphanbot.user.name)
            help_txt = "Use the following commands to learn more about how to use {0}.".format(self.dyphanbot.user.name)
            embed = discord.Embed(
                title="{0} Help".format(self.dyphanbot.user.name),
                description=help_txt,
                colour=discord.Colour(0x7289DA)
            )
            embed.add_field(
                name="`{0}plugins`".format(prefix),
                value="Lists available plugins that provide help, as well as an optional short description for each plugin.",
                inline=False
            )
            embed.add_field(
                name="`{0}commands [plugin]`".format(prefix),
                value="Only lists the plugin's available commands (useful for a general overview of the commands rather than a complete help doc).",
                inline=False
            )
            embed.add_field(
                name="`{0}help [plugin/command]`".format(prefix),
                value="Displays more info about the plugin. If a command is specified, displays info about the command's plugin.",
                inline=False
            )
            embed.set_footer(
                text="Running {0}{1}".format(
                    release_info["name"],
                    f" v{version}" if version else ""
                )
            )
            await message.channel.send(embed=embed)
        else:
            plugin = None
            if args[0] in plugins.keys():
                plugin = plugins[args[0]]
            elif args[0] in self.dyphanbot.commands:
                command = self.dyphanbot.commands[args[0]]
                if 'plugin' in command.__dict__ and command.plugin:
                    plugin = command.plugin
            
            if not plugin:
                return await message.channel.send("Plugin not found or can't find command's plugin..")

            if not hasattr(plugin, 'help'):
                await message.channel.send("Plugin provides no help or usage information...")
            else:
                try:
                    phelp = await plugin.help(message, args)
                    embed = discord.Embed(
                        title=phelp['title'] if 'title' in phelp else type(plugin).__name__,
                        description=phelp['helptext'] if 'helptext' in phelp else "*N/A*",
                        colour=phelp['color'] if 'color' in phelp else discord.Colour(0x7289DA)
                    )

                    if 'sections' in phelp and phelp['sections']:
                        for section in phelp['sections']:
                            embed.add_field(
                                name=section['name'],
                                value=section['value'],
                                inline=section['inline'] if 'inline' in section else True
                            )
                    
                    await message.channel.send(embed=embed)
                except Exception as e:
                    await message.channel.send("Whoops! Something went wrong... ```py\n{}: {}\n```".format(type(e).__name__, e))
    
    async def commands(self, message, args):
        """ Sends an embed listing available commands in a plugin """
        plugins = self.dyphanbot.pluginloader.get_plugins()

        if len(args) < 1:
            return await self.help(message, args)
        
        if args[0] not in plugins.keys():
            return await message.channel.send("Plugin not found.")
        
        pname = args[0]
        pcmds = []
        for cmd_name, command in self.dyphanbot.commands.items():
            if 'plugin' not in command.__dict__ or not command.plugin:
                continue

            if pname.strip() == type(command.plugin).__name__:
                pcmds.append(cmd_name)
        
        pcmdstr = "Plugin has no available commands."
        if len(pcmds) > 0:
            pcmdstr = ', '.join(["`{0}`".format(x) for x in pcmds])
        
        embed = discord.Embed(
            title="{0} Commands".format(pname),
            description=pcmdstr,
            colour=discord.Colour(0x7289DA)
        )
        await message.channel.send(embed=embed)

    async def prefix(self, message, args):
        guild_id = str(message.guild.id)
        if len(args) < 1:
            prefix = None
            ext_prefix = '+'
            if self.guildsettings.get(guild_id):
                prefix = self.guildsettings[guild_id].get("prefix")
                ext_prefix = self.guildsettings[guild_id].get("ext-prefix", '+')
            await message.channel.send(
                "Command prefix: `{0}`\nExtension prefix: `{1}`".format(
                    prefix if prefix else "<Unset>",
                    ext_prefix if ext_prefix else "<Unset>"
                )
            )
        elif len(args) <= 1 and args[0] == "ext":
            ext_prefix = '+'
            if self.guildsettings.get(guild_id):
                ext_prefix = self.guildsettings[guild_id].get("ext-prefix", '+')
            await message.channel.send("Extension prefix: `{0}`".format(ext_prefix if ext_prefix else "<Unset>"))
        else:
            ext_arg = False
            if args[0] == "ext":
                ext_arg = True
            if not message.author.guild_permissions.manage_guild:
                await message.channel.send("You don't have permission to change the {0} prefix!!".format("extension" if ext_arg else "command"))
                return
            if ext_arg:
                args = ' '.join(args[1:])
            else:
                args = ' '.join(args)
            if not self.guildsettings.get(guild_id):
                self.guildsettings[guild_id] = {}
            if ext_arg and args == self.guildsettings[guild_id].get("prefix"):
                return await message.channel.send("Extension prefix can't be the same as the command prefix!!")
            self.guildsettings[guild_id]["ext-prefix" if ext_arg else "prefix"] = args
            self.guildsettings = self._save_settings(self.guildsettings)
            await message.channel.send("The {0} prefix for this guild was set to `{1}`".format("extension" if ext_arg else "command", self.guildsettings[guild_id]["ext-prefix" if ext_arg else "prefix"]))

    async def disable(self, message, args):
        guild_id = str(message.guild.id)
        if not message.author.guild_permissions.manage_guild:
            return await message.channel.send("You don't have permission to disable commands for this server!!")
        if len(args) < 1:
            disabled_cmds_lst = []
            if self.guildsettings.get(guild_id):
                disabled_cmds = self.guildsettings[guild_id].get("disabled_commands") or []
                disabled_cmds_lst = disabled_cmds
            await message.channel.send("Disabled commands: {0}.".format(', '.join(["`{0}`".format(x) for x in disabled_cmds_lst])) if len(disabled_cmds_lst) > 0 else "No commands disabled on this server.")
        elif len(args) > 1:
            if not self.guildsettings.get(guild_id):
                self.guildsettings[guild_id] = {}
            if not "disabled_commands" in self.guildsettings[guild_id]:
                self.guildsettings[guild_id]["disabled_commands"] = []
            if args[0] == "add":
                self.guildsettings[guild_id]["disabled_commands"] += list(args[1:])
                self.guildsettings = self._save_settings(self.guildsettings)
                await message.channel.send("Successfully disabled commands: {0}.".format(', '.join(["`{0}`".format(x) for x in args[1:]])))
            elif args[0] == "rem":
                disabled_cmds = self.guildsettings[guild_id]["disabled_commands"]
                new_list = [x for x in disabled_cmds if x not in args[1:]]
                self.guildsettings[guild_id]["disabled_commands"] = new_list
                self.guildsettings = self._save_settings(self.guildsettings)
                await message.channel.send("Successfully enabled commands: {0}.".format(', '.join(["`{0}`".format(x) for x in args[1:]])))
            else:
                await message.channel.send("Invalid subcommand.\nUsage: `@{0} disable [<add|rem> <commands...>]`".format(self.dyphanbot.user.name))
        else:
            await message.channel.send("Adds/Removes commands to/from the disabled commands list on this server.\nUsage: `@{0} disable [<add|rem> <commands...>]`".format(self.dyphanbot.user.name))