import logging

import pendulum
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from discord.ext import commands

from .db import DB
from .tracker import Tracker

log = logging.getLogger(__name__)


class Scheduler:
    def __init__(self, clan_tag: str, db: DB, bot: commands.Bot) -> None:
        self.clan_tag: str = clan_tag
        self.scheduler = AsyncIOScheduler()
        self.db = db
        self.bot = bot

        # Start the scheduler
        self.scheduler.start()

    def start_scheduler(self) -> None:
        # track the war once per hour starting now-ish
        self.scheduler.add_job(
            self.war_tracking,
            "interval",
            next_run_time=pendulum.now(tz="UTC").add(seconds=5),
            minutes=60,
            timezone="UTC",
        )

        self.scheduler.add_job(
            Tracker.track_war_battles,
            "interval",
            args=[self.clan_tag, self.db],
            next_run_time=pendulum.now("UTC").add(seconds=3),
            minutes=30,
            timezone="UTC",
            id="track_war_battles",
            name="Track war battles",
        )

        self.scheduler.add_job(
            Tracker.track_clan,
            "interval",
            args=[self.clan_tag, self.db],
            next_run_time=pendulum.now("UTC").add(seconds=2),
            minutes=30,
            jitter=350,
            timezone="UTC",
            id="track_clan",
            name="Track clan data",
        )

        self.scheduler.add_job(
            Tracker.track_war_logs,
            "interval",
            args=[self.clan_tag, self.db],
            next_run_time=pendulum.now("UTC").add(seconds=60),
            hours=4,
            misfire_grace_time=30,
            jitter=350,
            timezone="UTC",
            id="track_war_logs",
            name="Track war logs",
        )

    async def war_tracking(self):
        current_war = await Tracker.track_war(self.clan_tag, self.db)

        if current_war["state"] == "warDay" or current_war["state"] == "collectionDay":
            self.schedule_end_of_war_jobs(current_war)

    def schedule_end_of_war_jobs(self, war):
        war_end_timestamp = war.get("collectionEndTime", None) or war.get(
            "warEndTime", None
        )
        war_end_date = pendulum.from_timestamp(war_end_timestamp, tz="UTC")

        # War tracking jobs to collected war data
        t_minus_jobs = [1, 5, 10, 20, 30]
        for t_minus in t_minus_jobs:
            schedule_time = war_end_date.subtract(minutes=t_minus)
            job_id = self.get_job_id(
                war, "Tminus{}-{:.0f}".format(t_minus, schedule_time.timestamp())
            )
            self.schedule_war_job(
                self.war_tracking,
                schedule_time,
                job_id,
                "End of war job for {}".format(job_id),
            )

        # Job to fetch war logs if this is a War Day
        if war["state"] == "warDay":
            war_log_time = war_end_date.add(seconds=10)
            job_id = self.get_job_id(war, "war_logs")
            self.schedule_war_job(
                self.war_logs,
                war_log_time,
                job_id,
                "War logs job for {}".format(job_id),
                [war["clan"]["tag"]],
            )

        # Job to have bot print war summary
        summary_time = war_end_date.add(seconds=15)
        job_id = self.get_job_id(war, "war_summary")
        self.schedule_war_job(
            self.war_summary,
            summary_time,
            job_id,
            "War summary job for {}".format(job_id),
            [war["clan"]["tag"]],
        )

        log.debug(self.scheduler.get_jobs())

    def schedule_war_job(self, func, date, job_id, name=None, args=None):
        if not self.scheduler.get_job(job_id):
            self.scheduler.add_job(
                func, "date", id=job_id, name=name or job_id, run_date=date, args=args
            )

    async def war_logs(self, clan_tag):
        await Tracker.track_war_logs(clan_tag, self.db)

    async def war_summary(self, clan_tag):
        if not self.bot.is_ready() or not self.bot.get_cog("WarLog"):
            return

        await self.bot.get_cog("WarLog").war_summary_auto(clan_tag)

    @staticmethod
    def get_job_id(war, suffix):
        end_time = war.get("collectionEndTime", None) or war.get("warEndTime", None)
        return "{}-{}-{}-{}".format(war["clan"]["tag"], war["state"], end_time, suffix)
