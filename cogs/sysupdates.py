import json
from datetime import datetime

import feedparser
from discord.ext import commands


class friiRSS(commands.Cog):
    async def check_sysupdates(self, ponged, roleid, channel):

        with open("info.json") as j:
            js = json.load(j)
            entries = js["sysupdates"]

        now = datetime.now().strftime("%H:%M:%S")
        print(f"[{now}] Checking for sysupdates")

        feed = feedparser.parse("https://yls8.mtheall.com/ninupdates/feed.php")
        for entry in feed.entries:
            if "3DS" in entry.title or "WiiU" in entry.title:
                continue
            version = entry.title[7:]
            if version not in entries:
                if not ponged:
                    await channel.send(f"<@&{roleid}> New firmware version detected!")
                    ponged = True
                await channel.send(f"Version {version} released on: {entry.published}")
                entries.append(version)

        with open("info.json", "w") as j:
            js["sysupdates"] = entries
            j.seek(0, 0)
            json.dump(js, j)

        return ponged


def setup(bot):
    bot.add_cog(friiRSS(bot))
