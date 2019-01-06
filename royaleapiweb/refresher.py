import time

import clashroyale
import requests
from yaspin import yaspin

ROYALE_API = "royaleapi"
OFFICIAL_API = "official"


class Refresher:
    def __init__(self, clan_tag: str, key: str, api: str, sleep_seconds: int) -> None:
        self.clan_tag: str = clan_tag
        self.key: str = key
        self.sleep_seconds = sleep_seconds
        self.api = api

        if api.lower() == ROYALE_API:
            self.client = clashroyale.RoyaleAPI(key, is_async=False)
        else:
            self.client = clashroyale.OfficialAPI(key, is_async=False)

    def get_clan_members(self):
        if self.api == ROYALE_API:
            clan = self.client.get_clan(self.clan_tag)
            return clan.members
        else:
            return self.client.get_clan_members(self.clan_tag)

    @staticmethod
    def refresh_player_battles(player_tag):
        r = requests.get(f"https://royaleapi.com/player/{player_tag}/battles")
        return r.status_code == 200

    def run(self):
        with yaspin(text="Getting clan members...") as spinner:
            members = self.get_clan_members()
            spinner.green.ok("✓")

        for member in members:
            with yaspin() as spinner:
                spinner.text = f"Sleeping for {self.sleep_seconds} seconds..."
                time.sleep(self.sleep_seconds)

                spinner.text = f"Refreshing player {member.tag}"
                success = self.refresh_player_battles(member.tag.lstrip("#"))
                if not success:
                    spinner.red.fail("⨉")
                else:
                    spinner.green.ok("✓")

    def run_no_spin(self):
        print("Getting clan members...")
        members = self.get_clan_members()

        for member in members:
            print(f"Sleeping for {self.sleep_seconds} seconds...")
            time.sleep(self.sleep_seconds)
            print(f"Refreshing player {member.tag}...", end="", flush=True)
            success = self.refresh_player_battles(member.tag.lstrip("#"))
            if not success:
                print("⨉")
            else:
                print("✓")
