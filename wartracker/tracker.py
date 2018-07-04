import aiohttp


class Tracker:
    KEY = None

    @classmethod
    def set_key(cls, key):
        cls.KEY = key

    @classmethod
    async def track_war(cls, clantag, db):
        url = 'https://api.royaleapi.com/clan/{}/war'.format(clantag)
        headers = {'auth': cls.KEY}

        async with aiohttp.ClientSession(trust_env=True) as cs:
            async with cs.get(url, headers=headers) as r:
                current_war = await r.json()

        db.add_current_war_document(current_war)

        return current_war

    @classmethod
    async def track_war_battles(cls, clantag, db, bot):
        url = 'https://api.royaleapi.com/clan/{}/battles?type={}'.format(clantag, 'war')
        headers = {'auth': cls.KEY}

        async with aiohttp.ClientSession(trust_env=True) as cs:
            async with cs.get(url, headers=headers) as r:
                battles = await r.json()

        new_battles = db.add_war_battles(battles)

        for battle in new_battles:
            #     warlog = bot.get_cog('WarLog')
            #     # if bot.is_ready() and warlog:
            #     await warlog.send_war_battle(battle)
            pass

    @classmethod
    async def track_clan(cls, clantag, db):
        url = 'https://api.royaleapi.com/clan/{}'.format(clantag)
        headers = {'auth': cls.KEY}

        async with aiohttp.ClientSession(trust_env=True) as cs:
            async with cs.get(url, headers=headers) as r:
                clan = await r.json()

        db.add_clan(clan)
