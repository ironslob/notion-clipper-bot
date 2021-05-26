# -*- coding: utf-8 -*-

from contextlib import contextmanager
from functools import wraps
from flask import got_request_exception

import os
import logging
import rollbar
import rollbar.contrib.flask
import time
import traceback

logger = logging.getLogger(__name__)
rollbar_token = os.environ.get("ROLLBAR_TOKEN", None)


def except_retry(exceptions, retries, retry_delay=0):
    def inner(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            nonlocal retries

            while retries >= 0:
                try:
                    return f(*args, **kwargs)

                except Exception as e:
                    logger.debug(e)

                    if isinstance(e, exceptions) and retries > 0:
                        logger.debug(
                            "retrying exception as %d retries remain" % retries
                        )
                        retries -= 1

                        if retry_delay:
                            time.sleep(retry_delay)

                    else:
                        raise e

        return decorated

    return inner


@contextmanager
def except_warning(exceptions=(), extra_data=None):
    try:
        yield

    except Exception as e:
        if exceptions and not isinstance(e, exceptions):
            raise e

        warning(
            exception=e,
            extra_data=extra_data,
        )


def warning(exception=None, app=None, extra_data=None, message=None):
    if app:
        app.logger.warning(message)
        app.logger.warning(extra_data)

    if exception is None:
        if extra_data is None:
            extra_data = {}

        extra_data["stacktrace"] = traceback.format_stack()

        report_message(
            message=message,
            level="warning",
            extra_data=extra_data,
            app=app,
        )

    else:
        report(
            exception=exception,
            app=app,
            extra_data=extra_data,
            level="warning",
        )

    logger.warning(message)


def init(app=None):
    if not rollbar_token:
        logger.debug("not initialising rollbar")

    else:
        rollbar_env = os.environ.get("ROLLBAR_ENV", "")

        rollbar.init(
            access_token=rollbar_token,
            environment=rollbar_env,
            allow_logging_basic_config=False,
            handler="blocking",  # needed for AWS Lambda
        )

        if app:
            got_request_exception.connect(flask_report, app)


def zappa_report(e, event, context):
    report(
        exception=e,
        extra_data={
            "event": event,
            "context": context,
        },
    )

    return True


def flask_report(app, exception):
    report(
        exception=exception,
        app=app,
    )


def report_message(
    message, level="error", request=None, extra_data=None, payload_data=None, app=None
):
    init()

    traceback.print_exc()

    if not rollbar_token:
        logger.debug("not submitting to rollbar - is disabled")

    else:
        logger.debug("reporting message info - %s", str(extra_data))

        rollbar.report_message(
            message=message,
            level=level,
            request=request,
            extra_data=extra_data,
            payload_data=payload_data,
        )


def report(exception=None, app=None, extra_data=None, level=None, exc_info=None):
    init()

    traceback.print_exc()

    if not rollbar_token:
        logger.debug("not submitting to rollbar - is disabled")

    elif app:
        logger.debug("reporting exception for flask - %s", str(exception))
        rollbar.contrib.flask.report_exception(app, exception)

    else:
        logger.debug("reporting exception info - %s", str(extra_data))

        rollbar.report_exc_info(
            exc_info=exc_info,
            extra_data=extra_data,
            level=level,
        )


def report_exception(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        response = None

        try:
            response = f(*args, **kwargs)

        except Exception as e:
            report(
                exception=e,
            )

            raise e

        return response

    return decorated_function
