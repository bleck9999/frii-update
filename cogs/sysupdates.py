import json
from datetime import datetime

import feedparser
from discord.ext import commands


class Loop(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def main(self, channel):
        roleid = self.bot.role
        with open("info.json") as j:
            js = json.load(j)
            entries = js["sysupdates"]

        self.bot.log("Checking for sysupdates")

        feed = feedparser.parse("https://yls8.mtheall.com/ninupdates/feed.php")
        for entry in feed.entries:
            if "3DS" in entry.title or "WiiU" in entry.title:  # bad console alert
                continue
            version = entry.title[7:]
            if version not in entries:
                if not self.bot.ponged:
                    await channel.send(f"<@&{roleid}> New firmware version detected!")
                    self.bot.ponged = True
                await channel.send(f"New version {version} released on: {entry.published}")
                entries.append(version)

        with open("info.json", "w") as j:
            js["sysupdates"] = entries
            j.seek(0, 0)
            json.dump(js, j)


def setup(bot):
    bot.add_cog(Loop(bot))
