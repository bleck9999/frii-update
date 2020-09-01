import time
from discord.ext import commands


class friiUpdate(commands.Bot):

    def __init__(self, command_prefix):
        super().__init__(command_prefix=command_prefix)

    def load_cog(self, extension):
        self.load_extension(extension)


token = open("discord_token.txt").readline()

print("Connecting to P.U.T.I.N. network...")
time.sleep(1)
print("Connected!")

bot = friiUpdate('.')
print("Load cog...")
bot.load_cog("cogs.friiUpdate")
print("Run bot...")
bot.run(token)
