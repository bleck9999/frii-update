import configparser
import discord
from discord.ext import commands
from github import Github

# format for entry: [Repo Path (str), Embed Colour (discord.Color)]
repos = [

]


class Loop(commands.Cog):
    def __init__(self, bot):
        conf = configparser.ConfigParser()
        conf.read("frii_update.ini")
        self.bot = bot
        self.channel = bot.fetch_channel(conf["Config"]["Channel ID"])
        self.role = bot.fetch_role(conf["Config"]["Channel ID"])



def setup(bot):
    bot.add_cog(Loop(bot))