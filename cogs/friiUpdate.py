import asyncio
import configparser
import json
import time
from datetime import datetime

import discord
import git
from discord.ext import commands
from github import Github

from cogs import sysupdates


class Loop(commands.Cog):
    def __init__(self, bot):
        self.conf = configparser.ConfigParser()
        self.conf.read("frii_update.ini")
        self.bot = bot
        self.channel = int(self.conf["Config"]["Channel ID"])
        self.role = int(self.conf["Config"]["Role ID"])
        self.ghAPI = Github(self.conf["Tokens"]["Github"],
                            per_page=20)  # let's not decimate the ratelimit after 4 seconds

        with open("info.json", "r") as j:
            c = json.load(j)
            self.repos = c["repos"]
            for i in self.repos:
                i[1] = discord.Color(i[1])

        # asyncio.run(self.updateLoop())

    async def send_embed(self, channel, title, url, description, datemsg, date, author, author_url, thumbnail, i):
        embed = discord.Embed(title=title, color=self.repos[i][1])
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

    async def updateLoop(self, check_sys_updates):
        await self.bot.wait_until_ready()
        channel = await self.bot.fetch_channel(self.channel)
        if "Last_Checked" in self.conf["Config"].keys():
            lastcheck = datetime.strptime(self.conf["Config"]["Last_Checked"], "%H%M%S %d%m%Y")
        else:
            lastcheck = datetime.utcnow()
        while True:
            ponged = False

            if check_sys_updates:
                ponged = await sysupdates.friiRSS.check_sysupdates(sysupdates, ponged, self.role, channel)

            for i in range(len(self.repos)):
                repo = git.Repo(self.repos[i][0])
                # NEW_COMMITS = {}
                origin = repo.remotes["origin"]
                ghRepo = self.ghAPI.get_repo(f"{origin.url[19:] if origin.url[-1] != '/' else origin.url[19:-1]}")
                branches = [branch.name for branch in repo.branches]
                repoName = origin.url.split(sep='/')[4]

                repo.git.fetch("-p")

                for branch in origin.refs:
                    if branch.remote_head == "HEAD" or branch.remote_head in branches:
                        pass
                    else:
                        repo.git.branch("--track", branch.remote_head, branch.name)
                        if not ponged:
                            await channel.send(f"<@&{self.role}> New branch(es) detected!")
                            ponged = True
                        await channel.send(f"{branch.remote_head} on {repoName}")

                for branch in repo.branches:
                    if branch.tracking_branch() not in origin.refs:
                        if not ponged:
                            await channel.send(f"<@&{self.role}> Branch(es) deleted!")
                            ponged = True
                        await channel.send(f"{branch.name} on {repoName}")

                        if repo.active_branch == branch:
                            if branch != repo.branches[0]:
                                repo.git.checkout(repo.branches[0].name)
                            else:
                                repo.git.checkout(repo.branches[1].name)
                        repo.git.branch("-D", branch.name)

                    print(
                        f"[{datetime.now().strftime('%H:%M:%S')}] Checking: {repoName} - {branch.name}")
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

                        await self.send_embed(channel,
                                              f"{repoName}: {commit.hexsha} on {branch.name}",
                                              f"{origin.url}/commit/{commit.hexsha}",
                                              commit.message,
                                              "Committed on ",
                                              time.asctime(time.gmtime(commit.committed_date)),
                                              author.login,
                                              author.html_url,
                                              author.avatar_url,
                                              i
                                              )

                for pull in ghRepo.get_pulls():
                    if pull.created_at > lastcheck:
                        if not ponged:
                            await channel.send(f"<@&{self.role}> New pr(s) detected!")
                            ponged = True

                        await self.send_embed(channel,
                                              f"{repoName}: #{pull.number} - {pull.title} {'(draft)' if pull.draft else ''}",
                                              pull.html_url,
                                              pull.body,
                                              "Opened on: ",
                                              pull.created_at,
                                              pull.user.login,
                                              pull.user.html_url,
                                              pull.user.avatar_url,
                                              i
                                              )

                    for comment in pull.get_issue_comments():
                        if comment.created_at > lastcheck:
                            await self.send_embed(channel,
                                                  f"{repoName} - New comment on pull #{pull.number}",
                                                  comment.html_url,
                                                  comment.body,
                                                  "Commented on: ",
                                                  comment.created_at,
                                                  comment.user.login,
                                                  comment.user.html_url,
                                                  comment.user.avatar_url,
                                                  i
                                                  )

                print(f"[{datetime.now().strftime('%H:%M:%S')}] Checking prs for {repoName}")
                prs = ghRepo.get_pulls(state="closed")
                limit = 20 if prs.totalCount >= 20 else prs.totalCount

                for pull in prs[:limit]:
                    if pull.merged and pull.merged_at > lastcheck:
                        await channel.send(
                            f"{repoName} - PR #{pull.number} merged at {pull.merged_at} by {pull.merged_by.login}")
                    elif pull.closed_at > lastcheck:
                        await channel.send(f"{repoName} - PR #{pull.number} closed at {pull.closed_at}")

            # this way pulls dont get re-detected every time the bot restarts
            lastcheck = datetime.utcnow()
            self.conf["Config"]["Last_Checked"] = lastcheck.strftime("%H%M%S %d%m%Y")
            with open("frii_update.ini", "w") as confFile:
                self.conf.write(confFile)

            await asyncio.sleep(900)

    @commands.command(aliases=("start", "run"))
    async def startLoop(self, ctx):
        await self.updateLoop(True)


def setup(bot):
    bot.add_cog(Loop(bot))
