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
    """Checks cainiao for shipping updates, given a comma separated list of tracking numbers in frii_update.ini,
    with the field name "tracking numbers" and the section name "Cainiao"
    probably a bit unstable because of timezone memes but who really cares"""
    def __init__(self, bot):
        self.bot = bot
        self.conf = configparser.ConfigParser()
        self.conf.read("frii_update.ini")
        self.tns = self.conf["Cainiao"]["tracking numbers"].split(sep=",")
        self.tns = [x.strip().upper() for x in self.tns]

    async def main(self, channel):
        local_tz = datetime.now(timezone.utc).astimezone().tzinfo
        lastcheck = self.bot.lastcheck.replace(tzinfo=local_tz)
        r = requests.get(f"https://global.cainiao.com/detail.htm?mailNoList={'%2C'.join(self.tns)}",
                         headers={"Cookie": "grayVersion=1; userSelectTag=0"})
        raw_data = html.unescape(r.text).split("<textarea style=\"display: none;\" id=\"waybill_list_val_box\">")[1].split("</textarea>")[0]
        tracking_info = json.loads(raw_data)["data"]

        to_remove, to_add = [], []
        for tn, item in zip(self.tns, tracking_info):
            if item['mailNo'] != tn:
                self.bot.log(f"Tracking number mismatch: expected {tn}, got {item['mailNo']}")
                old_tn = tn
                to_remove.append(old_tn)
                tn = item['mailNo'].split(sep=':')[1].replace(')', '')
                to_add.append(tn)
                await channel.send(f"Tracking number changed, {old_tn} -> {tn}")
            self.bot.log(f"Checking item: {tn}")
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
                    embed.title = f"Shipping update for item {tn}"
                    embed.description = f"{update.action_code}: \n{update.desc}\n\nRecieved at {update.time}"
                    await channel.send(embed=embed)

        for item in to_remove:
            self.modify_tns('del', item)
        for item in to_add:
            self.modify_tns('add', item)

    def modify_tns(self, operation, number):
        number = number.upper()
        if operation == "del":
            self.tns.remove(number)
        elif operation == "add":
            self.tns.append(number)
        else:
            raise Exception("Invalid operation provided")

        self.conf["Cainiao"]["tracking numbers"] = ", ".join(self.tns)
        with open("frii_update.ini", 'w') as f:
            self.conf.write(f)

    @commands.command(aliases=["add_tn"])
    async def add_tracking_numer(self, ctx, number):
        self.bot.log(f"Adding tracking number {number.upper()} (by request)")
        self.modify_tns("add", number)
        await ctx.send(f"Succesfully added {number.upper()}")

    @commands.command(aliases=["delete_tracking_number", "del_tn"])
    async def del_tracking_number(self, ctx, number):
        self.bot.log(f"Deleting tracking number {number.upper()} (by request)")
        self.modify_tns("del", number)
        await ctx.send(f"Succesfully removed {number.upper()}")


def setup(bot):
    bot.add_cog(Loop(bot))
