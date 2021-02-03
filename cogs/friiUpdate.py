import asyncio
import configparser
import json
import time
from datetime import datetime

import discord
import git
from discord.ext import commands
from gql import gql, Client
from gql.transport.aiohttp import AIOHTTPTransport


from cogs import sysupdates


class Loop(commands.Cog):
    def __init__(self, bot):
        self.conf = configparser.ConfigParser()
        self.conf.read("frii_update.ini")
        self.bot = bot
        self.channel = int(self.conf["Config"]["Channel ID"])
        self.role = int(self.conf["Config"]["Role ID"])
        self.PRlimit = int(self.conf["Config"]["Pull limit"])
        self.CommentLimit = int(self.conf["Config"]["Comment limit"])
        self.RVlimit = int(self.conf["Config"]["Review limit"])
        self.RLlimit = int(self.conf["Config"]["Release limit"])
        self.interval = int(self.conf["Config"]["Interval"])

        with open("info.json", "r") as j:
            c = json.load(j)
            self.repos = c["repos"]
            for i in self.repos:
                i[1] = discord.Color(i[1])

        # asyncio.run(self.updateLoop())

    async def send_embed(self, channel, title, url, description, datemsg, date, author, author_url, thumbnail, i):
        embed = discord.Embed(title=title, color=self.repos[i][1])
        if author_url != "null":
            embed.set_author(name=author, url=author_url)
        else:
            embed.set_author(name=author)
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
        if "Last checked" in self.conf["Config"].keys():
            lastcheck = datetime.strptime(self.conf["Config"]["Last checked"], "%H%M%S %d%m%Y")
        else:
            lastcheck = datetime.utcnow()

        reviewStates = {
            "APPROVED": "Changes approved on",
            "CHANGES_REQUESTED": "Changes requested on",
            "COMMENTED": "Review submitted for",
            "DISMISSED": "Review submitted for",
            "PENDING": "Review submitted for"
        }

        headers = {"Authorization": f"Bearer {self.conf['Tokens']['github']}"}
        transport = AIOHTTPTransport(url="https://api.github.com/graphql", headers=headers)
        async with Client(transport=transport, fetch_schema_from_transport=True) as session:
            while True:
                ponged = False

                if check_sys_updates:
                    ponged = await sysupdates.friiRSS.check_sysupdates(sysupdates, ponged, self.role, channel)

                for i in range(len(self.repos)):
                    repo = git.Repo(self.repos[i][0])
                    # NEW_COMMITS = {}
                    origin = repo.remotes["origin"]

                    branches = [branch.name for branch in repo.branches]
                    newBranches = []
                    repoName = origin.url.split(sep='/')[4]
                    repoAuthor = origin.url.split(sep='/')[3]

                    repo.git.fetch("-p")

                    for branch in origin.refs:
                        if branch.remote_head == "HEAD" or branch.remote_head in branches:
                            pass
                        else:
                            repo.git.branch("--track", branch.remote_head, branch.name)
                            if not ponged:
                                await channel.send(f"<@&{self.role}> New branch(es) detected!")
                                ponged = True
                            await channel.send(f"New branch: {branch.remote_head} on {repoName}")

                            newBranches.append(branch.remote_head)

                    for branch in repo.branches:
                        if branch.tracking_branch() not in origin.refs:
                            if not ponged:
                                await channel.send(f"<@&{self.role}> Branch(es) deleted!")
                                ponged = True
                            await channel.send(f"Deleted branch: {branch.name} on {repoName}")

                            if repo.active_branch == branch:
                                if branch != repo.branches[0]:
                                    repo.git.checkout(repo.branches[0].name)
                                else:
                                    repo.git.checkout(repo.branches[1].name)
                            repo.git.branch("-D", branch.name)
                            continue

                        print(
                            f"[{datetime.now().strftime('%H:%M:%S')}] Checking: {repoName} - {branch.name}")
                        if branch.name in newBranches and origin.refs["HEAD"].commit in list(repo.iter_commits(branch.name)):
                            occ = len(list(repo.iter_commits(origin.refs["HEAD"].name)))
                        else:
                            occ = len(list(repo.iter_commits(branch.name)))
                        repo.git.checkout(branch.name)
                        repo.git.pull()
                        Clist = list(repo.iter_commits(branch.name))
                        ncc = len(Clist) - occ
                        res = []

                        if ncc > 0:
                            req = """query($owner:String!, $name:String!, $branch:String!, $ncc:Int!) {
                              repository(owner: $owner, name: $name) {
                                ref(qualifiedName: $branch) {
                                  target {
                                    ... on Commit {
                                      history(first: $ncc) {
                                        pageInfo {
                                          endCursor
                                        }
                                        edges {
                                          node {
                                            author {
                                              avatarUrl
                                              user {login url}
                                            }
                                          }
                                        }
                                      }
                                    }
                                  }
                                }
                              }
                            }"""
                            params = {"owner": repoAuthor,
                                      "name": repoName,
                                      "branch": branch.name,
                                      "ncc": ncc if ncc <= 100 else 100}
                            result = await session.execute(gql(req), variable_values=params)
                            res = result["repository"]["ref"]["target"]["history"]["edges"]
                        if ncc > 100:
                            req = """query($owner:String!, $name:String!, $branch:String!, $cursor:String, $count:Int!) {
                                      repository(owner: $owner, name: $name) {
                                        ref(qualifiedName: $branch) {
                                          target {
                                            ... on Commit {
                                              history(after: $cursor, first: $count) {
                                                pageInfo {
                                                  endCursor
                                                }
                                                edges {
                                                  node {
                                                    author {
                                                      avatarUrl
                                                      user {login url}
                                                    }
                                                  }
                                                }
                                              }
                                            }
                                          }
                                        }
                                      }
                                    }"""
                            left = ncc-100
                            while left > 0:
                                params = {"owner": repoAuthor,
                                          "name": repoName,
                                          "branch": branch.name,
                                          "cursor": result["repository"]["ref"]["target"]["history"]["pageInfo"]["endCursor"],
                                          "count": left if left <= 100 else 100}
                                result = await session.execute(gql(req), variable_values=params)
                                res += result["repository"]["ref"]["target"]["history"]["edges"]
                                left -= 100

                        for index in reversed(range(ncc)):
                            commit = Clist[index]
                            author = res[index]["node"]["author"]

                            if author["user"] is None: # fukin edge cases reeeee
                                login = commit.author.name
                                authorUrl = "null"
                            else:
                                login = author["user"]["login"]
                                authorUrl = author["user"]["url"]

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
                                                  login,
                                                  authorUrl,
                                                  author["avatarUrl"],
                                                  i)

                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Fetching GitHub information for {repoName}")
                    req = """
                    query ($owner:String!, $repo_name:String!, $Plimit:Int!, $Climit:Int!, $RVlimit:Int!, $RLlimit:Int!) {
                        repository(owner:$owner, name:$repo_name) {
                          pullRequests(last:$Plimit) {
                            nodes {
                              author {
                                avatarUrl
                                login
                                url
                              }
                              body
                              closed
                              closedAt
                              comments (last: $Climit) { nodes {
                                author {
                                  avatarUrl
                                  login
                                  url
                                }
                                body
                                createdAt
                                url
                              }}
                              reviews (last: $RVlimit) { nodes {
                                author {
                                  avatarUrl
                                  login
                                  url
                                }
                                comments (last: $Climit) { nodes {
                                  author {
                                    avatarUrl
                                    login
                                    url
                                  }
                                  body
                                  createdAt
                                  diffHunk
                                  id
                                  url
                                }}
                                body
                                createdAt
                                state
                                url
                              }}
                              createdAt
                              isDraft
                              merged
                              mergedAt
                              mergedBy {login}
                              number
                              title
                              url
                            }
                          }
                          releases (last: $RLlimit){
                            nodes {
                              author { 
                                login
                                url
                                avatarUrl
                              }
                              description
                              isPrerelease
                              name
                              publishedAt
                              url
                            }
                          }
                      }
                    }"""
                    params = {"owner": repoAuthor,
                              "repo_name": repoName,
                              "Plimit": self.PRlimit,
                              "Climit": self.CommentLimit,
                              "RVlimit": self.RVlimit,
                              "RLlimit": self.RLlimit
                              }
                    result = await session.execute(gql(req), variable_values=params)
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Checking prs for {repoName}")
                    pulls = result["repository"]["pullRequests"]["nodes"]

                    for pull in pulls:
                        createdAt = datetime.strptime(pull["createdAt"], "%Y-%m-%dT%H:%M:%SZ")
                        if createdAt > lastcheck:
                            if not ponged:
                                await channel.send(f"<@&{self.role}> New pr(s) detected!")
                                ponged = True

                            await self.send_embed(channel,
                                                  f"{repoName}: #{pull['number']} - {pull['title']} "
                                                  f"{'[DRAFT]' if pull['isDraft'] else ''}",
                                                  pull['url'],
                                                  pull['body'],
                                                  "Opened on: ",
                                                  createdAt,
                                                  pull["author"]["login"],
                                                  pull["author"]["url"],
                                                  pull["author"]["avatarUrl"],
                                                  i)

                        for comment in pull["comments"]["nodes"]:
                            CcreatedAt = datetime.strptime(comment["createdAt"], "%Y-%m-%dT%H:%M:%SZ")
                            if CcreatedAt > lastcheck:
                                await self.send_embed(channel,
                                                      f"{repoName} - New comment on {pull['title']} (#{pull['number']})",
                                                      comment["url"],
                                                      comment["body"],
                                                      "Commented on: ",
                                                      CcreatedAt,
                                                      comment["author"]["login"],
                                                      comment["author"]["url"],
                                                      comment["author"]["avatarUrl"],
                                                      i)

                        for review in pull["reviews"]["nodes"]:
                            RcreatedAt = datetime.strptime(review["createdAt"], "%Y-%m-%dT%H:%M:%SZ")
                            if RcreatedAt > lastcheck and review['body']:
                                # the way reviews work is completely insane
                                # github is fantastic and creates a new review with no body for *any* review comment
                                # there's no point sending this every time that happens.
                                await self.send_embed(channel,
                                                      f"{repoName} - {reviewStates[review['state']]} {pull['title']} (#{pull['number']}) {'[PENDING]' if review['state'] == 'PENDING' else ''}",
                                                      review['url'],
                                                      review['body'],
                                                      "Submitted on: ",
                                                      RcreatedAt,
                                                      review['author']['login'],
                                                      review['author']['url'],
                                                      review['author']['avatarUrl'],
                                                      i)

                            for comment in review['comments']["nodes"]:
                                CcreatedAt = datetime.strptime(comment["createdAt"], "%Y-%m-%dT%H:%M:%SZ")
                                if CcreatedAt > lastcheck:
                                    embed = discord.Embed(title=f"{repoName} - New review comment on {pull['title']} (#{pull['number']})")
                                    embed.set_author(name=comment['author']['login'], url=comment['author']['url'], icon_url=comment['author']['avatarUrl'])
                                    if len(comment['body']) > 1020: #limit for embed fields is 1024 chars
                                        embed.insert_field_at(0, name="Comment", value=f"{comment['body'][:1020]} ...")
                                    else:
                                        embed.insert_field_at(0, name="Comment", value=comment['body'])
                                    if len(comment['diffHunk']) > 1020:
                                        print(f"[{datetime.now().strftime('%H:%M:%S')}] Diff not shown for review comment {comment['id']}")
                                    else:
                                        embed.insert_field_at(1, name="Diff", value=f"```diff\n{comment['diffHunk']}```")

                                    await channel.send(embed=embed)

                        if pull["closed"]:
                            closedAt = datetime.strptime(pull["closedAt"], "%Y-%m-%dT%H:%M:%SZ")
                            if pull["merged"]:
                                mergedAt = datetime.strptime(pull["mergedAt"], "%Y-%m-%dT%H:%M:%SZ")
                                if mergedAt > lastcheck:
                                    await channel.send(
                                        f"{repoName} - {pull['title']} (#{pull['number']}) merged at {mergedAt} by {pull['mergedBy']['login']}")
                            elif closedAt > lastcheck:
                                await channel.send(f"{repoName} - {pull['title']} (#{pull['number']}) closed at {closedAt}")

                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Checking releases for {repoName}")
                    releases = result["repository"]["releases"]["nodes"]
                    for release in releases:
                        publishedAt = datetime.strptime(release["publishedAt"], "%Y-%m-%dT%H:%M:%SZ")
                        if publishedAt > lastcheck:
                            if not ponged:
                                await channel.send(f"<@&{self.role}> New release detected!")
                                ponged = True
                            await self.send_embed(channel,
                                                  f"{repoName} - {'[PRERELEASE]' if release['isPrerelease'] else ''} Release {release['name']}",
                                                  release["url"],
                                                  release["description"],
                                                  "Published on: ",
                                                  publishedAt,
                                                  review["author"]["login"],
                                                  review["author"]["url"],
                                                  review["author"]["avatarUrl"],
                                                  i)

                # this way things don't get re-detected every time the bot restarts
                lastcheck = datetime.utcnow()
                self.conf["Config"]["Last checked"] = lastcheck.strftime("%H%M%S %d%m%Y")
                with open("frii_update.ini", "w") as confFile:
                    self.conf.write(confFile)

                await asyncio.sleep(self.interval)

    @commands.command(aliases=("start", "run"))
    async def startLoop(self, ctx):
        await self.updateLoop(bool(self.conf["Config"]["Check sysupdates"]))

    @commands.command()
    async def interval(self, ctx, interval):
        """Changes the amount of time the bot waits between checks.
        Usage: `.interval <time (s)>`"""
        try:
            int(interval)
        except ValueError:
            await ctx.send("Interval must be an integer")
            return
        self.interval = int(interval)
        await ctx.send(f"Interval set to {self.interval} seconds")


def setup(bot):
    bot.add_cog(Loop(bot))
