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

GHtimestring = "%Y-%m-%dT%H:%M:%SZ"


class Loop(commands.Cog):
    def __init__(self, bot):
        self.conf = configparser.ConfigParser()
        self.conf.read("frii_update.ini")
        self.bot = bot
        self.channel = int(self.conf["Config"]["Channel ID"])
        self.role = int(self.conf["Config"]["Role ID"])
        self.Plimit = int(self.conf["Config"]["Pull limit"])
        self.Climit = int(self.conf["Config"]["Comment limit"])
        self.RVlimit = int(self.conf["Config"]["Review limit"])
        self.RLlimit = int(self.conf["Config"]["Release limit"])
        self.Ilimit = int(self.conf["Config"]["Issue limit"])
        self.PClimit = int(self.conf["Config"]["Commit limit"])

        with open("info.json", "r") as j:
            c = json.load(j)
            self.repos = c["repos"]
            for i in self.repos:
                i[1] = discord.Color(i[1])

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

    async def main(self, channel):
        reviewStates = {
            "APPROVED": "Changes approved on",
            "CHANGES_REQUESTED": "Changes requested on",
            "COMMENTED": "Review submitted for",
            "DISMISSED": "Review submitted for",
            "PENDING": "Review submitted for"
        }
        lastcheck = self.bot.lastcheck

        headers = {"Authorization": f"Bearer {self.conf['Tokens']['github']}"}
        transport = AIOHTTPTransport(url="https://api.github.com/graphql", headers=headers)
        async with Client(transport=transport, fetch_schema_from_transport=True) as session:
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
                        if not self.bot.ponged:
                            await channel.send(f"<@&{self.role}> New branch(es) detected!")
                            self.bot.ponged = True
                        await channel.send(f"New branch: {branch.remote_head} on {repoName}")

                        newBranches.append(branch.remote_head)

                for branch in repo.branches:
                    if branch.tracking_branch() not in origin.refs:
                        if not self.bot.ponged:
                            await channel.send(f"<@&{self.role}> Branch(es) deleted!")
                            self.bot.ponged = True
                        await channel.send(f"Deleted branch: {branch.name} on {repoName}")

                        if repo.active_branch == branch:
                            if branch != repo.branches[0]:
                                repo.git.checkout(repo.branches[0].name)
                            else:
                                repo.git.checkout(repo.branches[1].name)
                        repo.git.branch("-D", branch.name)
                        continue

                    self.bot.log(f"Checking: {repoName} - {branch.name}")
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

                        if not self.bot.ponged:
                            await channel.send(
                                f"<@&{self.role}> New commit{'s' if ncc > 1 else ''} detected!")
                            self.bot.ponged = True

                        self.bot.log(f"New commit detected! ID: {commit.hexsha}")
                        await self.send_embed(channel,
                                              f"{repoName}: {commit.hexsha} on {branch.name}",
                                              f"https://github.com/{repoAuthor}/{repoName}/commit/{commit.hexsha}",
                                              commit.message,
                                              "Committed on ",
                                              time.asctime(time.gmtime(commit.committed_date)),
                                              login,
                                              authorUrl,
                                              author["avatarUrl"],
                                              i)

                if self.Plimit + self.RVlimit + self.RLlimit + self.Ilimit > 0:
                    self.bot.log(f"Fetching GitHub information for {repoName}")
                    if self.Climit == 0 and self.RVlimit > 0:
                        self.bot.log("Warning: Comment limit set to 0 but Review limit > 0, this may cause unintended behaviour")
                    if self.Plimit == 0 and self.RVlimit > 0:
                        self.bot.log(f"Ignoring Review limit of {self.RVlimit} since Pull request limit is 0")
                        self.RVlimit = 0

                    # i wouldnt have to do any of this
                    # but no graphql decided that an unused variable is an error
                    # always, no way to turn it off
                    # fucks sake
                    args = ["$Plimit:Int!", "$Climit:Int!", "$RVlimit:Int!",
                            "$RLlimit:Int!", "$Ilimit:Int!", "$PClimit:Int!"]
                    using = []
                    for x in args:
                        if eval(f"self.{x.split(sep=':')[0][1:]}") > 0:  # look i know
                            using.append(x)                              # no excuses anymore

                    # right what's about to happen probably needs some explanation
                    # i dont want to copy the same massive fuck off string for every configuration you could have
                    # k thanks end of explanation
                    req = """
                    query ($owner:String!,
                        $repo_name:String!,""" + ",".join(using) + "){" + """
                        repository(owner:$owner, name:$repo_name){""" + ("""
                          pullRequests(last:$Plimit){
                            nodes {
                              author {
                                avatarUrl
                                login
                                url
                              }
                              body
                              closed
                              closedAt""" if self.Plimit > 0 else '') + ("""
                              comments (last: $Climit){ nodes {
                                author {
                                  avatarUrl
                                  login
                                  url
                                }
                                body
                                createdAt
                                url
                              }}""" if self.Climit > 0 and self.Plimit > 0 else '') + ("""
                              commits (last: $PClimit){ nodes {
                                commit {
                                  committedDate
                                  author {
                                    avatarUrl
                                    name
                                    user {login url}
                                  }
                                  message
                                  oid
                                  url
                                }
                              }}""" if self.PClimit > 0 else '') + ("""
                              reviews (last: $RVlimit){ nodes {
                                author {
                                  avatarUrl
                                  login
                                  url
                                }""" if self.RVlimit > 0 else '') + ("""
                                comments (last: $Climit){ nodes {
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
                                }}""" if self.RVlimit > 0 and self.Climit > 0 else '') + ("""
                                body
                                createdAt
                                state
                                url
                              }}""" if self.RVlimit > 0 else '') + ("""
                              createdAt
                              isDraft
                              merged
                              mergedAt
                              mergedBy {login}
                              number
                              title
                              url
                            }
                          }""" if self.Plimit > 0 else '') + ("""
                          releases (last: $RLlimit){ nodes {
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
                          }}""" if self.RLlimit > 0 else '') + ("""
                          issues (last: $Ilimit){ nodes {
                            author {
                              login
                              url
                              avatarUrl
                            }
                            body
                            closed
                            closedAt""" if self.Ilimit > 0 else '') + ("""
                            comments (last: $Climit) { nodes {
                              author {
                                avatarUrl
                                login
                                url
                              }
                              body
                              createdAt
                              url
                            }}""" if self.Climit > 0 and self.Ilimit > 0 else '') + ("""
                            createdAt
                            number
                            title
                            url
                          }}""" if self.Ilimit > 0 else '') + """
                        }
                    }"""                                                        # graphQL was a mistake
                    params = {"owner": repoAuthor,
                              "repo_name": repoName}
                    for x in using:
                        params[x.split(sep=':')[0][1:]] = eval(f"self.{x.split(sep=':')[0][1:]}")
                    result = await session.execute(gql(req), variable_values=params)

                pulls = []
                if self.Plimit > 0:
                    self.bot.log(f"Checking prs for {repoName}")
                    pulls = result["repository"]["pullRequests"]["nodes"]
                for pull in pulls:
                    createdAt = datetime.strptime(pull["createdAt"], GHtimestring)
                    if createdAt > lastcheck:
                        if not self.bot.ponged:
                            await channel.send(f"<@&{self.role}> New pr(s) detected!")
                            self.bot.ponged = True

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

                    if self.Climit > 0:
                        for comment in pull["comments"]["nodes"]:
                            CcreatedAt = datetime.strptime(comment["createdAt"], GHtimestring)
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

                    if self.RVlimit > 0:
                        for review in pull["reviews"]["nodes"]:
                            RcreatedAt = datetime.strptime(review["createdAt"], GHtimestring)
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

                            if self.Climit > 0:
                                for comment in review['comments']["nodes"]:
                                    CcreatedAt = datetime.strptime(comment["createdAt"], GHtimestring)
                                    if CcreatedAt > lastcheck:
                                        embed = discord.Embed(title=f"{repoName} - New review comment on {pull['title']} (#{pull['number']})")
                                        embed.url = comment["url"]
                                        embed.set_author(name=comment['author']['login'], url=comment['author']['url'], icon_url=comment['author']['avatarUrl'])
                                        if len(comment['body']) > 1020: #limit for embed fields is 1024 chars
                                            embed.insert_field_at(0, name="Comment", value=f"{comment['body'][:1020]} ...")
                                        else:
                                            embed.insert_field_at(0, name="Comment", value=comment['body'])
                                        if len(comment['diffHunk']) > 1020:
                                            self.bot.log(f"Diff not shown for review comment {comment['id']}")
                                        else:
                                            embed.insert_field_at(1, name="Diff", value=f"```diff\n{comment['diffHunk']}```")

                                        await channel.send(embed=embed)

                    if self.PClimit > 0:
                        for commit in pull["commits"]["nodes"]:
                            commit = commit["commit"]  # yes really
                            CcreatedAt = datetime.strptime(commit["committedDate"], GHtimestring)
                            if CcreatedAt > lastcheck:
                                if not self.bot.ponged:
                                    await channel.send(f"<@&{self.role}> New commit detected!")
                                    self.bot.ponged = True

                                author = commit["author"]["user"]

                                await self.send_embed(channel,
                                                      f"{repoName}: {commit['oid']} on #{pull['number']}",
                                                      commit['url'],
                                                      commit['message'],
                                                      "Committed on: ",
                                                      CcreatedAt,
                                                      commit["author"]["name"] if author is None else author["login"],
                                                      "" if author is None else author["url"],
                                                      commit["author"]["avatarUrl"],
                                                      i)

                    if pull["closed"]:
                        closedAt = datetime.strptime(pull["closedAt"], GHtimestring)
                        if pull["merged"]:
                            mergedAt = datetime.strptime(pull["mergedAt"], GHtimestring)
                            if mergedAt > lastcheck:
                                await channel.send(
                                    f"{repoName} - {pull['title']} (#{pull['number']}) merged at {mergedAt} by {pull['mergedBy']['login']}")
                        elif closedAt > lastcheck:
                            await channel.send(f"{repoName} - {pull['title']} (#{pull['number']}) closed at {closedAt}")

                issues = []
                if self.Ilimit > 0:
                    self.bot.log(f"Checking issues for {repoName}")
                    issues = result["repository"]["issues"]["nodes"]
                for issue in issues:
                    createdAt = datetime.strptime(issue["createdAt"], GHtimestring)
                    if createdAt > lastcheck:
                        if not self.bot.ponged:
                            await channel.send(f"<@&{self.role}> New issue(s) detected!")
                            self.bot.ponged = True

                        await self.send_embed(channel,
                                              f"{repoName}: (#{issue['number']}) - {issue['title']}",
                                              issue['url'],
                                              issue['body'],
                                              "Opened on: ",
                                              createdAt,
                                              issue["author"]["login"],
                                              issue["author"]["url"],
                                              issue["author"]["avatarUrl"],
                                              i)
                    # me when i
                    if self.Climit > 0:  # when i duplicated code fragment (14 lines long)
                        for comment in issue["comments"]["nodes"]:
                            CcreatedAt = datetime.strptime(comment["createdAt"], GHtimestring)
                            if CcreatedAt > lastcheck:
                                await self.send_embed(channel,
                                                      f"{repoName} - New comment on {issue['title']} (#{issue['number']})",
                                                      comment["url"],
                                                      comment["body"],
                                                      "Commented on: ",
                                                      CcreatedAt,
                                                      comment["author"]["login"],
                                                      comment["author"]["url"],
                                                      comment["author"]["avatarUrl"],
                                                      i)

                    if issue["closed"]:
                        closedAt = datetime.strptime(issue["closedAt"], GHtimestring)
                        if closedAt > lastcheck:
                            await channel.send(f"{repoName} - {issue['title']} (#{issue['number']}) closed at {closedAt}")

                releases = []
                if self.RLlimit > 0:
                    self.bot.log(f"Checking releases for {repoName}")
                    releases = result["repository"]["releases"]["nodes"]
                for release in releases:
                        publishedAt = datetime.strptime(release["publishedAt"], GHtimestring)
                        if publishedAt > lastcheck:
                            if not self.bot.ponged:
                                await channel.send(f"<@&{self.role}> New release detected!")
                                self.bot.ponged = True
                            await self.send_embed(channel,
                                                  f"{repoName} - {'[PRERELEASE]' if release['isPrerelease'] else ''} Release {release['name']}",
                                                  release["url"],
                                                  release["description"],
                                                  "Published on: ",
                                                  publishedAt,
                                                  release["author"]["login"],
                                                  release["author"]["url"],
                                                  release["author"]["avatarUrl"],
                                                  i)


def setup(bot):
    bot.add_cog(Loop(bot))
