import logging

import aiohttp

log = logging.getLogger(__name__)


class Tracker:
    KEY = None
    trust_env = False

    @classmethod
    def set_key(cls, key):
        cls.KEY = key

    @classmethod
    async def track_war(cls, clantag, db):
        url = "https://api.royaleapi.com/clan/{}/war".format(clantag)

        current_war = await Tracker._make_call(url)

        db.add_current_war_document(current_war)

        return current_war

    @classmethod
    async def track_war_battles(cls, clantag, db):
        url = "https://api.royaleapi.com/clan/{}/battles?type={}".format(clantag, "war")

        try:
            battles = await Tracker._make_call(url)
        except aiohttp.client_exceptions.ContentTypeError:
            log.exception("Problem converting war battles to JSON.")
            return

        return db.add_war_battles(battles)

    @classmethod
    async def track_clan(cls, clantag, db):
        url = "https://api.royaleapi.com/clan/{}".format(clantag)

        clan = await Tracker._make_call(url)

        db.add_clan(clan)

    @classmethod
    async def track_war_logs(cls, clantag, db):
        url = "https://api.royaleapi.com/clan/{}/warlog".format(clantag)

        war_logs = await Tracker._make_call(url)

        for war_log in war_logs:
            war_log["clantag"] = clantag

        db.add_war_logs(war_logs)

    @classmethod
    async def _make_call(cls, url):
        headers = {"auth": cls.KEY}

        async with aiohttp.ClientSession(trust_env=cls.trust_env) as cs:
            async with cs.get(url, headers=headers) as r:
                log.debug(
                    "X-Ratelimit-Remaining: {}, Retry-After: {}".format(
                        r.headers.get("X-Ratelimit-Remaining", "Not set"),
                        r.headers.get("Retry-After", "Not set"),
                    )
                )

                return await r.json()
