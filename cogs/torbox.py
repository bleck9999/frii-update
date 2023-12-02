import base64
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
        if state not in ["Completed", "paused", "uploading"]:
            embed.description += f"ETA: {timedelta(seconds=data['eta'])}"
        if state == "uploading":
            embed.description += f"Download link expiry: {timedelta(seconds=data['eta'])}\n"
            embed.description += await self.get_dl_link(data["name"], "all")
        await ctx.send(embed=embed)

    async def refresh_auth(self):
        if not self.refresh_token or not self.token:
            await self.bot.log("Token refresh failed (token or refresh token missing)")
            return 1
        async with aiohttp.ClientSession() as s:
            r = await s.post(f"{self.auth_url}/token?grant_type=refresh_token",
                             data=json.dumps({"refresh_token": self.refresh_token}),
                             headers=self.noauth_hd)
            if r.status != 200:
                self.bot.log(f"Token refresh failed! (status code {r.status})")
                return
            j = await r.json()
            self.token = j["access_token"]
            self.refresh_token = j["refresh_token"]
            self.save_state()

    async def fuzzy_torrent_by_name(self, ctx, name):
        if await self.refresh_auth():
            return await ctx.send("Authentication failed, reconfigure token")
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
                return r[0]["name"]

    async def main(self, channel):
        if await self.refresh_auth():
            return await channel.send("Authentication failed, reconfigure token")
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
        if await self.refresh_auth():
            return await ctx.send("Authentication failed, reconfigure token")
        name = await self.fuzzy_torrent_by_name(ctx, name)
        if not isinstance(name, str):
            return
        async with aiohttp.ClientSession() as s:
            r = await s.get(f"{self.db_url}/torrents?select=download_speed,upload_speed,eta,download_state,"
                            f"progress,seeds,peers,name"
                            f"&name=eq.{name}", headers=self.auth_headers)
            if r.status != 200:
                self.bot.log(f"GET torrents returned {r.status}")
                return await ctx.send("Failed to fetch torrent information")
            r = await r.json()
            data = r[0]
            await self.send_torrent(ctx, data)

    @commands.command(aliases=["tr_watch", "tr_unwatch", "torbox_unwatch"])
    async def torbox_watch(self, ctx, name):
        if await self.refresh_auth():
            return await ctx.send("Authentication failed, reconfigure token")
        name = await self.fuzzy_torrent_by_name(ctx, name)
        if not isinstance(name, str):
            return
        if name in self.watched:
            self.watched.remove(name)
            await ctx.send(f"Stopped watching {name}")
        else:
            self.watched.append(name)
            await ctx.send(f"Now watching {name}")
        self.save_state()

    @commands.command(aliases=["tr_pause", "tr_resume", "torbox_resume"])
    async def torbox_pause(self, ctx, name):
        if await self.refresh_auth():
            return await ctx.send("Authentication failed, reconfigure token")
        name = await self.fuzzy_torrent_by_name(ctx, name)
        if not isinstance(name, str):
            return
        async with aiohttp.ClientSession() as s:
            r = await s.get(f"{self.db_url}/torrents?select=id,auth_id,download_state&name=eq.{name}",
                            headers=self.auth_headers)
            data = await r.json()
            data = data[0]
            if data["download_state"] == "paused":
                action = "resume"
            else:
                action = "pause"
            headers = self.auth_headers
            headers["Content-Type"] = "application/json"
            r = await s.post(self.control_url,
                             data=json.dumps({"id_": data["id"],
                                              "auth_id": data["auth_id"],
                                              "operation": action}),
                             headers=headers)
            r = await r.json()
            if r["status"] is True:
                await ctx.send(f"{name} {'paused' if action == 'pause' else 'resumed'} succesfully")
            else:
                await ctx.send(f"Failed to {action} {name}")

    async def get_dl_link(self, fullname, mode, arg=None):
        if await self.refresh_auth():
            return #await ctx.send("Authentication failed, reconfigure token")
        async with aiohttp.ClientSession() as s:
            r = await s.get(f"{self.db_url}/torrents?select=id,download_path,files,server,download_present,servers(download_url)"
                            f"&name=eq.{fullname}",
                            headers=self.auth_headers)
            if r.status != 200:
                return "Failed to fetch torrent information"
            r = await r.json()
            data = r[0]
            if data["download_present"]:
                server_url = data["servers"]["download_url"]
            else:
                # check if this is needed (its possible it sets download_present)
                # but it might also be that asking /servers directly is unnecessary and the above query
                # will set download_present if it's not already true
                server_id = data["server"]
                r = await s.get(f"{self.db_url}/servers?select=download_url&id=eq.{server_id}",
                                headers=self.auth_headers)
                server_url = await r.json()
                server_url = server_url["download_url"]

            if mode == "all":
                mode = "dir"
                arg = data["download_path"].split('/')[2]
            if mode == "dir":
                b64dir = base64.urlsafe_b64encode(arg.encode("UTF-8")).decode("UTF-8")
                return (f"{server_url}/zip/torrents/{data['id']}"
                        f"?d={b64dir}&token={self.token}")
            elif mode == "file":
                pass  # todo
                # if you're wondering the way to do it is
                # GET <server_url>/file/torrents/<data['id']>/<file_idx>
                # i just dont feel like writing a file search to get the index


def setup(bot):
    bot.add_cog(Loop(bot))
