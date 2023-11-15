import io
import discord
import json
from bs4 import BeautifulSoup
from discord.ext import commands
from gql import gql, Client
from gql.transport.aiohttp import AIOHTTPTransport
from cogs.mailutils import strip_whitespace

class Loop(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        try:
            getattr(self.bot, "emails")
        except AttributeError:
            self.bot.emails = []
        self.emails = self.bot.emails  # this gets nuked on restart
        # but emails get nuked after 24 hours with free tier anyway, so it's not a big deal

        self.tokens: dict[str: str] = {}
        if "Testmail" in self.bot.conf:
            namespaces = self.bot.conf["Testmail"]["namespaces"].split(sep=',')
            namespaces = [x.strip() for x in namespaces]
            for ns in namespaces:
                self.tokens[ns] = self.bot.conf["Testmail"][ns]
            self.migrate_ini_config()
        else:
            with open("cogs/testmail/info.json", 'r') as f:
                self.tokens = json.load(f)

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

    def migrate_ini_config(self):
        import os
        if not os.path.isdir("cogs/testmail"):
            os.mkdir("cogs/testmail")
            with open("cogs/testmail/info.json", 'w') as f:
                json.dump(self.tokens, f)
        self.bot.log("Configuration data has been moved to cogs/testmail/info.json, "
                     "please remove the [Testmail] section from frii_update.ini")

    async def main(self, channel):
        """Uses testmail api (https://testmail.app/)
        Expects dict[namespace (str) : token (str)] in testmail/info.json
        and token in frii_update.ini for each namespace under `Tokens` with the name `testmail.<namespace>`"""
        for namespace in self.tokens:
            headers = {"Authorization": f"Bearer {self.tokens[namespace]}"}

            transport = AIOHTTPTransport(url="https://api.testmail.app/api/graphql", headers=headers)
            async with Client(transport=transport, fetch_schema_from_transport=True) as session:
                self.bot.log(f"Checking testmail namespace {namespace}")
                result = await session.execute(gql(self.tm_req.replace("NM_REPLACE", namespace)))
                for email in result["inbox"]["emails"]:
                    if email not in self.emails:
                        embed = discord.Embed()
                        embed.set_author(name=f"From: {email['from']}\nTo: {email['to']}\nSubject: {email['subject']}")
                        try:
                            embed.description = email['text'][:2047]
                        except TypeError:
                            text = BeautifulSoup(email['html'], "html.parser").get_text()
                            embed.description = strip_whitespace(strip_whitespace(text))[:2047]
                        await channel.send(embed=embed)
                        self.emails.append(email)
                        # reee why cant i give a string and have discord.File do it for me
                        sio = io.StringIO(email["html"])
                        bio = io.BytesIO(sio.read().encode('utf8'))
                        htmlfile = discord.File(bio, filename="email.html")
                        await channel.send(file=htmlfile)

    @commands.command()
    async def checktestmail(self, ctx):
        return await self.main(ctx)

    @commands.command()
    async def clearmail(self, ctx):
        """Clears temporary storage of emails"""
        self.bot.emails = []
        return await ctx.send("Cleared!")

    @commands.command()
    async def listsaved(self, ctx, verbosity=1):
        """Retrieves stored emails. Verbosity:
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
