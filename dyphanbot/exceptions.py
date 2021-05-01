""" Definitions for DyphanBot-related exceptions """

class DyphanBotError(Exception):
    """ Base Exception for DyphanBot Errors """
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message

class InvalidConfigurationError(DyphanBotError):
    """ Raised on invalid configuration """
    def __init__(self, key, message):
        super().__init__(message)
        self.key = key

    def __str__(self):
        return "{0}: '{1}'".format(self.message, self.key)

class PluginError(DyphanBotError):
    """ Raised by plugins """
