import configparser
from discord import Intents
from discord.ext import commands
from traceback import format_exception

config = configparser.ConfigParser()
config.read("frii_update.ini")


class FriiUpdate(commands.Bot):
    def __init__(self, command_prefix, **options):
        super().__init__(command_prefix, **options)
        self.load_extension("cogs.sysupdates")
        self.load_extension("cogs.friiUpdate")
        self.role = int(config["Config"]["Role ID"])

    # Exception handling modified from nh-server/Kurisu
    # Licensed under apache2 (https://www.apache.org/licenses/LICENSE-2.0)
    async def on_command_error(self, ctx, exception):
        channel = await self.fetch_channel(int(config["Config"]["Channel ID"]))
        await channel.send(f"<@&{self.role}> an unhandled exception has occurred")
        exc = getattr(exception, 'original', exception)
        msg = "".join(format_exception(type(exc), exc, exc.__traceback__))
        error_paginator = commands.Paginator()
        for chunk in [msg[i:i + 1800] for i in range(0, len(msg), 1800)]:
            error_paginator.add_line(chunk)
        for page in error_paginator.pages:
            await channel.send(page)


intents = Intents.none()
intents.messages = True
bot = FriiUpdate(command_prefix=".", intents=intents)
print("Run bot")
bot.run(config["Tokens"]["Discord"])
