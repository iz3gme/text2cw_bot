# text2cw_bot
Telegram bot which convert text messages to cw

This bot was born from ideas in @cw_qrs chat - https://t.me/cw_qrs - to have another instrument
to exercise cw, based on ebook2cw it answers any message you send it with the convertion
to cw audio of the message itself.

There's no real magic here as this is mostly a wrapper around excellent program ebook2cw
https://fkurz.net/ham/ebook2cw.html by Fabian Kurz DJ1YFK.

It was developped, tested and now lives - as @text2cw_bot https://t.me/text2cw_bot - on a
rasperrypi but should run smoothly on any linux platform, please note that the code have been
written in the perfect style of "it just works" 0=)

If you want to run your own copy of the bot i suggest create a virtual environment to avoid library version incompatibility (actually the problematic one is python-telegram-bot which in recent version is changed and my code would not run on them)
- create virtual environment and activate it
  ```sh
  python -m venv venv
  source venv/bin/activate
  ```
- install telegram bot and all other required libraries
  ```sh
  pip install -r requirements.txt
  ```
- install ebook2cw and check binary is /usr/bin/ebook2cw
  ```sh
  sudo apt install ebook2cw
  ```
- install QSO (part of morse package) and check binary is /usr/bin/QSO
  ```sh
  sudo apt install morse
  ```
- install UbuntuMono font and check /usr/share/fonts/truetype/ubuntu/UbuntuMono-R.ttf exists
  ```sh
  sudo apt install fonts-ubuntu
  ```
- ask botfather to create the bot token as usual
- exit virtual environment and start the bot with
  ```sh
  ./start_text2cw_bot.sh -s 0 placeyourtokenhere
  ```
  now test it via telegram

If everything is ok and you want to start it at boot you can copy _text2cw_bot.service_ in
_/etc/systemd/system_ and put your bot token in there then start it with
  ```sh
  systemctl start text2cw_bot
  ```
test it again via telegram and eventually check it status
  ```sh
  systemctl status text2cw_bot
  ```
Once you feel ready enable it
  ```sh
  systemctl enable text2cw_bot
  ```
