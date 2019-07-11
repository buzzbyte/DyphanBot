import logging

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

    async def _process_command(self, message, cmd, args):
        if cmd.startswith('_'):
            return None
        try:
            return await getattr(self, cmd)(message, args)
        except AttributeError:
            return None

    async def prefix(self, message, args):
        guild_id = str(message.guild.id)
        if len(args) < 1:
            prefix = None
            if self.guildsettings.get(guild_id):
                prefix = self.guildsettings[guild_id].get("prefix")
            await message.channel.send("Command prefix: `{0}`".format(prefix if prefix else "<Unset>"))
        elif len(args) <= 1 and args[0] == "ext":
            ext_prefix = '+'
            if self.guildsettings.get(guild_id):
                ext_prefix = self.guildsettings[guild_id].get("ext-prefix", '+')
            await message.channel.send("Extension prefix: `{0}`".format(ext_prefix if ext_prefix else "<Unset>"))
        else:
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