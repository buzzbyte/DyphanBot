from pkg_resources import get_distribution, DistributionNotFound

__version__ = None

try:
    __version__ = get_distribution("dyphanbot").version
except DistributionNotFound:
    # package is not installed
    try:
        from _version import version
        __version__ = version
    except ImportError:
        pass

from dyphanbot.pluginloader import Plugin
from dyphanbot.exceptions import PluginError
