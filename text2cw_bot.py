#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" Telegram bot which convert text messages to cw.

This bot was born from ideas in https://t.me/cw_qrs chat to have another instrument
to exercise cw, based on ebook2cw it answers any message you send it with the convertion
to cw audio of the message itself.
It was developped and tested on a rasperrypi but should run smoothly on any linux
platform, please note that the code have been written in the perfect style of "it
just works" 0=)

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version.

This program is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
You should have received a copy of the GNU General Public License along with
this program. If not, see <http://www.gnu.org/licenses/>.
"""

__author__ = "Marco Filippi IZ3GME"
__authors__ = ["IZ3GME",]
__contact__ = "iz3gme.marco@gmail.com"
__copyright__ = "Copyright 2021 IZ3GME, Marco Filippi"
__license__ = "GPLv3"
__status__ = "Production"
__version__ = "0.0.1"


import logging

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)

logger = logging.getLogger(__name__)

from telegram.ext import Updater, CommandHandler, ConversationHandler, CallbackContext, MessageHandler, Filters, PicklePersistence
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton, ChatAction
from telegram.ext.dispatcher import run_async

import subprocess
from os import remove, rename
import re
from urllib.parse import urlparse
from random import sample

# helper function to get latest news from an RSS feed
import feedparser
from time import strftime

def get_feed(feed_url, last_n=1):
    '''
    Read RSS feed and format a CW message with lates news
    
        Parameters:
            feed_url (str): full url of rss feed
            last_n   (int): number of news to get counting from lates, 0 for all 
        
        Returns:
            cw_message (str): resulting message or None if any error occours
    '''
    NewsFeed = feedparser.parse(feed_url)

    if NewsFeed.bozo == 0:
        # feeds out there can be malformed so we try to be as safe as possible
        news = dict()
        for i,e in enumerate(NewsFeed.entries):
            published = getattr(e, "published_parsed", None)
            title = getattr(e, "title", None)
            summary = getattr(e, "summary", None)

            entry = list()
            if published:
                k = published
                entry.append(published)
            else:
                k = i
            if title:
                entry.append(title)
            if summary:
                entry.append(summary)
            news[k] = entry
        articles = [" <BT> ".join(v) for k,v in sorted(news.items())[-last_n:]]

        title = getattr(NewsFeed.feed, "title", None)
        if title:
             cw_message = "VVV VVV de " + title + " <AR> "
        else:
             cw_message = "VVV VVV de morsebot <AR>"
        cw_message += " <AR> ".join(articles)
        cw_message += " <AR> "
        if title:
            cw_message += " de " + title + " <SK>"
        else:
            cw_message += " de morsebot <SK>"

        cw_message = ' '.join(cw_message.split())  #remove multiple spaces from message
    else:
        cw_message = None
    
    return cw_message


MAIN, TYPING_WPM, TYPING_SNR, TYPING_TONE, TYPING_TITLE, TYPING_FORMAT, TYPING_DELMESSAGE, EFFECTIVEWPM, TYPING_EFFECTIVEWPM, TYPING_FEED, TYPING_NEWS_TO_READ, TYPING_SHOW_NEWS, TYPING_QRQ, TYPING_EXTRA_SPACE, TYPING_SHUFFLE = range(15)

ANSWER_FORMATS = ['voice', 'audio']


ANSWER_SHUFFLES = ['nothing', 'words', 'letters', 'both']

def shuffle_nothing(text):
    return text

def shuffle_words(text):
    t = text.split()
    return ' '.join(sample(t, len(t)))

def shuffle_letters(text):
    return ' '.join([''.join(sample(word, len(word))) for word in text.split()])

def shuffle_both(text):
    t = text.split()
    return ' '.join([''.join(sample(word, len(word))) for word in sample(t, len(t))])

do_shuffle = {
    'nothing': shuffle_nothing,
    'words': shuffle_words,
    'letters': shuffle_letters,
    'both': shuffle_both
}

DEFAULTS = {
    'wpm': 25,
    'effectivewpm': None,
    'tone': 600,
    'snr': None,
    'title': 'CW Text',
    'format': ANSWER_FORMATS[0],
    'delmessage': False,
    'feed': "https://www.ansa.it/sito/ansait_rss.xml",
    'news to read': 5,
    'show news': False,
    'qrq': None,
    'extra space': None,
    'shuffle': 'nothing',
}

class bot():

        def __init__(self):
            super(bot, self).__init__()
            self._updater = None
            self._chat_set = set()

        @property
        def _commands(self):
            return [
                ['help', 'ask for help message', self._cmd_help, None, None],
                ['feed', 'Change feed source', self._cmd_feed, TYPING_FEED, self._accept_feed],
                ['news_to_read', 'Set number of news to read from feed', self._cmd_news_to_read, TYPING_NEWS_TO_READ, self._accept_news_to_read],
                ['show_news', 'Tell me if you want to have the news in clear text also', self._cmd_show_news, TYPING_SHOW_NEWS, self._accept_show_news],
                ['read_news', 'I\'ll read the feed for you and send news in cw', self._cmd_read_news, None, None],
                ['wpm', 'Set speed in words per minute', self._cmd_wpm, TYPING_WPM, self._accept_wpm],
                ['tone', 'Set tone frequency in Hertz', self._cmd_tone, TYPING_TONE, self._accept_tone],
                ['snr', 'When set a noise background is added, valid values are -10 to 10 (in db), set to NONE to disable', self._cmd_snr, TYPING_SNR, self._accept_snr],
                ['effectivewpm', 'Set effective speed in words per minute, If set, the spaces are sent at this speed ("Farnsworth")', self._cmd_effectivewpm, TYPING_EFFECTIVEWPM, self._accept_effectivewpm],
                ['extra_space', 'Extra Word spacing. Similar to effective speed, but only affects the inter-word spacing, not the inter-character spacing', self._cmd_extra_space, TYPING_EXTRA_SPACE, self._accept_extra_space],
                ['title', 'Set answer file name', self._cmd_title, TYPING_TITLE, self._accept_title],
                ['format', 'Choose between voice and audio answer format', self._cmd_format, TYPING_FORMAT, self._accept_format],
                ['delmessage', 'Tell me if you want your messages to be deleted once converted', self._cmd_delmessage, TYPING_DELMESSAGE, self._accept_delmessage],
                ['qrq', 'Increase speed by 1 wpm in intervals of minutes', self._cmd_qrq, TYPING_QRQ, self._accept_qrq],
                ['shuffle', 'Shuffle words and/or letters in text (just in messages, not in feeds)', self._cmd_shuffle, TYPING_SHUFFLE, self._accept_shuffle],
                ['settings', 'show current settings', self._cmd_settings, None, None],
            ]

        @property
        def _helptext(self):
            message = [
                "I can convert text to cw (Morse) audio",
                "Just send me a message and I'll answer with the audio file",
                "You can change speed, tone and file name using commands",
                "(adding noise is not fully implemented yet)",
                "",
                "I'm mostly a wrapper around excellent program ebook2cw https://fkurz.net/ham/ebook2cw.html by Fabian Kurz DJ1YFK",
                "Should you find any bug please write to my creator @iz3gme",
                "",
                "I can understand this commands:", 
            ]
            for command, description, method, typing_state, accept_method in self._commands:
                if command:
                    message += ['/'+command, '    '+description]
            message += [
                "",
                "TEXT COMMANDS",
                "       CW prosigns can be generated by enclosing arbitrary letters in angle brackets (e.g. <AR>, <SK>, ...).",
                "",
                "       The tone frequency (f), speed (w), effective speed (e), volume (v, 1..100) waveform (T) and SNR (N) can be changed arbitrarily within the text by inserting commands, starting with  a  pipe  symbol,",
                "       followed by the parameter to change and the value.",
                "",
                "       Example: |f400 changes the tone frequency to 400Hz, |w60 changes the speed to 60wpm, |T3 changes the waveform to squarewave.",
            ]
            return "\n".join(message)

        @property
        def _keyboard(self):
            # decimate commands and build button rows
            rowlen = 5
            commandtext = [self._commands[i:i+rowlen] for i in range(0, len(self._commands), rowlen)]
            buttons = [[KeyboardButton('/'+j[0]) for j in i if j[0]] for i in commandtext]

            replymarkup = ReplyKeyboardMarkup(
                buttons,
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

        @property
        def _keyboard_formats(self):
            replymarkup = ReplyKeyboardMarkup(
                [
                    [
                        KeyboardButton(i) for i in ANSWER_FORMATS
                    ],
                    [
                        KeyboardButton('/leave'),
                    ],
                ],
                resize_keyboard=True,
                one_time_keyboard=False
            )
            return replymarkup

        @property
        def _keyboard_shuffles(self):
            replymarkup = ReplyKeyboardMarkup(
                [
                    [
                        KeyboardButton(i) for i in ANSWER_SHUFFLES
                    ],
                    [
                        KeyboardButton('/leave'),
                    ],
                ],
                resize_keyboard=True,
                one_time_keyboard=False
            )
            return replymarkup

        @property
        def _keyboard_yesno(self):
            replymarkup = ReplyKeyboardMarkup(
                [
                    [ 
                        "Yes",
                        "No",
                    ],
                    [
                        KeyboardButton('/leave'),
                    ],
                ],
                resize_keyboard=True,
                one_time_keyboard=False
            )
            return replymarkup

        @property
        def _keyboard_all(self):
            replymarkup = ReplyKeyboardMarkup(
                [
                    [
                        "All",
                        KeyboardButton('/leave'),
                    ],
                ],
                resize_keyboard=True,
                one_time_keyboard=False
            )
            return replymarkup

        @property
        def _keyboard_none(self):
            replymarkup = ReplyKeyboardMarkup(
                [
                    [
                        "None",
                        KeyboardButton('/leave'),
                    ],
                ],
                resize_keyboard=True,
                one_time_keyboard=False
            )
            return replymarkup

        @property
        def _keyboard_default(self):
            replymarkup = ReplyKeyboardMarkup(
                [
                    [
                        "Default",
                        KeyboardButton('/leave'),
                    ],
                ],
                resize_keyboard=True,
                one_time_keyboard=False
            )
            return replymarkup

        def _default(self, data_dict, key, value):
            if key not in data_dict:
                data_dict[key] = value
                return True
            return False

        def _you_exist(self, update: Update, context: CallbackContext):
            if context.user_data and context.user_data['exist']:
                # check for each setting and set default if needed
                for (key, value) in DEFAULTS.items():
                    if self._default(context.user_data, key, value):
                        update.message.reply_text("I now support a new setting, I set it to default for you (%s - %s)" % (key, str(value)))
                return True
            else:
                update.message.reply_text("Please use /start to begin")
            return False

        # due to persistence command methods cannot be asyncronous (or at least I don't know how to make it in a safe way)
        # time consuming steps have been isolated and we call them from sync methods
        @run_async
        def _reply_with_audio(self, update: Update, context: CallbackContext, text, reply_markup=None):
            ''' this is just an async wrapper to the sync function '''
            self._sync_reply_with_audio( update, context, text, reply_markup)

        def _sync_reply_with_audio(self, update: Update, context: CallbackContext, text, reply_markup=None):
            wpm = context.user_data['wpm']
            effectivewpm = context.user_data['effectivewpm']
            extraspace = context.user_data['extra space']
            tone = context.user_data['tone']
            snr = context.user_data['snr']
            title = context.user_data['title']
            format = context.user_data['format']
            qrq = context.user_data['qrq']

            tempfilename = "/tmp/" + update.message.from_user.first_name + "_" + str(update.message.message_id) + "_" + title
            command = ["/usr/bin/ebook2cw", "-c", "DONOTSEPARATECHAPTERS", "-o", tempfilename, "-u"]
            command.extend(["-w", str(wpm)])
            if effectivewpm is not None: command.extend(["-e", str(effectivewpm)])
            if extraspace is not None: command.extend(["-W", str(extraspace)])
            if qrq is not None: command.extend(["-Q", str(qrq)])
            command.extend(["-f", str(tone)])
            if snr is not None: command.extend(["-N", str(snr)])
            command.extend(["-B", "500", "-C", "800"]) # add fixed settings for filter and center freq 
            command.extend(["-t", title])
            command.extend(["-a", update.message.from_user.first_name])
            
            context.bot.send_chat_action(chat_id=update.effective_message.chat_id, action=ChatAction.RECORD_AUDIO)
            subprocess.run(command, input=bytes(text+"\n", encoding='utf8'))
            tempfilename += "0000.mp3" # ebook2cw always add chapternumber and extension

            context.bot.send_chat_action(chat_id=update.effective_message.chat_id, action=ChatAction.UPLOAD_AUDIO)
            if format == "audio":
                 newtempfilename = "/tmp/" + update.message.from_user.first_name + "_" + "_" + title + ".mp3"
                 rename(tempfilename, newtempfilename)
                 tempfilename = newtempfilename
                 update.message.reply_audio(audio=open(tempfilename, "rb"), title=title, reply_markup=reply_markup)
            else: #default to voice format
                update.message.reply_voice(voice=open(tempfilename, "rb"), caption=title, reply_markup=reply_markup)
            remove(tempfilename)

        @run_async
        def _do_read_news(self, update: Update, context: CallbackContext, feed, last_n, show_news):
            context.bot.send_chat_action(chat_id=update.effective_message.chat_id, action=ChatAction.TYPING)
            last_n = last_n if last_n != 'all' else 0
            try:
                text = get_feed(feed, last_n)
            except:
                text = None
            if text:
                if show_news:
                    context.bot.send_chat_action(chat_id=update.effective_message.chat_id, action=ChatAction.TYPING)
                    # send clear text adding a newline after each prosign
                    update.message.reply_text(re.sub('(<..>)', r'\1\n', text))
                # here we MUST call the sync version to avoid possible thread deadlocks
                self._sync_reply_with_audio(update, context, text, reply_markup=self._keyboard)
            else:
                update.message.reply_text("Sorry but something went wrong and I coudn't read the feed\nAre you sure you gave me a valid RSS feed URL?\nPlease start back with the command if you want to try again", reply_markup=self._keyboard)

        def _cmd_start(self, update: Update, context: CallbackContext) -> None:
            logging.debug('bot._cmd_start')

            # silently set all settings to default at first connection
            try:
                if not context.user_data['exist']:
                    pass
            except KeyError:
                for (key, value) in DEFAULTS.items():
                    self._default(context.user_data, key, value)
            context.user_data['exist'] = True

            update.message.reply_text(
                'Hi ' + update.message.from_user.first_name + '\n' + self._helptext,
                disable_web_page_preview=True,
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
                update.message.reply_text(
                    self._helptext,
                    disable_web_page_preview=True,
                    reply_markup=self._keyboard
                )
            
                return MAIN

        def _cmd_settings(self, update: Update, context: CallbackContext) -> None:
            logging.debug('bot._cmd_settings')
            if self._you_exist(update, context):
                text = "Your current settings are:\n" + "\n".join([
                    "%s\t%s" % (key, str(context.user_data[key])) for (key,default) in DEFAULTS.items()
                ])
                update.message.reply_text(text)
                return MAIN

        def _cmd_wpm(self, update: Update, context: CallbackContext) -> None:
            logging.debug('bot._cmd_wpm')
            if self._you_exist(update, context):
                if len(context.args) > 0:
                    return self._set_wpm(update, context, context.args[0])

                update.message.reply_text(
                    "Current value is %iwpm\nWhat is your desired speed?" % context.user_data["wpm"],
                    reply_markup=self._keyboard_leave
                )
                return TYPING_WPM

        def _accept_wpm(self, update: Update, context: CallbackContext) -> None:
            logging.debug('bot._accept_wpm')
            if self._you_exist(update, context):
                return self._set_wpm(update, context, update.message.text)

        def _set_wpm(self, update: Update, context: CallbackContext, value) -> None:
            try:
                value = int(value)
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

        def _cmd_effectivewpm(self, update: Update, context: CallbackContext) -> None:
            logging.debug('bot._cmd_effectivewpm')
            if self._you_exist(update, context):
                if len(context.args) > 0:
                    return self._set_effectivewpm(update, context, context.args[0])

                value = "none" if context.user_data["effectivewpm"] is None else "%iwpm" % context.user_data["effectivewpm"]
                update.message.reply_text(
                    "I can send spaces between words and letters at a different speed then text (usually slower for Farnsworth)\nCurrent value is %s\nWhat is your desired effective wpm (type none to have spaces sent at normal speed)?" % value,
                    reply_markup=self._keyboard_none
                )
                return TYPING_EFFECTIVEWPM

        def _accept_effectivewpm(self, update: Update, context: CallbackContext) -> None:
            logging.debug('bot._accept_effectivewpm')
            if self._you_exist(update, context):
                return self._set_effectivewpm(update, context, update.message.text)

        def _set_effectivewpm(self, update: Update, context: CallbackContext, value) -> None:
            try:
                value = int(value)
            except ValueError:
                # not a number, may be none?
                if value.lower() == 'none':
                    context.user_data["effectivewpm"] = None
                    update.message.reply_text(
                        "Ok - spaces will be sent at normal speed",
                        reply_markup=self._keyboard
                    )
                    return MAIN
                else:
                    update.message.reply_text(
                        "Hey ... this is not a number!!"
                    )
                return None
            else:
                if 1 <= value <= 100:
                    context.user_data["effectivewpm"] = value
                    update.message.reply_text(
                        "Ok - effective speed is now %iwpm" % value,
                        reply_markup=self._keyboard
                    )
                    return MAIN
                else:
                    update.message.reply_text(
                        "Sorry - Valid effective wpm is between 1 and 100\nTry again"
                    )
                        
        def _cmd_extra_space(self, update: Update, context: CallbackContext) -> None:
            logging.debug('bot._cmd_extra_space')
            if self._you_exist(update, context):
                if len(context.args) > 0:
                    return self._set_extra_space(update, context, context.args[0])

                value = "none" if context.user_data["extra space"] is None else str(context.user_data["extra space"])
                update.message.reply_text(
                    "I can send longer spaces between words\nCurrent value is %s\nWhat is your desired extra word spacing (eg. a value of 0.5 adds half an extra word space, type none to have spaces sent at normal speed)?" % value,
                    reply_markup=self._keyboard_none
                )
                return TYPING_EXTRA_SPACE

        def _accept_extra_space(self, update: Update, context: CallbackContext) -> None:
            logging.debug('bot._accept_extra_space')
            if self._you_exist(update, context):
                return self._set_extra_space(update, context, update.message.text)

        def _set_extra_space(self, update: Update, context: CallbackContext, value) -> None:
            try:
                value = value.replace(',', '.') # we accept both , and . as decimal separator
                value = float(value)
            except ValueError:
                # not a number, may be none?
                if value.lower() == 'none':
                    context.user_data["extra space"] = None
                    update.message.reply_text(
                        "Ok - spaces between words will be sent at normal speed",
                        reply_markup=self._keyboard
                    )
                    return MAIN
                else:
                    update.message.reply_text(
                        "Hey ... this is not a number!!"
                    )
                return None
            else:
                if 0 < value <= 10:
                    context.user_data["extra space"] = value
                    update.message.reply_text(
                        "Ok - extra space is now %s" % str(value),
                        reply_markup=self._keyboard
                    )
                    return MAIN
                else:
                    update.message.reply_text(
                        "Sorry - Valid extra space is between 0 and 10\nTry again"
                    )

        def _cmd_tone(self, update: Update, context: CallbackContext) -> None:
            logging.debug('bot._cmd_tone')
            if self._you_exist(update, context):
                if len(context.args) > 0:
                    return self._set_tone(update, context, context.args[0])

                update.message.reply_text(
                    "Current value is %iHz\nWhat is your desired tone frequency?" % context.user_data["tone"],
                    reply_markup=self._keyboard_leave
                )
                return TYPING_TONE

        def _accept_tone(self, update: Update, context: CallbackContext) -> None:
            logging.debug('bot._accept_tone')
            if self._you_exist(update, context):
                return self._set_tone(update, context, update.message.text)

        def _set_tone(self, update: Update, context: CallbackContext, value) -> None:
            try:
                value = int(value)
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
                if len(context.args) > 0:
                    return self._set_snr(update, context, context.args[0])

                value = "none" if context.user_data["snr"] is None else "%idb" % context.user_data["snr"]
                update.message.reply_text(
                    "I have only a partial support for noise: after mixing signal with white noise audio will be filtered with a 500Hz filter centered at 800Hz,\nCurrent value is %s\nWhat is your desired snr (type none for no added noise at all)?" % value,
                    reply_markup=self._keyboard_none
                )
                return TYPING_SNR

        def _accept_snr(self, update: Update, context: CallbackContext) -> None:
            logging.debug('bot._accept_snr')
            if self._you_exist(update, context):
                return self._set_snr(update, context, update.message.text)

        def _set_snr(self, update: Update, context: CallbackContext, value) -> None:
            try:
                value = int(value)
            except ValueError:
                if value.lower() == 'none':
                    context.user_data["snr"] = None
                    update.message.reply_text(
                        "Ok - no noise will be added",
                        reply_markup=self._keyboard
                    )
                    return MAIN
                else:
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
                        
        def _cmd_qrq(self, update: Update, context: CallbackContext) -> None:
            logging.debug('bot._cmd_qrq')
            if self._you_exist(update, context):
                if len(context.args) > 0:
                    return self._set_qrq(update, context, context.args[0])

                value = "none" if context.user_data["qrq"] is None else "%i minutes" % context.user_data["qrq"]
                update.message.reply_text(
                    "Current value is %s\nHow often (in minutes) should I increase speed (type none for no qrq)?" % value,
                    reply_markup=self._keyboard_none
                )
                return TYPING_QRQ

        def _accept_qrq(self, update: Update, context: CallbackContext) -> None:
            logging.debug('bot._accept_qrq')
            if self._you_exist(update, context):
                return self._set_qrq(update, context, update.message.text)

        def _set_qrq(self, update: Update, context: CallbackContext, value) -> None:
            try:
                value = int(value)
            except ValueError:
                if value.lower() == 'none':
                    context.user_data["qrq"] = None
                    update.message.reply_text(
                        "Ok - no qrq",
                        reply_markup=self._keyboard
                    )
                    return MAIN
                else:
                    update.message.reply_text(
                        "Hey ... this is not a number!!"
                    )
                return None
            else:
                if 1 <= value <= 60:
                    context.user_data["qrq"] = value
                    update.message.reply_text(
                        "Ok - qrq is now %i minutes" % value,
                        reply_markup=self._keyboard
                    )
                    return MAIN
                else:
                    update.message.reply_text(
                        "Sorry - Valid qrq is between 1 and 60 minutes\nTry again"
                    )
                        
        def _cmd_title(self, update: Update, context: CallbackContext) -> None:
            logging.debug('bot._cmd_title')
            if self._you_exist(update, context):
                if len(context.args) > 0:
                    return self._set_title(update, context, " ".join(context.args))

                update.message.reply_text(
                    "Current title is %s\nWhat is your desired title?" % context.user_data["title"],
                    reply_markup=self._keyboard_leave
                )
                return TYPING_TITLE

        def _accept_title(self, update: Update, context: CallbackContext) -> None:
            logging.debug('bot._accept_title')
            if self._you_exist(update, context):
                return self._set_title(update, context, update.message.text)

        def _set_title(self, update: Update, context: CallbackContext, value) -> None:
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

        def _cmd_format(self, update: Update, context: CallbackContext) -> None:
            logging.debug('bot._cmd_format')
            if self._you_exist(update, context):
                if len(context.args) > 0:
                    return self._set_format(update, context, context.args[0])

                update.message.reply_text(
                    "\n".join([
                        "Current format is %s" % context.user_data["format"],
                        "I can send cw as either " + ' or '.join(ANSWER_FORMATS),
                        "Which one you prefere?"
                    ]),
                    reply_markup=self._keyboard_formats
                )
                return TYPING_FORMAT

        def _accept_format(self, update: Update, context: CallbackContext) -> None:
            logging.debug('bot._accept_format')
            if self._you_exist(update, context):
                return self._set_format(update, context, update.message.text)

        def _set_format(self, update: Update, context: CallbackContext, value) -> None:
            value = value.lower()
            if value not in ANSWER_FORMATS:
                update.message.reply_text(
                    "Hey ... this is not a format I know!!\nPlease choose between "+ ', '.join(ANSWER_FORMATS)
                )
                return None
            else:
                context.user_data["format"] = value
                update.message.reply_text(
                    "Ok - format is now %s" % value,
                    reply_markup=self._keyboard
                )
                return MAIN

        def _cmd_shuffle(self, update: Update, context: CallbackContext) -> None:
            logging.debug('bot._cmd_shuffle')
            if self._you_exist(update, context):
                if len(context.args) > 0:
                    return self._set_shuffle(update, context, context.args[0])

                update.message.reply_text(
                    "\n".join([
                        "Current shuffle is %s" % context.user_data["shuffle"],
                        "I can shuffle " + ', '.join(ANSWER_FORMATS) + " in messages you send me so you can have a different way to exercize",
                        "Please note that I'll never shuffle news text",
                        "What do you want me to shuffle?"
                    ]),
                    reply_markup=self._keyboard_shuffles
                )
                return TYPING_SHUFFLE

        def _accept_shuffle(self, update: Update, context: CallbackContext) -> None:
            logging.debug('bot._accept_shuffle')
            if self._you_exist(update, context):
                return self._set_shuffle(update, context, update.message.text)

        def _set_shuffle(self, update: Update, context: CallbackContext, value) -> None:
            value = value.lower()
            if value not in ANSWER_SHUFFLES:
                update.message.reply_text(
                    "Hey ... this is not a shuffle I know!!\nPlease choose between "+ ', '.join(ANSWER_SHUFFLES)
                )
                return None
            else:
                context.user_data["shuffle"] = value
                update.message.reply_text(
                    "Ok - shuffle is now %s" % value,
                    reply_markup=self._keyboard
                )
                return MAIN

        def _cmd_delmessage(self, update: Update, context: CallbackContext) -> None:
            logging.debug('bot._cmd_delmessage')
            if self._you_exist(update, context):
                if len(context.args) > 0:
                    return self._set_delmessage(update, context, context.args[0])

                update.message.reply_text(
                    "\n".join([
                        "Previously you asked me to delete your messages" if context.user_data["delmessage"] else "Actually I dont delete your messages",
                        "Do you want me to delete your messages?"
                    ]),
                    reply_markup=self._keyboard_yesno
                )
                return TYPING_DELMESSAGE

        def _accept_delmessage(self, update: Update, context: CallbackContext) -> None:
            logging.debug('bot._accept_delmessage')
            if self._you_exist(update, context):
                return self._set_delmessage(update, context, update.message.text)

        def _set_delmessage(self, update: Update, context: CallbackContext, value) -> None:
            value = value.lower()
            if value not in ["yes", "no"]:
                update.message.reply_text(
                    "Please be serious, answer Yes or No"
                )
                return None
            else:
                value = value == "yes"
                context.user_data["delmessage"] = value
                update.message.reply_text(
                    "Ok - I'll delete messages from now on" if value else "OK - I'll leave your messages untouched",
                    reply_markup=self._keyboard
                )
                return MAIN

        def _cmd_feed(self, update: Update, context: CallbackContext) -> None:
            logging.debug('bot._cmd_feed')
            if self._you_exist(update, context):
                if len(context.args) > 0:
                    return self._set_feed(update, context, " ".join(context.args))

                update.message.reply_text(
                    "Current feed URL is\n%s\nPlease give the full URL of your RSS feed?\nType default if you want to reset to default feed" % context.user_data["feed"],
                    reply_markup=self._keyboard_default
                )
                return TYPING_FEED

        def _accept_feed(self, update: Update, context: CallbackContext) -> None:
            logging.debug('bot._accept_feed')
            if self._you_exist(update, context):
                return self._set_feed(update, context, update.message.text)

        def _set_feed(self, update: Update, context: CallbackContext, value) -> None:
            if value.lower() == 'default':
                value = DEFAULTS['feed']
            if urlparse(value)[0] not in ('http', 'https', 'ftp', 'feed'):
                update.message.reply_text(
                    "Hey ... this is not a valid URL!!"
                )
                return None
            else:
                context.user_data["feed"] = value
                update.message.reply_text(
                    "Ok - I'll read news from\n%s\nHope you'll like it" % value,
                    reply_markup=self._keyboard
                )
            return MAIN

        def _cmd_news_to_read(self, update: Update, context: CallbackContext) -> None:
            logging.debug('bot._cmd_news_to_read')
            if self._you_exist(update, context):
                if len(context.args) > 0:
                    return self._set_news_to_read(update, context, context.args[0])

                update.message.reply_text(
                    "How many news do you want from the feed? (current value is %s)\nRemember that my reading speed is about 1 news/s so if you ask me 60 news I'll take about 1 minute to answer, if you are in a hurry please ask someone else :-P" % str(context.user_data["news to read"]),
                    reply_markup=self._keyboard_leave
                )
                return TYPING_NEWS_TO_READ

        def _accept_news_to_read(self, update: Update, context: CallbackContext) -> None:
            logging.debug('bot._accept_news_to_read')
            if self._you_exist(update, context):
                return self._set_news_to_read(update, context, update.message.text)

        def _set_news_to_read(self, update: Update, context: CallbackContext, value) -> None:
            value = value.lower()
            try:
                value = int(value)
                if value < 1:
                    update.message.reply_text(
                        "Please answer with a number greater then 0"
                    )
                    return None
            except ValueError:
                if value != 'all':
                    update.message.reply_text(
                        "Please give a number or all ... I wont accept anything else"
                    )
                    return None
            update.message.reply_text(
                "Ok - I'll send you %s news" % str(value),
                reply_markup=self._keyboard
            )
            context.user_data["news to read"] = value
            return MAIN
                
        def _cmd_show_news(self, update: Update, context: CallbackContext) -> None:
            logging.debug('bot._cmd_show_news')
            if self._you_exist(update, context):
                if len(context.args) > 0:
                    return self._set_show_news(update, context, context.args[0])

                update.message.reply_text(
                    "\n".join([
                        "Previously you asked me to show the news in clear text" if context.user_data["show news"] else "Actually I dont show the news text to you",
                        "Do you want me to send the news text to you?"
                    ]),
                    reply_markup=self._keyboard_yesno
                )
                return TYPING_SHOW_NEWS

        def _accept_show_news(self, update: Update, context: CallbackContext) -> None:
            logging.debug('bot._accept_show_news')
            if self._you_exist(update, context):
                return self._set_show_news(update, context, update.message.text)

        def _set_show_news(self, update: Update, context: CallbackContext, value) -> None:
            value = value.lower()
            if value not in ["yes", "no"]:
                update.message.reply_text(
                    "Please be serious, answer Yes or No"
                )
                return None
            else:
                value = value == "yes"
                context.user_data["show news"] = value
                update.message.reply_text(
                    "Ok - I'll show the news text to you from now on" if value else "OK - I'll keep the news text secret :-P",
                    reply_markup=self._keyboard
                )
                return MAIN

        def _cmd_read_news(self, update: Update, context: CallbackContext) -> None:
            logging.debug('bot._cmd_read_news')
            if self._you_exist(update, context):
                feed = context.user_data["feed"]
                last_n = context.user_data["news to read"]
                show_news = context.user_data["show news"]
                # do the real job in differt thread
                self._do_read_news(update, context, feed, last_n, show_news)
                return MAIN

        def _cmd_leave(self, update: Update, context: CallbackContext) -> None:
            logging.debug('bot._cmd_leave')
            if self._you_exist(update, context):
                update.message.reply_text(
                    "Ok ... leaving value unchanged",
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
                delmessage = context.user_data['delmessage']
                shuffle =  context.user_data['shuffle']

                text = update.message.text
                text = do_shuffle[shuffle](text)
                self._reply_with_audio(update, context, text)
                if delmessage:
                    update.message.delete()

        def start(self, token):
            pp = PicklePersistence(filename='text2cw_bot.data')
            self._updater = Updater(token, persistence=pp, use_context=True)

            # tell BotFather my list of commands
            commands = [ [command, description] for command, description, method, typing_state, accept_method in self._commands if command]
            self._updater.bot.setMyCommands(commands)

            # build conversation handler for each state
            main_commands = [CommandHandler(command, method) for command, description, method, typing_state, accept_method in self._commands if command]

            # build all accept answer state
            typing_states = {
                typing_state: [
                        MessageHandler(
                            Filters.text & ~Filters.command, accept_method
                        ),
                        CommandHandler('leave', self._cmd_leave),
                    ]
                for command, description, method, typing_state, accept_method in self._commands 
                if typing_state
            }

            # build conversation
            conv_handler = ConversationHandler(
                entry_points=[CommandHandler('start', self._cmd_start)],
                states={
                    **typing_states,
                    MAIN: main_commands + [
                        MessageHandler(Filters.text & ~Filters.command, self._handle_text),
                    ],
                },
                fallbacks=[
                    CommandHandler('stop', self._cmd_stop),
                    MessageHandler(Filters.all, self._handle_unknown),
                ],
                name="my_conversation",
                persistent=True,
            )

            self._updater.dispatcher.add_handler(conv_handler)
            self._updater.dispatcher.add_handler(MessageHandler(Filters.all, self._handle_unknown))

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
