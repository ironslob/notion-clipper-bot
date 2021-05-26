# -*- coding: utf-8 -*-

from flask import g, session
from flask_dance.consumer import OAuth2ConsumerBlueprint

import logging
import os

logger = logging.getLogger(__name__)

client_id = os.environ.get('NOTION_OAUTH_CLIENT_ID')
client_secret = os.environ.get('NOTION_OAUTH_CLIENT_SECRET')

assert client_id, 'Must specify NOTION_OAUTH_CLIENT_ID environment variable'
assert client_secret, 'Must specify NOTION_OAUTH_CLIENT_SECRET environment variable'

notion_bp = OAuth2ConsumerBlueprint(
    "notion",
    __name__,
    client_id=client_id,
    client_secret=client_secret,
    base_url="https://api.notion.com",
    token_url="https://api.notion.com/v1/oauth/token",
    authorization_url="https://api.notion.com/v1/oauth/authorize",
    redirect_url='/all-done',
)
