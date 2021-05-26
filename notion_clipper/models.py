# -*- coding: utf-8 -*-

from flask_dance.consumer.storage.sqla import OAuthConsumerMixin
from sqlalchemy import Column, JSON, ForeignKey, Text, DateTime, BigInteger, TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from .database import Base

import logging

logger = logging.getLogger(__name__)

class TelegramUser(Base):
    __tablename__ = 'telegram_user'

    telegram_user_id = Column(BigInteger, nullable=False, primary_key=True)
    telegram_chat_id = Column(BigInteger, nullable=False)
    first_name = Column(Text, nullable=False)
    last_name = Column(Text, nullable=False)
    username = Column(Text, nullable=False)
    language_code = Column(Text, nullable=False)
    first_seen = Column(TIMESTAMP(True), nullable=False)
    last_seen = Column(TIMESTAMP(True), nullable=False)

    notion_auth = relationship('NotionAuth', backref='user', uselist=False)


class NotionAuth(Base, OAuthConsumerMixin):
    __tablename__ = 'notion_auth'

    provider = Column(Text, nullable=False)
    token = Column(JSONB, nullable=False)
    telegram_user_id = Column(BigInteger, ForeignKey('telegram_user.telegram_user_id'))
    database = Column(JSONB, nullable=True)
