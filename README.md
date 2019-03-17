# DyphanBot (rewrite)
~~<sup>~~Dyphan's transplanted guts~~</sup>~~

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

Currently, there are three implemented configuration settings:
    * `token`: The Discord API token required for DyphanBot to run.
    * `disabled_plugins`: The list of plugins that should be disabled.
    * `plugin_dirs`: Additional plugin directories DyphanBot can look in.

## TODO
- [ ] Revise the way handlers are handled.
- [ ] Rethink how plugins should work.
- [ ] Write a good "API" layer for plugins to use.
- [ ] Implement basic voice functionality that multiple plugins can use.
- [x] ~~Implement saving data.~~
- [x] ~~Rewrite the voice plugin.~~
- [x] ~~Make use of an actual configuration file.~~
- [ ] Possibly make a runtime patch to discord.py to implement voice receive
    (until it's officially available).
