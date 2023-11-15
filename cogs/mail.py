import datetime
import json
import re

import discord
import mechanize
import io

from bs4 import BeautifulSoup
from discord.ext import commands
from cogs.mailutils import strip_whitespace


class Loop(commands.Cog):
    """Contains main loops for mail.com and testmail
    if the config section for either does not exist, it's treated as deactivated
    eg if there is no [Testmail] section, only mail.com will be checked
    Further documentation available in checkTestmail and checkMailcom"""
    def __init__(self, bot):
        self.bot = bot

        self.accounts: dict[str: str] = {}
        self.localtz = datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo
        if "Mail.com" in self.bot.conf:
            addrs = [x.strip() for x in self.bot.conf["Mail.com"]["addresses"].split(sep=',')]
            # assume nobody has a password that starts or ends with 4 consecutive spaces
            # we dont strip each entry for this reason (above accounts for 1@mail.com,<possible space>2@mail.com
            pws = self.bot.conf["Mail.com"]["passwords"].split(sep='    ')
            for i in range(len(addrs)):
                self.accounts[addrs[i].strip()] = pws[i]
            self.migrate_ini_config()
        else:
            with open("cogs/mail.com/info.json", 'r') as f:
                self.accounts = json.load(f)

    def migrate_ini_config(self):
        import os
        if not os.path.isdir("cogs/mail.com"):
            os.mkdir("cogs/mail.com")
            with open("cogs/mail.com/info.json", 'w') as f:
                json.dump(self.accounts, f)
        self.bot.log("Configuration data has been moved to cogs/mail.com/info.json, "
                     "please remove the [Mail.com] section from frii_update.ini")

    async def main(self, channel):
        """Scrapes mail.com using mechanize and bs4
        Expects dict[email (str) : password (str)] in mail/info.json"""
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
            try:
                br.follow_link(text="Go to mail.com mailbox with limited functionality")
            except mechanize.LinkNotFoundError:
                # sometimes a different "browser not supported screen shows up instead because of course
                br.follow_link(text="limited functionality")
            link = br.find_link(text_regex=re.compile("Inbox( \d+ unread)?"))
            res = br.open(link.absolute_url)
            soup = BeautifulSoup(res.get_data(), "html.parser")

            emails = []
            for item in soup.find_all("li"):
                if item["class"] == ["message-list__item", "mail-panel", "is-unread"]:
                    returnaddr = br.geturl()

                    messageurl = item.find(class_="message-list__link mail-panel__link")["href"]
                    res = br.open(messageurl)
                    message = BeautifulSoup(res.get_data(), "html.parser")
                    # get the absolute URL now because we navigate away later and the relative url would break
                    bodylink = mechanize.Link(br.geturl(), message.find("iframe")["src"], '', '', '').absolute_url

                    details = message.find(href=re.compile(r".+/messagedetail\?[0123456789-]{3,6}\.-messageDetailPanel-mailHeader-showMore.*"))
                    res = br.open(details["href"])
                    details = BeautifulSoup(res.get_data(), "html.parser")
                    subject = details.find(**{"class_": "mail-detail-header__content", "data-webdriver": "subject"}).text
                    recipient = details.find(**{"class_": "mail-detail-header__email", "data-webdriver": "toAddress1"}).text
                    sendername = details.find(**{"class_": "mail-detail-header__name"}).text  # doesn't have a webdriver label fsr
                    senderaddr = details.find(**{"class_": "mail-detail-header__email", "data-webdriver": "fromAddress1"}).text
                    receivedon = details.find(**{"class_": "mail-detail-header__content", "data-webdriver": "date"}).text

                    res = br.open(bodylink)
                    text = BeautifulSoup(res.get_data(), "html.parser").get_text()

                    embed = discord.Embed()
                    info = f'From: "{sendername}" <{senderaddr}>\nTo: {recipient}\nSubject: {subject}'
                    embed.set_author(name=info[:256])
                    text = strip_whitespace(strip_whitespace(text))
                    embed.description = text[:2000] + f"\n\nRecieved on: {receivedon}"
                    htmlfile = discord.File(io.BytesIO(res.get_data()), filename="email.html")

                    emails.append((embed, htmlfile))
                    br.open(returnaddr)

            for email in emails[::-1]:
                await channel.send(embed=email[0])
                await channel.send(file=email[1])

    @commands.command()
    async def checkmailcom(self, ctx):
        await self.main(ctx)

def setup(bot):
    bot.add_cog(Loop(bot))
