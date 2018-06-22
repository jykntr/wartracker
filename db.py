from datetime import datetime

from pymongo import MongoClient, ASCENDING
from pymongo.errors import DuplicateKeyError

COLLECTION_DAY = 'collectionDay'
WAR_DAY = 'warDay'

WARTRACKER_ID = '_wartracker_id'
UPDATE_TIMESTAMP = '_update_timestamp'
UPDATE_DATE_STRING = '_update_date_string'
UPDATE_UTC_DATE_STRING = '_update_utc_date_string'


class DB():
    def __init__(self, uri, db_name):
        self.uri = uri
        self.db_name = db_name
        self.client = None
        self.database = None
        self.war = None

    def connect(self):
        self.client = MongoClient(self.uri)
        self.database = self.client.clashtracker
        self.war = self.database.war
        self.war_battles = self.database.war_battles
        self.clan = self.database.clan

        self.war.create_index(WARTRACKER_ID, name=WARTRACKER_ID, unique=True)
        self.war_battles.create_index([('utcTime', ASCENDING), ('team.tag', ASCENDING)], unique=True)

    def add_current_war_document(self, document):
        if document['state'] == WAR_DAY:
            wartracker_id = '{}_{}_{}'.format(document['clan']['tag'],
                                              document['state'],
                                              document['warEndTime'])

        elif document['state'] == COLLECTION_DAY:
            wartracker_id = '{}_{}_{}'.format(document['clan']['tag'],
                                              document['state'],
                                              document['collectionEndTime'])
        else:
            return None

        # Make our own id field to use for filtering & ensuring uniqueness
        document[WARTRACKER_ID] = wartracker_id
        self.add_timestamps(document)

        filter = {}
        filter[WARTRACKER_ID] = wartracker_id
        results = self.war.replace_one(filter, document, upsert=True)
        print('{} {}'.format(results.matched_count, results.modified_count))

    def add_war_battles(self, document):
        for battle in document:
            if battle['type'].startswith('clanWar'):
                try:
                    self.add_timestamps(battle)
                    results = self.war_battles.insert_one(battle)
                    print(results)
                except DuplicateKeyError:
                    pass

    def add_clan(self, document):
        self.add_timestamps(document)
        return self.clan.insert_one(document)

    def add_timestamps(self, document):
        document[UPDATE_TIMESTAMP] = int(datetime.utcnow().timestamp())
        document[UPDATE_DATE_STRING] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        document[UPDATE_UTC_DATE_STRING] = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

        return document
