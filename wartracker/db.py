import logging

import pendulum
import pymongo
from pymongo import MongoClient, ASCENDING
from pymongo.errors import DuplicateKeyError

log = logging.getLogger(__name__)

COLLECTION_DAY = "collectionDay"
WAR_DAY = "warDay"

WARTRACKER_ID = "_wartracker_id"
UPDATE_UTC_TIMESTAMP = "_update_utc_timestamp"
UPDATE_UTC_DATE_STRING = "_update_utc_date_string"
UPDATE_LOCAL_DATE_STRING = "_update_local_date_string"
END_DATE_UTC = "_end_date_utc"
END_DATE_LOCAL = "_end_date_local"
BATTLE_DATE_UTC = "_battle_date_utc"
BATTLE_DATE_LOCAL = "_battle_date_local"
CREATED_DATE_UTC = "_created_date_utc"
CREATED_DATE_LOCAL = "_created_date_local"


class DB:
    def __init__(self, uri, db_name):
        self.uri = uri
        self.db_name = db_name
        self.client = None
        self.database = None
        self.war = None
        self.war_battles = None
        self.clan = None
        self.war_log_channels = None
        self.war_logs = None

    def connect(self):
        self.client = MongoClient(self.uri)
        self.database = self.client.clashtracker
        self.war = self.database.war
        self.war_battles = self.database.war_battles
        self.clan = self.database.clan
        self.war_log_channels = self.database.war_log_channels
        self.war_logs = self.database.war_logs

        self.war.create_index(WARTRACKER_ID, name=WARTRACKER_ID, unique=True)
        self.war_battles.create_index(
            [("utcTime", ASCENDING), ("team.tag", ASCENDING)], unique=True
        )
        self.war_log_channels.create_index(
            [("clan", ASCENDING), ("server", ASCENDING)], unique=True
        )
        self.war_logs.create_index(
            [("createdDate", ASCENDING), ("clantag", ASCENDING)], unique=True
        )

    def add_current_war_document(self, document):
        # Get the time that War/Collection day ends
        try:
            if document["state"] == WAR_DAY:
                end_timestamp = document["warEndTime"]
            elif document["state"] == COLLECTION_DAY:
                end_timestamp = document["collectionEndTime"]
            else:
                # If this isn't a War/Collection day, just skip it
                return
        except KeyError:
            log.exception("Unknown document...")
            log.debug(document)
            return

        # Make our own id field to use for filtering & ensuring uniqueness and add it to the document
        wartracker_id = "{}_{}_{}".format(
            document["clan"]["tag"], document["state"], end_timestamp
        )
        document[WARTRACKER_ID] = wartracker_id

        # Add timestamps to document
        self.add_timestamps(document)

        # Add readable end dates to document
        war_end_date = pendulum.from_timestamp(end_timestamp, tz="UTC")
        local_end_date = war_end_date.in_timezone("America/Denver")
        document[END_DATE_UTC] = war_end_date.to_datetime_string()
        document[END_DATE_LOCAL] = local_end_date.to_datetime_string()

        # Add or update document
        id_filter = {WARTRACKER_ID: wartracker_id}
        results = self.war.replace_one(id_filter, document, upsert=True)
        print("{} {}".format(results.matched_count, results.modified_count))

    def add_war_battles(self, document):
        added_battles = []
        for battle in document:
            try:
                if battle["type"].startswith("clanWar"):
                    # Add timestamps for update
                    self.add_timestamps(battle)

                    # Add readable battle dates to document
                    battle_date = pendulum.from_timestamp(battle["utcTime"], tz="UTC")
                    local_battle_date = battle_date.in_timezone("America/Denver")
                    battle[BATTLE_DATE_UTC] = battle_date.to_datetime_string()
                    battle[BATTLE_DATE_LOCAL] = local_battle_date.to_datetime_string()

                    # Attempt to add the document
                    try:
                        results = self.war_battles.insert_one(battle)
                        # if results show it was added, return the added battles to a list
                        if results.acknowledged:
                            added_battles.append(battle)

                        print(results)
                    except DuplicateKeyError:
                        pass
            except TypeError:
                log.exception("Malformed Battle: {}".format(battle))

        return added_battles

    def add_war_logs(self, document):
        added_war_logs = []
        for war_log in document:
            # Add timestamps for update
            self.add_timestamps(war_log)

            # Add readable created dates
            created_date = pendulum.from_timestamp(war_log["createdDate"], tz="UTC")
            local_created_date = created_date.in_timezone("America/Denver")
            war_log[CREATED_DATE_UTC] = created_date.to_datetime_string()
            war_log[CREATED_DATE_LOCAL] = local_created_date.to_datetime_string()

            try:
                results = self.war_logs.insert_one(war_log)
                if results.acknowledged:
                    added_war_logs.append(war_log)

                print(results)
            except DuplicateKeyError:
                pass

        return added_war_logs

    def add_clan(self, document):
        self.add_timestamps(document)
        return self.clan.insert_one(document)

    def get_latest_collection_day(self):
        document = self.war.find_one(
            {"state": "collectionDay"}, sort=[("$natural", pymongo.DESCENDING)]
        )
        return document

    def get_latest_war_day(self):
        document = self.war.find_one(
            {"state": "warDay"}, sort=[("$natural", pymongo.DESCENDING)]
        )
        return document

    def get_latest_war(self):
        document = self.war.find_one(sort=[("$natural", pymongo.DESCENDING)])
        return document

    @staticmethod
    def add_timestamps(document):
        utc_date = pendulum.now(tz="UTC")
        local_date = utc_date.in_timezone("America/Denver")
        document[UPDATE_UTC_TIMESTAMP] = int(utc_date.timestamp())
        document[UPDATE_UTC_DATE_STRING] = utc_date.to_datetime_string()
        document[UPDATE_LOCAL_DATE_STRING] = local_date.to_datetime_string()

        return document

    def set_war_log_channel(self, clantag, server_id, channel_id):
        document = {"clan": clantag, "server": server_id, "channel": channel_id}
        filter = {"clan": clantag, "server": server_id}

        self.war_log_channels.replace_one(filter, document, upsert=True)

    def get_war_log_channels(self, clantag):
        channels = []
        for war_log_channel in self.war_log_channels.find({"clan": clantag}):
            channels.append(war_log_channel["channel"])

        return channels
