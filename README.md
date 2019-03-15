# DyphanBot (rewrite)
~~<sup>~~Dyphan's transplanted guts~~</sup>~~

An expandable Discord bot! Written in Python3 using
[discord.py](https://github.com/Rapptz/discord.py) (rewrite branch).
Still in early stages.

Supports plugin-loading from `~/.dyphan/plugins` and `~/.config/dyphan/plugins`
directories, as well as the built-in `plugins` directory.

Currently reads the token from `~/testee_token.json`. File name and location
*will be changed* when more configuration options are implemented.

## TODO
- [ ] Revise the way handlers are handled.
- [ ] Rethink how plugins should work.
- [ ] Write a good "API" layer for plugins to use.
- [ ] Implement basic voice functionality that multiple plugins can use.
- [ ] Implement saving data.
- [x] Rewrite the voice plugin.
- [ ] Make use of an actual configuration file.
- [ ] Possibly make a runtime patch to discord.py to implement voice receive
    (until it's officially available).
