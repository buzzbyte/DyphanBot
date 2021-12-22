import asyncio
import logging
import base64

from cryptography import fernet
from aiohttp import web, WSCloseCode
from aioauth_client import DiscordClient as DiscordOAuthClient
from aiohttp_session import setup as setup_session, get_session
from aiohttp_session.cookie_storage import EncryptedCookieStorage
import discord

from . import routes

class APIUser(discord.User):
    """ Represents the authenticated user """
    __slots__ = ('_data', '_dyphanbot', 'name', 'id', 'discriminator',
                 '_avatar', 'bot', 'system', '_public_flags', '_state',
                 'locale', '_flags', 'verified', 'mfa_enabled', 'email',
                 'premium_type', 'bot_master')

    def __init__(self, client, data):
        self._data = data
        self._dyphanbot = client
        super().__init__(state=client._connection, data=data)

    def __repr__(self):
        return (
            f'<APIUser id={self.id} name={self.name!r} discriminator={self.discriminator!r}'
            f' verified={self.verified} mfa_enabled={self.mfa_enabled} email={self.email}'
            f' premium_type={self.premium_type} bot_master={self.bot_master}>'
        )

    def _update(self, data):
        super()._update(data)
        self.verified = data.get('verified', False)
        self.locale = data.get('locale')
        self._flags = data.get('flags', 0)
        self.mfa_enabled = data.get('mfa_enabled', False)
        self.email = data.get('email')
        self.premium_type = data.get('premium_type', 0)
        self.bot_master = self.is_botmaster()
    
    def to_json(self):
        """ Return the original JSON-formated dict of this object """
        return {
            **self._data,
            "bot_master": self.bot_master
        }
    
    def is_botmaster(self):
        """ Returns True if this user is a botmaster, False otherwise """
        return self._dyphanbot.is_botmaster(self)

class WebAPI(object):
    """ Main class for API server """

    logger = logging.getLogger(__name__)
    
    def __init__(self, dyphanbot, config={}):
        self._disabled = False
        self.dyphanbot = dyphanbot
        self.config = config

        self.plugin_subapps = {}

        if not self._check_config():
            self._disabled = True
            return
        
        self.discord_oauth = DiscordOAuthClient(
            client_id=config.get("discord_client_id"),
            client_secret=config.get("discord_client_secret")
        )

        self.api_router = routes.APIRouter(dyphanbot, self)
    
    def _check_config(self):
        """ Validates that the API is properly configured. """
        if not self.config:
            self.logger.warn("Web API is not configured! Will be disabled.")
            return False
        
        required_keys = ["discord_client_id", "discord_client_secret"]
        if not all(key in self.config for key in required_keys):
            self.logger.warn(
                "Web API requires further configuration. "
                "'discord_client_id' and 'discord_client_secret' are required "
                "for API authentication."
            )
            return False
        return True

    def register_plugin(self, plugin_name, app):
        """ Resgisters plugin as a subapp """
        self.plugin_subapps[plugin_name] = app
    
    async def get_user(self, request):
        session = await get_session(request)
        user = session.get('user')
        if user:
            return APIUser(self.dyphanbot, user)
    
    async def user_in_guild(self, user_id, guild_id):
        guild = self.dyphanbot.get_guild(guild_id)
        if guild:
            return guild.get_member(user_id)
        return None

    async def require_auth(self, request):
        user = await self.get_user(request)
        if not user:
            raise web.HTTPUnauthorized()
        return user
    
    async def require_perm(self, request, context, guild_permissions=None, guild_id=None):
        assert context in ['botmaster', 'guild'], "'context' must be either 'botmaster' or 'guild'"
        user = await self.require_auth(request)
        if context == "botmaster":
            if not self.dyphanbot.is_botmaster(user):
                raise web.HTTPForbidden()
        elif context == "guild":
            assert guild_permissions is not None and guild_id is not None, "'guild' context requires 'guild_permissions' and 'guild_id'"
            member = self.user_in_guild(user.id, guild_id)
            if not member:
                raise web.HTTPForbidden()
            member_perms = member.guild_permissions
            for perm in guild_permissions:
                if not getattr(member_perms, perm):
                    raise web.HTTPForbidden()

    async def on_shutdown(self, app):
        """ Called on server shutdown. Gracefully closes all current websockets. """
        self.logger.info("Shutting down API server...")
        for ws in set(app.get('websockets', [])):
            await ws.close(code=WSCloseCode.GOING_AWAY,
                           message="Server shutdown: Closing websockets.")
    
    async def _run(self, app, host, port):
        try:
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, host, port)
            await site.start()
        except (web.GracefulExit, KeyboardInterrupt):
            await runner.cleanup()
    
    def error_middleware(self):
        """ Middleware to handle HTTP errors """
        @web.middleware
        async def middleware(request, handler):
            try:
                return await handler(request)
            except web.HTTPException as err:
                return web.json_response({
                    "error": {
                        "status_code": err.status_code,
                        "reason": err.reason,
                        "text": err.text
                    }
                })
        return middleware

    def start_server(self):
        """ Asynchronously runs the API server using the main event loop """
        if self._disabled:
            return
        
        host = self.config.get('host', "127.0.0.1")
        port = self.config.get('port', "3580")
        
        loop = self.dyphanbot.loop or asyncio.get_event_loop()

        app = web.Application(logger=self.logger, middlewares=[self.error_middleware()])
        fernet_key = fernet.Fernet.generate_key()
        secret_key = base64.urlsafe_b64decode(fernet_key)
        setup_session(app, EncryptedCookieStorage(secret_key))
        app.add_routes(self.api_router.get_routes())
        app.on_shutdown.append(self.on_shutdown)

        # register all plugin subapps
        for plugin_name, plugin_app in self.plugin_subapps.items():
            app.add_subapp(f"/plugin/{plugin_name.lower()}/", plugin_app)

        loop.create_task(self._run(app, host, port))
        self.logger.info(f"Web API server now listening at {host}:{port}")