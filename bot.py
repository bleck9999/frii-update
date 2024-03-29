import asyncio
import configparser
import datetime
import importlib
import inspect
import os

import discord.ext.commands
from discord import Intents
from discord.ext import commands
from traceback import format_exception

config = configparser.ConfigParser()
config.read("frii_update.ini")


class FriiUpdate(commands.Bot):
    def __init__(self, command_prefix, **options):
        super().__init__(command_prefix, **options)
        self.conf = configparser.ConfigParser()
        self.conf.read("frii_update.ini")
        for cog in cogs:
            self.load_extension("cogs." + cog)
            globals()[cog] = importlib.import_module("cogs." + cog)
        self.role = int(self.conf["Bot"]["Role ID"])
        self.lastcheck = datetime.datetime.utcnow()
        self.interval = int(self.conf["Bot"]["Interval"])
        self.ponged = False

    async def on_ready(self):
        self.log("Ready!")

    @staticmethod
    def log(text):
        now = datetime.datetime.now().strftime("%H:%M:%S")
        caller = inspect.stack()[1].filename.split('/')[-1][:-3]
        print(f"[{now}] - {caller}: {text}")

    # Exception handling modified from nh-server/Kurisu
    # Licensed under apache2 (https://www.apache.org/licenses/LICENSE-2.0)
    async def on_command_error(self, ctx, exception):
        if isinstance(exception, discord.ext.commands.errors.CommandNotFound):
            return
        channel = await self.fetch_channel(int(self.conf["Bot"]["Channel ID"]))
        await channel.send(f"<@&{self.role}> an unhandled exception has occurred")
        # by saying this we imply that some errors *are* handled gracefully
        exc = getattr(exception, 'original', exception)
        msg = "".join(format_exception(type(exc), exc, exc.__traceback__))
        error_paginator = commands.Paginator()
        for chunk in [msg[i:i + 1800] for i in range(0, len(msg), 1800)]:
            error_paginator.add_line(chunk)
        for page in error_paginator.pages:
            await channel.send(page)


cogs = []
for cog in os.listdir("cogs"):
    if cog.split('.')[-1] == "py":
        cog = cog.split('.')[0]
        if cog in config["Modules"] and config["Modules"][cog].lower() == "true":
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] - bot: Loading {cog}.py")
            cogs.append(cog)

intents = Intents.none()
intents.messages = True
if "prefix" not in config["Bot"]:
    config["Bot"]["prefix"] = '.'
    with open("frii_update.ini", 'w') as f:
        config.write(f)
bot = FriiUpdate(command_prefix=config["Bot"]["prefix"], intents=intents)


@bot.command()
async def start(ctx):
    if "Last checked" in bot.conf["Bot"].keys():
        bot.lastcheck = datetime.datetime.strptime(bot.conf["Bot"]["Last checked"], "%H%M%S %d%m%Y")
    await bot.wait_until_ready()
    channel = await bot.fetch_channel(bot.conf["Bot"]["Channel ID"])

    while True:
        bot.ponged = False
        values = list(bot.extensions.values())
        for module in values:
            attempts = 0
            obj = module.Loop(bot)
            while True:
                try:
                    await obj.main(channel)
                    break
                except Exception as e:
                    if attempts >= 3:
                        raise e
                    attempts += 1
                    bot.log(f"Ignoring exception with args {e.args}")
                    await asyncio.sleep(10)
                    bot.log("Retrying")

        bot.lastcheck = datetime.datetime.utcnow()
        bot.conf["Bot"]["Last checked"] = bot.lastcheck.strftime("%H%M%S %d%m%Y")
        with open("frii_update.ini", "w") as confFile:
            bot.conf.write(confFile)
        await asyncio.sleep(bot.interval)


@bot.command()
async def load(ctx, module):
    bot.load_extension("cogs."+module)
    await ctx.send(f"Loaded {module}")


@bot.command()
async def unload(ctx, module):
    bot.unload_extension("cogs."+module)
    await ctx.send(f"Unloaded {module}")


@bot.command()
async def interval(ctx, time):
    """Changes the amount of time the bot waits between checks. Resets when the bot is restarted.
    Usage: `.interval <time (s)>`"""
    try:
        int(time)
    except ValueError:
        await ctx.send("Interval must be an integer")
        return
    bot.interval = int(time)
    await ctx.send(f"Interval set to {time} seconds")

bot.log("Connecting...")
token = config["Bot"]["Token"]
del config
bot.run(token)
