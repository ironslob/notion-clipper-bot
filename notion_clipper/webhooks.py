# -*- coding: utf-8 -*-

from .zappa_async import task_sns
import logging

logger = logging.getLogger(__name__)

@task_sns
def process(message):
    pass
