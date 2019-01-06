import pendulum


class Clan:
    def __init__(self, clan_json):
        self.json = clan_json

    @property
    def clan_name(self):
        return self.json["name"]

    @property
    def clan_tag(self):
        return self.json["tag"]

    @property
    def clan_badge(self):
        return self.json["badge"]["image"]

    @property
    def member_tags(self):
        member_tags = []
        for member in self.json["members"]:
            member_tags.append(member["tag"])

        return member_tags

    def get_member(self, tag):
        for member in self.json["members"]:
            if member["tag"] == tag:
                return member

        return None

    def get_top_donators(self, number_of_donators=3):
        sorted_members = sorted(
            self.json["members"], key=lambda x: x["donations"], reverse=True
        )

        return sorted_members[:number_of_donators]


class Battles:
    def __init__(self, battles_json):
        self.json = battles_json

    @property
    def number_of_battles(self):
        return len(self.json)

    def is_inactive(self, weeks_to_be_inactive=2):
        if self.number_of_battles == 0:
            return True
        else:
            battle_time = pendulum.from_timestamp(self.json[0]["utcTime"])
            return battle_time < pendulum.now("UTC").subtract(
                weeks=weeks_to_be_inactive
            )

    def get_last_battle_string(self):
        if self.number_of_battles == 0:
            return "No battles"
        else:
            battle_time = pendulum.from_timestamp(self.json[0]["utcTime"])
            return battle_time.diff_for_humans()


class War:
    def __init__(self, war_json):
        self.json = war_json

    def is_war_day(self):
        return "warEndTime" in self.json

    def is_collection_day(self):
        return "collectionEndTime" in self.json

    @property
    def clan_name(self):
        return self.json["clan"]["name"]

    @property
    def clan_tag(self):
        return self.json["clan"]["tag"]

    @property
    def clan_badge(self):
        return self.json["clan"]["badge"]["image"]

    @property
    def participant_count(self):
        return self.json["clan"]["participants"]

    @property
    def wins(self):
        return self.json["clan"]["wins"]

    @property
    def possible_battles(self):
        if self.is_war_day():
            return max(self.participant_count, self.battles_played)
        else:
            return self.participant_count * 3

    @property
    def battles_played(self):
        return self.json["clan"]["battlesPlayed"]

    @property
    def update_time(self):
        return pendulum.from_timestamp(self.json["_update_utc_timestamp"])

    @property
    def end_time(self):
        if self.is_war_day():
            return pendulum.from_timestamp(self.json["warEndTime"])
        else:
            return pendulum.from_timestamp(self.json["collectionEndTime"])

    @property
    def total_cards_earned(self):
        cards_earned = 0
        for participant in self.participants:
            cards_earned = cards_earned + participant["cardsEarned"]

        return cards_earned

    @property
    def participants(self):
        return self.json["participants"]

    @property
    def standings(self):
        if self.is_war_day():
            return self.json["standings"]
        else:
            return None
