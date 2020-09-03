welcome to bootleg github webhook for discord

i dont expect people to actually use this but i mean it works™

New™ updated instructions:
1. clone this repo
2. make a file called "repos.json" and one called "frii_update.ini"
3. in frii_update.ini, make a section named `Tokens` and one named `Config`
4. under the `Tokens` section, assign `Github` to a github api token, and `Discord` to your discord bot's token
5. under the `Config` section, assign `Role ID` to the id of the role you want the bot to ping and `Channel ID` to the id of the channel you want the bot to send messages
6. in repos.json, put a nested list of `["path/to/cloned/repo",colour integer]`. You will need one of these lists for each repo you want to track
7. install the dependencies (you can do this with `pip install -r requirements.txt`)
8. run the bot
9. send `.start` in a channel the bot can see 