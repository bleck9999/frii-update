from datetime import datetime, timezone
import discord
from discord.ext import commands
import configparser
import html
import json
import requests


class TrackingEvent:
    def __init__(self, raw: dict):
        self.action_code = raw["actionCode"]
        self.tz = raw['timeZone']
        if len(self.tz) == 2:
            self.tz = f"{self.tz[0]}0{self.tz[1]}00"
        elif len(self.tz) == 5:
            pass
        elif self.tz:
            raise Exception("time go brrr")
        else:
            self.tz = "+0800"  # no timezone? just guess lol
        self.time = datetime.strptime(f"{raw['time']} {self.tz}", "%Y-%m-%d %H:%M:%S %z")
        self.desc = raw["desc"]
        self.status = raw["status"]


class Loop(commands.Cog):
    """"""
    def __init__(self, bot):
        self.bot = bot
        self.conf = configparser.ConfigParser()
        self.conf.read("frii_update.ini")
        self.tns = self.conf["Cainiao"]["tracking numbers"].split(sep=",")
        self.tns = [x.strip() for x in self.tns]

    async def main(self, channel):
        local_tz = datetime.now(timezone.utc).astimezone().tzinfo
        lastcheck = self.bot.lastcheck.replace(tzinfo=local_tz)
        r = requests.get(f"https://global.cainiao.com/detail.htm?mailNoList={'%2C'.join(self.tns)}",
                         headers={"Cookie": "grayVersion=1; userSelectTag=0"})
        raw_data = html.unescape(r.text).split("<textarea style=\"display: none;\" id=\"waybill_list_val_box\">")[1].split("</textarea>")[0]
        tracking_info = json.loads(raw_data)["data"]

        for item in tracking_info:
            self.bot.log(f"Checking item: {item['mailNo']}")
            latest = TrackingEvent(item["latestTrackingInfo"])
            if latest.time > lastcheck:
                updates = [latest]
                events = [TrackingEvent(x) for x in item["section1"]["detailList"] + item["section2"]["detailList"]]
                if len(events) >= 2:
                    for event in events[1:]:
                        if event.time > lastcheck:
                            updates.append(event)
                        else:
                            break

                for update in updates[::-1]:
                    embed = discord.Embed()
                    embed.title = f"Shipping update for item {item['mailNo']}"
                    embed.description = f"{update.action_code}: \n{update.desc}\n\nRecieved at {update.time}"
                    await channel.send(embed=embed)

    @commands.command(aliases=["add_tn"])
    async def add_tracking_numer(self, ctx, number):
        self.tns.append(number)
        self.bot.log(f"Adding tracking number {number} (by request)")
        self.conf["Cainiao"]["tracking numbers"] = ", ".join(self.tns)
        with open("frii_update.ini", 'w') as f:
            self.conf.write(f)
        await ctx.send(f"Succesfully added {number}")

    @commands.command(aliases=["delete_tracking_number", "del_tn"])
    async def del_tracking_number(self, ctx, number):
        self.tns.remove(number)
        self.bot.log(f"Deleting tracking number {number} (by request)")
        self.conf["Cainiao"]["tracking numbers"] = ", ".join(self.tns)
        with open("frii_update.ini", 'w') as f:
            self.conf.write(f)
        await ctx.send(f"Succesfully removed {number}")


def setup(bot):
    bot.add_cog(Loop(bot))
