Instructions (Professionalism edition™)
1. Clone this repo including the submodule (frii-config)
2. Install pyside6. It's not in the requirements.txt for the very reasonable reason of it's actually a dependency for frii-config, not frii-update
3. Run frii-config (`frii-config/configurator.py`) and add any repositories you want to track
4. Rename `frii_update_example.ini` to `frii_update.ini` and replace in the default values with your text editor of choice. Details on what each option does can be found below.
5. Install frii-update's dependencies (you can do this with `pip install -r requirements.txt`)
6. Run the bot
7. Send `.start` in a channel the bot can see 

As per the regularly scheduled increase in project scope frii update will now attempt to load any .py
file in the `cogs` directory, then execute its `Loop.main()` function with one parameter,
channel: a discord.py channel object fetched from the ID in `frii_update.ini`.  
It's encouraged to use FriiUpdate's staticmethod `log(text)` over your own print statements where possible.

## Configuration
### [Modules]
Structure: `name_of_module = true/false`  
When loading a module, the bot tries to read an entry with the name of the module 
(so if the module is `cogs/memes.py`, it will look for `memes`). If this option is set to
`True` (case insensitive), the module will be loaded. 
### [Bot]
| Option     | Type   | Description                                                                                                                               |
|------------|--------|-------------------------------------------------------------------------------------------------------------------------------------------|
| Role ID    | `Int`  | The discord ID of the role to ping for alerts                                                                                             |
| Channel ID | `Int`  | The discord ID of the channel to send messages to                                                                                         |
| Interval   | `Int`  | The amount of time to wait (in seconds) before each check                                                                                 |
| Token      | `Str`  | Discord token. Details on how to create one here: https://github.com/reactiflux/discord-irc/wiki/Creating-a-discord-bot-&-getting-a-token |
| Log Level  | `Str`  | Currently only two settings: debug (post all exceptions) and error (ignore some exceptions). Implementation depends on module author.     |
| Prefix     | `Str   | Bot command prefix                                                                                                                        |
### [Github]
| Option        | Type  | Description                                                                                                                                               |
|---------------|-------|-----------------------------------------------------------------------------------------------------------------------------------------------------------|
| Pull limit    | `Int` | The maximum number of pull requests to fetch. Set to 0 to disable.                                                                                        |
| Commit limit  | `Int` | The maximum number of commits to fetch. Only used with pull requests comparing across forks. Set to 0 to disable.                                         |
| Comment limit | `Int` | The maximum number of pull requests to fetch. Set to 0 to disable. Due to how reviews work setting this to zero is not recommended when review limit > 0. |
| Review limit  | `Int` | The maximum number of reviews to fetch. Only used with pull requests. Set to 0 to disable.                                                                |
| Release limit | `Int` | The maximum number of releases to fetch. Set to 0 to disable.                                                                                             |
| Issue limit   | `Int` | The maximum number of issues to fetch. Set to 0 to disable.                                                                                               |
| Token         | `Str` | Github API token. Requires public: repo and read: user scopes. Can be generated here: https://github.com/settings/tokens                                  |

After one complete cycle, a new entry will be added under `[Bot]` named `Last Checked`.
This is not meant to be edited under normal circumstances, but I can't stop you from doing so if you wish.
It stores the last time the bot checked in the strftime format `%H%M%S %d%m%Y`.

Some modules use additional configuration keys. In this case, documentation is not my job lmao check readmes or the module's docstring