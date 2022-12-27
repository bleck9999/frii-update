from datetime import datetime
import discord
from discord.ext import commands
import hashlib
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

        self.id = hashlib.sha1(f"{self.desc}{self.action_code}".encode()).hexdigest()


class Loop(commands.Cog):
    """Checks cainiao for shipping updates, given a comma separated list of tracking numbers in frii_update.ini,
    with the field name "tracking numbers" and the section name "Cainiao" """
    def __init__(self, bot):
        self.bot = bot
        self.__tns = self.bot.conf["Cainiao"]["tracking numbers"].split(sep=",")
        self.__tns = [x.strip().upper() for x in self.__tns]
        if "last event" not in self.bot.conf["Cainiao"]:
            self.bot.conf["Cainiao"]["last event"] = ','.join(['0'] * len(self.__tns))
        self.ids = {num: event_id for num, event_id in zip(self.__tns, self.bot.conf["Cainiao"]["last event"].split(sep=','))}

    async def main(self, channel):
        r = requests.get(f"https://global.cainiao.com/detail.htm?mailNoList={'%2C'.join(self.ids.keys())}",
                         headers={"Cookie": "grayVersion=1; userSelectTag=0"})
        raw_data = html.unescape(r.text).split("<textarea style=\"display: none;\" id=\"waybill_list_val_box\">")[1].split("</textarea>")[0]
        tracking_info = json.loads(raw_data)["data"]

        to_remove, to_add = [], []
        for tn, item in zip(self.ids.keys(), tracking_info):
            if item['mailNo'] != tn:
                self.bot.log(f"Tracking number mismatch: expected {tn}, got {item['mailNo']}")
                old_tn = tn
                to_remove.append(old_tn)
                tn = item['mailNo'].split(sep=':')[1].replace(')', '')
                to_add.append(tn)
                await channel.send(f"Tracking number changed, {old_tn} -> {tn}")
            self.bot.log(f"Checking item: {tn}")
            latest = TrackingEvent(item["latestTrackingInfo"])
            if latest.id != self.ids[tn]:
                updates = [latest]
                events = [TrackingEvent(x) for x in item["section1"]["detailList"] + item["section2"]["detailList"]]
                if len(events) >= 2:
                    for event in events[1:]:
                        if event.id != self.ids[tn]:
                            updates.append(event)
                        else:
                            break

                for update in updates[::-1]:
                    embed = discord.Embed()
                    embed.title = f"Shipping update for item {tn}"
                    embed.description = f"{update.action_code}: \n{update.desc}\n\nRecieved at {update.time}"
                    await channel.send(embed=embed)

            self.modify_tns("update", tn, latest.id)

        for item in to_remove:
            self.modify_tns('del', item)
        for item in to_add:
            self.modify_tns('add', item)

        with open("frii_update.ini", 'w') as f:
            self.bot.conf.write(f)

    def modify_tns(self, operation, number, event='0') -> int:
        number = number.upper()
        if operation == "del":
            self.ids.pop(number)
        elif operation == "add":
            if number in self.ids:
                return 1
            self.ids[number] = '0'
        elif operation == "update":
            self.ids[number] = event
        else:
            raise Exception("Invalid operation provided")

        self.bot.conf["Cainiao"]["tracking numbers"] = ", ".join(self.ids.keys())
        self.bot.conf["Cainiao"]["last event"] = ', '.join(self.ids.values())
        return 0

    @commands.command(aliases=["add_tn"])
    async def add_tracking_number(self, ctx, number):
        number = number.upper()
        self.bot.log(f"Adding tracking number {number} (by request)")
        if self.modify_tns("add", number) == 1:
            return await ctx.send(f"{number} not added (duplicate)")
        with open("frii_update.ini", 'w') as f:
            self.bot.conf.write(f)
        await ctx.send(f"Succesfully added {number}")

    @commands.command(aliases=["delete_tracking_number", "del_tn"])
    async def del_tracking_number(self, ctx, number):
        self.bot.log(f"Deleting tracking number {number.upper()} (by request)")
        self.modify_tns("del", number)
        with open("frii_update.ini", 'w') as f:
            self.bot.conf.write(f)
        await ctx.send(f"Succesfully removed {number.upper()}")


def setup(bot):
    bot.add_cog(Loop(bot))
