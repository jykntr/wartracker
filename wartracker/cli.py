import asyncio
import logging
import os

import click

from .bot import WarTrackerBot
from .db import DB
from .scheduler import Scheduler
from .tags import normalize_tag, is_tag_valid, get_legal_tag_chars
from .tracker import Tracker

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", logging.INFO),
    format="%(asctime)s:%(levelname)s:%(name)s:%(module)s:%(funcName)s:%(lineno)d - %(message)s",
)

log = logging.getLogger(__name__)
logging.getLogger("discord").setLevel(logging.INFO)
logging.getLogger("requests").setLevel(logging.INFO)
logging.getLogger("urllib3").setLevel(logging.INFO)
logging.getLogger("websockets").setLevel(logging.INFO)
logging.getLogger("asyncio").setLevel(logging.INFO)


def validate_player_tag_input(ctx, param, value):
    tag = normalize_tag(value)
    valid_tag = is_tag_valid(tag)

    if not valid_tag:
        raise click.BadParameter(
            "Tags may only contain the following characters: '{}'".format(
                get_legal_tag_chars()
            )
        )

    return tag


@click.command()
@click.option(
    "--bot-token",
    envvar="BOTTOKEN",
    default=None,
    help="Discord bot token. If not specified bot will not start.",
)
@click.option(
    "--command-prefix",
    envvar="BOT_PREFIX",
    default="$",
    help="The bots command prefix.",
)
@click.option(
    "--key",
    envvar="ROYALEAPIKEY",
    prompt="Enter the key for RoyaleAPI",
    help="RoyaleAPI authorization key.",
)
@click.option(
    "--database",
    envvar="MONGODBURI",
    default="mongodb://localhost:27017/",
    help='MongoDB Database URI.  E.g. "mongodb://localhost:27017/"',
)
@click.option(
    "--dbname",
    envvar="DBNAME",
    default="clashtracker",
    help="Name of database to connect with.",
)
@click.option(
    "--proxy-vars", is_flag=True, help="Use proxy environment variables if set."
)
@click.argument("clantag", envvar="CLANTAG", callback=validate_player_tag_input)
def main(clantag, key, database, dbname, bot_token, command_prefix, proxy_vars):
    Tracker.set_key(key)
    Tracker.trust_env = proxy_vars

    db = DB(database, dbname)
    db.connect()

    scheduler = Scheduler(clantag, db)

    if bot_token:
        bot = WarTrackerBot(bot_token, db, scheduler, command_prefix=command_prefix)
        bot.run()

    else:
        try:
            scheduler.add_jobs()
            asyncio.get_event_loop().run_forever()
        except (KeyboardInterrupt, SystemExit):
            pass


if __name__ == "__main__":
    main()
