from discord.ext import commands
import re


def strip_whitespace(text):
    text = text.strip().replace(' ', ' ').replace('‌', ' ')
    text = re.sub(r"[ \t]+", ' ', text)
    text = re.sub(r"( *\n+ *)+", '\n', text)
    return text


class Loop(commands.Cog):
    """Library file for mail.py and testmail.py
    provides strip_whitespace and (if enabled in frii_update.ini) checkmail"""
    def __init__(self, bot):
        self.bot = bot

    async def main(self, channel):
        pass  # epic stub function

    @commands.command()
    async def checkmail(self, ctx):
        if "testmail" in self.bot.conf["Modules"] and \
                self.bot.conf["Modules"]["testmail"].lower() == "true":
            await self.bot.all_commands["checktestmail"](ctx)
        if "mail" in self.bot.conf["Modules"] and \
                self.bot.conf["Modules"]["mail"].lower() == "true":
            await self.bot.all_commands["checkmailcom"](ctx)

def setup(bot):
    bot.add_cog(Loop(bot))