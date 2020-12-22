# -*- coding: utf-8 -*-

"""Implement simple telegram bot hiding all details"""

import logging

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)

logger = logging.getLogger(__name__)

from telegram.ext import Updater, CommandHandler, ConversationHandler, CallbackContext, MessageHandler, Filters, PicklePersistence
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton

import subprocess
from os import remove, rename
import re

MAIN, TYPING_WPM, TYPING_SNR, TYPING_TONE, TYPING_TITLE = range(5)

class bot():

        def __init__(self):
            super(bot, self).__init__()
            self._updater = None
            self._chat_set = set()

        @property
        def _helptext(self):
            return "\n".join([
                "I can convert text to cw (Morse) audio",
                "Just send me a message and I'll answer with the mp3 audio file",
                "You can change speed, tone and file name using commands",
                "(adding noise is not fully implemented yet)",
                "",
                "Shoud you find any bug please write to my creator @iz3gme",
                "",
                "I can understand this commands:", 
                "/wpm",
                "    Set speed in words per minute",
                "/tone",
                "    Set tone frequency in Hertz",
                "/snr",
                "    When set a noise background is added, valid values are -10 to 10 (in db), set to NONE to disable",
                "/title",
                "    Set answer file name",
            ])

        @property
        def _keyboard(self):
            replymarkup = ReplyKeyboardMarkup(
                [
                    [
                        KeyboardButton('/wpm'),
                        KeyboardButton('/tone'),
                        KeyboardButton('/snr'),
                    ],
                    [
                        KeyboardButton('/title'),
#                        KeyboardButton('/settings'),
                        KeyboardButton('/help'),
                    ],
                ],
                resize_keyboard=True,
                one_time_keyboard=False
            )
            return replymarkup

        @property
        def _keyboard_leave(self):
            replymarkup = ReplyKeyboardMarkup(
                [
                    [
                        KeyboardButton('/leave'),
                    ],
                ],
                resize_keyboard=True,
                one_time_keyboard=False
            )
            return replymarkup

        def _you_exist(self, update: Update, context: CallbackContext):
            if context.user_data and context.user_data['exist']:
            	return True
            else:
                update.message.reply_text("You don't exist, go away!")
            return False

        def _cmd_start(self, update: Update, context: CallbackContext) -> None:
            logging.debug('bot._cmd_start')
            if not (context.user_data and context.user_data['exist']):
                context.user_data['wpm'] = 25
                context.user_data['tone'] = 600
                context.user_data['snr'] = None
                context.user_data['title'] = 'CW Text'
                context.user_data['exist'] = True
            update.message.reply_text(
                'Hi ' + update.message.from_user.first_name + '\n' + self._helptext,
                reply_markup=self._keyboard
            )
            return MAIN

        def _cmd_stop(self, update: Update, context: CallbackContext) -> None:
            logging.debug('bot._cmd_stop')
            if self._you_exist(update, context):
                context.user_data['exist'] = False
                update.message.reply_text(
                    "Bye bye\nremember you can use /start to join us again",
                    reply_markup=ReplyKeyboardRemove()
                    )
                return ConversationHandler.END

        def _cmd_help(self, update: Update, context: CallbackContext) -> None:
            logging.debug('bot._cmd_help')
            if self._you_exist(update, context):
                update.message.reply_text(self._helptext)
                return MAIN

        def _cmd_wpm(self, update: Update, context: CallbackContext) -> None:
            logging.debug('bot._cmd_wpm')
            if self._you_exist(update, context):
                update.message.reply_text(
                    "Current value is %iwpm\nWhat is your desired speed?" % context.user_data["wpm"],
                    reply_markup=self._keyboard_leave
                )
                return TYPING_WPM

        def _accept_wpm(self, update: Update, context: CallbackContext) -> None:
            logging.debug('bot._accept_wpm')
            if self._you_exist(update, context):
                try:
            	    value = int(update.message.text)
                except ValueError:
                    update.message.reply_text(
                        "Hey ... this is not a number!!"
                    )
                    return None
                else:
                    if 1 <= value <= 100:
                        context.user_data["wpm"] = value 	    
                        update.message.reply_text(
                            "Ok - speed is now %iwpm" % value,
                            reply_markup=self._keyboard
                        )
                        return MAIN
                    else:
                        update.message.reply_text(
                            "Sorry - Valid wpm is between 1 and 100\nTry again"
                        )
                        
        def _cmd_tone(self, update: Update, context: CallbackContext) -> None:
            logging.debug('bot._cmd_tone')
            if self._you_exist(update, context):
                update.message.reply_text(
                    "Current value is %iHz\nWhat is your desired tone frequency?" % context.user_data["tone"],
                    reply_markup=self._keyboard_leave
                )
                return TYPING_TONE

        def _accept_tone(self, update: Update, context: CallbackContext) -> None:
            logging.debug('bot._accept_tone')
            if self._you_exist(update, context):
                try:
            	    value = int(update.message.text)
                except ValueError:
                    update.message.reply_text(
                        "Hey ... this is not a number!!"
                    )
                    return None
                else:
                    if 200 <= value <= 1200:
                        context.user_data["tone"] = value 	    
                        update.message.reply_text(
                            "Ok - tone frequency is now %iHz" % value,
                            reply_markup=self._keyboard
                        )
                        return MAIN
                    else:
                        update.message.reply_text(
                            "Sorry - Valid frequency is between 200 and 1200\nTry again"
                        )
                        
        def _cmd_snr(self, update: Update, context: CallbackContext) -> None:
            logging.debug('bot._cmd_snr')
            if self._you_exist(update, context):
                value = "none" if context.user_data["snr"] is None else "%idb" % context.user_data["snr"]
                update.message.reply_text(
                    "Current value is %s\nWhat is your desired snr (type none for no added noise at all)?" % value,
                    reply_markup=self._keyboard_leave
                )
                return TYPING_SNR

        def _accept_snr(self, update: Update, context: CallbackContext) -> None:
            logging.debug('bot._accept_snr')
            if self._you_exist(update, context):
                try:
            	    value = int(update.message.text)
                except ValueError:
                    update.message.reply_text(
                        "Hey ... this is not a number!!"
                    )
                    return None
                else:
                    if -10 <= value <= 10:
                        context.user_data["snr"] = value 	    
                        update.message.reply_text(
                            "Ok - snr is now %idb" % value,
                            reply_markup=self._keyboard
                        )
                        return MAIN
                    else:
                        update.message.reply_text(
                            "Sorry - Valid snr is between -10 and 10\nTry again"
                        )
                        
        def _accept_nosnr(self, update: Update, context: CallbackContext) -> None:
            logging.debug('bot._accept_nosnr')
            if self._you_exist(update, context):
                context.user_data["snr"] = None 	    
                update.message.reply_text(
                    "Ok - no noise will be added",
                    reply_markup=self._keyboard
                )
                return MAIN
                        
        def _cmd_title(self, update: Update, context: CallbackContext) -> None:
            logging.debug('bot._cmd_title')
            if self._you_exist(update, context):
                update.message.reply_text(
                    "Current title is %s\nWhat is your desired title?" % context.user_data["title"],
                    reply_markup=self._keyboard_leave
                )
                return TYPING_TITLE

        def _accept_title(self, update: Update, context: CallbackContext) -> None:
            logging.debug('bot._accept_title')
            if self._you_exist(update, context):
                value = update.message.text
                if re.search(r'[^A-Za-z0-9_\- ]', value):
                    update.message.reply_text(
                        "Hey ... this is not a valid title!!\nPlease use only letters, numbers, blank, underscore, hyphen (A-Za-z0-9 _-)"
                    )
                    return None
                else:
                    if 0 < len(value) <= 50:
                        context.user_data["title"] = value 	    
                        update.message.reply_text(
                            "Ok - title is now %s" % value,
                            reply_markup=self._keyboard
                        )
                        return MAIN
                    else:
                        update.message.reply_text(
                            "Sorry - I can accept titles of 50 chars at most\nTry again"
                        )
                        
        def _accept_nosnr(self, update: Update, context: CallbackContext) -> None:
            logging.debug('bot._accept_nosnr')
            if self._you_exist(update, context):
                context.user_data["snr"] = None 	    
                update.message.reply_text(
                    "Ok - no noise will be added",
                    reply_markup=self._keyboard
                )
                return MAIN
                        
        def _cmd_leave(self, update: Update, context: CallbackContext) -> None:
            logging.debug('bot._cmd_leave')
            if self._you_exist(update, context):
                update.message.reply_text(
                    "Ok - leaving value unchanged",
                    reply_markup=self._keyboard
                )
                return MAIN

        def _handle_unknown(self, update: Update, context: CallbackContext) -> None:
            logging.debug('bot._handle_unknown')
            if self._you_exist(update, context):
                update.message.reply_text("Sorry, this is something I can't understand")
                return None

        def _handle_text(self, update: Update, context: CallbackContext) -> None:
            if self._you_exist(update, context):
                wpm = context.user_data['wpm']
                tone = context.user_data['tone']
                snr = context.user_data['snr']
                title = context.user_data['title']
                
                tempfilename = "/tmp/" + update.message.from_user.first_name + "_" + title
                command = ["/usr/bin/ebook2cw", "-c", "DONOTSEPARATECHAPTERS", "-o", tempfilename, "-u"]
                command.extend(["-w", str(wpm)])
                command.extend(["-f", str(tone)])
                if snr is not None: command.extend(["-N", str(snr)])
                command.extend(["-t", title])
                command.extend(["-a", update.message.from_user.first_name])
                
                subprocess.run(command, input=bytes(update.message.text+"\n", encoding='utf8'))
                rename(tempfilename+"0000.mp3", tempfilename+".mp3")
                tempfilename += ".mp3"
                update.message.reply_audio(audio=open(tempfilename, "rb"), title=title)
                remove(tempfilename)

        def start(self, token):
            pp = PicklePersistence(filename='text2morse_bot')
            self._updater = Updater(token, persistence=pp, use_context=True)

            # Add conversation handler with the states MAIN and TYPING_VALUE
            conv_handler = ConversationHandler(
                entry_points=[CommandHandler('start', self._cmd_start)],
                states={
                    MAIN: [
                        CommandHandler('help', self._cmd_help),
                        CommandHandler('stop', self._cmd_stop),
                        CommandHandler('wpm', self._cmd_wpm),
                        CommandHandler('tone', self._cmd_tone),
                        CommandHandler('snr', self._cmd_snr),
                        CommandHandler('title', self._cmd_title),
                        MessageHandler(Filters.text & ~Filters.command, self._handle_text),
                    ],
                    TYPING_WPM: [
                        MessageHandler(
                            Filters.text & ~Filters.command, self._accept_wpm
                        ),
                        CommandHandler('leave', self._cmd_leave),
                    ],
                    TYPING_TONE: [
                        MessageHandler(
                            Filters.text & ~Filters.command, self._accept_tone
                        ),
                        CommandHandler('leave', self._cmd_leave),
                    ],
                    TYPING_SNR: [
                        MessageHandler(
                            Filters.text & ~(Filters.command | Filters.regex('^none$')), self._accept_snr
                        ),
                        MessageHandler(
                            Filters.text & ~Filters.command & Filters.regex('^none$'), self._accept_nosnr
                        ),
                        CommandHandler('leave', self._cmd_leave),
                    ],
                    TYPING_TITLE: [
                        MessageHandler(
                            Filters.text & ~Filters.command, self._accept_title
                        ),
                        CommandHandler('leave', self._cmd_leave),
                    ],
                },
                fallbacks=[MessageHandler(Filters.all, self._handle_unknown)],
                name="my_conversation",
                persistent=True,
            )

            self._updater.dispatcher.add_handler(conv_handler)

            self._updater.start_polling(bootstrap_retries=-1)

        def stop(self):
            self._updater.stop()
            self._updater = None
            
        def idle(self):
            self._updater.idle()


if __name__ == "__main__":
    import argparse
    import time

    argp = argparse.ArgumentParser(description=__doc__)
    argp.add_argument('-s', '--sleep', default=120, type=int,
        help='Sleep time before exiting (sec), 0 to sleep forever')
    argp.add_argument('token',
        help='Bot token (ask BotFather)')
    args = argp.parse_args()

    logging.info("Creating bot")
    abot = bot()
    abot.start(args.token)

    logging.info("Waiting for %i sec before exiting" % (args.sleep))
    if args.sleep != 0:
    	time.sleep(args.sleep)
    else:
    	abot.idle()

    logging.info("Done")
    abot.stop()
