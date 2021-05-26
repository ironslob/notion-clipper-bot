# -*- coding: utf-8 -*-

from flask import g, session

import logging

logger = logging.getLogger(__name__)


def telegram_user_id_for_request():
    return session['telegram_user_id']
