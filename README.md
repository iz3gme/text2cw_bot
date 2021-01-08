# text2cw_bot
Telegram bot which convert text messages to cw

This bot was born from ideas in https://t.me/cw_qrs chat to have another instrument
to exercise cw, based on ebook2cw it answers any message you send it with the convertion
to cw audio of the message itself.

It was developped and tested on a rasperrypi but should run smoothly on any linux
platform, please note that the code have been written in the perfect style of "it
just works" 0=)

If you want to run your own copy of the bot you have to
- install telegram bot library for python3 (https://python-telegram-bot.org/)
- install ebook2cw and check binary is in /usr/bin/ebook2cw
- ask botfather to create the bot token as usual
- start the bot with
  ```sh
  text2cw_bot.py -s 0 placeyourtokenhere
  ```
  and test it via telegram
  
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
