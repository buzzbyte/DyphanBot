# DyphanBot
~~<sup>~~Dyphan's guts~~</sup>~~

An expandable Discord bot! Written in Python3 using
[discord.py](https://github.com/Rapptz/discord.py) (rewrite branch).
Still in early stages.

Supports plugin-loading from `~/.dyphan/plugins` and `~/.config/dyphan/plugins`
directories, as well as the built-in `plugins` directory. You can add additional
plugin directories in DyphanBot's configuration file.

## Configuration
DyphanBot looks for a `config.json` file in `~/.dyphan` and `~/.config/dyphan`
directories. Once it finds the file, it will assign the location it first found
it in as the default data directory.

Currently, there are four main configuration settings:
- `token`: The Discord API token required for DyphanBot to run.
- `bot_masters`: A list of Discord user IDs that have access to DyphanBot's
    software (basically sysadmins).
- `disabled_plugins`: The list of plugins that should be disabled.
- `plugin_dirs`: Additional plugin directories DyphanBot can look in.
