""" This module contains the PluginLoader class responsible for loading plugins. """

import os
import glob
import logging
import importlib.util

from dyphanbot.constants import PLUGIN_DIRS

class PluginLoader(object):
    """ Provides methods to help load plugins.

    Args:
        dyphanbot (:obj:`dyphanbot.DyphanBot`):
            The main DyphanBot object.

    """

    def __init__(self, dyphanbot):
        self.logger = logging.getLogger(__name__)
        self.dyphanbot = dyphanbot
        self.plugins = {}

    def load_plugins(self):
        """ Loads and initializes each plugin in the plugin directories. """
        for directory in PLUGIN_DIRS:
            if not os.path.isdir(directory):
                continue

            self.load_plugin_from_directory(directory)

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
        try:
            plugin = import_file(path)
            if getattr(plugin, "plugin_init", None):
                plugin.plugin_init(self.dyphanbot)
                self.plugins[name] = plugin
                self.logger.info("Loaded plugin: %s", name)
        #except (ImportError, SyntaxError, NameError) as err:
            #self.logger.warning("Unable to load plugin '%s': %s", name, err)
        except Exception as err:
            #self.logger.warning("Unable to load plugin '%s': %s", name, err)
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
