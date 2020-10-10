""" This module contains the PluginLoader class responsible for loading plugins. """

import os
import glob
import logging
import functools
import importlib.util

from dyphanbot.constants import PLUGIN_DIRS

class Plugin(object):
    """ Superclass for DyphanBot plugins. """

    def __init__(self, dyphanbot):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.dyphanbot = dyphanbot

        self.logger.info("Initialized plugin: %s", self.__class__.__name__)
        self.start()

    def start(self):
        pass

    def load_json(self, filename, initial_data={}, save_json=None, **kwargs):
        return self.dyphanbot.data.load_json(os.path.join(self.__class__.__name__, filename), initial_data, save_json, **kwargs)

    def save_json(self, filename, data, **kwargs):
        return self.dyphanbot.data.save_json(os.path.join(self.__class__.__name__, filename), data, **kwargs)
    
    def get_local_prefix(self, message):
        return self.dyphanbot.bot_controller._get_prefix(message.guild) or "{} ".format(self.dyphanbot.bot_mention(message))
    
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
    """ Provides methods to help load plugins.

    Args:
        dyphanbot (:obj:`dyphanbot.DyphanBot`):
            The main DyphanBot object.

    """

    def __init__(self, dyphanbot, disabled_plugins=[], user_plugin_dirs=[]):
        self.logger = logging.getLogger(__name__)
        self.dyphanbot = dyphanbot
        self.disabled_plugins = disabled_plugins
        self.plugin_dirs = PLUGIN_DIRS + [os.path.expanduser(pdirs) for pdirs in user_plugin_dirs]
        self.plugins = {}

    def init_plugins(self):
        plugins = Plugin.__subclasses__()
        self.logger.debug("Found %d subclassed plugins: %s", len(plugins), plugins)
        for plugin in plugins:
            try:
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
                self.plugins[plugin.__name__] = plugin_obj
            except Exception as err:
                self.logger.warning("Unable to load plugin '%s': %s", plugin.__name__, err)
                raise

        if hasattr(self, 'subclassed_or_not_real_plugins'):
            del self.subclassed_or_not_real_plugins # delet dis

    def load_plugins(self):
        """ Loads and initializes each plugin in the plugin directories. """
        self.logger.debug("Searching %d plugin directories: %s", len(self.plugin_dirs), self.plugin_dirs)
        for directory in self.plugin_dirs:
            if not os.path.isdir(directory):
                continue

            self.load_plugin_from_directory(directory)
        self.init_plugins()

    def load_plugin_from_directory(self, directory):
        """ Loads and initializes each plugin in the argument directory.

        Args:
            directory (str): The directory to load from.

        """
        directory = os.path.join(directory, '**', '[!_]*.py')
        for plugin_path in glob.glob(directory, recursive=True):
            self.load_plugin_from_path(plugin_path)

    def load_plugin_from_path(self, path):
        """ Loads and initializes each plugin from its path.

        Args:
            path (str): The path to the plugin's python file.

        """
        name = os.path.splitext(os.path.basename(path))[0]
        if name in self.disabled_plugins:
            self.logger.info("Skipped disabled plugin: %s", name)
            return
        try:
            plugin = import_file(path)
            if getattr(plugin, "plugin_init", None):
                plugin.plugin_init(self.dyphanbot)
                self.plugins[name] = plugin
                self.logger.info("Loaded plugin: %s", name)
            else:
                # this is really dumb, but it's the only way I can get it to
                # work with subclassed plugins for some reason...
                if not hasattr(self, 'subclassed_or_not_real_plugins'):
                    self.subclassed_or_not_real_plugins = {}
                self.subclassed_or_not_real_plugins[name] = plugin
        except Exception as err:
            self.logger.warning("Unable to load plugin '%s': %s", name, err)
            raise

    def get_plugins(self):
        """ Returns the loaded plugins.

        Returns:
            dict: The loaded plugin objects.

        """
        return self.plugins

def import_file(path):
    """ Imports a python file from the path in the argument.

    Args:
        path (str): The path to the python file to be imported.

    Returns:
        The imported file as a module.

    """
    filename = os.path.splitext(os.path.basename(path))[0]
    spec = importlib.util.spec_from_file_location(filename, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
