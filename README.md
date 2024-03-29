# DyphanBot
~~<sup>~~Dyphan's guts~~</sup>~~

An expandable Discord bot! Written in Python using
[Pycord](https://github.com/Pycord-Development/pycord).
Still in early stages.

Supports plugin-loading from `~/.dyphan/plugins` and `~/.config/dyphan/plugins`
directories, as well as the built-in `plugins` directory. You can add additional
plugin directories in DyphanBot's configuration file.

## Dependencies
Each DyphanBot plugin can have its own dependency. The dependencies for
DyphanBot's core, as well as the built-in plugins that require other
dependencies, are listed here:
* **Core**
  * Python >= 3.8
  * [py-cord](https://github.com/Pycord-Development/pycord) >= 2.0
* **Audio**
  * py-cord[voice]
  * [yt-dlp](https://github.com/yt-dlp/yt-dlp)
* **WebAPI (WIP)**
  * ~~[websockets](https://github.com/aaugustin/websockets)~~
  * ~~[requests-oauthlib](https://github.com/requests/requests-oauthlib)~~
  * [aiohttp_session[secure]](https://github.com/aio-libs/aiohttp-session)
  * [aioauth-client](https://github.com/klen/aioauth-client)

## Configuration
DyphanBot looks for a `config.json` file in `~/.dyphan` and `~/.config/dyphan`
directories. Once it finds the file, it will assign the location it first found
it in as the default data directory.

Available configuration settings:
- `token`: The Discord API token required for DyphanBot to run.
- `bot_masters`: A list of Discord user IDs that have access to DyphanBot's
    software (basically sysadmins).
- `disabled_plugins`: The list of plugins that should be disabled.
- `plugin_dirs`: Additional plugin directories DyphanBot can look in.
- `intents`: A key-value pair of Discord intents the bot should run with  
  (see [Discord docs][intent docs] and [Pycord reference][intent refs] for
   more info).

<details>
<summary><b>Config Sample</b></summary>

```json
{
    "token": "__YOUR_DISCORD_BOT_API_TOKEN__",
    "bot_masters": [ 123456789876543210, 098765432123456789 ],
    "disabled_plugins": [
        "testplugin",
        "example_plugin"
    ],
    "plugin_dirs": [
        "~/my_plugins",
        "/path/to/dyphanbot/plugins"
    ],
    "intents": {
        "members": true,
        "typing": false
    }
}
```
</details>

[intent docs]: https://discord.com/developers/docs/topics/gateway#gateway-intents
[intent refs]: https://docs.pycord.dev/en/master/api.html#discord.Intents

## Installation

```bash
git clone https://github.com/buzzbyte/DyphanBot.git
cd DyphanBot
python3 -m pip install -U .

# to run:
python3 -m dyphanbot
```

## Usage

Soon&trade; ...

## License
DyphanBot is licensed under GNU AGPLv3 (see [license](LICENSE))