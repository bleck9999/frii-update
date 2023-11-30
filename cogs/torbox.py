import json
import os.path

import discord
from discord.ext import commands
import aiohttp
from datetime import timedelta


class Loop(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.auth_url = "https://db.torbox.app/auth/v1"
        self.db_url = "https://db.torbox.app/rest/v1"
        self.control_url = "https://api.torbox.app/v1/api/t/controltorrent"
        if "Torbox" in self.bot.conf:
            self.apikey = self.bot.conf["Torbox"]["apikey"]
            self.noauth_hd = {"Authorization": f"Bearer {self.apikey}",
                              "Apikey": self.apikey}
        else:
            self.bot.log("Supabase API key not configured")
            exit(1)  # prankd

        self.watched = []
        self.token = ''
        self.refresh_token = ''
        if os.path.exists("cogs/torbox/info.json"):
            with open("cogs/torbox/info.json", 'r') as f:
                data = json.load(f)
                self.watched = data["watched"]
                self.token = data["token"]
                self.refresh_token = data["refresh_token"]
        else:
            os.mkdir("cogs/torbox")
            self.save_state()

    @property
    def auth_headers(self):
        return {"Authorization": f"Bearer {self.token}",
                "Apikey": self.apikey}

    def save_state(self):
        with open("cogs/torbox/info.json", 'w') as f:
            json.dump({"watched": self.watched,
                       "token": self.token,
                       "refresh_token": self.refresh_token}, f)

    @staticmethod
    def fmt_speed(speed: int) -> str:
        if speed >= 1000000:
            return f"{speed/1000000:.1f}MB/s"
        elif speed >= 1000:
            return f"{speed/1000:.1f}kB/s"
        else:
            return f"{speed}B/s"

    @staticmethod
    async def send_torrent(self, ctx, data):
        embed = discord.Embed(title=f"{data['name']}")
        state = data["download_state"]
        embed.description = f"State: {state}\n"
        if state in ["downloading"]:
            embed.description += f"Download speed: {self.fmt_speed(data['download_speed'])}\n"
        if state not in ["paused"]:
            embed.description += f"Upload speed: {self.fmt_speed(data['upload_speed'])}\n" \
                                 f"Seeds: {data['seeds']}\nPeers: {data['peers']}\n"
        if state not in ["Completed"]:
            embed.description += f"Progress: {data['progress'] * 100:.0f}%\n"
        if state not in ["Completed", "paused"]:
            embed.description += f"ETA: {timedelta(seconds=data['eta'])}"
        await ctx.send(embed=embed)

    async def refresh_auth(self):
        async with aiohttp.ClientSession() as s:
            r = await s.post(f"{self.auth_url}/token?grant_type=refresh_token",
                             data=r"""{"refresh_token": "REPLACEME"}""".replace("REPLACEME", self.refresh_token),
                             headers=self.noauth_hd)
            if r.status != 200:
                self.bot.log("Token refresh failed!")
            j = await r.json()
            self.token = j["access_token"]
            self.refresh_token = j["refresh_token"]
            self.save_state()

    async def main(self, channel):
        await self.refresh_auth()
        async with aiohttp.ClientSession() as s:
            for name in self.watched:
                r = await s.get(f"{self.db_url}/torrents?select=download_speed,upload_speed,"
                                f"eta,download_state,progress,seeds,peers,name"
                                f"&name=eq.{name}", headers=self.auth_headers)
                if r.status != 200:
                    self.bot.log(f"GET torrents returned {r.status}")
                r = await r.json()
                await self.send_torrent(channel, r[0])

    @commands.command(aliases=["tr_status"])
    async def torbox_status(self, ctx, name):
        await self.refresh_auth()
        async with aiohttp.ClientSession() as s:
            r = await s.get(f"{self.db_url}/torrents?select=download_speed,upload_speed,eta,download_state,"
                            f"progress,seeds,peers,name"
                            f"&name=ilike.%{name}%", headers=self.auth_headers)
            if r.status != 200:
                self.bot.log(f"GET torrents returned {r.status}")
                return await ctx.send("Failed to fetch torrent information")
            r = await r.json()
            if len(r) > 1:
                embed = discord.Embed(title=f"{len(r)} matches found:")
                embed.description = [f"{i+1}. {data['name']}" for i, data in enumerate(r)]
                await ctx.send(embed=embed)
            elif len(r) == 0:
                await ctx.send(f"No torrents found matching {name}")
            else:
                data = r[0]
                await self.send_torrent(ctx, data)

    @commands.command(aliases=["tr_watch", "tr_unwatch", "torbox_unwatch"])
    async def torbox_watch(self, ctx, name):
        await self.refresh_auth()
        async with aiohttp.ClientSession() as s:
            r = await s.get(f"{self.db_url}/torrents?select=name&name=ilike.%{name}%",
                            headers=self.auth_headers)
            if r.status != 200:
                self.bot.log(f"GET torrents returned {r.status}")
                return await ctx.send("Failed to fetch torrent information")
            r = await r.json()
            if len(r) > 1:
                embed = discord.Embed(title=f"{len(r)} matches found:")
                embed.description = [f"{i + 1}. {data['name']}" for i, data in enumerate(r)]
                await ctx.send(embed=embed)
            elif len(r) == 0:
                await ctx.send(f"No torrents found matching {name}")
            else:
                fullname = r[0]["name"]
                if fullname in self.watched:
                    self.watched.remove(fullname)
                    await ctx.send(f"Stopped watching {fullname}")
                else:
                    self.watched.append(fullname)
                    await ctx.send(f"Now watching {fullname}")
                self.save_state()


def setup(bot):
    bot.add_cog(Loop(bot))
