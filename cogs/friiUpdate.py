import time, datetime  # i could probably change most of these to a from x import y
import discord
import git  # im being warned this is unneeded but im scared because idk how imports work
import re
import feedparser
import asyncio
import json, pickle
from sys import exc_info
from traceback import format_exception
from discord.ext import commands
from logzero import logger
from github import Github

# TODO maybe add issue and/or pr tracking idfk
# note: this will require some form of interaction with the github API 

# FORMAT FOR REPO: ["repo name", git.Repo("path/to/cloned/repo"), discord.Color(embed_colour)].
# Note that it will cause issues if the origin url ends in .git 
repos = pickle.load(open("repos.conf", "rb"))
nonobranches = ["gh-pages"]


async def getBranches(repo):
    branches = []  # repo.branches returns them as a git.refs.head.Head and i want just the name
    for i in repo.branches:
        branches.append(i.name)
    return branches


async def findNewBranches(repo, origin):
    nBranches = []
    existingBranches = await getBranches(repo)
    for i in origin.refs:
        name = str(i).split(sep="/")[1]
        if name in nonobranches:
            print("Branch", name, "NOT being tracked")
        # for some reason these branches just dont work properly.
        # ideally i'd figure out why and fix it, but i dont feel like it soo

        elif name != "HEAD" and name not in existingBranches:
            nBranches.append(name)
    return nBranches


class loop(commands.Cog):
    is_active = True
    sleepTime = 900  # default to 900s (15min) wait time
    branches = []

    def __init__(self, bot):
        self.bot = bot
        gittoken = open("github_token.txt").readline()[:-1]  # i did this because new lines 
        self.ghAPI = Github(gittoken)  # if it works dont touch it

    async def send_embed(self, embed):
        channel = await self.get_channel()
        await channel.send(embed=embed)

    async def get_channel(self):
        channel = self.bot.get_channel(699664761809273002)
        return channel

    async def send(self, content):
        channel = await self.get_channel()
        await channel.send(content)

    @commands.command(aliases=["sleepTime", "delay", "time"])
    async def interval(self, ctx, interval):
        """Change the wait time for the updateloop"""
        try:
            int(interval)
        except ValueError:
            await ctx.send("Invalid integer")
        else:
            self.sleepTime = int(interval)
            await ctx.send(f"Set delay to {interval}s")

    async def TNB(self, repo, nbranches, name):  # set up a tracking branch for new branches
        if not self.ponged:
            self.ponged = True
            await self.send("<@&700345049191415920> New branch(es) detected!")
        for i in nbranches:
            string = "origin/" + i
            repo.git.checkout(string, track=True)
            string = name + ": New branch - " + i
            print("New branch detected! Name:", i)
            await self.send(string)

    async def yeetDeadBranches(self, repo, branches, name):  # fuck, git fetch -p exists
        out = ""
        retries = 0
        while retries < 4:
            try:
                out = repo.git.remote("prune", "--dry-run", "origin")
            except Exception:
                logger.warn(f"Exception occurred in prune, assuming connection and waiting: {exc_info()}")
                logger.info(f"Retrying in 30s... ({retries + 1}/4)")
                await asyncio.sleep(30)
                retries += 1
            else:
                break
        if retries == 4:
            raise Exception("Maximum retries reached, aborting")
        elif retries > 0:
            logger.info(":handup:")

        dB = []
        dBName = ""
        for i in re.finditer("\[would prune\]", out):
            start = i.end() + 8
            for i in out[start:]:
                if i == '\n':
                    break
                dBName += i
            dB.append(dBName)
            dBName = ""
        for i in dB:
            if repo.active_branch.name == i:
                if branches[0] != repo.active_branch.name:
                    repo.git.checkout(branches[0])
                else:
                    repo.git.checkout(branches[1])
            if i not in nonobranches:
                repo.delete_head(i)
            refName = "refs/remotes/origin/" + i  # only the jankest possible methods
            repo.git.update_ref("-d", refName)  # TODO exception handling
            msg = "Deleted branch " + i + " in repo " + name
            await self.send(msg)
            branches = await getBranches(
                repo)  # just yeeted a branch that could cause the if else above to fail. Probably unlikely but better safe than sorry
        out = await getBranches(repo)
        return out

    async def updateLoop(self):
        print("Tracking: ")
        for i in repos:
            print(i[1].remotes.origin.url)
        print("")

        prDict = {}
        with open("prs.json") as j:
            if len(j.read()) > 2:
                j.seek(0, 0)
                prDict = json.load(j)
        # print(prDict) #DEBUG
        while self.is_active:

            now = datetime.datetime.now().strftime("%H:%M:%S")
            print(f"[{now}] Checking for sysupdates")

            retries = 0
            while retries < 4:
                try:
                    updateFeed = feedparser.parse("https://yls8.mtheall.com/ninupdates/feed.php")
                except Exception:
                    logger.warn(f"Exception occurred in reading feed, assuming connection and waiting: {exc_info()}")
                    logger.info(f"Retrying in 30s... ({retries + 1}/4)")
                    await asyncio.sleep(30)
                    retries += 1
                else:
                    break
            if retries == 4:
                raise Exception("Maximum retries reached, aborting")
            elif retries > 0:
                logger.info(":handup:")

            for entry in updateFeed.entries:
                # handle update tracking file not existing

                try:
                    f = open("./updateTracking.txt", "r")
                except FileNotFoundError:
                    f = open("./updateTracking.txt", "a")
                    f.write(f"{entry.title[7:]}\n")
                    f.close()
                    f = open("./updateTracking.txt", "r")

                if entry.title[7:] not in f.read():
                    retries = 0
                    while retries < 4:
                        try:
                            await self.send("<@&700345049191415920> New firmware version detected!")
                            await self.send(f"Version {entry.title[7:]} released on: {entry.published}")
                        except Exception:
                            logger.warn(f"Exception occurred in send, assuming connection and waiting: {exc_info()}")
                            logger.info(f"Retrying in 30s... ({retries + 1}/4)")
                            await asyncio.sleep(30)
                            retries += 1
                        else:
                            break
                    if retries == 4:
                        raise Exception("Maximum retries reached, aborting")
                    elif retries > 0:
                        logger.info(":handup:")

                    f.close()
                    f = open("./updateTracking.txt", "a")
                    f.write(f"{entry.title[7:]}\n")

            self.ponged = False
            for i in repos:
                NO_NEW = {}
                NO_NEW_PULLS = True
                currentCommits = {}
                remoteBranches = []

                origin = i[1].remotes["origin"]
                assert origin.exists()  # imagine if this failed

                repoName = str(i[1].remotes.origin.url)[19:]
                if repoName[-1] == '/':
                    repoName = repoName[:-1]

                branches = await getBranches(i[1])
                # currentCommit = i[1].commit('master') 
                for b in branches:
                    # print(b, i[1].commit(b)) #DEBUG
                    currentCommits[b] = i[1].commit(b)

                retries = 0
                while retries < 4:
                    try:
                        i[1].git.fetch()
                    except Exception:
                        logger.warn(f"Exception occurred in fetch, assuming connection and waiting: {exc_info()}")
                        logger.info(f"Retrying in 30s... ({retries + 1}/4)")
                        await asyncio.sleep(30)
                        retries += 1
                    else:
                        break
                if retries == 4:
                    raise Exception("Maximum retries reached, aborting")
                elif retries > 0:
                    logger.info(":handup:")

                retries = 0
                while retries < 4:
                    try:
                        ghRepo = self.ghAPI.get_repo(repoName)
                    except Exception:
                        logger.warn(f"Exception occurred in gh api init, assuming connection and waiting: {exc_info()}")
                        logger.info(f"Retrying in 30s... ({retries + 1}/4)")
                        await asyncio.sleep(30)
                        retries += 1
                    else:
                        break

                pulls = ghRepo.get_pulls()
                prcount = 0
                if repoName not in prDict and pulls.totalCount > 0:
                    prDict[repoName] = {}

                for pull in pulls:
                    if str(pull.number) in prDict[repoName]:
                        if pull.comments > prDict[repoName][str(pull.number)][0]:
                            NO_NEW_PULLS = False
                            # else NO_NEW_PULLS stays True
                    else:  # new pull opened
                        NO_NEW_PULLS = False
                    prcount += 1

                # print(NO_NEW_PULLS) #DEBUG

                if retries == 4:
                    raise Exception("Maximum retries reached, aborting")
                elif retries > 0:
                    logger.info(":handup:")

                nbranches = await findNewBranches(i[1], origin)
                if nbranches != []:
                    await self.TNB(i[1], nbranches, i[0])

                for n in nbranches:
                    currentCommits[n] = i[1].commit("origin/HEAD")

                for x in i[1].remotes["origin"].refs:
                    remoteBranches.append(str(x).split(sep="/")[1])
                # print(branches) #DEBUG 
                branches = await self.yeetDeadBranches(i[1], branches, i[0])
                cSinceChange = -1 * len(branches)
                for branch in branches:
                    now = datetime.datetime.now().strftime("%H:%M:%S")
                    print(f"[{now}] Checking: {i[0]} - {branch}")
                    i[1].git.checkout(branch)
                    cDiff = -1  # cSinceChange is per repo, this is per branch
                    # cDiff = 2 #DEBUG
                    retries = 0
                    while retries < 4:
                        try:
                            i[1].git.pull()
                        except Exception:
                            logger.warn(f"Exception occurred in pull, assuming connection and waiting: {exc_info()}")
                            logger.info(f"Retrying in 30s... ({retries + 1}/4)")
                            await asyncio.sleep(30)
                            retries += 1
                        else:
                            break
                    if retries == 4:
                        raise Exception("Maximum retries reached, aborting")
                    elif retries > 0:
                        logger.info(":handup:")

                    # print("cC: ",currentCommits[branch]) #DEBUG
                    commitList = list(i[1].iter_commits(branch))
                    for j in commitList:
                        cSinceChange += 1
                        cDiff += 1
                        # print(branch,j) #DEBUG
                        if j == currentCommits[branch]:
                            if cDiff == 0:
                                NO_NEW[branch] = True
                            else:
                                NO_NEW[branch] = False
                            break
                    if branch not in NO_NEW:
                        # this can happen occasionally, i as of yet have no clue why
                        # from what i can tell its current commit is a commit with no branch which um
                        # why the fuck can that exist
                        # ok i have learnt why the fuck that can exist
                        # i hate it
                        NO_NEW[branch] = True
                        logger.warning(f"{branch} marked as having no new due to not existing in it previously")
                        # i have literally no idea if this just goes away, or if there's a way to fix it.

                    if not NO_NEW[branch]:  # only show info if there are new commits
                        if not self.ponged:
                            await self.send(
                                f"<@&700345049191415920> New commit{'s' if cDiff > 1 else ''} detected!")  # mention the git-update role
                            self.ponged = True  # only mention once 
                        commitList.reverse()
                        commitListLength = len(commitList)
                        startPoint = commitListLength - cDiff
                        for k in range(startPoint,
                                       commitListLength):  # for some reason end is exlusive but start is inclusive
                            commit = commitList[k]

                            EMBEDNAME = f"{i[0]} - {branch}: {str(commit.hexsha)}"

                            # creating commit embed
                            commitURL = f"{i[1].remotes.origin.url}/commit/{commit.hexsha}"
                            commitTime = time.asctime(time.gmtime(commit.authored_date))
                            embed = discord.Embed(title=EMBEDNAME, color=i[2])

                            print(f"New commit detected! ID: {commit.hexsha}")

                            retries = 0
                            while retries < 4:
                                try:
                                    author = ghRepo.get_commit(commit.hexsha).author
                                except Exception:
                                    logger.warn(
                                        f"Exception occurred in fetching author, assuming connection and waiting: {exc_info()}")
                                    logger.info(f"Retrying in 30s... ({retries + 1}/4)")
                                    await asyncio.sleep(30)
                                    retries += 1
                                else:
                                    break
                            if retries == 4:
                                raise Exception("Maximum retries reached, aborting")
                            elif retries > 0:
                                logger.info(":handup:")

                            embed.set_author(name=author.login, url=author.html_url)  # , icon_url=author.avatar_url)
                            embed.url = commitURL
                            embed.set_thumbnail(url=author.avatar_url)
                            if len(str(commit.message)) >= 2000:
                                # char limit for description is 2048
                                # 48 chars is enough for the commit date
                                commitmessage = str(commit.message)[:1997] + "..."
                            else:
                                commitmessage = str(commit.message)
                            embed.description = commitmessage + "\nCommitted on " + str(commitTime)

                            retries = 0
                            while retries < 4:
                                try:
                                    await self.send_embed(embed)
                                except Exception:
                                    logger.warn(
                                        f"Exception occurred in send_embed, assuming connection and waiting: {exc_info()}")
                                    logger.info(f"Retrying in 30s... ({retries + 1}/4)")
                                    await asyncio.sleep(30)
                                    retries += 1
                                else:
                                    break
                            if retries == 4:
                                raise Exception("Maximum retries reached, aborting")
                            elif retries > 0:
                                logger.info(":handup:")

                # print(NO_NEW_PULLS) #DEBUG
                if not NO_NEW_PULLS:

                    for pull in pulls:
                        # print("executed") #DEBUG
                        if str(str(pull.number)) in prDict[repoName].keys():
                            if pull.comments > prDict[repoName][str(pull.number)][0]:
                                comments = pull.get_issue_comments()
                                for comment in comments[prDict[repoName][str(pull.number)][0]:]:
                                    embedTitle = f"{i[0]} - New comment on pull #{pull.number}"
                                    embed = discord.Embed(title=embedTitle, color=i[2])
                                    commentTime = comment.created_at.strftime("%a %b %d %H:%M:%S %Y %z")

                                    retries = 0
                                    while retries < 4:
                                        try:
                                            author = comment.user
                                        except Exception:
                                            logger.warn(
                                                f"Exception occurred in fetching author, assuming connection and waiting: {exc_info()}")
                                            logger.info(f"Retrying in 30s... ({retries + 1}/4)")
                                            await asyncio.sleep(30)
                                            retries += 1
                                        else:
                                            break
                                    if retries == 4:
                                        raise Exception("Maximum retries reached, aborting")
                                    elif retries > 0:
                                        logger.info(":handup:")

                                    embed.url = comment.html_url
                                    embed.set_author(name=author.login, url=author.html_url)
                                    embed.set_thumbnail(url=author.avatar_url)
                                    if len(str(comment.body)) >= 2000:
                                        commentbody = str(comment.body)[:1997] + "..."
                                    else:
                                        commentbody = str(comment.body)
                                    embed.description = commentbody + "\nOpened on " + str(commentTime)

                                    retries = 0
                                    while retries < 4:
                                        try:
                                            await self.send_embed(embed)
                                        except Exception:
                                            logger.warn(
                                                f"Exception occurred in send_embed, assuming connection and waiting: {exc_info()}")
                                            logger.info(f"Retrying in 30s... ({retries + 1}/4)")
                                            await asyncio.sleep(30)
                                            retries += 1
                                        else:
                                            break
                                    if retries == 4:
                                        raise Exception("Maximum retries reached, aborting")
                                    elif retries > 0:
                                        logger.info(":handup:")

                        else:
                            if not self.ponged:
                                await self.send(
                                    f"<@&700345049191415920> New pr{'s' if prcount > 1 else ''} detected!")  # mention the git-update role
                                self.ponged = True  # only mention once

                            embedTitle = f"{i[0]} - {pull.title} (#{pull.number})"
                            embed = discord.Embed(title=embedTitle, color=i[2])
                            openedTime = pull.created_at.strftime("%a %b %d %H:%M:%S %Y %z")

                            print(f"New pr detected! Number: {pull.number}")

                            retries = 0
                            while retries < 4:
                                try:
                                    author = pull.user
                                except Exception:
                                    logger.warn(
                                        f"Exception occurred in fetching author, assuming connection and waiting: {exc_info()}")
                                    logger.info(f"Retrying in 30s... ({retries + 1}/4)")
                                    await asyncio.sleep(30)
                                    retries += 1
                                else:
                                    break
                            if retries == 4:
                                raise Exception("Maximum retries reached, aborting")
                            elif retries > 0:
                                logger.info(":handup:")

                            embed.set_author(name=author.login, url=author.html_url)
                            embed.url = pull.html_url
                            embed.set_thumbnail(url=author.avatar_url)
                            if len(str(pull.body)) >= 2000:
                                pullbody = str(pull.body)[:1997] + "..."
                            else:
                                pullbody = str(pull.body)
                            embed.description = pullbody + "\nOpened on " + str(openedTime)

                            retries = 0
                            while retries < 4:
                                try:
                                    await self.send_embed(embed)
                                except Exception:
                                    logger.warn(
                                        f"Exception occurred in send_embed, assuming connection and waiting: {exc_info()}")
                                    logger.info(f"Retrying in 30s... ({retries + 1}/4)")
                                    await asyncio.sleep(30)
                                    retries += 1
                                else:
                                    break
                            if retries == 4:
                                raise Exception("Maximum retries reached, aborting")
                            elif retries > 0:
                                logger.info(":handup:")

                    if pulls.totalCount > 0:
                        for pull in pulls:
                            prDict[repoName][str(pull.number)] = [pull.comments]

                todel = []
                if repoName in prDict:
                    for num in prDict[repoName].keys():
                        state = ghRepo.get_pull(int(num)).state
                        if state != "open":
                            await self.send(f"{i[0]} - PR #{num} {state}")
                            todel.append(num)
                for n in todel: del prDict[repoName][n]

                if cSinceChange > 0:
                    cSinceMessage = f"There have been {cSinceChange} commits since last check for {i[0]}."
                    retries = 0
                    while retries < 4:
                        try:
                            await self.send(cSinceMessage)
                        except Exception:
                            logger.warn(f"Exception occurred in send, assuming connection and waiting: {exc_info()}")
                            logger.info(f"Retrying in 30s... ({retries + 1}/4)")
                            await asyncio.sleep(30)
                            retries += 1
                        else:
                            break
                    if retries == 4:
                        raise Exception("Maximum retries reached, aborting")
                    elif retries > 0:
                        logger.info(":handup:")

            with open("prs.json", 'w') as j:
                json.dump(prDict, j)  # write any changes

            sleepTime = self.sleepTime
            await asyncio.sleep(sleepTime)
            # TODO find a better way to do this

    @commands.command(aliases=["startloop", "start", "run"])
    async def startLoop(self, ctx):
        """Start the loop (of doom)"""
        await self.updateLoop()

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        await self.send("<@&700345049191415920> An unhandled exception has occurred!")
        msg = "".join(format_exception(type(error), error, error.__traceback__))
        logger.error(msg)
        for chunk in [msg[i:i + 1800] for i in range(0, len(msg), 1800)]:
            await self.send(f'```\n{chunk}\n```')


def setup(bot):
    bot.add_cog(loop(bot))
