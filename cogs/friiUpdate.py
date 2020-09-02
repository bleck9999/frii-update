import asyncio
import configparser
import discord
import git
from discord.ext import commands
from github import Github

# format for entry: [Repo Path (str), Embed Colour (discord.Color)]
repos = [
    ["/media/blecc/storageBecause/switchhax2/Atmosphere", discord.Color(0x00a6ff)],
    ["/media/blecc/storageBecause/switchhax2/hekate", discord.Color(0xff0000)],
    ["/media/blecc/storageBecause/switchhax2/kurisu", discord.Color(0x8000ff)],
    ["/media/blecc/storageBecause/switchhax2/switch-guide", discord.Color(0x272B30)],
    ["/media/blecc/storageBecause/switchhax2/Lockpick_RCM", discord.Color(0xffff00)],
    ["/media/blecc/storageBecause/switchhax2/emmchaccgen", discord.Color(0x005200)],
    ["/media/blecc/storageBecause/switchhax2/GUIModManager", discord.Color(0x00ff00)],
    ["/media/blecc/storageBecause/switchhax2/TegraExplorer", discord.Color(0xba5d00)],
    ["/media/blecc/storageBecause/switchhax2/TegraScript", discord.Color(0xba5d00)],
    ["/media/blecc/storageBecause/switchhax2/themezer-nx", discord.Color(0x27aad6)]
]


class Loop(commands.Cog):
    def __init__(self, bot):
        conf = configparser.ConfigParser()
        conf.read("frii_update.ini")
        self.bot = bot
        self.channel = int(conf["Config"]["Channel ID"])
        self.role = int(conf["Config"]["Channel ID"])
        self.ghAPI = Github(conf["Tokens"]["Github"])

        # asyncio.run(self.updateLoop())

    async def updateLoop(self):
        await self.bot.wait_until_ready()
        #channel = await self.bot.fetch_channel(self.channel)
        while True:
            for i in range(len(repos)):
                repo = git.Repo(repos[i][0])
                NEW_COMMITS = {}
                fetchinfo = repo.git.fetch()

                # for branch in repo.branches:

    @commands.command()
    async def startLoop(self, ctx):
        await self.updateLoop()


def setup(bot):
    bot.add_cog(Loop(bot))
