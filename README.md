welcome to bootleg github webhook for discord

i dont expect people to actually use this but i mean it works™

New™ updated instructions:
1. clone this repo
2. make a file called "info.json"
3. rename `frii_update_example.ini` to `frii_update.ini` and fill in the values
4. in info.json, make a dict, under a key called `repos` put nested list of `["path/to/cloned/repo",colour integer]`. You will need one of these lists for each repo you want to track
5. under a key called `sysupdates`, put an empty list
6. install the dependencies (you can do this with `pip install -r requirements.txt`)
7. run the bot
8. send `.start` in a channel the bot can see 
