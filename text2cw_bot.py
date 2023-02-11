#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" Telegram bot which convert text messages to cw.

This bot was born from ideas in https://t.me/cw_qrs chat to have another
instrument to exercise cw, based on ebook2cw it answers any message you send
it with the convertion to cw audio of the message itself.
It was developped and tested on a rasperrypi but should run smoothly on any
linux platform, please note that the code have been written in the perfect
style of "it just works" 0=)

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
__authors__ = ["IZ3GME", ]
__contact__ = "iz3gme.marco@gmail.com"
__copyright__ = "Copyright 2021 IZ3GME, Marco Filippi"
__license__ = "GPLv3"
__status__ = "Production"
__version__ = "0.0.1"


from telegram.ext import Updater, CommandHandler, ConversationHandler, \
    CallbackContext, MessageHandler, Filters, PicklePersistence
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, \
    KeyboardButton, ChatAction, ParseMode
from telegram.ext.dispatcher import run_async
from telegram.utils.helpers import escape_markdown
from xhtml2pdf import pisa

import subprocess
from os import remove, rename
import re
from urllib.parse import urlparse
import string
from datetime import datetime

# Remember, to allow repeatability all random functions must be called
# exclusively from main thread
from random import sample, choices, choice, seed

# helper function to get latest news from an RSS feed
import feedparser
from time import strftime

# helper functions to convert numbers to text
from num2text import NumberToText, FindNumbers

# helper word dictionary class
from parole import dizionario

import logging

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)


def get_feed(feed_url, last_n=1, news_time=True, title_filter=None):
    '''
    Read RSS feed and format a CW message with lates news

        Parameters:
            feed_url (str): full url of rss feed
            last_n   (int): number of news to get, 0 for all
            title_filter (str): filter only news with given string in title
                                case insensitive

        Returns:
            cw_message (str): resulting message or None if any error occours
    '''
    NewsFeed = feedparser.parse(feed_url)

    if NewsFeed.bozo == 0:
        # feeds out there can be malformed so we try to be as safe as possible
        news = dict()
        for i, e in enumerate(NewsFeed.entries):
            published = getattr(e, "published_parsed", None)
            title = getattr(e, "title", None)
            summary = getattr(e, "summary", None)

            if title_filter is None or title is None or title_filter.lower() in title.lower():
                entry = list()
                if published and news_time:
                    k = published
                    entry.append(strftime("%d/%m/%Y %H:%M", published))
                else:
                    k = i
                if title:
                    entry.append(title)
                if summary:
                    # remove any <a href> tag from text
                    # not a perfect re but works
                    summary = re.sub(r'<a .*>.*</a>', '', summary)
                    entry.append(summary)
                news[k] = entry
        articles = [" <BT> ".join(v)
                    for k, v in sorted(news.items())[-last_n:]]

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
    else:
        cw_message = None

    return cw_message


def safe_file_name(name: str):
    # remove unsafe char from file name
    pattern = re.compile(" [^a-zA-Z0-9_]")
    return pattern.sub('', name)


MAIN, TYPING_WPM, TYPING_SNR, TYPING_TONE, TYPING_TITLE, TYPING_FORMAT, \
    TYPING_DELMESSAGE, EFFECTIVEWPM, TYPING_EFFECTIVEWPM, TYPING_FEED, \
    TYPING_NEWS_TO_READ, TYPING_SHOW_NEWS, TYPING_QRQ, TYPING_EXTRA_SPACE, \
    TYPING_SHUFFLE, TYPING_NEWS_TIME, TYPING_SIMPLIFY, TYPING_NOACCENTS, \
    TYPING_CHARSET, TYPING_GROUPS, TYPING_WAVEFORM, TYPING_CONVERTNUMBERS, \
    TYPING_GROUPS_PREFIX, TYPING_WORD_MAX, TYPING_SIGN \
    = range(25)

ANSWER_FORMATS = ['voice', 'audio']


ANSWER_SHUFFLES = ['nothing', 'words', 'letters', 'both']


ANSWER_WAVEFORM = ['sine', 'sawtooth', 'square']


ANSWER_SIGNS = ['Ariete', 'Toro', 'Gemelli', 'Cancro', 'Leone', 'Vergine',
                'Bilancia', 'Scorpione', 'Sagittario', 'Capricorno', 'Aquario',
                'Pesci']


def shuffle_nothing(text):
    return text


def shuffle_words(text):
    t = text.split()
    return ' '.join(sample(t, len(t)))


def shuffle_letters(text):
    return ' '.join([''.join(sample(word, len(word)))
                     for word in text.split()])


def shuffle_both(text):
    t = text.split()
    return ' '.join([''.join(sample(word, len(word)))
                     for word in sample(t, len(t))])


do_shuffle = {
    'nothing': shuffle_nothing,
    'words': shuffle_words,
    'letters': shuffle_letters,
    'both': shuffle_both
}


def gen_groups(charset: str, k: int):
    # this is a very corner case but with 1 symbol there's only 1 possible seq
    if len(charset) == 1:
        # this is a very corner case but with 1 symbol
        # there's only 1 possible seq
        seq = charset[0] * 5 * k
    else:
        seq = choices(charset, k=5*k)
        # avoid more that 2 repeating char
        for i in range(len(seq)-3):
            while (seq[i] == seq[i+1] and seq[i+1] == seq[i+2]):
                seq[i+2] = choice(charset)
        seq = "".join(seq)
    # split in groups of 5
    groups = [seq[i:i+5] for i in range(0, len(seq), 5)]
    return groups


def create_exercise_pdf(groups, filename: str, wpm, effectivewpm,
                        extraspace, charset, exseed):
    # build HTML
    source_html = '''
        <html>
          <head>
            <style>
              @page {
                size: A4 portrait;
                margin-top: 1cm;
                margin-bottom: 1cm;
                margin-left: 3cm;
                margin-right: 3cm;
              }
              @font-face {
                font-family: myMono;
                src: url('/usr/share/fonts/truetype/ubuntu/UbuntuMono-R.ttf');
              }
              td.main {
                height: 8cm;
                text-align: center;
              }
              td {
                text-align: center;
                height:0.6cm;
                font-family:"myMono";
                font-size: 30em;
              }
            </style>
          </head>
          <body>'''

    source_html += "Random exercise generated by text2cw bot at " + \
        datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    if exseed is not None:
        source_html += " exercise code " + exseed
    source_html += "<br>"
    source_html += "cw audio at " + str(wpm) + "wpm"
    if effectivewpm is not None:
        source_html += ", effective speed " + str(effectivewpm)
    if extraspace is not None:
        source_html += ", extra space " + str(extraspace)
    source_html += "<br>"
    source_html += "charset " + charset + "<br>"

    exercise_tables = list()
    for exercise in groups:
        table = '<table>'
        # split groups in lines of 5
        groups_lines = [exercise[i:i+5] for i in range(0, len(exercise), 5)]
        for line in groups_lines:
            table += '<tr>'
            for group in line:
                table += '<td>' + " ".join(list(group)) + '</td>'
            table += '</tr>'
        table += '</table>'
        exercise_tables.append(table)

    source_html += '''<table class="main">
            <tr>
              <td class="main">'''
    source_html += '''</td>
            </tr>
            <tr>
              <td> <hr> </td>
            </tr>
            <tr>
              <td class="main">'''.join(exercise_tables)
    source_html += '''</td>
            </tr>
          </table>'''

    source_html += '''</body>
          </html>'''

    # open output file for writing (truncated binary)
    result_file = open(filename, "w+b")

    # convert HTML to PDF
    pisa_status = pisa.CreatePDF(
            source_html,                # the HTML to convert
            dest=result_file)           # file handle to recieve result

    # close output file
    result_file.close()                 # close output file

    # return False on success and True on errors
    return pisa_status.err


def simplify_text(s: str):
    """ Simplify string removing uncommon chars """

    # replace unwanted chars with space
    # acents are left for specific translate function
    # <> are needed for prosigns and | for inline commands
    pattern = re.compile("[^a-zA-Z0-9-/.?'=,<>|àèéìòùç]")
    simple = pattern.sub(' ', s)

    # remove multiple spaces from message
    simple = ' '.join(simple.split())

    return simple


def translate_accents(s: str):
    # translate accents to simple letters
    return s.translate(str.maketrans("àèéìòùç", "aeeiouc"))


def convert_numbers(s: str):
    """ Add text translation to all numbers in string """

    pos = list(FindNumbers(s))
    pos.reverse()   # reverse positions list so we'll loop from the end
    for start, end, snumber in pos:
        s = s[:end] + ' ' + NumberToText(snumber) + ' ' + s[end:]
    return s

NEWS_FEED = 'https://www.ansa.it/sito/ansait_rss.xml'
#HOROSCOPE_FEED = 'http://it.horoscopofree.com/rss/horoscopofree-it.rss'

DEFAULTS = {
    'wpm': [25],
    'effectivewpm': None,
    'tone': 600,
    'snr': None,
    'title': 'CW Text',
    'format': ANSWER_FORMATS[0],
    'delmessage': False,
    'feed': NEWS_FEED,
#    'horoscope feed': HOROSCOPE_FEED,
    'news to read': 5,
    'show news': False,
    'qrq': None,
    'extra space': None,
    'shuffle': 'nothing',
    'news time': True,
    'simplify': False,
    'no accents': False,
    'charset': string.ascii_uppercase + string.digits,
    'groups': 20,
    'waveform': ANSWER_WAVEFORM[0],
    'convert numbers': False,
    'groups prefix': True,
    'word max': 10,
}


class bot():

        def __init__(self):
            super(bot, self).__init__()
            self._updater = None

        @property
        def _commands(self):
            return [
                ['feed', 'Change feed source', self._cmd_feed,
                    TYPING_FEED, self._accept_feed],
                ['news_to_read', 'Set number of news to read from feed',
                    self._cmd_news_to_read, TYPING_NEWS_TO_READ,
                    self._accept_news_to_read],
                ['show_news',
                    'Tell me if you want to have the news and QSO in clear'
                    ' text also',
                    self._cmd_show_news, TYPING_SHOW_NEWS,
                    self._accept_show_news],
                ['news_time',
                    'Do you want published date and time in front of each '
                    'news? (if available)',
                    self._cmd_news_time, TYPING_NEWS_TIME,
                    self._accept_news_time],
                ['read_news',
                    "I`ll read the feed for you and send news in cw",
                    self._cmd_read_news, None, None],
                ['charset',
                    'Change the set of chars used to generate groups',
                    self._cmd_charset, TYPING_CHARSET,
                    self._accept_charset],
                ['groups',
                    'Change the number of groups to send',
                    self._cmd_groups, TYPING_GROUPS,
                    self._accept_groups],
                ['groups_prefix',
                    'Add a VVV= prefix to groups',
                    self._cmd_groups_prefix, TYPING_GROUPS_PREFIX,
                    self._accept_groups_prefix],
                ['send_groups',
                    "Generate and send a sequence of random groups",
                    self._send_groups, None, None],
                ['groups_exercise',
                    'Generate three full group exercises using current'
                    ' settings and send both cw audio and a printable PDF;'
                    ' if you want a repeatable exercise add a keyword to the'
                    ' command, same keyword same exercise,'
                    ' eg. /groups_exercise mykey1',
                    self._groups_exercise, None, None],
                ['wpm', 'Set speed in words per minute', self._cmd_wpm,
                    TYPING_WPM, self._accept_wpm],
                ['send_callsign',
                    'Pickup a random callsign using'
                    ' only current charset and send it',
                    self._send_callsign, None, None],
                ['send_word',
                    'Pickup a random words from (italian) dictionary using'
                    ' only current charset and send it, follow the command'
                    ' with the number of desired words (default just one)',
                    self._send_word, None, None],
                ['word_max', 'Set max word lenght', self._cmd_word_max,
                    TYPING_WORD_MAX, self._accept_word_max],
                ['tone', 'Set tone frequency in Hertz', self._cmd_tone,
                    TYPING_TONE, self._accept_tone],
                ['waveform', 'Set waveform', self._cmd_waveform,
                    TYPING_WAVEFORM, self._accept_waveform],
                ['snr',
                    'When set a noise background is added, valid values are '
                    '-10 to 10 (in db), set to NONE to disable', self._cmd_snr,
                    TYPING_SNR, self._accept_snr],
                ['effectivewpm', 'Set effective speed in words per minute, If '
                    'set, the spaces are sent at this speed ("Farnsworth")',
                    self._cmd_effectivewpm, TYPING_EFFECTIVEWPM,
                    self._accept_effectivewpm],
                ['extra_space', 'Extra Word spacing. Similar to effective '
                    'speed, but only affects the inter-word spacing, not the '
                    'inter-character spacing', self._cmd_extra_space,
                    TYPING_EXTRA_SPACE, self._accept_extra_space],
                ['title', 'Set answer file name', self._cmd_title,
                    TYPING_TITLE, self._accept_title],
                ['format', 'Choose between voice and audio answer format',
                    self._cmd_format, TYPING_FORMAT, self._accept_format],
                ['delmessage', 'Tell me if you want your messages to be '
                    'deleted once converted', self._cmd_delmessage,
                    TYPING_DELMESSAGE, self._accept_delmessage],
                ['qrq', 'Increase speed by 1 wpm in intervals of minutes',
                    self._cmd_qrq, TYPING_QRQ, self._accept_qrq],
                ['qso', 'Generate a random QSO',
                    self._cmd_qso, None, None],
                ['shuffle', 'Shuffle words and/or letters in text (just in '
                    'messages, not in feeds or qso)', self._cmd_shuffle,
                    TYPING_SHUFFLE, self._accept_shuffle],
                ['simplify', 'Remove uncommon symbols from message',
                    self._cmd_simplify, TYPING_SIMPLIFY,
                    self._accept_simplify],
                ['noaccents', 'Translate accented letters to simple ones',
                    self._cmd_noaccents, TYPING_NOACCENTS,
                    self._accept_noaccents],
                ['convertnumbers', 'Add text translation to each number in'
                                   ' text (only in text messages and news)',
                    self._cmd_convertnumbers, TYPING_CONVERTNUMBERS,
                    self._accept_convertnumbers],
                ['help', 'ask for help message', self._cmd_help, None, None],
                ['settings', 'show current settings', self._cmd_settings,
                    None, None],
#                ['horoscope', 'Read horoscope (in italian)',
#                    self._cmd_horoscope, TYPING_SIGN,
#                    self._accept_sign],
            ]

        @property
        def _helptext(self):
            message = [
                "I can convert text to cw (Morse) audio",
                "Just send me a message and I'll answer with the audio file",
                "You can change speed, tone and file name using commands",
                "(adding noise is not fully implemented yet)",
                "",
                "I'm mostly a wrapper around excellent program ebook2cw",
                "https://fkurz.net/ham/ebook2cw.html by Fabian Kurz DJ1YFK",
                "Should you find any bug please write to my creator @iz3gme",
                "",
                "I can understand this commands:",
            ]
            for command, description, method, typing_state, accept_method \
                    in self._commands:
                if command:
                    message += ['/'+command, '    '+description]
            message += [
                "",
                "TEXT COMMANDS",
                "       CW prosigns can be generated by enclosing arbitrary "
                "letters in angle brackets (e.g. <AR>, <SK>, ...).",
                "",
                "       The tone frequency (f), speed (w), effective speed "
                "(e), volume (v, 1..100) waveform (T) and SNR (N) can be "
                "changed arbitrarily within the text by inserting "
                "commands, starting with  a  pipe  symbol,"
                "followed by the parameter to change and the value.",
                "",
                "       Example: |f400 changes the tone frequency to 400Hz, "
                "|w60 changes the speed to 60wpm, |T3 changes the "
                "waveform to squarewave.",
            ]
            return "\n".join(message)

        @property
        def _keyboard(self):
            # decimate commands and build button rows
            rowlen = 5
            commandtext = [self._commands[i:i+rowlen]
                           for i in range(0, len(self._commands), rowlen)]
            buttons = [[KeyboardButton('/'+j[0])
                        for j in i if j[0]] for i in commandtext]

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
        def _keyboard_signs(self):
            replymarkup = ReplyKeyboardMarkup(
                [
                    [
                        KeyboardButton(i) for i in ANSWER_SIGNS
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
        def _keyboard_waveform(self):
            replymarkup = ReplyKeyboardMarkup(
                [
                    [
                        KeyboardButton(i) for i in ANSWER_WAVEFORM
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

        @property
        def _keyboard_charset(self):
            replymarkup = ReplyKeyboardMarkup(
                [
                    [
                        "Letters", "Digits", "Both", "HST", "All",
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
                        update.message.reply_text(
                            "I now support a new setting, I set it to default "
                            "for you (%s - %s)" % (key, str(value)))
                # silently save user name for debugging
                self._default(context.user_data, 'username',
                              update.message.from_user.name)
                # try to update username if we had None previously
                if update.message.from_user.name is not None and context.user_data['username'] is None:
                    context.user_data['username'] = update.message.from_user.name
                return True
            else:
                update.message.reply_text("Please use /start to begin")
            return False

        # due to persistence command methods cannot be asyncronous
        # (or at least I don't know how to make it in a safe way)
        # time consuming steps have been isolated and we call them using
        # run_async()
        def _reply_with_audio(self, update: Update, context: CallbackContext,
                              text, reply_markup=None):
            wpm = context.user_data['wpm']
            effectivewpm = context.user_data['effectivewpm']
            extraspace = context.user_data['extra space']
            tone = context.user_data['tone']
            snr = context.user_data['snr']
            title = context.user_data['title']
            format = context.user_data['format']
            qrq = context.user_data['qrq']
            simplify = context.user_data['simplify']
            no_accents = context.user_data['no accents']
            waveform = context.user_data['waveform']

            if simplify:
                    text = simplify_text(text)
            if no_accents:
                    text = translate_accents(text)

            # remove multiple spaces from message
            text = ' '.join(text.split())

            if '-wpm-' not in title:
                # add wpm to end of title if not user supplied
                title = title + ' -wpm-wpm'

            for w in wpm:
                # as title can be user supplied be very safe in substitution
                t = title.replace('-wpm-', str(w))

                tempfilename = "/tmp/" + \
                    safe_file_name(update.message.from_user.name) + \
                    "_" + str(update.message.message_id) + "_" + t
                command = ["/usr/bin/ebook2cw", "-c", "DONOTSEPARATECHAPTERS",
                           "-o", tempfilename, "-u"]
                command.extend(["-w", str(w)])
                if effectivewpm is not None:
                    command.extend(["-e", str(effectivewpm)])
                if extraspace is not None:
                    command.extend(["-W", str(extraspace)])
                if qrq is not None:
                    command.extend(["-Q", str(qrq)])
                command.extend(["-f", str(tone)])
                if snr is not None:
                    command.extend(["-N", str(snr)])
                    # add fixed settings for filter and center freq
                    command.extend(["-B", "500", "-C", "800"])
                command.extend(["-t", t])
                command.extend(["-a", update.message.from_user.name])
                command.extend(["-T", str(ANSWER_WAVEFORM.index(waveform))])

                context.bot.send_chat_action(
                                chat_id=update.effective_message.chat_id,
                                action=ChatAction.RECORD_AUDIO)
                subprocess.run(command,
                               input=bytes(text+"\n", encoding='utf8'))
                # ebook2cw always add chapternumber and extension
                tempfilename += "0000.mp3"

                context.bot.send_chat_action(
                                chat_id=update.effective_message.chat_id,
                                action=ChatAction.UPLOAD_AUDIO)
                if format == "audio":
                    newtempfilename = "/tmp/" + \
                        safe_file_name(update.message.from_user.name) + "_" + t + ".mp3"
                    rename(tempfilename, newtempfilename)
                    tempfilename = newtempfilename
                    update.message.reply_audio(
                                        audio=open(tempfilename, "rb"),
                                        title=t,
                                        reply_markup=reply_markup)
                else:  # default to voice format
                    update.message.reply_voice(
                                        voice=open(tempfilename, "rb"),
                                        caption=t,
                                        reply_markup=reply_markup)
                remove(tempfilename)

        def _do_qso(self, update: Update, context: CallbackContext, show_news):
            context.bot.send_chat_action(
                            chat_id=update.effective_message.chat_id,
                            action=ChatAction.TYPING)
            try:
                command = ["/usr/bin/QSO"]
                output = subprocess.run(command,
                                        capture_output=True, text=True)
                text = output.stdout
            except:
                text = None
            if text:
                if show_news:
                    context.bot.send_chat_action(
                            chat_id=update.effective_message.chat_id,
                            action=ChatAction.TYPING)
                    update.message.reply_text(
                            '||'+escape_markdown(text, version=2)+'||',
                            parse_mode=ParseMode.MARKDOWN_V2)
                # to avoid possible thread deadlocks we cannot use run_async()
                self._reply_with_audio(update, context, text,
                                       reply_markup=self._keyboard)
            else:
                update.message.reply_text(
                    "Sorry but something went wrong, you probably hit a bug\n"
                    "Please try again later",
                    reply_markup=self._keyboard)

        def _do_read_news(self, update: Update, context: CallbackContext,
                          feed, last_n, show_news, convertnumbers,
                          title_filter=None):
            news_time = context.user_data['news time']
            context.bot.send_chat_action(
                            chat_id=update.effective_message.chat_id,
                            action=ChatAction.TYPING)
            last_n = last_n if last_n != 'all' else 0
            try:
                text = get_feed(feed, last_n, news_time, title_filter)
            except:
                text = None
            if text:
                if show_news:
                    context.bot.send_chat_action(
                            chat_id=update.effective_message.chat_id,
                            action=ChatAction.TYPING)
                    # send clear text adding a newline after each prosign
                    mtext = re.sub('(<..>)', r'\1\n', text)
                    # split message in 4096 chunks (telegram message limit)
                    for i in range(0, len(mtext), 4096):
                        update.message.reply_text(
                            '||'+escape_markdown(mtext[i:i+4096], version=2)+'||',
                            parse_mode=ParseMode.MARKDOWN_V2
                        )
                if convertnumbers:
                    text = convert_numbers(text)
                # to avoid possible thread deadlocks we cannot use run_async()
                self._reply_with_audio(update, context, text,
                                       reply_markup=self._keyboard)
            else:
                update.message.reply_text(
                    "Sorry but something went wrong and I coudn't read the"
                    " feed\n"
                    "Are you sure you gave me a valid RSS feed URL?\n"
                    "Please start back with the command if you want to try "
                    "again",
                    reply_markup=self._keyboard)

        def _do_groups_exercise(self, update: Update, context: CallbackContext,
                                groups, charset, seed) -> None:
            wpm = context.user_data['wpm']
            effectivewpm = context.user_data['effectivewpm']
            extraspace = context.user_data['extra space']
            prefix = context.user_data['groups prefix']

            for exercise in groups:
                text = "VVV= " if prefix else ""
                text += " ".join(exercise)
                self._reply_with_audio(
                                update,
                                context,
                                text)

            context.bot.send_chat_action(
                        chat_id=update.effective_message.chat_id,
                        action=ChatAction.TYPING)
            tempfilename = "/tmp/" + \
                safe_file_name(update.message.from_user.first_name) +\
                "_" + str(update.message.message_id) + \
                "_groups_exercise.pdf"
            create_exercise_pdf(groups, tempfilename,
                                wpm, effectivewpm, extraspace, charset, seed)
            context.bot.send_chat_action(
                        chat_id=update.effective_message.chat_id,
                        action=ChatAction.UPLOAD_DOCUMENT)
            update.message.reply_document(
                document=open(tempfilename, "rb"),
                filename="CW groups exercise.pdf"
            )
            remove(tempfilename)

        def _cmd_start(self, update: Update, context: CallbackContext) -> None:
            logger.debug('bot._cmd_start')

            # silently set all settings to default at first connection
            try:
                if not context.user_data['exist']:
                    pass
            except KeyError:
                for (key, value) in DEFAULTS.items():
                    self._default(context.user_data, key, value)
            context.user_data['exist'] = True

            update.message.reply_text(
                'Hi '+update.message.from_user.first_name+'\n'+self._helptext,
                disable_web_page_preview=True,
                reply_markup=self._keyboard
            )
            return MAIN

        def _cmd_stop(self, update: Update, context: CallbackContext) -> None:
            logger.debug('bot._cmd_stop')
            if self._you_exist(update, context):
                context.user_data['exist'] = False
                update.message.reply_text(
                    "Bye bye\nremember you can use /start to join us again",
                    reply_markup=ReplyKeyboardRemove()
                    )
                return ConversationHandler.END

        def _cmd_help(self, update: Update, context: CallbackContext) -> None:
            logger.debug('bot._cmd_help')
            if self._you_exist(update, context):
                update.message.reply_text(
                    self._helptext,
                    disable_web_page_preview=True,
                    reply_markup=self._keyboard
                )

                return MAIN

        def _cmd_settings(self, update: Update, context: CallbackContext
                          ) -> None:
            logger.debug('bot._cmd_settings')
            if self._you_exist(update, context):
                text = "Your current settings are:\n" + "\n".join(
                                    ["%s\t%s" % (key,
                                                 str(context.user_data[key]))
                                     for (key, default) in DEFAULTS.items()
                                     ]
                                    )
                update.message.reply_text(text)
                return MAIN

        def _cmd_charset(self, update: Update, context: CallbackContext
                         ) -> None:
            logger.debug('bot._cmd_charset')
            if self._you_exist(update, context):
                if len(context.args) > 0:
                    return self._set_charset(update, context,
                                             " ".join(context.args))

                update.message.reply_text(
                    "Current charset is\n%s\n"
                    "Which charset should I use to generate groups?"
                    % context.user_data["charset"],
                    reply_markup=self._keyboard_charset
                )
                return TYPING_CHARSET

        def _accept_charset(self, update: Update, context: CallbackContext
                            ) -> None:
            logger.debug('bot._accept_charset')
            if self._you_exist(update, context):
                return self._set_charset(update, context, update.message.text)

        def _set_charset(self, update: Update, context: CallbackContext, value
                         ) -> None:
            if value == "Letters":
                charset = string.ascii_uppercase
            elif value == "Digits":
                charset = string.digits
            elif value == "Both":
                charset = string.ascii_uppercase + string.digits
            elif value == "HST":
                charset = string.ascii_uppercase + string.digits + ".,?/="
            elif value == "All":
                charset = string.ascii_uppercase + string.digits + "-/.?'=,"
            else:
                # uppercase, remove duplicates, remove space and sort
                charset = "".join(sorted(set(value.upper()))).replace(" ", "")
            context.user_data["charset"] = charset
            update.message.reply_text(
                        "Ok - the new charset is\n%s" % charset,
                        reply_markup=self._keyboard
                    )
            return MAIN

        def _cmd_groups_prefix(self, update: Update, context: CallbackContext
                               ) -> None:
            logger.debug('bot._cmd_groups_prefix')
            if self._you_exist(update, context):
                if len(context.args) > 0:
                    return self._set_groups_prefix(update, context,
                                                   context.args[0])

                update.message.reply_text(
                    "\n".join([
                        "I can send a VVV= prefix at groups start",
                        "I actually send it" \
                        if context.user_data["groups prefix"] else \
                        "Actually I dont dont send it",
                        "Do you want the prefix in future exercises?"
                    ]),
                    reply_markup=self._keyboard_yesno
                )
                return TYPING_GROUPS_PREFIX

        def _accept_groups_prefix(self, update: Update,
                                  context: CallbackContext) -> None:
            logger.debug('bot._accept_groups_prefix')
            if self._you_exist(update, context):
                return self._set_groups_prefix(update, context,
                                               update.message.text)

        def _set_groups_prefix(self, update: Update, context: CallbackContext,
                               value) -> None:
            value = value.lower()
            if value not in ["yes", "no"]:
                update.message.reply_text(
                    "Please be serious, answer Yes or No"
                )
                return None
            else:
                value = value == "yes"
                context.user_data["groups prefix"] = value
                update.message.reply_text(
                    "Ok - I'll send prefix from now on" \
                    if value else "OK - I'll not send prefix",
                    reply_markup=self._keyboard
                )
                return MAIN

        def _cmd_groups(self, update: Update, context: CallbackContext
                        ) -> None:
            logger.debug('bot._cmd_groups')
            if self._you_exist(update, context):
                if len(context.args) > 0:
                    return self._set_groups(update, context, context.args[0])

                update.message.reply_text(
                    "Current value is %i groups\n"
                    "How many groups do you want me to send?" %
                    context.user_data["groups"],
                    reply_markup=self._keyboard_leave
                )
                return TYPING_GROUPS

        def _accept_groups(self, update: Update, context: CallbackContext
                           ) -> None:
            logger.debug('bot._accept_groups')
            if self._you_exist(update, context):
                return self._set_groups(update, context, update.message.text)

        def _set_groups(self, update: Update, context: CallbackContext, value
                        ) -> None:
            try:
                value = int(value)
            except ValueError:
                update.message.reply_text(
                    "Hey ... this is not a number!!"
                )
                return None
            else:
                if 1 <= value <= 100:
                    context.user_data["groups"] = value
                    update.message.reply_text(
                        "Ok - I'll send %i groups" % value,
                        reply_markup=self._keyboard
                    )
                    return MAIN
                else:
                    update.message.reply_text(
                        "Sorry - I can send 100 groups at most\nTry again"
                    )

        def _send_groups(self, update: Update, context: CallbackContext
                         ) -> None:
            if self._you_exist(update, context):
                charset = context.user_data['charset']
                groups = context.user_data['groups']
                prefix = context.user_data['groups prefix']

                text = "VVV= " if prefix else ""
                text += " ".join(gen_groups(charset, groups))
                # groups text is hidden by a spoiler
                update.message.reply_text('||'
                                          + escape_markdown(text, version=2)
                                          + '||',
                                          parse_mode=ParseMode.MARKDOWN_V2)
                # do the real job in differt thread
                self._updater.dispatcher.run_async(
                                    self._reply_with_audio,
                                    update,
                                    context,
                                    text,
                                    update=update)

        def _cmd_word_max(self, update: Update, context: CallbackContext
                          ) -> None:
            logger.debug('bot._cmd_word_max')
            if self._you_exist(update, context):
                if len(context.args) > 0:
                    return self._set_word_max(update, context, context.args[0])
                if context.user_data["word max"] is None:
                    update.message.reply_text(
                        "You actually have no word lenght limit\n"
                        "Which is the maximum lenght of word you want?"
                        " (Use NONE for no limit)",
                        reply_markup=self._keyboard_none
                    )
                else:
                    update.message.reply_text(
                        "Current value is %i\n"
                        "Which is the maximum lenght of word you want?"
                        " (Use NONE for no limit)" %
                         context.user_data["word max"],
                         reply_markup=self._keyboard_none
                    )
                return TYPING_WORD_MAX

        def _accept_word_max(self, update: Update, context: CallbackContext
                             ) -> None:
            logger.debug('bot._accept_word_max')
            if self._you_exist(update, context):
                return self._set_word_max(update, context, update.message.text)

        def _set_word_max(self, update: Update, context: CallbackContext, value
                          ) -> None:
            try:
                value = int(value)
            except ValueError:
                # not a number, may be none?
                if value.lower() == 'none':
                    context.user_data["word max"] = None
                    update.message.reply_text(
                        "Ok - I'll send words of any lenght",
                        reply_markup=self._keyboard
                    )
                    return MAIN
                else:
                    update.message.reply_text(
                        "Hey ... this is not a number!!"
                    )
                return None
            else:
                if 3 <= value:
                    context.user_data["word max"] = value
                    update.message.reply_text(
                        "Ok - max word lenght is now %i" % value,
                        reply_markup=self._keyboard
                    )
                    return MAIN
                else:
                    update.message.reply_text(
                        "Sorry - Max word lenght must be greater then 3\n"
                        "Try again"
                    )

        def _cmd_horoscope(self, update: Update, context: CallbackContext
                           ) -> None:
            logger.debug('bot._cmd_horoscope')
            if self._you_exist(update, context):
                if len(context.args) > 0:
                    return self._set_sign(update, context, context.args[0])

                update.message.reply_text(
                    "Please choose your sign",
                    reply_markup=self._keyboard_signs
                )
                return TYPING_SIGN

        def _accept_sign(self, update: Update, context: CallbackContext
                         ) -> None:
            logger.debug('bot._accept_sign')
            if self._you_exist(update, context):
                return self._set_sign(update, context, update.message.text)

        def _set_sign(self, update: Update, context: CallbackContext, value
                      ) -> None:
            # value = value.lower()
            if value not in ANSWER_SIGNS:
                update.message.reply_text(
                    "Hey ... this is not a sign!!\n"
                    "Please choose between " + ', '.join(ANSWER_SIGNS)
                )
                return None
            else:
                feed = context.user_data["horoscope feed"]
                last_n = 1
                show_news = context.user_data["show news"]
                convertnumbers = context.user_data['convert numbers']
                sign = value
                # do the real job in different thread
                self._updater.dispatcher.run_async(
                                    self._do_read_news, update,
                                    context, feed, last_n, show_news,
                                    convertnumbers, sign, update=update)
                return MAIN

        def _send_callsign(self, update: Update, context: CallbackContext
                       ) -> None:
            if self._you_exist(update, context):
                charset = context.user_data['charset']

                try:
                    d = self._callsign_list
                except AttributeError:
                    # try loading dictionary
                    try:
                        self._callsign_list = dizionario(filename='callsigns.txt')
                    except Exception as e:
                        logger.error(msg="Exception loading callsigns file:",
                                     exc_info=e)
                        # notify the user
                        update.message.reply_text(
                            "I'm sorry but I could not find the callsigns list,"
                            " please try again\n"
                            "If it happens again send a message to my creator"
                            " @IZ3GME to fix it")
                        return None
                    d = self._callsign_list

                try:
                    text = choice(d.anagrammi(charset))
                except IndexError:
                    # no word found, let the user know
                    update.message.reply_text(
                        "I'm sorry but I could not find any callsign\n"
                        "Try with more letters in charset")
                    return None

                # text is hidden by a spoiler
                update.message.reply_text('||'
                                          + escape_markdown(text, version=2)
                                          + '||',
                                          parse_mode=ParseMode.MARKDOWN_V2)
                # do the real job in differt thread
                self._updater.dispatcher.run_async(
                                    self._reply_with_audio,
                                    update,
                                    context,
                                    text,
                                    update=update)

        def _send_word(self, update: Update, context: CallbackContext
                       ) -> None:
            if self._you_exist(update, context):
                charset = context.user_data['charset']
                maxl = context.user_data['word max']
                try:
                    nwords = int(context.args[0]) if len(context.args) == 1 else 1
                except ValueError:
                    update.message.reply_text("Hey! %s is not a number!")
                    return None
                if not 1<=nwords<=100:
                    update.message.reply_text("Sorry, i'm lazy so I don't send more the 100 words at once")
                    return None
                try:
                    d = self._dictionary
                except AttributeError:
                    # try loading dictionary
                    try:
                        self._dictionary = dizionario()
                    except Exception as e:
                        logger.error(msg="Exception loading dictionary file:",
                                     exc_info=e)
                        # notify the user
                        update.message.reply_text(
                            "I'm sorry but I could not find the dictionary,"
                            " please try again\n"
                            "If it happens again send a message to my creator"
                            " @IZ3GME to fix it")
                        return None
                    d = self._dictionary

                try:
                    text = " ".join(choices(d.anagrammi(charset, minl=2, maxl=maxl), k=nwords))
                except IndexError:
                    # no word found, let the user know
                    update.message.reply_text(
                        "I'm sorry but I could not find any word\n"
                        "Try with more letters in charset and with greater max"
                        " lenght")
                    return None

                # text is hidden by a spoiler
                update.message.reply_text('||'
                                          + escape_markdown(text, version=2)
                                          + '||',
                                          parse_mode=ParseMode.MARKDOWN_V2)
                # do the real job in differt thread
                self._updater.dispatcher.run_async(
                                    self._reply_with_audio,
                                    update,
                                    context,
                                    text,
                                    update=update)

        def _groups_exercise(self, update: Update, context: CallbackContext
                             ) -> None:
            if self._you_exist(update, context):
                charset = context.user_data['charset']

                exseed = None
                if len(context.args) > 0:
                    exseed = " ".join(context.args)
                if exseed:
                    seed(exseed)
                groups = [gen_groups(charset, 12*5) for i in range(3)]
                if exseed:
                    seed()
                # do the real job in differt thread
                self._updater.dispatcher.run_async(
                                    self._do_groups_exercise,
                                    update,
                                    context,
                                    groups, charset, exseed)

        def _cmd_wpm(self, update: Update, context: CallbackContext) -> None:
            logger.debug('bot._cmd_wpm')
            if self._you_exist(update, context):
                if len(context.args) > 0:
                    return self._set_wpm(update, context, context.args[0])

                update.message.reply_text(
                    "Current value is %s wpm\nWhat is your desired speed?\n"
                    "You can specify a single value or a comma separated list "
                    "(eg. 15,20,30) so I'll send separate audio for each" %
                    ', '.join(map(str, context.user_data["wpm"])),
                    reply_markup=self._keyboard_leave
                )
                return TYPING_WPM

        def _accept_wpm(self, update: Update, context: CallbackContext
                        ) -> None:
            logger.debug('bot._accept_wpm')
            if self._you_exist(update, context):
                return self._set_wpm(update, context, update.message.text)

        def _set_wpm(self, update: Update, context: CallbackContext, value
                     ) -> None:
            try:
                value = list(map(int, value.split(',')))
            except ValueError:
                update.message.reply_text(
                    "Hey ... this is not a number!!"
                )
                return None
            else:
                if all(1 <= s <= 100 for s in value):
                    context.user_data["wpm"] = value
                    update.message.reply_text(
                        "Ok - speed is now %s wpm" % str(value),
                        reply_markup=self._keyboard
                    )
                    return MAIN
                else:
                    update.message.reply_text(
                        "Sorry - Valid wpm is between 1 and 100\nTry again"
                    )

        def _cmd_effectivewpm(self, update: Update, context: CallbackContext
                              ) -> None:
            logger.debug('bot._cmd_effectivewpm')
            if self._you_exist(update, context):
                if len(context.args) > 0:
                    return self._set_effectivewpm(update, context,
                                                  context.args[0])

                value = "none" if context.user_data["effectivewpm"] is None \
                    else "%iwpm" % context.user_data["effectivewpm"]
                update.message.reply_text(
                    "I can send spaces between words and letters at a "
                    "different speed then text (usually slower for "
                    "Farnsworth)\nCurrent value is %s\n"
                    "What is your desired effective wpm "
                    "(type none to have spaces sent at normal speed)?" % value,
                    reply_markup=self._keyboard_none
                )
                return TYPING_EFFECTIVEWPM

        def _accept_effectivewpm(self, update: Update, context: CallbackContext
                                 ) -> None:
            logger.debug('bot._accept_effectivewpm')
            if self._you_exist(update, context):
                return self._set_effectivewpm(update, context,
                                              update.message.text)

        def _set_effectivewpm(self, update: Update, context: CallbackContext,
                              value) -> None:
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
                        "Sorry - Valid effective wpm is between 1 and 100\n"
                        "Try again"
                    )

        def _cmd_extra_space(self, update: Update, context: CallbackContext
                             ) -> None:
            logger.debug('bot._cmd_extra_space')
            if self._you_exist(update, context):
                if len(context.args) > 0:
                    return self._set_extra_space(update, context,
                                                 context.args[0])

                value = "none" if context.user_data["extra space"] is None \
                        else str(context.user_data["extra space"])
                update.message.reply_text(
                    "I can send longer spaces between words\n"
                    "Current value is %s\n"
                    "What is your desired extra word spacing (eg. a value of "
                    "0.5 adds half an extra word space, type none to have "
                    "spaces sent at normal speed)?" % value,
                    reply_markup=self._keyboard_none
                )
                return TYPING_EXTRA_SPACE

        def _accept_extra_space(self, update: Update, context: CallbackContext
                                ) -> None:
            logger.debug('bot._accept_extra_space')
            if self._you_exist(update, context):
                return self._set_extra_space(update, context,
                                             update.message.text)

        def _set_extra_space(self, update: Update, context: CallbackContext,
                             value) -> None:
            try:
                # we accept both , and . as decimal separator
                value = value.replace(',', '.')
                value = float(value)
            except ValueError:
                # not a number, may be none?
                if value.lower() == 'none':
                    context.user_data["extra space"] = None
                    update.message.reply_text(
                        "Ok - I'll send spaces between words at normal speed",
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
                        "Sorry - Valid extra space is between 0 and 10\n"
                        "Try again"
                    )

        def _cmd_tone(self, update: Update, context: CallbackContext) -> None:
            logger.debug('bot._cmd_tone')
            if self._you_exist(update, context):
                if len(context.args) > 0:
                    return self._set_tone(update, context, context.args[0])

                update.message.reply_text(
                    "Current value is %iHz\n"
                    "What is your desired tone "
                    "frequency?" % context.user_data["tone"],
                    reply_markup=self._keyboard_leave
                )
                return TYPING_TONE

        def _accept_tone(self, update: Update, context: CallbackContext
                         ) -> None:
            logger.debug('bot._accept_tone')
            if self._you_exist(update, context):
                return self._set_tone(update, context, update.message.text)

        def _set_tone(self, update: Update, context: CallbackContext, value
                      ) -> None:
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
                        "Sorry - Valid frequency is between 200 and 1200\n"
                        "Try again"
                    )

        def _cmd_snr(self, update: Update, context: CallbackContext) -> None:
            logger.debug('bot._cmd_snr')
            if self._you_exist(update, context):
                if len(context.args) > 0:
                    return self._set_snr(update, context, context.args[0])

                value = "none" if context.user_data["snr"] is None \
                        else "%idb" % context.user_data["snr"]
                update.message.reply_text(
                    "I have only a partial support for noise: after mixing "
                    "signal with white noise audio will be filtered with a "
                    "500Hz filter centered at 800Hz,\n"
                    "Current value is %s\n"
                    "What is your desired snr (type none for no added noise "
                    "at all)?" % value,
                    reply_markup=self._keyboard_none
                )
                return TYPING_SNR

        def _accept_snr(self, update: Update, context: CallbackContext
                        ) -> None:
            logger.debug('bot._accept_snr')
            if self._you_exist(update, context):
                return self._set_snr(update, context, update.message.text)

        def _set_snr(self, update: Update, context: CallbackContext, value
                     ) -> None:
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
            logger.debug('bot._cmd_qrq')
            if self._you_exist(update, context):
                if len(context.args) > 0:
                    return self._set_qrq(update, context, context.args[0])

                value = "none" if context.user_data["qrq"] is None \
                    else "%i minutes" % context.user_data["qrq"]
                update.message.reply_text(
                    "Current value is %s\n"
                    "How often (in minutes) should I increase speed "
                    "(type none for no qrq)?" % value,
                    reply_markup=self._keyboard_none
                )
                return TYPING_QRQ

        def _accept_qrq(self, update: Update, context: CallbackContext
                        ) -> None:
            logger.debug('bot._accept_qrq')
            if self._you_exist(update, context):
                return self._set_qrq(update, context, update.message.text)

        def _set_qrq(self, update: Update, context: CallbackContext, value
                     ) -> None:
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
                        "Sorry - Valid qrq is between 1 and 60 minutes\n"
                        "Try again"
                    )

        def _cmd_title(self, update: Update, context: CallbackContext) -> None:
            logger.debug('bot._cmd_title')
            if self._you_exist(update, context):
                if len(context.args) > 0:
                    return self._set_title(update, context,
                                           " ".join(context.args))

                update.message.reply_text(
                    "Current title is %s\n"
                    "What is your desired title?\n"
                    "You can insert -wpm- in title to be replaced with "
                    "actual speed or I'll place it at"
                    " the end" % context.user_data["title"],
                    reply_markup=self._keyboard_leave
                )
                return TYPING_TITLE

        def _accept_title(self, update: Update, context: CallbackContext
                          ) -> None:
            logger.debug('bot._accept_title')
            if self._you_exist(update, context):
                return self._set_title(update, context, update.message.text)

        def _set_title(self, update: Update, context: CallbackContext, value
                       ) -> None:
            if re.search(r'[^A-Za-z0-9_\- ]', value):
                update.message.reply_text(
                    "Hey ... this is not a valid title!!\n"
                    "Please use only letters, numbers, blank, underscore, "
                    "hyphen (A-Za-z0-9 _-)"
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
                        "Sorry - I can accept titles of 50 chars at most\n"
                        "Try again"
                    )

        def _cmd_format(self, update: Update, context: CallbackContext
                        ) -> None:
            logger.debug('bot._cmd_format')
            if self._you_exist(update, context):
                if len(context.args) > 0:
                    return self._set_format(update, context, context.args[0])

                update.message.reply_text(
                    "\n".join([
                        "Current format is %s" % context.user_data["format"],
                        "I can send cw as either " + ' or '.join(
                                                    ANSWER_FORMATS),
                        "Which one you prefere?"
                    ]),
                    reply_markup=self._keyboard_formats
                )
                return TYPING_FORMAT

        def _accept_format(self, update: Update, context: CallbackContext
                           ) -> None:
            logger.debug('bot._accept_format')
            if self._you_exist(update, context):
                return self._set_format(update, context, update.message.text)

        def _set_format(self, update: Update, context: CallbackContext, value
                        ) -> None:
            value = value.lower()
            if value not in ANSWER_FORMATS:
                update.message.reply_text(
                    "Hey ... this is not a format I know!!\n"
                    "Please choose between " + ', '.join(ANSWER_FORMATS)
                )
                return None
            else:
                context.user_data["format"] = value
                update.message.reply_text(
                    "Ok - format is now %s" % value,
                    reply_markup=self._keyboard
                )
                return MAIN

        def _cmd_waveform(self, update: Update, context: CallbackContext
                          ) -> None:
            logger.debug('bot._cmd_waveform')
            if self._you_exist(update, context):
                if len(context.args) > 0:
                    return self._set_waveform(update, context, context.args[0])

                update.message.reply_text(
                    "\n".join([
                        "Current waveform is"
                        " %s" % context.user_data["waveform"],
                        "I can generate different waveform " + ' or '.join(
                                                    ANSWER_WAVEFORM),
                        "Which one you prefere?"
                    ]),
                    reply_markup=self._keyboard_waveform
                )
                return TYPING_WAVEFORM

        def _accept_waveform(self, update: Update, context: CallbackContext
                             ) -> None:
            logger.debug('bot._accept_waveform')
            if self._you_exist(update, context):
                return self._set_waveform(update, context, update.message.text)

        def _set_waveform(self, update: Update, context: CallbackContext, value
                          ) -> None:
            value = value.lower()
            if value not in ANSWER_WAVEFORM:
                update.message.reply_text(
                    "Hey ... this is not a waveform I know!!\n"
                    "Please choose between " + ', '.join(ANSWER_WAVEFORM)
                )
                return None
            else:
                context.user_data["waveform"] = value
                update.message.reply_text(
                    "Ok - waveform is now %s" % value,
                    reply_markup=self._keyboard
                )
                return MAIN

        def _cmd_shuffle(self, update: Update, context: CallbackContext
                         ) -> None:
            logger.debug('bot._cmd_shuffle')
            if self._you_exist(update, context):
                if len(context.args) > 0:
                    return self._set_shuffle(update, context, context.args[0])

                update.message.reply_text(
                    "\n".join([
                        "Current shuffle is %s" % context.user_data["shuffle"],
                        "I can shuffle " + ', '.join(ANSWER_SHUFFLES) + " in "
                        "messages you send me so you can have a different way "
                        "to exercise",
                        "Please note that I'll never shuffle news text",
                        "What do you want me to shuffle?"
                    ]),
                    reply_markup=self._keyboard_shuffles
                )
                return TYPING_SHUFFLE

        def _accept_shuffle(self, update: Update, context: CallbackContext
                            ) -> None:
            logger.debug('bot._accept_shuffle')
            if self._you_exist(update, context):
                return self._set_shuffle(update, context, update.message.text)

        def _set_shuffle(self, update: Update, context: CallbackContext, value
                         ) -> None:
            value = value.lower()
            if value not in ANSWER_SHUFFLES:
                update.message.reply_text(
                    "Hey ... this is not a shuffle I know!!\n"
                    "Please choose between " + ', '.join(ANSWER_SHUFFLES)
                )
                return None
            else:
                context.user_data["shuffle"] = value
                update.message.reply_text(
                    "Ok - shuffle is now %s" % value,
                    reply_markup=self._keyboard
                )
                return MAIN

        def _cmd_delmessage(self, update: Update, context: CallbackContext
                            ) -> None:
            logger.debug('bot._cmd_delmessage')
            if self._you_exist(update, context):
                if len(context.args) > 0:
                    return self._set_delmessage(update, context,
                                                context.args[0])

                update.message.reply_text(
                    "\n".join([
                        "Previously you asked me to delete your messages" \
                        if context.user_data["delmessage"] else \
                        "Actually I dont delete your messages",
                        "Do you want me to delete your messages?"
                    ]),
                    reply_markup=self._keyboard_yesno
                )
                return TYPING_DELMESSAGE

        def _accept_delmessage(self, update: Update,
                               context: CallbackContext) -> None:
            logger.debug('bot._accept_delmessage')
            if self._you_exist(update, context):
                return self._set_delmessage(update, context,
                                            update.message.text)

        def _set_delmessage(self, update: Update, context: CallbackContext,
                            value) -> None:
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
                    "Ok - I'll delete messages from now on" \
                    if value else "OK - I'll leave your messages untouched",
                    reply_markup=self._keyboard
                )
                return MAIN

        def _cmd_simplify(self, update: Update, context: CallbackContext
                          ) -> None:
            logger.debug('bot._cmd_simplify')
            if self._you_exist(update, context):
                if len(context.args) > 0:
                    return self._set_simplify(update, context,
                                              context.args[0])

                update.message.reply_text(
                    "\n".join([
                        "I can simplify text removing uncommon symbols",
                        "Previously you asked me to simplify messages" \
                        if context.user_data["simplify"] else \
                        "Actually I dont simplify messages",
                        "Do you want me to simplify text?"
                    ]),
                    reply_markup=self._keyboard_yesno
                )
                return TYPING_SIMPLIFY

        def _accept_simplify(self, update: Update,
                             context: CallbackContext) -> None:
            logger.debug('bot._accept_simplify')
            if self._you_exist(update, context):
                return self._set_simplify(update, context,
                                          update.message.text)

        def _set_simplify(self, update: Update, context: CallbackContext,
                          value) -> None:
            value = value.lower()
            if value not in ["yes", "no"]:
                update.message.reply_text(
                    "Please be serious, answer Yes or No"
                )
                return None
            else:
                value = value == "yes"
                context.user_data["simplify"] = value
                update.message.reply_text(
                    "Ok - I'll simplify messages from now on" \
                    if value else "OK - I'll leave your messages untouched",
                    reply_markup=self._keyboard
                )
                return MAIN

        def _cmd_noaccents(self, update: Update, context: CallbackContext
                           ) -> None:
            logger.debug('bot._cmd_noaccents')
            if self._you_exist(update, context):
                if len(context.args) > 0:
                    return self._set_noaccents(update, context,
                                               context.args[0])

                update.message.reply_text(
                    "\n".join([
                        "I can translate accented letters to plain ones",
                        "Previously you asked me to do this" \
                        if context.user_data["no accents"] else \
                        "Actually I dont translate accents",
                        "Do you want me to remove accented letters?"
                    ]),
                    reply_markup=self._keyboard_yesno
                )
                return TYPING_NOACCENTS

        def _accept_noaccents(self, update: Update,
                              context: CallbackContext) -> None:
            logger.debug('bot._accept_noaccents')
            if self._you_exist(update, context):
                return self._set_noaccents(update, context,
                                           update.message.text)

        def _set_noaccents(self, update: Update, context: CallbackContext,
                           value) -> None:
            value = value.lower()
            if value not in ["yes", "no"]:
                update.message.reply_text(
                    "Please be serious, answer Yes or No"
                )
                return None
            else:
                value = value == "yes"
                context.user_data["no accents"] = value
                update.message.reply_text(
                    "Ok - I'll translate accented letters from now on" \
                    if value else "OK - I'll leave your messages untouched",
                    reply_markup=self._keyboard
                )
                return MAIN

        def _cmd_convertnumbers(self, update: Update, context: CallbackContext
                                ) -> None:
            logger.debug('bot._cmd_convertnumbers')
            if self._you_exist(update, context):
                if len(context.args) > 0:
                    return self._set_convertnumbers(update, context,
                                                    context.args[0])

                update.message.reply_text(
                    "\n".join([
                        "I can add a text translation of each number in text",
                        "this is expecially usefull in QRQ plain text exercises",
                        "Previously you asked me to do this" \
                        if context.user_data["convert numbers"] else \
                        "Actually I dont translate numbers",
                        "Do you want me to add numbers translation?"
                    ]),
                    reply_markup=self._keyboard_yesno
                )
                return TYPING_CONVERTNUMBERS

        def _accept_convertnumbers(self, update: Update,
                                   context: CallbackContext) -> None:
            logger.debug('bot._accept_convertnumners')
            if self._you_exist(update, context):
                return self._set_convertnumbers(update, context,
                                                update.message.text)

        def _set_convertnumbers(self, update: Update, context: CallbackContext,
                                value) -> None:
            value = value.lower()
            if value not in ["yes", "no"]:
                update.message.reply_text(
                    "Please be serious, answer Yes or No"
                )
                return None
            else:
                value = value == "yes"
                context.user_data["convert numbers"] = value
                update.message.reply_text(
                    "Ok - I'll add a text translation to numbers from now on" \
                    if value else "OK - I'll leave your messages untouched",
                    reply_markup=self._keyboard
                )
                return MAIN

        def _cmd_feed(self, update: Update, context: CallbackContext) -> None:
            logger.debug('bot._cmd_feed')
            if self._you_exist(update, context):
                if len(context.args) > 0:
                    return self._set_feed(update, context,
                                          " ".join(context.args))

                update.message.reply_text(
                    "Current feed URL is\n%s\n"
                    "Please give the full URL of your RSS feed?\n"
                    "Type default if you want to reset to "
                    "default feed" % context.user_data["feed"],
                    reply_markup=self._keyboard_default
                )
                return TYPING_FEED

        def _accept_feed(self, update: Update, context: CallbackContext
                         ) -> None:
            logger.debug('bot._accept_feed')
            if self._you_exist(update, context):
                return self._set_feed(update, context, update.message.text)

        def _set_feed(self, update: Update, context: CallbackContext,
                      value) -> None:
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
                    "Ok - I'll read news from\n%s\n"
                    "Hope you'll like it" % value,
                    reply_markup=self._keyboard
                )
            return MAIN

        def _cmd_news_to_read(self, update: Update, context: CallbackContext
                              ) -> None:
            logger.debug('bot._cmd_news_to_read')
            if self._you_exist(update, context):
                if len(context.args) > 0:
                    return self._set_news_to_read(update, context,
                                                  context.args[0])

                update.message.reply_text(
                    "How many news do you want from the feed? "
                    "(current value is %s)\n"
                    "Remember that my reading speed is about 1 news/s so if "
                    "you ask me 60 news I'll take about 1 minute to answer, "
                    "if you are in a hurry please ask someone else "
                    ":-P" % str(context.user_data["news to read"]),
                    reply_markup=self._keyboard_all
                )
                return TYPING_NEWS_TO_READ

        def _accept_news_to_read(self, update: Update, context: CallbackContext
                                 ) -> None:
            logger.debug('bot._accept_news_to_read')
            if self._you_exist(update, context):
                return self._set_news_to_read(update, context,
                                              update.message.text)

        def _set_news_to_read(self, update: Update, context: CallbackContext,
                              value) -> None:
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
                        "Please give a number or all ... "
                        "I wont accept anything else"
                    )
                    return None
            update.message.reply_text(
                "Ok - I'll send you %s news" % str(value),
                reply_markup=self._keyboard
            )
            context.user_data["news to read"] = value
            return MAIN

        def _cmd_show_news(self, update: Update, context: CallbackContext
                           ) -> None:
            logger.debug('bot._cmd_show_news')
            if self._you_exist(update, context):
                if len(context.args) > 0:
                    return self._set_show_news(
                                            update, context, context.args[0])

                update.message.reply_text(
                    "\n".join([
                        "Previously you asked me to show the news in clear"
                        " text" if context.user_data["show news"] else \
                        "Actually I dont show the news text to you",
                        "Do you want me to send the news text to you?"
                    ]),
                    reply_markup=self._keyboard_yesno
                )
                return TYPING_SHOW_NEWS

        def _accept_show_news(self, update: Update, context: CallbackContext
                              ) -> None:
            logger.debug('bot._accept_show_news')
            if self._you_exist(update, context):
                return self._set_show_news(
                                    update, context, update.message.text)

        def _set_show_news(self, update: Update, context: CallbackContext,
                           value) -> None:
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
                    "Ok - I'll show the news text to you from now on" \
                    if value else "OK - I'll keep the news text secret :-P",
                    reply_markup=self._keyboard
                )
                return MAIN

        def _cmd_news_time(self, update: Update, context: CallbackContext
                           ) -> None:
            logger.debug('bot._cmd_news_time')
            if self._you_exist(update, context):
                if len(context.args) > 0:
                    return self._set_news_time(
                                            update, context, context.args[0])

                update.message.reply_text(
                    "\n".join([
                        "Previously you asked me to send published date and "
                        "time in front of each news" \
                        if context.user_data["news time"] else \
                        "Actually I dont published date and time in front of "
                        "each news",
                        "Do you want me to send the news date and time next "
                        "time?"
                    ]),
                    reply_markup=self._keyboard_yesno
                )
                return TYPING_NEWS_TIME

        def _accept_news_time(self, update: Update, context: CallbackContext
                              ) -> None:
            logger.debug('bot._accept_news_time')
            if self._you_exist(update, context):
                return self._set_news_time(update, context,
                                           update.message.text)

        def _set_news_time(self, update: Update, context: CallbackContext,
                           value) -> None:
            value = value.lower()
            if value not in ["yes", "no"]:
                update.message.reply_text(
                    "Please be serious, answer Yes or No"
                )
                return None
            else:
                value = value == "yes"
                context.user_data["news time"] = value
                update.message.reply_text(
                    "Ok - I'll send published date and time in front of each "
                    "news from now on" if value else \
                    "OK - I'll not send published date and time",
                    reply_markup=self._keyboard
                )
                return MAIN

        def _cmd_read_news(self, update: Update, context: CallbackContext
                           ) -> None:
            logger.debug('bot._cmd_read_news')
            if self._you_exist(update, context):
                feed = context.user_data["feed"]
                last_n = context.user_data["news to read"]
                show_news = context.user_data["show news"]
                convertnumbers = context.user_data['convert numbers']
                # do the real job in different thread
                self._updater.dispatcher.run_async(
                                    self._do_read_news, update,
                                    context, feed, last_n, show_news,
                                    convertnumbers, update=update)

                return MAIN

        def _cmd_qso(self, update: Update, context: CallbackContext) -> None:
            logger.debug('bot._cmd_qso')
            if self._you_exist(update, context):
                show_news = context.user_data["show news"]
                # do the real job in different thread
                self._updater.dispatcher.run_async(
                                    self._do_qso, update, context, show_news,
                                    update=update)

                return MAIN

        def _cmd_leave(self, update: Update, context: CallbackContext) -> None:
            logger.debug('bot._cmd_leave')
            if self._you_exist(update, context):
                update.message.reply_text(
                    "Ok ... leaving value unchanged",
                    reply_markup=self._keyboard
                )
                return MAIN

        def _handle_unknown(self, update: Update, context: CallbackContext
                            ) -> None:
            logger.debug('bot._handle_unknown')
            if self._you_exist(update, context):
                update.message.reply_text(
                    "Sorry, this is something I can't understand")
                return None

        def _handle_unknown_leave(self, update: Update, context: CallbackContext
                            ) -> None:
            logger.debug('bot._handle_unknown_leave')
            if self._you_exist(update, context):
                update.message.reply_text(
                    "Sorry, this is not valid now, use /leave if you want"
                    "to go back without changing current value"
                  )
                return None

        def _handle_text(self, update: Update, context: CallbackContext
                         ) -> None:
            if self._you_exist(update, context):
                delmessage = context.user_data['delmessage']
                shuffle = context.user_data['shuffle']
                convertnumbers = context.user_data['convert numbers']

                text = update.message.text
                text = do_shuffle[shuffle](text)
                if convertnumbers:
                    text = convert_numbers(text)
                # do the real job in differt thread
                self._updater.dispatcher.run_async(
                                    self._reply_with_audio,
                                    update,
                                    context,
                                    text,
                                    update=update)
                if delmessage:
                    update.message.delete()

        def _error_handler(self, update: Update, context: CallbackContext
                           ) -> None:
            """Log the error and send user a message to notify the problem"""
            # Log the error before we do anything else
            logger.error(msg="Exception caught by error handler:",
                         exc_info=context.error)

            # notify the user
            update.message.reply_text(
                "I'm sorry but you probably hit a bug, please try again\n"
                "If it happens again send a message to my creator @IZ3GME "
                "to fix it")

        def start(self, token):
            pp = PicklePersistence(filename='text2cw_bot.data')
            self._updater = Updater(token, persistence=pp, use_context=True,
                                    request_kwargs={'read_timeout': 10, })

            # tell BotFather my list of commands
            commands = [[command, description]
                        for command, description, method, typing_state,
                        accept_method in self._commands if command
                        ]
            self._updater.bot.setMyCommands(commands)

            # build conversation handler for each state
            main_commands = [CommandHandler(command, method)
                             for command, description, method, typing_state,
                             accept_method in self._commands if command
                             ]

            # build all accept answer state
            typing_states = {
                typing_state: [
                        MessageHandler(
                            Filters.text & ~Filters.command, accept_method
                        ),
                        CommandHandler('leave', self._cmd_leave),
                        MessageHandler(Filters.all, self._handle_unknown_leave),
                    ]
                for command, description, method, typing_state, accept_method
                in self._commands
                if typing_state
            }

            # build conversation
            conv_handler = ConversationHandler(
                entry_points=[CommandHandler('start', self._cmd_start)],
                states={
                    **typing_states,
                    MAIN: main_commands + [
                        MessageHandler(Filters.text & ~Filters.command,
                                       self._handle_text),
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
            self._updater.dispatcher.add_handler(
                            MessageHandler(
                                Filters.all,
                                self._handle_unknown
                                )
                            )

            # ...and the error handler
            self._updater.dispatcher.add_error_handler(self._error_handler)

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
    argp.add_argument(
            '-s', '--sleep', default=120, type=int,
            help='Sleep time before exiting (sec), 0 to sleep forever')
    argp.add_argument(
            '-d', '--debug', action='store_true',
            help='Enable debug level log')
    argp.add_argument('token',
                      help='Bot token (ask BotFather)')
    args = argp.parse_args()

    if args.debug:
        logger.setLevel(logging.DEBUG)
    logger.debug("Debug enabled")

    logger.info("Creating bot")
    abot = bot()
    abot.start(args.token)

    logger.info("Waiting for %i sec before exiting" % (args.sleep))
    if args.sleep != 0:
        time.sleep(args.sleep)
    else:
        abot.idle()

    logger.info("Done")
    abot.stop()
