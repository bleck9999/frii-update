import configparser
from discord.ext import commands


class FriiUpdate(commands.Bot):
    def __init__(self):
        self.load_extension("cogs.friiUpdate")


config = configparser.ConfigParser()
config.read("frii_update.ini")
bot = FriiUpdate(command_prefix=".")
bot.run(config["Tokens"]["Discord"])
