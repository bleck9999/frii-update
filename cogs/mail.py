import configparser
import datetime
import re

import discord
import mechanize
import io

from bs4 import BeautifulSoup
from discord.ext import commands
from gql import gql, Client
from gql.transport.aiohttp import AIOHTTPTransport


class Loop(commands.Cog):
    """Contains main loops for mail.com and testmail
    if the config section for either does not exist, it's treated as deactivated
    eg if there is no [Testmail] section, only mail.com will be checked
    Further documentation available in checkTestmail and checkMailcom"""
    def __init__(self, bot):
        self.bot = bot
        self.conf = configparser.ConfigParser()
        self.conf.read("frii_update.ini")
        self.active = []

        if "Testmail" in self.conf:
            self.active.append("testmail")
            self.tm_req = """query {
                              inbox(namespace:"NM_REPLACE"){
                                emails{
                                  from
                                  html
                                  subject
                                  text
                                  timestamp
                                  to
                                }
                              }
                            }"""
            self.namespaces = self.conf["Testmail"]["namespaces"].split(sep=',')
            self.namespaces = [x.strip() for x in self.namespaces]

            try:
                getattr(self.bot, "emails")
            except AttributeError:
                self.bot.emails = []
            self.emails = self.bot.emails  # this gets nuked on restart
            # but emails get nuked after 24 hours with free tier anyway so it's not a big deal

        if "Mail.com" in self.conf:
            self.active.append("mail.com")
            self.accounts = {}
            self.localtz = datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo
            addrs = [x.strip() for x in self.conf["Mail.com"]["addresses"].split(sep=',')]
            # assume nobody has a password that starts or ends with 4 consecutive spaces
            # we dont strip each entry for this reason (above accounts for 1@mail.com,<possible space>2@mail.com
            pws = self.conf["Mail.com"]["passwords"].split(sep='    ')
            for i in range(len(addrs)):
                self.accounts[addrs[i].strip()] = pws[i]

    async def checkTestmail(self, channel):
        """Uses testmail api (https://testmail.app/)
        Expects a comma seperated list `namespaces` under `Testmail`
        and token in frii_update.ini for each namespace under `Tokens` with the name `testmail.<namespace>`"""
        for namespace in self.namespaces:
            headers = {"Authorization": f"Bearer {self.conf['Testmail'][namespace]}"}

            transport = AIOHTTPTransport(url="https://api.testmail.app/api/graphql", headers=headers)
            async with Client(transport=transport, fetch_schema_from_transport=True) as session:
                self.bot.log(f"Checking testmail namespace {namespace}")
                result = await session.execute(gql(self.tm_req.replace("NM_REPLACE", namespace)))
                for email in result["inbox"]["emails"]:
                    if email not in self.emails:
                        embed = discord.Embed()
                        embed.set_author(name=f"From: {email['from']}\nTo: {email['to']}\nSubject: {email['subject']}")
                        embed.description = email['text'][:2047]
                        await channel.send(embed=embed)
                        self.emails.append(email)
                        # reee why cant i give a string and have discord.File do it for me
                        sio = io.StringIO(email["html"])
                        bio = io.BytesIO(sio.read().encode('utf8'))
                        htmlfile = discord.File(bio, filename="email.html")
                        await channel.send(file=htmlfile)

    async def checkMailcom(self, channel):
        """Scrapes mail.com using mechanize and bs4
        Expects comma seperated list `addresses` under `Mail.com`
        and corresponding `passwords` seperated by 4 spaces"""
        for account in self.accounts.items():
            self.bot.log(f"Checking mail.com account {account[0]}")
            br = mechanize.Browser()
            br.set_handle_robots(False)
            br.open("https://mail.com")
            br.form = list(br.forms())[0]
            br["username"] = account[0]
            br["password"] = account[1]
            res = br.submit()
            soup = BeautifulSoup(res.get_data(), "html.parser")
            br.open(soup.find_all("meta")[3]["content"][6:])
            br.follow_link(text="Go to mail.com mailbox with limited functionality")
            link = br.find_link(text_regex=re.compile("Inbox( \d+ unread)?"))
            res = br.open(link.absolute_url)
            soup = BeautifulSoup(res.get_data(), "html.parser")

            for item in soup.find_all("li"):
                if item["class"] == ["message-list__item", "mail-panel", "is-unread"]:
                    returnaddr = br.geturl()

                    messageurl = item.find(class_="message-list__link mail-panel__link")["href"]
                    res = br.open(messageurl)
                    message = BeautifulSoup(res.get_data(), "html.parser")
                    subject = message.find(class_="mail-header__subject").text
                    sender = message.find(class_="mail-header__sender")
                    if "title" in sender:
                        sender = sender["title"]
                    else:  # fukin email verification "ooo look at me i have a checkmark so you know im real"
                        sender = "mail.com Service (service@corp.mail.com)"

                    res = br.open(message.find("iframe")["src"])
                    text = BeautifulSoup(res.get_data(), "html.parser").get_text()

                    embed = discord.Embed()
                    embed.set_author(name=f"From: {sender}\nTo: {account[0]}\nSubject: {subject}")
                    embed.description = text[:2047]
                    await channel.send(embed=embed)

                    htmlfile = discord.File(io.BytesIO(res.get_data()), filename="email.html")
                    await channel.send(file=htmlfile)

                    br.open(returnaddr)

    async def main(self, channel):
        if "testmail" in self.active:
            await self.checkTestmail(channel)
        if "mail.com" in self.active:
            await self.checkMailcom(channel)

    @commands.command()
    async def checkmail(self, ctx):
        await self.main(ctx)

    @commands.command()
    async def clearmail(self, ctx):
        """Clears temporary storage of tesmail emails"""
        self.bot.emails = []
        return await ctx.send("Cleared!")

    @commands.command()
    async def listsaved(self, ctx, verbosity=1):
        """Retrieves stored tesmail emails. Verbosity:
        1: show subject and sender info only (default)
        2: also show text field
        3: show everything"""
        if not self.bot.emails:
            return await ctx.send("No emails saved!")
        for email in self.bot.emails:
            embed = discord.Embed()
            embed.set_author(name=f"From: {email['from']}\nTo: {email['to']}\nSubject: {email['subject']}")
            if verbosity >= 2:
                embed.description = email['text'][:2047]
            await ctx.send(embed=embed)
            if verbosity >= 3:
                sio = io.StringIO(email["html"])
                bio = io.BytesIO(sio.read().encode('utf8'))
                htmlfile = discord.File(bio, filename="email.html")
                await ctx.send(file=htmlfile)


def setup(bot):
    bot.add_cog(Loop(bot))
