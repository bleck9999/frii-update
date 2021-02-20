welcome to bootleg github webhook for discord

i dont expect people to actually use this but i mean it works™

instructions ("we have an app for that" edition)
1. clone this repo (make sure you use the `--recursive` or `--recurse-submodules` option)
2. install PySide6 (`pip install PySide6`)  
3. run frii-config (`frii-config/configurator.py`) and add the repositories you want to track
4. rename `frii_update_example.ini` to `frii_update.ini` and fill in the values with your text editor of choice
5. install frii-update's dependencies (you can do this with `pip install -r requirements.txt`)
6. run the bot (`bot.py`)
7. send `.start` in a channel the bot can see 

Optionally you can enable tracking system updates for the nintendo switch.
It uses the rss feed [here](https://yls8.mtheall.com/ninupdates/feed.php).

To enable this feature, open `frii_update.ini` and change do_sysupdates to `True`.
