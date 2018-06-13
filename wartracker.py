import asyncio
import datetime
import logging
import os

import clashroyale
import click
import requests
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import tags
from db import DB

logging.basicConfig(level=os.getenv("LOG_LEVEL", logging.INFO),
                    format='%(asctime)s:%(levelname)s:%(module)s:%(funcName)s:%(lineno)d - %(message)s')

log = logging.getLogger(__name__)
logging.getLogger('peewee').setLevel(logging.INFO)
logging.getLogger('requests').setLevel(logging.INFO)
logging.getLogger("urllib3").setLevel(logging.INFO)


def validate_player_tag_input(ctx, param, value):
    tag = tags.normalize_tag(value)
    valid_tag = tags.is_tag_valid(tag)

    if not valid_tag:
        raise click.BadParameter(
            'Tags may only contain the following characters: \'{}\''.format(tags.get_legal_tag_chars()))

    return tag


class Scheduler:
    def __init__(self, clan_tag: str, db: DB) -> None:
        self.clan_tag: str = clan_tag
        self.scheduler = AsyncIOScheduler()
        self.db = db

        # Start the scheduler
        self.scheduler.start()

    def start_scheduler(self) -> None:
        # track the war once per hour starting now
        self.scheduler.add_job(self.war_tracking,
                               'interval',
                               next_run_time=datetime.datetime.now(),
                               minutes=60,
                               timezone='America/Denver')

        self.scheduler.add_job(track_war_battles, 'interval', args=[self.clan_tag, self.db],
                               next_run_time=datetime.datetime.now(),
                               minutes=30,
                               timezone='America/Denver',
                               id='track_war_battles',
                               name='Track war battles')

    def war_tracking(self):
        current_war = track_war(self.clan_tag, self.db)

        if current_war['state'] == 'warDay' or current_war['state'] == 'collectionDay':
            self.schedule_end_of_war_jobs(current_war)

    def schedule_end_of_war_jobs(self, war):
        war_end_timestamp = war.get('collectionEndTime', None) or war.get('warEndTime', None)
        war_end_date = datetime.datetime.utcfromtimestamp(war_end_timestamp)

        t_minus_jobs = [1, 3, 5, 10, 20, 30]
        for t_minus in t_minus_jobs:
            id = self.get_job_id(war, 'Tminus{}'.format(t_minus))
            schedule_time = war_end_date - datetime.timedelta(minutes=t_minus)
            self.schedule_war_job(schedule_time, id, 'End of war job for {}'.format(id))

        print(self.scheduler.get_jobs())

    def schedule_war_job(self, date, id, name=None):
        if not self.scheduler.get_job(id):
            self.scheduler.add_job(self.war_tracking,
                                   'date',
                                   id=id,
                                   name=name or id,
                                   run_date=date)

    def get_job_id(self, war, suffix):
        end_time = war.get('collectionEndTime', None) or war.get('warEndTime', None)
        return '{}-{}-{}-{}'.format(war['clan']['tag'], war['state'], end_time, suffix)


class RoyaleAPI:
    KEY = None

    @classmethod
    def set_key(cls, key):
        cls.KEY = key

    @classmethod
    def client(cls):
        return clashroyale.Client(cls.KEY)


def track_war(clantag, db):
    url = 'https://api.royaleapi.com/clan/{}/war'.format(clantag)
    headers = {'auth': RoyaleAPI.KEY}

    r = requests.get(url, headers=headers)
    r.raise_for_status()

    current_war = r.json()

    db.add_current_war_document(current_war)

    return current_war


def track_war_battles(clantag, db):
    url = 'https://api.royaleapi.com/clan/{}/battles?type={}'.format(clantag, 'war')
    headers = {'auth': RoyaleAPI.KEY}

    r = requests.get(url, headers=headers)
    r.raise_for_status()

    battles = r.json()

    db.add_war_battles(battles)


@click.command('waranalysis')
@click.option('--key', envvar='ROYALEAPIKEY', prompt='Enter the key for RoyaleAPI', help='RoyaleAPI authorization key.')
@click.option('--database', envvar='MONGODBURI', default='mongodb://localhost:27017/',
              help='MongoDB Database URI.  E.g. "mongodb://localhost:27017/"')
@click.option('--dbname', envvar='DBNAME', default='clashtracker', help='Name of database to connect with.')
@click.argument('clantag', envvar='CLANTAG', callback=validate_player_tag_input)
def cli(clantag, key, database, dbname):
    RoyaleAPI.set_key(key)

    db = DB(database, dbname)
    db.connect()

    scheduler = Scheduler(clantag, db)
    scheduler.start_scheduler()

    try:
        asyncio.get_event_loop().run_forever()
    except (KeyboardInterrupt, SystemExit):
        pass


if __name__ == '__main__':
    cli()
