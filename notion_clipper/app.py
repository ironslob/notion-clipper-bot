# -*- coding: utf-8 -*-

from datetime import datetime
from flask import render_template, Flask, g, session, abort, redirect, jsonify, request, url_for
from werkzeug.middleware.proxy_fix import ProxyFix
from urllib.parse import urlparse, urlunparse
from flask_dance.consumer.storage.sqla import SQLAlchemyStorage

from telegram.messageentity import MessageEntity

import telegram
import logging
import os

from . import exceptions, models
from .helpers import get_bot
from .notion import notion_bp
from .database import SessionManager, SessionLocal

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

notion_headers = {
    'Notion-Version': '2021-05-11',
}

def _telegram_user():
    telegram_user_id = g.get('telegram_user_id', None) or session.get('telegram_user_id', None)
    telegram_user = None

    if telegram_user_id:
        telegram_user = g.db.query(models.TelegramUser).filter(models.TelegramUser.telegram_user_id == telegram_user_id).first()

    return telegram_user


def _reauth_notion(message):
    # delete notion, trigger send auth
    user = _telegram_user()
    g.db.delete(user.notion_auth)
    g.db.commit()

    _send_auth_message(user, message)


def _send_welcome_message(user, message):
    bot = get_bot()
    bot.sendMessage(
        chat_id = user.telegram_chat_id,
        text = 'Hello! This little bot will create a new page in whatever database you point it at.',
    )


def _send_auth_message(user, message):
    login_url = full_url_for('notion_auth', telegram_user_id=user.telegram_user_id)

    bot = get_bot()
    bot.sendMessage(
        chat_id = user.telegram_chat_id,
        text = 'Visit the following URL to connect your Notion account - %s - and note for now ONLY CHOOSE ONE database!' % login_url,
    )


def _send_database_message(user, message):
    login_url = full_url_for('notion_auth', telegram_user_id=user.telegram_user_id)

    bot = get_bot()
    bot.sendMessage(
        chat_id = user.telegram_chat_id,
        text = 'You need to tell me which database you want me to add pages to. Hang on while I show you a list...',
    )

    request = notion_bp.session.get('/v1/databases', headers=notion_headers)

    if request.ok:
        data = request.json()
        results = data['results']

        if not results:
            bot.sendMessage(
                chat_id = user.telegram_chat_id,
                text = 'I don\'t have access to any databases, you may need to disconnect this integration within your Notion settings page to allow access to different databases.',
            )

        else:
            def _database_title(database):
                return database['title'][0]['plain_text']

            if len(results) == 1:
                bot.sendMessage(
                    chat_id = user.telegram_chat_id,
                    text = 'Found 1 database - %s - and setting that as default' % _database_title(results[0]),
                )

                _choose_database(results[0]['id'])

            else:
                bot.sendMessage(
                    chat_id = user.telegram_chat_id,
                    text = 'I found %d databases, but I can only handle one at the moment. You\'ll have to remove the integration and re-add it in order to choose which databases (pages) you allow me to access.',
                )

                # TODO multiple databases requires implementing /database command, and taking a parameter

                # databases = "\n".join([
                #     '[inline /database %s](%s)' % (database['id'], _database_title(database))
                #     for database in results
                # ])

                # bot.sendMessage(
                #     chat_id = user.telegram_chat_id,
                #     text = databases,
                # )

    else:
        bot.sendMessage(
            chat_id = user.telegram_chat_id,
            text = 'Something went wrong, try again in a few minutes!',
        )


def _track_user_from_message(db, message):
    created = False
    default_language_code = 'en'
    user = db.query(models.TelegramUser).filter(models.TelegramUser.telegram_user_id == message.from_user.id).first()

    if not user:
        created = True
        user = models.TelegramUser(
            telegram_user_id=message.from_user.id,
            telegram_chat_id=message.chat.id,
            first_name=message.from_user.first_name or '',
            last_name=message.from_user.last_name or '',
            username=message.from_user.username or '',
            language_code=message.from_user.language_code or default_language_code,
            first_seen=datetime.now(),
            last_seen=datetime.now(),
        )

    else:
        db.telegram_chat_id = message.chat_id
        db.last_seen = datetime.now()

    db.add(user)
    db.commit()

    return user, created


def _handle_start(message):
    user = _telegram_user()

    _send_auth_message(user, message)


def _handle_help(message):
    help_copy = 'Some helpful message goes here about /help'

    bot = get_bot()

    bot.sendMessage(
        chat_id = message.chat.id,
        text = help_copy,
    )


def _handle_stop(message):
    bot = get_bot()

    bot.sendMessage(
        chat_id = message.chat.id,
        text = 'NOT IMPLEMENTED /stop',
    )


def _handle_about(message):
    about_copy = 'Some aboutful message goes here about /about'

    bot = get_bot()

    bot.sendMessage(
        chat_id = message.chat.id,
        text = about_copy,
    )


def _handle_database(message = None):
    _send_database_message(_telegram_user(), message)


class SQLAlchemySessionStorage(SQLAlchemyStorage):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        SQLAlchemySessionStorage.session = property(lambda x: g.db)

notion_bp.storage = SQLAlchemySessionStorage(models.NotionAuth, None, user=_telegram_user)


def request_source():
    (scheme, netloc, path, params, query, fragment) = urlparse(request.url)
    return urlunparse((scheme, netloc, '', None, None, None))


def full_url_for(*args, **kwargs):
    base_url = kwargs.pop('_base_url', None) or request_source()
    url = url_for(*args, **kwargs)
    full_url = base_url + url

    return full_url


def _choose_database(database_id):
    response = notion_bp.session.get('/v1/databases/%s' % database_id, headers=notion_headers)

    assert response.ok, response.text

    data = response.json()

    user = _telegram_user()
    notion_auth = user.notion_auth
    notion_auth.database = data

    g.db.add(notion_auth)
    g.db.commit()
    g.db.refresh(notion_auth)


def build_app():
    app = Flask(__name__)
    app.wsgi_app = ProxyFix(app.wsgi_app)
    app.secret_key = os.environ['SECRET_KEY']

    app.register_blueprint(notion_bp, url_prefix="/login")

    exceptions.init(app)

    @app.before_request
    def pre_request():
        g.db = SessionLocal()
        g.telegram_user_id = None


    @app.after_request
    def post_request(response):
        g.telegram_user_id = None

        try:
            g.db.rollback()

        except:
            pass

        finally:
            g.db.close()
            g.db = None

        return response


    @app.route('/all-done')
    def back_to_telegram():
        # TODO send a message to the telegram user, with choosing database
        _handle_database()

        return render_template('back_to_telegram.html')


    @app.route('/auth-test')
    def auth_test():
        pass


    @app.route('/', methods = [ 'GET', 'POST' ])
    def webhook():
        # {
        #    "message" : {
        #       "chat" : {
        #          "first_name" : "Matt",
        #          "id" : 983713751,
        #          "last_name" : "Wilson",
        #          "type" : "private",
        #          "username" : "ironslob"
        #       },
        #       "date" : 1604824088,
        #       "entities" : [
        #          {
        #             "length" : 6,
        #             "offset" : 0,
        #             "type" : "bot_command"
        #          }
        #       ],
        #       "from" : {
        #          "first_name" : "Matt",
        #          "id" : 983713751,
        #          "is_bot" : false,
        #          "language_code" : "en",
        #          "last_name" : "Wilson",
        #          "username" : "ironslob"
        #       },
        #       "message_id" : 2,
        #       "text" : "/start"
        #    },
        #    "update_id" : 263842683
        # }

        data = request.json

        if not data:
            return abort(400)

        bot = get_bot()

        update = telegram.Update.de_json(
            data = request.json,
            bot = bot,
        )

        message = update.message

        # is this the first time we've seen a user?
        #   yes -> send welcome message
        #   no ->
        #       do we have notion credentials for this user?
        #           no -> send notion connection message
        #           yes ->
        #               is this a command?
        #                   yes -> handle it
        #                   no -> send message contents to notion as new block

        # if message.bot
        # if message.chat
        # if message.voice
        bot = get_bot()

        # update.effective_chat.permissions

        if message and not message.from_user.is_bot:
            user, created = _track_user_from_message(g.db, message)
            notion_auth = user.notion_auth

            if user:
                g.telegram_user_id = user.telegram_user_id

            # slightly hack approach to "is this the first time we've seen this user?"
            if created:
                _send_welcome_message(user, message)

            commands = filter(lambda entity: entity.type == MessageEntity.BOT_COMMAND, message.entities)
            command = next(commands, None)

            if command:
                command_text = message.text[command.offset:command.length]

                command_handlers = {
                    '/start': _handle_start,
                    '/help': _handle_help,
                    '/stop': _handle_stop,
                    '/about': _handle_about,
                    '/database': _handle_database,
                    '/reauth': _reauth_notion,
                }

                requires_auth = [
                    '/database',
                ]

                if command_text in command_handlers:
                    if command_text in requires_auth and not notion_auth:
                        bot.sendMessage(
                            chat_id = message.chat.id,
                            text = 'Not ready for that! You need to setup with Notion first',
                        )

                        _send_auth_message(user, message)

                    else:
                        command_handlers[command_text](message)

                else:
                    bot.sendMessage(
                        chat_id = message.chat.id,
                        text = 'You sent a command I don\'t understand - %s' % command_text,
                    )

            elif not notion_auth:
                _send_auth_message(user, message)

            elif not notion_auth.database:
                _send_database_message(user, message)

            else:
                # send message to notion
                properties = notion_auth.database['properties']
                title_property = next(filter(lambda key: properties[key]['type'] == 'title', properties.keys()))

                payload = {
                    'parent': {
                        'type': 'database_id',
                        'database_id': notion_auth.database['id'],
                    },
                    'properties': {
                        title_property: {
                            'type': 'title',
                            'title': [
                                {
                                    'type': 'text',
                                    'text': {
                                        'content': message.text,
                                    }
                                }
                            ]
                        }
                    }
                }

                response = notion_bp.session.post('/v1/pages', json=payload, headers=notion_headers)

                msg = 'Done! ✅'

                if not response.ok:
                    msg = 'Error from Notion 😩'

                bot.sendMessage(
                    chat_id = message.chat.id,
                    text = msg,
                )

        return jsonify({ 'ok': 1 })


    @app.route('/notion/<telegram_user_id>')
    def notion_auth(telegram_user_id):
        session['telegram_user_id'] = telegram_user_id
        session.modified = True

        return redirect(url_for('notion.login'))

    @app.route('/ping')
    def ping():
        return jsonify({ 'ok': 1 })


    # can also use curl -F "url=https://<YOURDOMAIN.EXAMPLE>/<WEBHOOKLOCATION>" https://api.telegram.org/bot<YOURTOKEN>/setWebhook
    @app.route('/setup', methods = [ 'GET', 'POST' ])
    def setup_webhook():
        bot = get_bot()

        logger.debug('setting webhook to {request.url_root}')

        # webhook = bot.set_webhook('https://webhook.site/23b43c0b-1a56-40fb-9fa4-f9eb9744d4c3')
        webhook = bot.set_webhook(request.url_root)

        return jsonify({ 'ok': 1 })

    return app

application = build_app()

if __name__ == '__main__':
    application.run(
        debug = True,
        port = 6000,
    )
