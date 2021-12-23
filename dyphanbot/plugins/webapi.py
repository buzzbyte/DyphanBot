import os
import json
import logging
import asyncio
import websockets
from requests_oauthlib import OAuth2Session

import discord

API_BASE_URL = "https://discordapp.com/api"
TOKEN_URL = API_BASE_URL + "/oauth2/token"

class WebAPI(object):
    """docstring for WebAPI."""

    def __init__(self, dyphanbot):
        self.dyphanbot = dyphanbot

    async def _require_params(self, ws, expected, actual):
        for param in expected:
            if param not in actual:
                await ws.send_error("Required parameter missing: '{}'".format(param))
                return False
        return True

    def _get_channel(self, channel_id):
        return self.dyphanbot.get_channel(channel_id)

    def _get_guild(self, guild_id):
        return self.dyphanbot.get_guild(guild_id)

    def _can_access_channel(self, channel_id):
        channel = self._get_channel(channel_id)
        return channel.permissions_for(self.dyphanbot.user).send_messages

    async def _is_user_bot_master(self, ws, session):
        bot_masters = self.dyphanbot.get_bot_masters()
        user = await self.user(ws, session)
        return user['id'] in bot_masters

    async def _is_user_in_guild(self, ws, session, guild_id):
        bot_masters = self.dyphanbot.get_bot_masters()
        guilds = await self.guilds(ws, session)
        for guild in guilds:
            if guild_id in guild['id']:
                return True
        return False

    async def default(self, ws, session, params={}):
        return ws._error_dict("Unknown action")

    async def user(self, ws, session, params={}):
        return { "status": "success", "user": session.get(API_BASE_URL + '/users/@me').json() }

    async def guilds(self, ws, session, params={}):
        return { "status": "success", "user_guilds": session.get(API_BASE_URL + '/users/@me/guilds').json() }

    async def connections(self, ws, session, params={}):
        return { "status": "success", "user_connections": session.get(API_BASE_URL + '/users/@me/connections').json() }
    
    async def bot_info(self, ws, session, params={}):
        botuser = self.dyphanbot.user
        return {"status": "success", "bot_info": {
            "id": str(botuser.id),
            "name": botuser.name,
            "discriminator": botuser.discriminator,
            "display_name": botuser.display_name,
            "avatar": botuser.avatar,
            "avatar_url": str(botuser.avatar.url),
            "color": str(botuser.color),
            "bot": botuser.bot
        }}
    
    async def shared_guilds(self, ws, session, params={}):
        user_guilds = await self.guilds(ws, session)
        bot_guilds = [str(x.id) for x in self.dyphanbot.guilds]
        shared_guilds = []
        for uguild in user_guilds:
            if str(uguild.get("id")) in bot_guilds:
                shared_guilds.append({
                    "features": uguild.get("features"),
                    "name": uguild.get("name"),
                    "owner": uguild.get("owner"),
                    "icon": uguild.get("icon"),
                    "id": str(uguild.get("id")),
                    "user_permissions": str(uguild.get("permissions")),
                    "bot_permissions": str(self.dyphanbot.get_guild(int(uguild.get("id"))).me.guild_permissions.value)
                })
        return { "status": "success", "shared_guilds": shared_guilds }

    async def bot_guilds(self, ws, session, params={}):
        if not await self._is_user_bot_master(ws, session):
            return ws._error_dict("Not logged in as a bot master.")
        bot_guilds = []
        for guild in self.dyphanbot.guilds:
            bot_guilds.append({
                "features": guild.features,
                "name": guild.name,
                "owner_id": str(guild.owner.id),
                "icon": guild.icon,
                "id": str(guild.id),
                "permissions": str(guild.me.guild_permissions.value)
            })
        return { "status": "success", "bot_guilds": bot_guilds }
    
    async def get_plugins(self, ws, session, params={}):
        if not await self._is_user_bot_master(ws, session):
            return ws._error_dict("Not logged in as a bot master.")
        pluginlist = self.dyphanbot.pluginloader.get_plugins().keys()
        return { "status": "success", "plugins": list(pluginlist) }
    
    async def get_plugin(self, ws, session, params):
        if not await self._is_user_bot_master(ws, session):
            return ws._error_dict("Not logged in as a bot master.")
        if not await self._require_params(ws, ['plugin'], params):
            return
        plugin = self.dyphanbot.pluginloader.get_plugins().get(params["plugin"])
        if not plugin:
            return ws._error_dict("Plugin does not exist.")
        return { "status": "success", "plugin": dir(plugin) }
    
    async def guild_settings(self, ws, session, params):
        if not await self._require_params(ws, ['guild_id'], params):
            return
        shared_guilds = await self.shared_guilds(ws,session)
        if params["guild_id"] not in [x["id"] for x in shared_guilds.get("shared_guilds", [])] and not await self._is_user_bot_master(ws, session):
            return ws._error_dict("Not logged in as a bot master.")
        guild_settings = self.dyphanbot.bot_controller._get_settings_for_guild(self.dyphanbot.get_guild(int(params["guild_id"])))
        if not guild_settings:
            return ws._error_dict("No settings found for this guild.")
        return { "status": "success", "guild_settings": guild_settings }

    async def send_message(self, ws, session, params):
        if not await self._require_params(ws, ['channel_id', 'message'], params):
            return
        if not await self._is_user_bot_master(ws, session):
            return ws._error_dict("Not logged in as a bot master.")
        channel_id = int(params['channel_id'])
        if "guild_id" in params:
            guild_id = int(params['guild_id'])
            guild = self.dyphanbot.get_guild(guild_id)
            if not guild:
                return ws._error_dict("Cannot find guild")
            channel = guild.get_channel(channel_id)
        else:
            channel = self.dyphanbot.get_channel(channel_id)
        if not channel:
            return ws._error_dict("Cannot find channel")
        await channel.send(params['message'])
        return { "status": "success" }

    async def send_voice(self, ws, session, params):
        if not await self._require_params(ws, ['guild_id', 'audio_url'], params):
            return
        if not await self._is_user_bot_master(ws, session):
            return ws._error_dict("Not logged in as a bot master.")
        guild_id = int(params['guild_id'])
        guild = self.dyphanbot.get_guild(guild_id)
        if not guild:
            return ws._error_dict("Cannot find guild")
        if not guild.voice_client:
            return ws._error_dict("Not connected to voice")
        guild.voice_client.play(discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(params['audio_url'])))
        return { "status": "success" }

    async def control_voice(self, ws, session, params):
        if not await self._require_params(ws, ['guild_id', 'action'], params):
            return
        if not await self._is_user_in_guild(ws, session, params['guild_id']):
            return ws._error_dict("User not in guild")
        if params['action'] not in ['play', 'pause', 'stop', 'get']:
            return ws._error_dict("Unknown playback action")
        guild_id = int(params['guild_id'])
        guild = self.dyphanbot.get_guild(guild_id)
        if not guild:
            return ws._error_dict("Cannot find guild")
        if not guild.voice_client:
            return ws._error_dict("Not connected to voice")
        action = params['action']
        if action in "play":
            if guild.voice_client.is_paused():
                guild.voice_client.resume()
        elif action in "pause":
            if guild.voice_client.is_playing() and not guild.voice_client.is_paused():
                guild.voice_client.pause()
        elif action in "stop":
            guild.voice_client.stop()
        elif action in "get":
            if guild.voice_client.source:
                title = guild.voice_client.source.title if "YTDLSource" in guild.voice_client.source.__class__.__name__ else "Untitled"
                return { "status": "success", "title": title, "is_playing": guild.voice_client.is_playing() }
        else:
            return ws._error_dict("Unimplemented")
        return { "status": "success" }

class DyBotServerProtocol(websockets.server.WebSocketServerProtocol):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(__name__)

    async def recv(self):
        data = await super().recv()
        self.logger.info("Received raw data: %s", data)
        try:
            data = json.loads(data)
        except json.JSONDecodeError as e:
            await self.send_error("Received invalid JSON data", e)
            return

        return data

    async def send(self, data):
        self.logger.info("Send: %s", data)
        data = json.dumps(data)
        await super().send(data)

    async def send_error(self, message=None, exception=None):
        error_response = self._error_dict(message, exception)
        await self.send(error_response)

    def _error_dict(self, message=None, exception=None):
        error_response = {
            "status": "failure",
            "error": message,
            "exception": {
                "type": type(exception).__name__,
                "message": str(exception)
            } if exception else None
        }

        return error_response

class DyBotServer(object):
    def __init__(self, dyphanbot):
        self.logger = logging.getLogger(__name__)
        self.dyphanbot = dyphanbot
        self.webapi = WebAPI(self.dyphanbot)
        self.config_fn = "wsconf.json"
        self.initial_config = {
            "host": "127.0.0.1",
            "port": 8888,
            "oauth": {
                "client_id": "_DISCORD_CLIENT_ID_",
                "client_secret": "_DISCORD_CLIENT_SECRET_"
            }
        }

        self.config = self.load_config()
        self.host = self.config['host']
        self.port = self.config['port']

    def run(self):
        if ('host' and 'port' and 'oauth') not in self.config:
            self.logger.error(
                "Websocket config (loacated at '%s') is missing required keys (needs to have 'host', 'port', and 'oauth').",
                os.path.join(self.dyphanbot.data.data_dir, self.config_fn)
            )
            return
        if self.config['oauth'] == self.initial_config['oauth']:
            self.logger.error(
                "OAuth settings are not configured yet. Please configure them in the websocket config located at '%s'",
                os.path.join(self.dyphanbot.data.data_dir, self.config_fn)
            )
            return

        host_fmt = "{0}://{1}"
        hostport_fmt = "{0}://{1}:{2}"
        origins = [
            host_fmt.format('http', 'localhost'),
            hostport_fmt.format('http', 'localhost', 5000),
            host_fmt.format('http', self.host),
            host_fmt.format('https', self.host),
            hostport_fmt.format('http', self.host, self.port),
            hostport_fmt.format('https', self.host, self.port),
            hostport_fmt.format('http', self.host, 5000),
            hostport_fmt.format('https', self.host, 5000)
        ]

        loop = self.dyphanbot.loop
        server = websockets.serve(self.handler, host=self.host, port=self.port,
                                  create_protocol=DyBotServerProtocol, origins=origins)
        loop.run_until_complete(server)
        self.logger.info("Running DyBotServer on %s port %s", self.host, self.port)

    async def process_action(self, ws, session, action, params):
        if not action.startswith('_'):
            res = await getattr(self.webapi, action, self.webapi.default)(ws, session, params)
        else:
            res = await self.webapi.default(ws, session)
        if res:
            try:
                await ws.send(res)
            except Exception as e:
                await ws.send_error(exception=e)

    async def handler(self, ws, uri):
        async for data in ws:
            self.logger.info("Receive: `%s` from %s", data, uri)
            if not data:
                continue
            if "test" in data:
                await ws.send({ "status": "success", "received": data['test'] });
                continue
            if "auth_token" not in data:
                await ws.send_error("Authentication Error: Missing OAuth token.")
            else:
                session = self.get_discord_auth(token=data['auth_token'])
                action = data["action"] if "action" in data else "user"
                params = data["params"] if "params" in data else {}
                await self.process_action(ws, session, action, params)

    def get_discord_auth(self, token=None, state=None, scope=None):
        return OAuth2Session(
            client_id=self.config['oauth']['client_id'] or str(self.dyphanbot.user.id),
            token=token,
            state=state,
            scope=scope,
            auto_refresh_kwargs={
                'client_id': self.config['oauth']['client_id'] or str(self.dyphanbot.user.id),
                'client_secret': self.config['oauth']['client_secret'],
            },
            auto_refresh_url=TOKEN_URL
        )

    def _save_config(self, fn, data):
        return self.dyphanbot.data.save_json(self.config_fn, data, indent=4)

    def load_config(self):
        return self.dyphanbot.data.load_json(self.config_fn, self.initial_config, self._save_config)

def plugin_init(dyphanbot):
    # Not ready for that just yet...
    #dybotserver = DyBotServer(dyphanbot)
    #dybotserver.run()
    pass
