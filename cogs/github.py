import asyncio
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
        self.bot = bot
        self.role = int(self.bot.conf["Bot"]["Role ID"])
        self.limits = {}
        for k in self.bot.conf["Github"]:
            if "limit" in k.lower():
                self.limits[k.lower().split(sep=' ')[0]] = int(self.bot.conf["Github"][k])

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
        try:
            await self.check(channel)
        except git.exc.GitCommandError as e:  # most of the time these are just generic connection errors
            if self.bot.conf["Bot"]["log level"].lower() == "debug":
                raise e
            self.bot.log(f"Ignoring exception with args {e.args}")
            await asyncio.sleep(10)
            self.bot.log("Retrying")
            await self.main(channel)

    async def check(self, channel):
        reviewStates = {
            "APPROVED": "Changes approved on",
            "CHANGES_REQUESTED": "Changes requested on",
            "COMMENTED": "Review submitted for",
            "DISMISSED": "Review submitted for",
            "PENDING": "Review submitted for"
        }
        lastcheck = self.bot.lastcheck

        headers = {"Authorization": f"Bearer {self.bot.conf['Github']['token']}"}
        transport = AIOHTTPTransport(url="https://api.github.com/graphql", headers=headers)
        async with Client(transport=transport, fetch_schema_from_transport=True) as session:
            for i in range(len(self.repos)):
                repo = git.Repo(self.repos[i][0])
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

                        if author["user"] is None:  # fukin edge cases reeeee
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

                if self.limits["pull"] or self.limits["review"] or self.limits["release"] or self.limits["issue"]:
                    self.bot.log(f"Fetching GitHub information for {repoName}")
                    if self.limits["comment"] == 0 and self.limits["review"] > 0:
                        self.bot.log("Warning: Comment limit set to 0 but Review limit > 0, this may cause unintended behaviour")
                    if self.limits["pull"] == 0 and self.limits["review"] > 0:
                        self.bot.log(f"Ignoring Review limit of {self.limits['review']} since pull request limit is 0")
                        self.limits["review"] = 0

                    using = []
                    for limit in self.limits:
                        if self.limits[limit] > 0:
                            using.append(f"${limit}:Int!")

                    # right what's about to happen probably needs some explanation
                    # i dont want to copy the same massive fuck off string for every configuration you could have
                    # k thanks end of explanation
                    req = """
                    query ($owner:String!,
                        $repo_name:String!,""" + ",".join(using) + "){" + """
                        repository(owner:$owner, name:$repo_name){""" + ("""
                          pullRequests(last:$pull){
                            nodes {
                              author {
                                avatarUrl
                                login
                                url
                              }
                              body
                              closed
                              closedAt""" if self.limits["pull"] > 0 else '') + ("""
                              comments (last: $comment){ nodes {
                                author {
                                  avatarUrl
                                  login
                                  url
                                }
                                body
                                createdAt
                                url
                              }}""" if self.limits["comment"] > 0 and self.limits["pull"] > 0 else '') + ("""
                              commits (last: $commit){ nodes {
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
                              }}
                              headRepository {isFork}""" if self.limits["commit"] > 0 else '') + ("""
                              reviews (last: $review){ nodes {
                                author {
                                  avatarUrl
                                  login
                                  url
                                }""" if self.limits["review"] > 0 else '') + ("""
                                comments (last: $comment){ nodes {
                                  author {
                                    avatarUrl
                                    login
                                    url
                                  }
                                  body
                                  createdAt
                                  diffHunk
                                  id
                                  outdated
                                  url
                                }}""" if self.limits["review"] > 0 and self.limits["comment"] > 0 else '') + ("""
                                body
                                createdAt
                                state
                                url
                              }}""" if self.limits["review"] > 0 else '') + ("""
                              createdAt
                              isDraft
                              merged
                              mergedAt
                              mergedBy {login}
                              number
                              title
                              url
                            }
                          }""" if self.limits["pull"] > 0 else '') + ("""
                          releases (last: $release){ nodes {
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
                          }}""" if self.limits["release"] > 0 else '') + ("""
                          issues (last: $issue){ nodes {
                            author {
                              login
                              url
                              avatarUrl
                            }
                            body
                            closed
                            closedAt""" if self.limits["issue"] > 0 else '') + ("""
                            comments (last: $comment) { nodes {
                              author {
                                avatarUrl
                                login
                                url
                              }
                              body
                              createdAt
                              url
                            }}""" if self.limits["comment"] > 0 and self.limits["issue"] > 0 else '') + ("""
                            createdAt
                            number
                            title
                            url
                          }}""" if self.limits["issue"] > 0 else '') + """
                        }
                    }"""
                    # graphQL was a mistake
                    params = {"owner": repoAuthor,
                              "repo_name": repoName}
                    for x in using:
                        x = x.split(sep=':')[0][1:]
                        params[x] = self.limits[x]
                    result = await session.execute(gql(req), variable_values=params)

                pulls = []
                if self.limits["pull"] > 0:
                    self.bot.log(f"Checking prs for {repoName}")
                    pulls = result["repository"]["pullRequests"]["nodes"]
                for pull in pulls:
                    changes = {}
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

                    if pull["headRepository"] is None:  # according to docs this can be null (because of course)
                        pass
                    elif self.limits["commit"] > 0 and pull["headRepository"]["isFork"]:
                        for commit in pull["commits"]["nodes"]:
                            commit = commit["commit"]  # yes really
                            CcreatedAt = datetime.strptime(commit["committedDate"], GHtimestring)
                            if CcreatedAt > lastcheck:
                                changes[CcreatedAt] = "commit", commit

                    if self.limits["comment"] > 0:
                        for comment in pull["comments"]["nodes"]:
                            CcreatedAt = datetime.strptime(comment["createdAt"], GHtimestring)
                            if CcreatedAt > lastcheck:
                                changes[CcreatedAt] = "comment", comment

                    if self.limits["review"] > 0:
                        for review in pull["reviews"]["nodes"]:
                            RcreatedAt = datetime.strptime(review["createdAt"], GHtimestring)
                            if RcreatedAt > lastcheck and review['body']:
                                # the way reviews work is completely insane
                                # github is fantastic and creates a new review with no body for *any* review comment
                                # there's no point sending this every time that happens.
                                changes[RcreatedAt] = "review", review

                            if self.limits["comment"] > 0:
                                for comment in review['comments']["nodes"]:
                                    CcreatedAt = datetime.strptime(comment["createdAt"], GHtimestring)
                                    if CcreatedAt > lastcheck:
                                        changes[CcreatedAt] = "review comment", comment

                    for change in sorted(changes.keys()):
                        if changes[change][0] == "commit":
                            commit = changes[change][1]
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

                        elif changes[change][0] == "comment":
                            comment = changes[change][1]
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

                        elif changes[change][0] == "review":
                            review = changes[change][1]
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

                        elif changes[change][0] == "review comment":
                            comment = changes[change][1]
                            embed = discord.Embed(title=f"{repoName} - New review comment on {pull['title']} (#{pull['number']})")
                            embed.url = comment["url"]
                            embed.set_author(name=comment['author']['login'], url=comment['author']['url'], icon_url=comment['author']['avatarUrl'])
                            if len(comment['body']) > 1020:  # limit for embed fields is 1024 chars
                                embed.insert_field_at(0, name="Comment", value=f"{comment['body'][:1020]} ...")
                            else:
                                embed.insert_field_at(0, name="Comment", value=comment['body'])
                            if len(comment['diffHunk']) > 1014:
                                self.bot.log(f"Diff not shown for review comment {comment['id']}")
                            else:
                                embed.insert_field_at(1, name=f"Diff {'(outdated)' if comment['outdated'] else ''}",
                                                      value=f"```diff\n{comment['diffHunk']}```")

                            await channel.send(embed=embed)

                    if pull["merged"]:
                        mergedAt = datetime.strptime(pull["mergedAt"], GHtimestring)
                        if mergedAt > lastcheck:
                            await channel.send(
                                f"{repoName} - {pull['title']} (#{pull['number']}) merged at {mergedAt} by {pull['mergedBy']['login']}")
                    elif pull["closed"]:
                        # merged PRs are also marked as closed so elif here ensures this only runs if it's closed and not merged
                        closedAt = datetime.strptime(pull["closedAt"], GHtimestring)
                        if closedAt > lastcheck:
                            await channel.send(f"{repoName} - {pull['title']} (#{pull['number']}) closed at {closedAt}")

                issues = []
                if self.limits["issue"] > 0:
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

                    if self.limits["comment"] > 0:
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
                if self.limits["release"] > 0:
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

    @commands.command()
    async def status(self, ctx, repo):
        """Displays open issues/pull requests for the given repo
        Usage: `.status <repo (username/reponame)>`"""
        owner, name = repo.split(sep='/')
        using = []
        for k in ["pull", "issue"]:
            if self.limits[k] > 0:
                using.append(f"${k}:Int!")
        req = """
        query ($owner:String!, $repo_name:String!,""" + ",".join(using) + "){" + """
            repository(owner:$owner, name:$repo_name){""" + ("""
              pullRequests(last:$pull, states:OPEN){nodes {
                author {login}
                number
                title
                url
              }}""" if self.limits["pull"] > 0 else '') + ("""
              issues (last: $issue, states:OPEN){ nodes {
                author {login}
                number
                title
                url
              }}""" if self.limits["issue"] > 0 else '') + """
            }
        }"""
        params = {"owner": owner,
                  "repo_name": name}
        for x in using:
            x = x.split(sep=':')[0][1:]
            params[x] = self.limits[x]

        headers = {"Authorization": f"Bearer {self.bot.conf['Tokens']['github']}"}
        transport = AIOHTTPTransport(url="https://api.github.com/graphql", headers=headers)
        async with Client(transport=transport, fetch_schema_from_transport=True) as session:
            res = await session.execute(gql(req), variable_values=params)

        if self.limits["pull"] > 0:
            pulls = res["repository"]["pullRequests"]["nodes"]
            desc = ""
            for pull in pulls:
                desc += f'#{pull["number"]}: [{pull["title"]}]({pull["url"]}) by {pull["author"]["login"]}\n'
            if not desc:
                await ctx.send("No open PRs at this time")
            else:
                descriptions = []
                paged = ""
                for line in desc.split(sep='\n'):
                    if len(paged + line) <= 2000:
                        paged += line + '\n'
                    else:
                        descriptions.append(paged)
                        paged = ''
                if paged:
                    descriptions.append(paged)
                for i, v in enumerate(descriptions):
                    embed = discord.Embed()
                    embed.title = '' if i else f"Open PRs for {repo} (max {self.limits['pull']} displayed)"
                    embed.description = v
                    await ctx.send(embed=embed)

        if self.limits["issue"] > 0:
            issues = res["repository"]["issues"]["nodes"]
            desc = ""
            for issue in issues:
                desc += f'#{issue["number"]}: [{issue["title"]}]({issue["url"]}) by {issue["author"]["login"]}\n'
            if not desc:
                await ctx.send("No open issues at this time")
            else:
                descriptions = []
                paged = ""
                for line in desc.split(sep='\n'):
                    if len(paged + line) <= 2000:
                        paged += line + '\n'
                    else:
                        descriptions.append(paged)
                        paged = ''
                if paged:
                    descriptions.append(paged)
                for i, v in enumerate(descriptions):
                    embed = discord.Embed()
                    embed.title = '' if i else f"Open issues for {repo} (max {self.limits['issue']} displayed)"
                    embed.description = v
                    await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Loop(bot))
