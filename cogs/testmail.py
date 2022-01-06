import configparser

import discord
from discord.ext import commands
from gql import gql, Client
from gql.transport.aiohttp import AIOHTTPTransport
import io


class Loop(commands.Cog):
    """Uses testmail api (https://testmail.app/)
    Expects a token in frii_update.ini under `Tokens` with the name `Testmail`
    and a `TM_Namespace` under `Config`"""
    def __init__(self, bot):
        self.bot = bot
        self.conf = configparser.ConfigParser()
        self.conf.read("frii_update.ini")
        self.req = """query {
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
                        }""".replace("NM_REPLACE", self.conf["Config"]["TM_Namespace"])
        try:
            getattr(self.bot, "emails")
        except AttributeError:
            self.bot.emails = []
        self.emails = self.bot.emails  # this gets nuked on restart 
        # but emails get nuked after 24 hours with free tier anyway so it's not a big deal

    async def main(self, channel):
        headers = {"Authorization": f"Bearer {self.conf['Tokens']['Testmail']}"}
        transport = AIOHTTPTransport(url="https://api.testmail.app/api/graphql", headers=headers)
        async with Client(transport=transport, fetch_schema_from_transport=True) as session:
            self.bot.log("Checking testmail")
            result = await session.execute(gql(self.req))
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

    @commands.command()
    async def checkmail(self, ctx):
        await self.main(ctx)

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
