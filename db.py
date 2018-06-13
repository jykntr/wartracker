from pymongo import MongoClient, ASCENDING
from pymongo.errors import DuplicateKeyError

COLLECTION_DAY = 'collectionDay'
WAR_DAY = 'warDay'

WARTRACKER_ID = '_wartracker_id'


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

        filter = {}
        filter[WARTRACKER_ID] = wartracker_id
        results = self.war.replace_one(filter, document, upsert=True)
        print('{} {}'.format(results.matched_count, results.modified_count))

    def add_war_battles(self, document):
        for battle in document:
            if battle['type'].startswith('clanWar'):
                try:
                    results = self.war_battles.insert_one(battle)
                    print(results)
                except DuplicateKeyError:
                    pass
