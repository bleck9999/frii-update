import datetime
import discord
from discord.ext import commands
import mechanize
from bs4 import BeautifulSoup


class Loop(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    async def main(self, channel):

        br = mechanize.Browser()
        br.set_handle_robots(False)
        br.open("https://mail.com")
        br.form = list(br.forms())[0]
        br["username"] = email
        br["password"] = password
        res = br.submit()
        soup = BeautifulSoup(res.get_data(), "html.parser")
        br.open(soup.find_all("meta")[3]["content"][6:])
        br.follow_link(text="Go to mail.com mailbox with limited functionality")
        link = br.find_link(text="Inbox")
        res = br.open(link.absolute_url)
        soup = BeautifulSoup(res.get_data(), "html.parser")

        for item in soup.find_all("li"):
            if item["class"] == ["message-list__item", "mail-panel"]:
                timestring = item.dl.find(class_="mail-header__date")["title"]
                zpad = timestring.split('at')[0]
                for i, char in enumerate(rhs := timestring.split('at')[1]):  # hack to zero-pad the hour
                    if char.isnumeric():
                        if rhs[i+1] == ':':
                            zpad += f'at 0{rhs[i:].strip()}'
                        else:
                            zpad += f"at{rhs}"
                        break
                parts = zpad.split(',')
                # now you might be wondering why i dont just do strptime(timestring, "%A, %B %j, %Y at %I:%M %p")
                # the answer is when i tried that it didnt parse the month and just defaulted to january
                # so i tried testing to see if i just did the string wrong and opened a console
                # strptime("Wednesday, April"   , "%A, %B")    => datetime(1900, 4, 1, 0, 0)
                # strptime("Wednesday, April 20", "%A, %B %j") => datetime(1900, 1, 20, 0, 0)
                # ??????????????
                date1 = datetime.datetime.strptime(parts[0] + parts[1].split(' ')[1], "%A%B")
                date2 = datetime.datetime.strptime(parts[1].split(' ')[2] + parts[2], "%j %Y at %I:%M %p")
                recvd = datetime.datetime(month=date1.month, day=date1.day,
                                          hour=date2.hour, minute=date2.minute, year=date2.year)
                if recvd > self.bot.lastcheck:
                    returnaddr = br.geturl()
                    messageurl = item.a["href"]
                    res = br.open(messageurl)
                    message = BeautifulSoup(res.get_data(), "html.parser")
                    subject = message.find(class_="mail-header__subject").text
                    sender = message.find(class_="mail-header__sender")["title"]
                    text = BeautifulSoup(res.get_data(), "html.parser").get_text()
                    embed = discord.Embed()
                    embed.set_author(f"From: {sender}\nTo: {email}\nSubject: {subject}")
                    embed.description = text[:2047]
                    await channel.send(embed=embed)
                    res = br.open(message.find("iframe")["src"])
                    htmlfile = discord.File(res.get_data(), filename="email.html")
                    await channel.send(file=htmlfile)


def setup(bot):
    bot.add_cog(Loop(bot))
