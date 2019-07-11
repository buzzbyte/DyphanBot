import os
import sys
import json
import logging

from dyphanbot.constants import DATA_DIRS
from dyphanbot.exceptions import InvalidConfigurationError

class ConfigManager(object):
    """ Contains methods for accessing and managing DyphanBot's configuration file """

    def __init__(self, dyphanbot):
        self.logger = logging.getLogger(__name__)
        self.dyphanbot = dyphanbot
        self.data_dir = None
        self._config_fn = "config.json"
        self._config_template = {
            "token": "_YOUR_DISCORD_API_TOKEN_HERE_"
        }

        self._config = self._setup_config()

    def __getattribute__(self, name):
        # This class' "protected" methods should only be called by either
        # `DyphanBot` or itself. This is to prevent plugins from normally
        # calling these methods.
        caller_class_name = object.__getattribute__(sys._getframe().f_back.f_locals["self"], "__class__").__name__
        this_class_name = object.__getattribute__(self, "__class__").__name__
        dyphanbot_class_name = object.__getattribute__(self, "dyphanbot").__class__.__name__
        if name.startswith("_"):
            if caller_class_name in [this_class_name, dyphanbot_class_name]:
                return object.__getattribute__(self, name)
        else:
            return object.__getattribute__(self, name)

    def _err(self, *args, **kwargs):
        print(*args, **kwargs)
        sys.exit(1)

    def _find_or_create_file(self, filepath):
        """ Finds the file or creates it. Returns the given file path. """
        # This looks useless but it probably isn't... lol
        try:
            open(filepath, 'x').close()
        except FileExistsError:
            pass
        finally:
            return filepath

    def _find_config(self):
        """ Looks for the config file in pre-defined locations and returns its
        path if found. Otherwise, create the file at the first location. """
        if self.data_dir is not None:
            # If there is a pre-defined data_dir, it's probably there.
            return self._find_or_create_file(os.path.join(self.data_dir, self._config_fn))

        # Look for the file in the pre-defined locations and, if found, assign
        # the directory and return the path it was found at
        for directory in DATA_DIRS:
            directory = os.path.expanduser(directory)
            config_path = os.path.join(directory, self._config_fn)
            if os.path.isfile(config_path):
                self.data_dir = directory
                return config_path

        # If that lookup failed and brought us here, use the first location and
        # create the config there.
        self.data_dir = os.path.expanduser(DATA_DIRS[0])
        os.makedirs(self.data_dir, exist_ok=True)
        return self._find_or_create_file(os.path.join(self.data_dir, self._config_fn))

    def _setup_config(self):
        config_path = self._find_config()
        with open(config_path, 'r+') as fd:
            raw_data = fd.read()
            if raw_data.strip() == "":
                json.dump(self._config_template, fd, indent=4)
                config = self._config_template
            else:
                try:
                    config = json.loads(raw_data)
                    if "token" not in config:
                        raise InvalidConfigurationError('token', "Required Discord API token is not defined")
                except (json.JSONDecodeError, InvalidConfigurationError) as e:
                    self._err("{}: {}".format(type(e).__name__, e))

        if config == self._config_template or len(config) == 0:
            self._err("Configuration file is located at '{0}' but has not been set up yet.\n".format(config_path),
                      "Please provide the required Discord API token for DyphanBot to run.")

        self.logger.info("Using configuration file located at '%s'.", config_path)
        return config

    def _get_key(self, key, default=None):
        if key in self._config:
            return self._config[key]
        else:
            return default

class DataManager(ConfigManager):
    """ Handles data files relative to the active data dir """

    def __init__(self, dyphanbot):
        super().__init__(dyphanbot)

    def load_json(self, filename, initial_data={}, save_json=None, **kwargs):
        filepath = os.path.join(self.data_dir, filename)
        try:
            with open(filepath, 'r') as fd:
                return json.load(fd, **kwargs)
        except (OSError, IOError):
            if not save_json:
                save_json = self.save_json
            return save_json(filename, initial_data)

    def save_json(self, filename, data, **kwargs):
        filepath = os.path.join(self.data_dir, filename)
        with open(filepath, 'w') as fd:
            json.dump(data, fd, **kwargs)

        return data

















#
