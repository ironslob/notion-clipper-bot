# -*- coding: utf-8 -*-

import os
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import logging

logger = logging.getLogger(__name__)

SQLALCHEMY_DATABASE_URL = os.environ['DATABASE_URL']

assert SQLALCHEMY_DATABASE_URL

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    echo=True,
    #**engine_args,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)

Base = declarative_base()

# SessionManager is an alternative way to get a DB connection
# as an alternative to FasTApi Depends that seems to quickly
# exhaust the Postgres open connections:
# https://github.com/tiangolo/full-stack-fastapi-postgresql/issues/104
@contextmanager
def SessionManager():
    db = SessionLocal()

    try:
        yield db

    except:
        db.rollback()
        raise

    finally:
        db.close()
