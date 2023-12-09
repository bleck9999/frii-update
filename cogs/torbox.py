import base64
import json
import os.path

import discord
from discord.ext import commands
import aiohttp
from datetime import timedelta


class TorrentState:
    def __init__(self, state: str):
        self.state = state

    def __repr__(self):
        return self.state

    @property
    def downloading(self):
        return self.state in ["downloading"]

    @property
    def uploading(self):
        return self.state not in ["paused", "Completed", "stalledUP"]

    @property
    def completed(self):
        return self.state not in ["Completed", "uploading", "stalledUP"]

    @property
    def in_progress(self):
        return self.state not in ["Completed", "paused", "uploading", "stalledUP"]

    @property
    def download_available(self):
        return self.state in ["uploading", "stalledUP"]


class Loop(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.auth_url = "https://db.torbox.app/auth/v1"
        self.db_url = "https://db.torbox.app/rest/v1"
        self.api_url = "https://api.torbox.app/v1/api/torrents"
        if "Torbox" in self.bot.conf:
            self.db_api_key = self.bot.conf["Torbox"]["apikey"]
            self.hd_db_noauth = {"Authorization": f"Bearer {self.db_api_key}",
                                 "Apikey": self.db_api_key}
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
    def hd_db_authed(self):
        return {"Authorization": f"Bearer {self.token}",
                "Apikey": self.db_api_key}

    @staticmethod
    def fmt_speed(speed: int) -> str:
        if speed >= 1000000:
            return f"{speed/1000000:.1f}MB/s"
        elif speed >= 1000:
            return f"{speed/1000:.1f}kB/s"
        else:
            return f"{speed}B/s"

    def save_state(self):
        with open("cogs/torbox/info.json", 'w') as f:
            json.dump({"watched": self.watched,
                       "token": self.token,
                       "refresh_token": self.refresh_token}, f)

    async def send_torrent(self, ctx, data):
        embed = discord.Embed(title=f"{data['name']}")
        state = TorrentState(data["download_state"])
        embed.description = f"State: {state}\n"
        if state.downloading:
            embed.description += f"Download speed: {self.fmt_speed(data['download_speed'])}\n"
        if state.uploading:
            embed.description += f"Upload speed: {self.fmt_speed(data['upload_speed'])}\n"
        if state.downloading:
            embed.description += f"Seeds: {data['seeds']}\nPeers: {data['peers']}\n"
        if not state.completed:
            embed.description += f"Progress: {data['progress'] * 100:.0f}%\n"
        if state.in_progress:
            embed.description += f"ETA: {timedelta(seconds=data['eta'])}"
        if state.download_available:
            embed.description += f"Download link expiry: {timedelta(seconds=data['eta'])}\n"
            embed.description += await self.get_dl_link(data["name"], "all")
        await ctx.send(embed=embed)

    async def refresh_db_auth(self):
        if not self.refresh_token or not self.token:
            await self.bot.log("Token refresh failed (token or refresh token missing)")
            return 1
        async with aiohttp.ClientSession() as s:
            r = await s.post(f"{self.auth_url}/token?grant_type=refresh_token",
                             data=json.dumps({"refresh_token": self.refresh_token}),
                             headers=self.hd_db_noauth)
            if r.status != 200:
                self.bot.log(f"Token refresh failed! (status code {r.status})")
                return
            j = await r.json()
            self.token = j["access_token"]
            self.refresh_token = j["refresh_token"]
            self.save_state()

    async def get_api_headers(self, auth_id) -> dict[str:str]:
        async with aiohttp.ClientSession() as s:
            r = await s.get(f"{self.db_url}/api_tokens?select=token&auth_id=eq.{auth_id}",
                            headers=self.hd_db_authed)
            if r.status != 200:
                return {"failed": "true"}
            r = await r.json()
            headers = {"Authorization": f"Bearer {r[0]['token']}",
                       "Content-Type": "application/json"}
            return headers

    async def fuzzy_torrent_by_name(self, ctx, name):
        if await self.refresh_db_auth():
            return await ctx.send("Authentication failed, reconfigure token")
        async with aiohttp.ClientSession() as s:
            r = await s.get(f"{self.db_url}/torrents?select=name&name=ilike.%{name}%",
                            headers=self.hd_db_authed)
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
        if await self.refresh_db_auth():
            return await channel.send("Authentication failed, reconfigure token")
        async with aiohttp.ClientSession() as s:
            for name in self.watched:
                r = await s.get(f"{self.db_url}/torrents?select=download_speed,upload_speed,"
                                f"eta,download_state,progress,seeds,peers,name"
                                f"&name=eq.{name}", headers=self.hd_db_authed)
                if r.status != 200:
                    self.bot.log(f"GET torrents returned {r.status}")
                r = await r.json()
                await self.send_torrent(channel, r[0])

    async def get_dl_link(self, fullname, mode, arg=None):
        if await self.refresh_db_auth():
            return "Authentication failure"
        async with aiohttp.ClientSession() as s:
            r = await s.get(f"{self.db_url}/torrents?select=id,download_path,files,server,download_present,servers(download_url)"
                            f"&name=eq.{fullname}",
                            headers=self.hd_db_authed)
            if r.status != 200:
                return "Failed to fetch torrent information"
            r = await r.json()
            data = r[0]
            if data["download_present"]:
                # server_url = data["servers"]["download_url"]
                root_id = data["download_path"]
            else:
                self.bot.log(f"{fullname}: download link not present")
                return "N/A"

            headers = self.get_api_headers(data["auth_id"])
            if "failed" in headers:
                return "Failed to fetch API token"

            if mode == "all":
                r = await s.get(f"{self.api_url}/requestzip?torrent_id={data['id']}&"
                                f"folder_id={root_id}&token={headers['Authorization'][7:]}")
                link = await r.json()
                return link["data"]
            if mode == "dir":
                pass  # todo
            elif mode == "file":
                pass  # todo

    @commands.command(alias="tr_add_magnet")
    async def torbox_add_magnet(self, ctx, magnet):
        if await self.refresh_db_auth():
            return await ctx.send("Authentication failed, reconfigure token")
        async with aiohttp.ClientSession() as s:
            r = await s.get(f"{self.db_url}/users?select=auth_id", headers=self.hd_db_authed)
            r = await r.json()
            headers = await self.get_api_headers(r[0]["auth_id"])
            headers.pop("Content-Type")
            r = await s.post(f"{self.api_url}/createtorrent",
                             data={"magnet": magnet},
                             headers=headers)
            j = await r.json()
            return await ctx.send(j["detail"])

    @commands.command(aliases=["tr_list_torrents"])
    async def torbox_list_torrents(self, ctx):
        if await self.refresh_db_auth():
            return await ctx.send("Authentication failed, reconfigure token")
        async with aiohttp.ClientSession() as s:
            r = await s.get(f"{self.db_url}/torrents?select=*",
                            headers=self.hd_db_authed)
            if r.status != 200:
                return await ctx.send("Failed to fetch torrent information")
            torrents = await r.json()
            if len(torrents) == 0:
                return await ctx.send("No torrents found")
            await ctx.send("Currently active torrents:")
            for torrent in torrents:
                await self.send_torrent(ctx, torrent)

    @commands.command(aliases=["tr_get_otp", "tr_get_link", "torbox_get_link"])
    async def torbox_get_otp(self, ctx, email, create_user=False):
        if not self.db_api_key:
            return await ctx.send("API key not provided")
        async with aiohttp.ClientSession() as s:
            r = await s.post(f"{self.auth_url}/otp",
                             data=json.dumps({"email": email, "create_user": bool(create_user)}),
                             headers=self.hd_db_noauth)
            if r.status != 200:
                await ctx.send("Failed to send email")
                print(await r.json())
            else:
                await ctx.send("Magic link sent successfully, check your email "
                               "and use `torbox_get_token` with the magic link")

    @commands.command(aliases=["tr_get_token"])
    async def torbox_get_token(self, ctx):#, link):
        # passing link as a command arg means you get sniped by the embed crawler
        # you'd need to wrap it in <> or `` to prevent embeds
        link = input()
        async with aiohttp.ClientSession() as s:
            r = await s.get(link, allow_redirects=False)
            print(await r.content.read())
            url = r.headers["Location"]
            r = await s.get(url, allow_redirects=False)
            cookies = [v for k, v in r.headers.items() if k == "Set-Cookie"]
            cookies.sort()  # just in case
            self.token = cookies[0].split(';')[0].split('=')[1]
            self.refresh_token = cookies[1].split(';')[0].split('=')[1]
            await self.refresh_db_auth()
            return await ctx.send("Successfully grabbed token")

    @commands.command(aliases=["tr_status"])
    async def torbox_status(self, ctx, name):
        if await self.refresh_db_auth():
            return await ctx.send("Authentication failed, reconfigure token")
        name = await self.fuzzy_torrent_by_name(ctx, name)
        if not isinstance(name, str):
            return
        async with aiohttp.ClientSession() as s:
            r = await s.get(f"{self.db_url}/torrents?select=download_speed,upload_speed,eta,download_state,"
                            f"progress,seeds,peers,name"
                            f"&name=eq.{name}", headers=self.hd_db_authed)
            if r.status != 200:
                self.bot.log(f"GET torrents returned {r.status}")
                return await ctx.send("Failed to fetch torrent information")
            r = await r.json()
            data = r[0]
            await self.send_torrent(ctx, data)

    @commands.command(aliases=["tr_watch", "tr_unwatch", "torbox_unwatch"])
    async def torbox_watch(self, ctx, name):
        if await self.refresh_db_auth():
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
        if await self.refresh_db_auth():
            return await ctx.send("Authentication failed, reconfigure token using "
                                  "`torbox_get_link` and `torbox_get_token`")
        name = await self.fuzzy_torrent_by_name(ctx, name)
        if not isinstance(name, str):
            return
        async with aiohttp.ClientSession() as s:
            r = await s.get(f"{self.db_url}/torrents?select=id,auth_id,download_state&name=eq.{name}",
                            headers=self.hd_db_authed)
            data = await r.json()
            data = data[0]
            if data["download_state"] != "paused":
                action = "pause"
            else:
                action = "resume"

            headers = self.get_api_headers(data["auth_id"])
            if "failed" in headers:
                return await ctx.send(f"Failed to fetch API token")
            r = await s.post(self.api_url,
                             data=json.dumps({"torrent_id": data["id"],
                                              "operation": action}),
                             headers=headers)
            r = await r.json()

            if "success" in r["detail"]:
                await ctx.send(f"{name} {'paused' if action == 'pause' else 'resumed'} succesfully")
            else:
                await ctx.send(f"Failed to {action} {name}")


def setup(bot):
    bot.add_cog(Loop(bot))
