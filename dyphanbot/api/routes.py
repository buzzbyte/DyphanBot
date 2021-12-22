import json
from aiohttp import web
from aiohttp_session import get_session

import discord

import dyphanbot.api as api

class APIRouter(object):
    """ Handles main API routes """
    
    def __init__(self, dyphanbot, api_client):
        self.dyphanbot = dyphanbot
        self.api_client = api_client
    
    def get_routes(self):
        """ Returns a list of routes to be added """
        return [
            web.get("/", self.index),
            web.get("/plugins", self.list_plugins),
            web.get("/commands", self.list_commands),
            web.get("/guilds", self.list_guilds),
            web.get("/guilds/user", self.user_guilds),
            web.get("/guilds/bot", self.bot_guilds),
            web.get("/guilds/mutual", self.mutual_guilds),
            web.get("/oauth", self.oauth)
        ]
    
    async def index(self, request):
        """ Responds with the bot's basic info """
        release_info = self.dyphanbot.release_info()
        user = await self.api_client.get_user(request)
        return web.json_response({
            "name": release_info['name'],
            "version": release_info['version'],
            "bot_user": str(self.dyphanbot.user) if self.dyphanbot.user else None,
            "authenticated_user": user.to_json() if user else None
        })
    
    async def oauth(self, request):
        """ Responds with an oauth url for authentication if the user is not logged in """
        redirect_uri = request.url.query.get('redirect_uri')
        session = await get_session(request)
        user = session.get('user')
        if not user:
            auth_client = self.api_client.discord_oauth
            auth_client.params['redirect_uri'] = redirect_uri or str(request.url.with_query(''))
            
            if auth_client.shared_key not in request.url.query:
                return web.json_response({
                    "is_authorized": False,
                    "oauth_url": auth_client.get_authorize_url(
                        scope="identify email guilds"
                    )
                })

            otoken, _ = await auth_client.get_access_token(request.url.query)
            auth_client.access_token = otoken

            _, user = await auth_client.user_info()
            session['user'] = user
        
        return web.json_response({
            "is_authorized": True,
            "user_info": user
        })
    
    async def list_plugins(self, request):
        """ Responds with a list of loaded plugins """
        plugins = self.dyphanbot.pluginloader.get_plugins()
        plugin_list = [plugin_name.lower() for plugin_name in plugins.keys()]
        return web.json_response({
            "plugins": plugin_list
        })
    
    async def list_commands(self, request):
        commands = self.dyphanbot.commands
        user = await self.api_client.get_user(request)
        listing = {}

        for cmd_name, cmd_func in commands.items():
            plugin = cmd_func.__dict__.get('plugin')
            pname  = type(plugin).__name__ if plugin else "(etc)"

            if not listing.get(pname):
                phelp  = await plugin.help(None, [pname]) if plugin else {}
                listing[pname] = {
                    "title": phelp.get("title"),
                    "shorthelp": phelp.get("shorthelp"),
                    "commands": {}
                }
            
            cmd_botmaster = cmd_func.__dict__.get('botmaster')
            cmd_gperms = cmd_func.__dict__.get('guild_perms')

            if not user and (cmd_gperms or cmd_botmaster):
                continue

            if user and cmd_botmaster and not user.bot_master:
                continue

            listing[pname]["commands"][cmd_name] = {
                "guild_permissions": cmd_gperms
            }

            if user and user.bot_master:
                listing[pname]["commands"][cmd_name]["botmaster"] = cmd_botmaster
        
        return web.json_response(listing)

    async def list_guilds(self, request):
        await self.api_client.require_auth(request)
        returned = {}
        for func in [self.mutual_guilds, self.bot_guilds, self.user_guilds]:
            try:
                resp = await func(request)
                returned[func.__name__] = json.loads(resp.text)[func.__name__]
            except Exception:
                pass
        return web.json_response(returned)

    async def mutual_guilds(self, request):
        user = await self.api_client.require_auth(request)
        mutual_guilds = []
        for guild in user.mutual_guilds:
            guild_dict = {}
            for k in ['id', 'name', 'description', '_icon', 'features',
                      'owner_id', 'preferred_locale', 'unavailable', '_large']:
                k = k.strip('_')
                guild_dict[k] = getattr(guild, k)
            member = guild.get_member(user.id)
            guild_dict['permissions_bot'] = guild.me.guild_permissions.value
            guild_dict['permissions_user'] = member.guild_permissions.value
            guild_dict['owner'] = str(guild.owner_id) == str(member.id)
            mutual_guilds.append(guild_dict)
        return web.json_response({
            "mutual_guilds": mutual_guilds
        })

    async def bot_guilds(self, request):
        user = await self.api_client.require_perm(request, "botmaster")
        bot_guilds = []
        for guild in self.dyphanbot.guilds:
            guild_dict = {}
            for k in ['id', 'name', 'description', '_icon', 'features',
                      'owner_id', 'preferred_locale', 'unavailable', '_large']:
                k = k.strip('_')
                guild_dict[k] = getattr(guild, k)
            guild_dict['permissions'] = guild.me.guild_permissions.value
            bot_guilds.append(guild_dict)
        return web.json_response({
            "bot_guilds": bot_guilds
        })

    async def user_guilds(self, request):
        auth_client = self.api_client.discord_oauth
        user = await self.api_client.require_auth(request)
        guilds = await auth_client.request('GET', 'users/@me/guilds')
        return web.json_response({
            "user_guilds": guilds
        })
