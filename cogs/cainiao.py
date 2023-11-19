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
    """Checks cainiao for shipping updates
    Expects dict[tracking_number (str) : event_hash (str)] in cainiao/info.json
    if setting up for the first time, leave the event hash as an empty string"""
    def __init__(self, bot):
        self.bot = bot
        self.ids: dict[str: str] = {}
        if "Cainiao" in self.bot.conf:
            tns = self.bot.conf["Cainiao"]["tracking numbers"].split(sep=",")
            tns = [x.strip().upper() for x in tns]
            if "last event" not in self.bot.conf["Cainiao"]:
                self.bot.conf["Cainiao"]["last event"] = ','.join(['0'] * len(tns))
            self.ids = {num: event_id.strip() for num, event_id in
                        zip(tns, self.bot.conf["Cainiao"]["last event"].split(sep=','))}
            self.migrate_ini_config()
        else:
            self.update_state()

    def migrate_ini_config(self):
        import os
        if not os.path.isdir("cogs/cainiao"):
            os.mkdir("cogs/cainiao")
            with open("cogs/cainiao/info.json", 'w') as f:
                json.dump(self.ids, f)
        self.bot.log("Configuration data has been moved to cogs/cainiao/info.json, "
                     "please remove the [Cainiao] section from frii_update.ini")
        raise RuntimeError("Please remove the [Cainiao] section from frii_update.ini")

    def update_state(self):
        with open("cogs/cainiao/info.json", 'r') as f:
            self.ids = json.load(f)

    async def main(self, channel):
        # if '' in self.ids:  # should be unnecessary now
        #     self.modify_tns("del", '')

        r = requests.get(f"https://global.cainiao.com/detail.htm?mailNoList={'%2C'.join(self.ids.keys())}",
                         headers={"Cookie": "grayVersion=1; userSelectTag=0"})
        try:
            raw_data = html.unescape(r.text).split("<textarea style=\"display: none;\" id=\"waybill_list_val_box\">")[1].split("</textarea>")[0]
        except IndexError:
            if self.bot.conf["Bot"]["log level"].lower() == "debug":
                await channel.send("Cainiao: captcha detected, skipping")
            self.bot.log("captcha detected, skipping")
            return
        tracking_info = json.loads(raw_data)["data"]

        to_remove, to_add = [], []
        for tn, item in zip(self.ids.keys(), tracking_info):
            if item['mailNo'] != tn:
                self.bot.log(f"Tracking number mismatch: expected {tn}, got {item['mailNo']}")
                to_remove.append(tn)
                new_tn = item['mailNo'].split(sep=':')[1].replace(')', '')
                to_add.append(new_tn)
                await channel.send(f"Tracking number changed, {tn} -> {new_tn}")
            self.bot.log(f"Checking item: {tn}")
            if "latestTrackingInfo" in item:
                latest = TrackingEvent(item["latestTrackingInfo"])
            else:
                self.bot.log(f"No tracking events found for {tn}")
                continue
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
                    if update.action_code == "GTMS_SIGNED":
                        to_remove.append(tn)  # order delivered
                    embed = discord.Embed()
                    embed.title = f"Shipping update for item {tn}"
                    embed.description = f"{update.action_code}: \n{update.desc}\n\nRecieved at {update.time}"
                    await channel.send(embed=embed)

            self.modify_tns("update", tn, latest.id)
        
        for item in to_remove:
            self.modify_tns('del', item)
        for item in to_add:
            self.modify_tns('add', item)

    def modify_tns(self, operation, number, event='0') -> int:
        number = number.upper()
        if operation == "del":
            if number not in self.ids:
                return 2
            self.ids.pop(number)
        elif operation == "add":
            if number in self.ids:
                return 1
            self.ids[number] = event
        elif operation == "update":
            self.ids[number] = event
        else:
            raise Exception("Invalid operation provided")

        with open("cogs/cainiao/info.json", 'w') as f:
            json.dump(self.ids, f)

        return 0

    @commands.command(aliases=["add_tn"])
    async def add_tracking_number(self, ctx, number):
        self.update_state()
        number = number.upper()
        self.bot.log(f"Adding tracking number {number} (by request)")
        if self.modify_tns("add", number) == 1:
            return await ctx.send(f"{number} not added (duplicate)")
        await ctx.send(f"Succesfully added {number}")

    @commands.command(aliases=["delete_tracking_number", "del_tn"])
    async def del_tracking_number(self, ctx, number):
        self.update_state()
        self.bot.log(f"Deleting tracking number {number.upper()} (source: del_tn)")
        if self.modify_tns("del", number) == 2:
            return await ctx.send(f"{number} not deleted (not found)")
        await ctx.send(f"Succesfully removed {number.upper()}")

    @commands.command(aliases=["list_tns"])
    async def list_tracking_numbers(self, ctx):
        self.update_state()
        await ctx.send(embed=discord.Embed(title="List of saved tracking numbers", description='\n'.join(self.ids)))


def setup(bot):
    bot.add_cog(Loop(bot))
