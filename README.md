welcome to bootleg github webhook for discord

i dont expect people to actually use this but i mean it works™
if you want to use it for whatever reason then use the pickle module to dump a list of repos to track into a file called "repos.conf" in the same directory as bot.py (format is above the assignment of `repos` in cogs/friiUpdate.py), put the tokens somewhere then run .start once the bot is online
by default it checks every 900s (15 minutes), if you want to change this change the sleepTime variable in friiUpdate.py to a different number (you can also try and use .interval/.sleepTime but good luck with that)

tokens are read from a file in the same directory as bot.py called "github_token.txt" and "discord_token.txt", the parsers are nonexistent so if it doesnt work ~~fix them and pr it~~ just put the tokens in the .py files or something i dont know 

it doesnt currently track issues, tags or releases, it also probably doesnt work with the same instance in multiple servers.
