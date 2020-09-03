import asyncio
import configparser
import datetime
import discord
import git
import json
import time
from discord.ext import commands
from github import Github

async def send_embed(channel, title, url, description, datemsg, date, author, author_url, thumbnail, i):
    embed = discord.Embed(title=title, color=repos[i][1])
    embed.set_author(name=author, url=author_url)
    embed.set_thumbnail(url=thumbnail)
    embed.url = url
    if len(description) >= 2000:
        # char limit for description is 2048
        # so leave 48 chars for the date
        description = description[:1997] + "..."
    else:
        description = description
    embed.description = description + "\n" + datemsg + str(date)
    await channel.send(embed=embed)


class Loop(commands.Cog):
    def __init__(self, bot):
        conf = configparser.ConfigParser()
        conf.read("frii_update.ini")
        self.bot = bot
        self.channel = int(conf["Config"]["Channel ID"])
        self.role = int(conf["Config"]["Role ID"])
        self.ghAPI = Github(conf["Tokens"]["Github"])

        with open("repos.json","r") as j:
            self.repos = json.load(j)
            for i in self.repos:
                i[1] = discord.Color(i[1])

        # asyncio.run(self.updateLoop())

    async def updateLoop(self):
        await self.bot.wait_until_ready()
        channel = await self.bot.fetch_channel(self.channel)
        while True:
            ponged = False
            for i in range(len(repos)):
                repo = git.Repo(repos[i][0])
                # NEW_COMMITS = {}
                origin = repo.remotes["origin"]
                ghRepo = self.ghAPI.get_repo(f"{origin.url[19:] if origin.url[-1] != '/' else origin.url[19:-1]}")
                branches = [branch.name for branch in repo.branches]

                repo.git.fetch("-p")

                for branch in origin.refs:
                    if branch.remote_head == "HEAD" or branch.remote_head in branches:
                        pass
                    else:
                        repo.git.branch("--track", branch.remote_head, branch.name)
                        if not ponged:
                            await channel.send(f"<@&{self.role}> New branch(es) detected!")
                            ponged = True
                        await channel.send(f"{branch.remote_head} on {origin.url.split(sep='/')[4]}")

                for branch in repo.branches:
                    if branch.tracking_branch() not in origin.refs:
                        if not ponged:
                            await channel.send(f"<@&{self.role}> Branch(es) deleted!")
                            ponged = True
                        await channel.send(f"{branch.name} on {origin.url.split(sep='/')[4]}")

                        if repo.active_branch == branch:
                            if branch != repo.branches[0]:
                                repo.git.checkout(repo.branches[0].name)
                            else:
                                repo.git.checkout(repo.branches[1].name)
                        repo.git.branch("-D", branch.name)

                for branch in repo.branches:
                    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Checking: {origin.url.split(sep='/')[4]} - {branch.name}")
                    occ = len(list(repo.iter_commits(branch.name)))  # old commit count
                    repo.git.checkout(branch.name)
                    repo.git.pull()
                    Clist = list(repo.iter_commits(branch.name))
                    ncc = len(Clist) - occ
                    for index in range(ncc):
                        commit = Clist[index]
                        author = ghRepo.get_commit(commit.hexsha).author
                        if not ponged:
                            await channel.send(
                                f"<@&{self.role}> New commit{'s' if ncc > 1 else ''} detected!")
                            ponged = True

                        await send_embed(channel,
                                         f"{origin.url.split(sep='/')[4]}: {commit.hexsha} on branch {branch.name}",
                                         f"{origin.url}/commit/{commit.hexsha}",
                                         commit.message,
                                         "Committed on ",
                                         time.asctime(time.gmtime(commit.committed_date)),
                                         author.login,
                                         author.html_url,
                                         author.avatar_url,
                                         i
                                         )

            await asyncio.sleep(900)

    @commands.command(aliases=("start", "run"))
    async def startLoop(self, ctx):
        await self.updateLoop()


def setup(bot):
    bot.add_cog(Loop(bot))
