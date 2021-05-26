# -*- coding: utf-8 -*-

import logging
import telegram
import os

logger = logging.getLogger(__name__)


telegram_token = os.environ.get('TELEGRAM_TOKEN')

assert telegram_token, 'need a TELEGRAM_TOKEN environment variable'


def get_bot():
    return telegram.Bot(telegram_token)
