""" This module contains the PluginLoader class responsible for loading plugins. """

import os
import sys
import glob
import logging
import functools
import importlib.util

from importlib.machinery import PathFinder

from aiohttp import web

from dyphanbot.constants import PLUGIN_DIRS

class Plugin(object):
    """ Superclass for DyphanBot plugins; plugins should subclass from this

    Attributes:
        dyphanbot (:obj:`dyphanbot.DyphanBot`): The main DyphanBot object
        intents (:obj:`discord.Intents`): The intents the bot has access to
    
    Args:
        dyphanbot (:obj:`dyphanbot.DyphanBot`): The main DyphanBot object
    
    """

    def __init__(self, dyphanbot):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.dyphanbot = dyphanbot
        self.intents = self.dyphanbot._intents

        self.logger.info("Initialized plugin: %s", self.name)
        self.start()
    
    @property
    def name(self):
        "str: Gets the plugin's name (defaults to class name if not overridden)"
        return self.__class__.__name__

    def start(self):
        """ Called after main init. Override this instead of `__init__`
            when subclassing.
        """
        pass

    def load_json(self, filename, initial_data={}, save_json=None, **kwargs):
        """ Loads JSON file as an object from the plugin's own data directory

        This simply calls the `DataManager.load_json()` method passing the
        plugin's data directory as a parent to the `filename`. If no file with
        that filename is found in this directory, it will automatically create
        a new one initialized with `initial_data` through `save_json` handler,
        or the default `DataManager.save_json()` if `save_json=None`.

        `**kwargs` are passed to the internal `json.load()` function for
        extra control.

        Args:
            filename (str): The filename found in the plugin's data directory
            initial_data (dict, optional): The default data to initialize a new
                json file with if none was found. Defaults to {}.
            save_json (func, optional): A optional save handler used to save a
                new json file if none was found. Defaults to built-in method.

        Returns:
            The loaded JSON data as a Python object.
        
        """
        return self.dyphanbot.data.load_json(os.path.join(self.__class__.__name__, filename), initial_data, save_json, **kwargs)

    def save_json(self, filename, data, **kwargs):
        """ Save `data` dict as a JSON file to the plugin's own data directory

        `**kwargs` are passed to the internal `json.dump()` function for
        extra control.

        Args:
            filename (str): The filename to save as
            data: The data object to save

        Returns:
            The saved data object
        
        """
        return self.dyphanbot.data.save_json(os.path.join(self.__class__.__name__, filename), data, **kwargs)
    
    def get_local_prefix(self, message):
        """ Returns the prefix for the guild if assigned, otherwise, returns
            the bot mention
        """
        default = "{} ".format(self.dyphanbot.bot_mention(message))
        if not message:
            return default
        return self.dyphanbot.bot_controller._get_prefix(message.guild) or default
    
    async def help(self, message, args):
        """ Overridable help method for plugins.
        
        Args:
            args (:obj:`list` of :obj:`str`): An optional list of arguments
                passed to the help command.

        Returns:
            A dictionary consisting of:
                - title:    A friendly title for the plugin. Optional, but
                            generally recomended.
                - helptext: A general description of the plugin. Translates to
                            an embed description upon parsing.
                - sections: Various optional sections that describe different
                            parts of the plugin. Translates to an embed's field
                            list. (optional)
                - color:    The color of the embed (defaults to the "blurple"
                            color: #7289DA/7506394).
                - unlisted: Whether the plugin should be listed upon calling
                            the `plugins` command (defaults to `False` if this
                            method is overridden).
        
        """
        return {
            "helptext": "No help provided... :c",
            "unlisted": True
        }

    @staticmethod
    def endpoint(handler=None, *, endpoint, method='GET'):
        """ Handles API requests to a certain endpoint of a plugin """
        if not handler:
            return functools.partial(Plugin.endpoint, endpoint=endpoint, method=method)

        assert not handler.__name__.startswith('_'), "Handlers must be public"
        handler.__dict__['endpoint_handler'] = True
        handler.__dict__['endpoint'] = endpoint
        handler.__dict__['method'] = method
        return handler
    
    @staticmethod
    def websocket(handler):
        """ Handles websocket connections for a plugin """
        assert not handler.__name__.startswith('_'), "Handlers must be public"
        handler.__dict__['websocket_handler'] = True
        return handler

    @staticmethod
    def event(handler):
        assert not handler.__name__.startswith('_'), "Handlers must be public"
        handler.__dict__['event_handler'] = True
        return handler

    @staticmethod
    def on_ready(handler):
        assert not handler.__name__.startswith('_'), "Handlers must be public"
        handler.__dict__['ready_handler'] = True
        return handler
    
    @staticmethod
    def on_member_join(handler):
        assert not handler.__name__.startswith('_'), "Handlers must be public"
        handler.__dict__['mjoin_handler'] = True

        return handler

    @staticmethod
    def command(handler=None, *, cmd=None, botmaster=False, perms=[]):
        if not handler:
            return functools.partial(Plugin.command, cmd=cmd, botmaster=botmaster, perms=perms)

        if not cmd:
            cmd = handler.__name__

        assert not handler.__name__.startswith('_'), "Handlers must be public"
        handler.__dict__['command'] = cmd
        handler.__dict__['botmaster'] = botmaster
        handler.__dict__['guild_perms'] = perms

        return handler

    @staticmethod
    def on_message(handler=None, *, raw=False):
        if not handler:
            return functools.partial(Plugin.on_message, raw=raw)

        assert not handler.__name__.startswith('_'), "Handlers must be public"
        handler.__dict__['msg_handler'] = True
        handler.__dict__['raw'] = raw

        return handler

class PluginLoader(object):
    """ Handles the loading and importing of plugins from each directory

    Attributes:
        dyphanbot (:obj:`dyphanbot.DyphanBot`): The main DyphanBot object
        disabled_plugins (:obj:`list` of :obj:`str`): A list of plugin names
            to disable
        plugin_dirs (:obj:`list` of :obj:`str`): A list of paths to
            plugin directories
        dev_mode (bool): If true, raises a plugin exception, otherwise skip it
    
    Args:
        dyphanbot (:obj:`dyphanbot.DyphanBot`): The main DyphanBot object
        disabled_plugins (:obj:`list` of :obj:`str`): A list of plugin names
            to disable
        user_plugin_dirs (:obj:`list` of :obj:`str`): A list of user-defined
            paths to plugin directories (appended to built-in paths)
        dev_mode (bool): If true, raises a plugin exception, otherwise skip it

    """

    def __init__(self, dyphanbot, disabled_plugins=[], user_plugin_dirs=[], dev_mode=False):
        self.logger = logging.getLogger(__name__)
        self.dyphanbot = dyphanbot
        self.disabled_plugins = disabled_plugins
        self.dev_mode = dev_mode

        self.plugin_dirs = PLUGIN_DIRS + [os.path.expanduser(pdirs) for pdirs in user_plugin_dirs]
        self.plugin_dirs.append(os.path.join(self.dyphanbot.data.data_dir, "plugins"))

        self.plugins = {}

    def init_plugins(self):
        """ Initializes subclassed plugins and registers them """
        plugins = Plugin.__subclasses__()
        self.logger.debug("Found %d subclassed plugins: %s", len(plugins),
                          ", ".join([x.__name__ for x in plugins]))
        for plugin in plugins:
            try:
                plogger = logging.getLogger(plugin.__name__)
                plugin_app = web.Application(logger=plogger)
                plugin_obj = plugin(self.dyphanbot)
                for name, method in plugin_obj.__class__.__dict__.items():
                    real_method = getattr(plugin_obj, name, None)
                    if not real_method or not callable(real_method):
                        continue
                    if hasattr(method, "ready_handler"):
                        self.dyphanbot.add_ready_handler(real_method)
                    elif hasattr(method, "mjoin_handler"):
                        self.dyphanbot.add_mjoin_handler(real_method)
                    elif hasattr(method, "command"):
                        self.dyphanbot.add_command_handler(
                            real_method.command, real_method,
                            permissions={
                                "botmaster": real_method.botmaster,
                                "guild_perms": real_method.guild_perms
                            },
                            plugin=plugin_obj
                        )
                    elif hasattr(method, "msg_handler") and hasattr(method, "raw"):
                        self.dyphanbot.add_message_handler(real_method, real_method.raw)
                    elif hasattr(method, "event_handler"):
                        real_method = self.dyphanbot.event(real_method)
                    elif hasattr(method, "endpoint_handler"):
                        plugin_app.router.add_route(
                            real_method.method, real_method.endpoint, real_method)
                self.dyphanbot.web_api.register_plugin(plugin.__name__, plugin_app)
                self.plugins[plugin.__name__] = plugin_obj
            except Exception as err:
                self.logger.warning("Unable to load plugin '%s': %s", plugin.__name__, err)
                if self.dev_mode:
                    raise

    def load_plugins(self):
        """ Iterates through each plugin directory and loads plugins from
            each directory, then initializes subclassed plugins
        """
        self.logger.debug("Searching %d plugin directories: %s", len(self.plugin_dirs), self.plugin_dirs)
        for directory in self.plugin_dirs:
            if not os.path.isdir(directory):
                continue

            self.load_plugins_from_directory(directory)
        self.init_plugins()

    def load_plugins_from_directory(self, directory, rpaths=[]):
        """ Recursively finds and loads each plugin module in the given
            directory

        Args:
            directory (str): The directory to load from.
            rpaths (:obj:`list`, optional): Recursive; A list of additional
                paths to recursively search plugins in.
        
        """
        directory = os.path.join(directory, '[!_.]*[!_.]')
        for plugin_path in glob.glob(directory, recursive=True):
            if os.path.isdir(plugin_path) and not os.path.isfile(os.path.join(plugin_path, "__init__.py")):
                # if plugin_path is a directory & it's not a package,
                # recursively load plugins from that directory
                rpaths.append(plugin_path)
                self.load_plugins_from_directory(plugin_path, rpaths)
                continue
            
            basename = os.path.basename(plugin_path)
            if '.' in basename and not basename.endswith('.py'):
                # skip non-python filenames
                continue
            basename = basename.split('.')[0]
            if not basename.strip():
                continue
            self.load_plugin(basename, rpaths)
    
    def load_plugin(self, name, additional_paths=[]):
        """ Imports and loads a plugin by name

        Disabled plugins are skipped and legacy plugins are initialized here.
        If the plugin is not a legacy plugin, this method just acts as a
        wrapper around `PluginLoader.import_plugin()`. If `dev_mode` is enabled
        and an exception was thrown, this raises the exception instead of
        skipping it with a warning (useful when developing plugins).

        Args:
            name (str): The name of the plugin's module to be loaded
            additional_paths (:obj:`list`, optional): Additional paths to
                search for the plugin in
        
        """
        if name in self.disabled_plugins:
            self.logger.info("Skipped disabled plugin: %s", name)
            return
        try:
            plugin = self.import_plugin(name, additional_paths)
            plogger = logging.getLogger(plugin.__name__)
            if getattr(plugin, "plugin_init", None):
                plogger.warn("The `plugin_init` hook is deprecated. Subclass from `Plugin` instead.")
                plugin.name = name
                plugin.plugin_init(self.dyphanbot)
                self.plugins[name] = plugin
                plogger.info("Loaded legacy plugin: %s", name)
        except Exception as err:
            self.logger.warning("Unable to load plugin '%s': %s", name, err)
            if self.dev_mode:
                raise
    
    def import_plugin(self, name, additional_paths=[]):
        """ Mimics Python's import mechanism to import plugins found in the
            specified plugin directories; returns the imported plugin module
        
        Args:
            name (str): The name of the plugin's module to be imported
            additional_paths (:obj:`list`, optional): Additional paths to
                search for the plugin in
        
        Returns:
            ModuleType: The imported plugin's module
        
        Raises:
            ImportError: If the name cannot be resolved without a package
                (e.g. a relative import)
            ModuleNotFoundError: If the name cannot be found in any of the
                searched directories.
        
        """
        try:
            abs_name = importlib.util.resolve_name(name, None)
        except ImportError:
            raise ImportError(f'Invalid plugin name {name!r}')

        try:
            # if the plugin is already loaded, return it
            return self.plugins[abs_name]
        except KeyError:
            pass
        
        try:
            # if the plugin is already imported, return it
            return sys.modules[abs_name]
        except KeyError:
            pass
        
        search_paths = list(set(self.plugin_dirs + additional_paths))
        spec = PathFinder.find_spec(abs_name, search_paths)
        if not spec:
            raise ModuleNotFoundError(f'No plugin named {abs_name!r}',
                                      name=abs_name)
        
        module = importlib.util.module_from_spec(spec)
        sys.modules[abs_name] = module
        spec.loader.exec_module(module)
        self.logger.debug("Imported plugin: %s", abs_name)
        return module

    def get_plugins(self):
        """ Returns the currently loaded plugins.

        Returns:
            dict: A key-value pair containing each plugin's name and its
                associated object

        """
        return self.plugins
