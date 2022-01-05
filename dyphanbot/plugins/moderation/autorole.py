import logging
import discord

# cause python... -_-
NL = "\n"

class AutoRole(object):
    def __init__(self, dyphanbot, utils):
        self.logger = logging.getLogger(__name__)
        self.dyphanbot = dyphanbot
        self.utils = utils
    
    def role_id2obj(self, guild, role_ids):
        roles = []
        for role_id in role_ids:
            role = guild.get_role(int(role_id))
            if role is None:
                self.logger.warn(f"Autorole: There is no role with id {role_id}. Skipping.")
                continue
            roles.append(role)
        return roles
    
    def role_list2str(self, roles):
        return ', '.join([f'`@{role.name}`' for role in roles])
    
    def topmost_role(self, guild, roles):
        if any(isinstance(role, (int, str)) for role in roles):
            roles = self.role_id2obj(guild, roles)
        
        return max([role or guild.default_role for role in roles] or [guild.default_role])
    
    def perms_check(self, message, autoroles):
        if not autoroles:
            return ""
        
        if not message.channel.permissions_for(message.guild.me).manage_roles:
            return "I need the `Manage Roles` permission in order for autorole to work properly."
        
        if message.guild.me.top_role <= self.topmost_role(message.guild, autoroles):
            return "I am unable to set roles higher than mine. Please make sure I have a higher role than the specified autoroles."
        
        return ""
    
    async def on_join(self, member):
        guild = member.guild
        autorole_settings = self.utils.get_gsettings(guild, "autorole")
        autoroles = autorole_settings.get("roles", [])
        if not autorole_settings or not autorole_settings.get('enabled', False):
            return

        roles = self.role_id2obj(guild, autoroles)
        await member.add_roles(*roles, reason="Autorole")
    
    async def add_roles(self, message):
        role_mentions = message.role_mentions
        if not role_mentions:
            return await message.channel.send("No roles were mentioned.")
        
        autorole_settings = self.utils.get_gsettings(message.guild, "autorole")
        autoroles = autorole_settings.get("roles", [])

        if message.guild.me.top_role <= self.topmost_role(message.guild, role_mentions):
            return await message.channel.send("Unable to set roles higher than mine. Please either select a lower role, or give me a higher role.")

        for role in role_mentions:
            role_id = str(role.id)
            if role_id in autoroles:
                continue

            autoroles.append(role_id)
        
        self.utils.set_gsettings(message.guild, "autorole", "roles", autoroles)
        self.utils._save_gsettings()

        roles = self.role_id2obj(message.guild, autoroles)
        autorole_warn = self.perms_check(message, roles)
        await message.channel.send(
            f"{autorole_warn}{NL}Autorole was set for roles: {self.role_list2str(roles)}{NL}"
            f"Enable with `{self.utils.get_local_prefix(message)}autorole enable` to activate.".strip()
        )
    
    async def remove_roles(self, message):
        role_mentions = message.role_mentions
        if not role_mentions:
            return await message.channel.send("No roles were mentioned.")
        
        autorole_settings = self.utils.get_gsettings(message.guild, "autorole")
        autoroles = autorole_settings.get("roles", [])
        removed_roles = []

        for role in role_mentions:
            role_id = str(role.id)
            if role_id not in autoroles:
                continue

            removed_roles.append(role_id)
        
        autoroles = [role_id for role_id in autoroles if role_id not in removed_roles]

        if len(autoroles) < 1:
            self.utils.set_gsettings(message.guild, "autorole", "enabled", False)

        self.utils.set_gsettings(message.guild, "autorole", "roles", autoroles)
        self.utils._save_gsettings()

        disabled_str = f"{NL}Autorole disabled (no roles left)." if len(autoroles) < 1 else ""
        await message.channel.send(f"Removed autoroles for: {self.role_list2str(role_mentions)}{disabled_str}")
    
    async def toggle(self, message, enable):
        autorole_settings = self.utils.get_gsettings(message.guild, "autorole")
        enabled = autorole_settings.get("enabled", False)
        autoroles = autorole_settings.get("roles", [])

        action_text = "enabled" if enable else "disabled"
        opposite_text = "disable" if enable else "enable"

        if (enable and enabled) or (not enable and not enabled):
            return await message.channel.send(
                f"Autorole is already {action_text} for {len(autoroles)} roles in this server.{NL}"
                f"Type `{self.utils.get_local_prefix(message)}autorole list` for a list of the roles added.{NL}"
                f"Type `{self.utils.get_local_prefix(message)}autorole {opposite_text}` to {opposite_text}."
            )
        
        if enable and not autoroles:
            return await message.channel.send(
                f"No roles have been specified to enable autorole.{NL}"
                f"Use `{self.utils.get_local_prefix(message)}autorole add` to set roles.{NL}"
                f"Type `{self.utils.get_local_prefix(message)}autorole help` for more."
            )

        self.utils.set_gsettings(message.guild, "autorole", "enabled", enable)
        self.utils._save_gsettings()

        autorole_warn = self.perms_check(message, autoroles)
        await message.channel.send(f"{autorole_warn}{NL}Autorole has been {action_text} for {len(autoroles)} roles!".strip())
    
    async def list_roles(self, message):
        autorole_settings = self.utils.get_gsettings(message.guild, "autorole")
        enabled = autorole_settings.get("enabled", False)
        autoroles = autorole_settings.get("roles", [])
        roles = self.role_id2obj(message.guild, autoroles)

        enabled_text = "enabled" if enabled else "disabled"

        autorole_warn = self.perms_check(message, roles)
        autorole_list_str = f"Autorole list: {self.role_list2str(roles)}" if roles else "No roles have been set."
        await message.channel.send(f"{autorole_warn}{NL}Autorole is currently {enabled_text} for this server.{NL}{autorole_list_str}".strip())
    
    async def clear(self, message):
        self.utils.set_gsettings(message.guild, "autorole", "roles", [])
        self.utils.set_gsettings(message.guild, "autorole", "enabled", False)
        self.utils._save_gsettings()

        await message.channel.send("Autoroles have been cleared and disabled.")
    
    async def test_dbg(self, message):
        tested_user = message.author
        if message.mentions:
            tested_user = message.mentions[0]
        
        await self.on_join(tested_user)
        await message.channel.send(f"Autorole tested on {tested_user.mention}.")
    
    async def help(self, message, args):
        prefix = self.utils.get_local_prefix(message)
        invocation = f"{prefix}{args[0]}"
        usage_text = """
        `{0} list` - Lists the autoroles currently set for this server.
        `{0} add` - Adds the mentioned role to the list of autoroles that will be assigned on join.
        `{0} remove` - Removes the mentioned role from the list of autoroles.
        `{0} enable` - Activates autorole assignment.
        `{0} disable` - Deactivates autorole assignment.
        `{0} clear` - Clears the autorole list and deactivates autorole assignment.
        `{0} help` - Shows this help.
        """.format(invocation)
        return {
            "title": "Autorole",
            "helptext": "Set up roles that are automatically given to members when they join.",
            "sections": [
                {
                    "name": "Usage",
                    "value": usage_text.strip()
                }
            ]
        }

    async def invoke(self, message, args):
        if len(args) > 0:
            scmd = args[0].strip()
            if scmd == 'add':
                await self.add_roles(message)
            elif scmd == 'remove':
                await self.remove_roles(message)
            elif scmd == 'enable':
                await self.toggle(message, True)
            elif scmd == 'disable':
                await self.toggle(message, False)
            elif scmd == 'clear':
                await self.clear(message)
            elif scmd == 'list':
                await self.list_roles(message)
            elif scmd == 'help':
                await self.dyphanbot.bot_controller.help(message, ['autorole'])
            else:
                if scmd == 'test' and self.dyphanbot.is_botmaster(message.author):
                    # idiot-proofing... this is mainly for debugging anyway.
                    return await self.test_dbg(message)
                
                await message.channel.send(f"Unknown subcommand. Type `{self.utils.get_local_prefix(message)}autorole help` for available commands.")
        else:
            await self.list_roles(message)