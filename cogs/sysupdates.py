import json
from datetime import datetime

import feedparser
from discord.ext import commands


class Loop(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.infomigration()
        with open("cogs/sysupdates/info.json") as j:
            self.entries = json.load(j)

    def infomigration(self):
        import os
        if os.path.exists("info.json"):
            try:
                os.mkdir("cogs/github")
                os.mkdir("cogs/sysupdates")
                c = json.load(open("info.json", 'r'))
                repos, sysupdates = c["repos"], c["sysupdates"]
                with open("cogs/github/info.json", 'w') as f:
                    json.dump(repos, f)
                with open("cogs/sysupdates/info.json", 'w') as f:
                    json.dump(sysupdates, f)

                os.remove("info.json")
            except Exception as e:
                self.bot.log("info.json migration failed!")
                raise e

    async def main(self, channel):
        roleid = self.bot.role

        self.bot.log("Checking for sysupdates")

        feed = feedparser.parse("https://yls8.mtheall.com/ninupdates/feed.php")
        for entry in feed.entries:
            if "3DS" in entry.title or "WiiU" in entry.title:  # bad console alert
                continue
            version = entry.title[7:]
            if version not in self.entries:
                if not self.bot.ponged:
                    await channel.send(f"<@&{roleid}> New firmware version detected!")
                    self.bot.ponged = True
                await channel.send(f"New version {version} released on: {entry.published}")

                self.entries.append(version)
                with open("cogs/sysupdates/info.json", "w") as j:
                    j.seek(0, 0)
                    json.dump(self.entries, j)


def setup(bot):
    bot.add_cog(Loop(bot))
