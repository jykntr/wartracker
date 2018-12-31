import logging

import discord
from discord.ext import commands

from . import emoji_util
from .db import DB
from .emoji import emojis
from .models import War, Clan, Battles
from .scheduler import Scheduler
from .tracker import Tracker

log = logging.getLogger(__name__)


class WarTrackerBot(commands.Bot):
    def __init__(self, token: str, db: DB, scheduler: Scheduler, **options):
        super().__init__(**options)

        self.token = token
        self.db = db
        self.scheduler = scheduler

        self.add_cog(WarLog(self))

    def run(self):
        super().run(self.token)

    async def on_ready(self):
        log.info("We have logged in as {}".format(self.user))
        self.scheduler.bot = self
        self.scheduler.add_jobs()


class WarLog:
    """War log commands"""

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setwarlog(self, ctx, *, channel: discord.TextChannel):
        log.debug(
            "Setting war log to: {}, {}, {}, {}, {}.".format(
                "GJ98VC", channel.guild.name, channel.name, channel.guild.id, channel.id
            )
        )
        self.bot.db.set_war_log_channel("GJ98VC", channel.guild.id, channel.id)

    @setwarlog.error
    async def setwarlog_error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            await ctx.send(error)
        else:
            log.debug("Error setting")
            log.debug(error)

    def create_war_summary(self, auto=True):
        war = War(self.bot.db.get_latest_war())

        embed = discord.Embed(color=0x8000ff)
        WarLog.set_author(embed, war)
        if not auto or war.is_collection_day():
            WarLog.add_summary_line(embed, war)
            WarLog.add_standings(embed, war)
        WarLog.add_double_final_battle_wins(embed, war)
        WarLog.add_perfect_days(embed, war)
        WarLog.add_wall_of_shame(embed, war)
        WarLog.add_footer(embed, war, auto)

        return embed

    async def war_summary_auto(self, clantag):
        channel_ids = self.bot.db.get_war_log_channels(clantag)
        embed = self.create_war_summary(True)

        for channel_id in channel_ids:
            channel = self.bot.get_channel(channel_id)
            if channel:
                try:
                    await channel.send(embed=embed)
                except discord.DiscordException:
                    log.exception(
                        (
                            "Unexpected exception sending auto war summary. "
                            "Clan: {}, channel {}"
                        ).format(clantag, channel_id)
                    )

    @commands.command(name="warsum")
    async def war_summary_command(self, ctx):
        await ctx.trigger_typing()
        await Tracker.track_war("GJ98VC", self.bot.db)
        await ctx.send(embed=self.create_war_summary(auto=False))

    @staticmethod
    async def create_inactives_summary(clantag):
        inactive_players = []

        clan = Clan(await Tracker.get_clan(clantag))
        for tag in clan.member_tags:
            battles = Battles(await Tracker.get_player_battles(tag))

            if battles.is_inactive():
                member = clan.get_member(tag)
                member["last_battle_description"] = battles.get_last_battle_string()
                inactive_players.append(clan.get_member(tag))

        embed = discord.Embed(color=0x8000ff)
        embed.set_author(
            name=clan.clan_name,
            url="http://royaleapi.com/clan/{}/".format(clan.clan_tag),
            icon_url=clan.clan_badge,
        )

        lines = []
        count = 0
        for player in inactive_players:
            count = count + 1
            lines.append(
                "`\u2800{:2d}. {:\u2007<15} {:\u2007<11} ({:4d}, {})`{}".format(
                    count,
                    player["name"],
                    player["last_battle_description"],
                    player["trophies"],
                    player["role"],
                    emoji_util.get_bad_emote(),
                )
            )

        if len(lines) > 0:
            lines.insert(
                0,
                "`\u2800{:>2}\u2800 {:\u2007<15} {:\u2007<11} {}`".format(
                    "#", "Name", "Last battle", "(trophies, role)"
                ),
            )
            text = "\n".join(lines)
        else:
            text = "No inactive players! {}".format(emoji_util.get_good_emote())

        embed.add_field(name="Inactive Players", value=text, inline=False)

        return embed

    async def inactives_auto(self, clantag):
        channel_ids = self.bot.db.get_war_log_channels(clantag)
        embed = await self.create_inactives_summary(clantag)

        for channel_id in channel_ids:
            channel = self.bot.get_channel(channel_id)
            if channel:
                try:
                    await channel.send(embed=embed)
                except discord.DiscordException:
                    log.exception(
                        (
                            "Unexpected exception sending auto war summary. "
                            "Clan: {}, channel {}"
                        ).format(clantag, channel_id)
                    )

    @commands.command(name="inactives")
    async def inactives_command(self, ctx):
        await ctx.trigger_typing()
        embed = await self.create_inactives_summary("GJ98VC")
        await ctx.send(embed=embed)

    @staticmethod
    def set_author(embed, war):
        if war.is_war_day():
            name = "{} {}".format(war.clan_name, "War Day")
        else:
            name = "{} {}".format(war.clan_name, "Collection Day")

        embed.set_author(
            name=name,
            url="http://royaleapi.com/clan/{}/".format(war.clan_tag),
            icon_url=war.clan_badge,
        )

    @staticmethod
    def add_summary_line(embed, war):
        embed.add_field(
            name="Participants",
            value="{} {}".format(emojis["participant"], war.participant_count),
            inline=True,
        )
        embed.add_field(
            name="Wins", value="{} {}".format(emojis["warwin"], war.wins), inline=True
        )
        embed.add_field(
            name="Battles played",
            value="{} {}/{}".format(
                emojis["battle"], war.battles_played, war.possible_battles
            ),
            inline=True,
        )
        embed.add_field(
            name="Cards collected",
            value="{} {}".format(emojis["cards"], war.total_cards_earned),
            inline=True,
        )
        embed.add_field(
            name="Average cards per player",
            value="{} {:.0f}".format(
                emojis["cards"], war.total_cards_earned / war.participant_count
            ),
            inline=True,
        )

    @staticmethod
    def add_perfect_days(embed, war):
        if war.is_war_day():
            return

        lines = []
        perfect_day_count = 0
        for participant in war.participants:
            if participant["wins"] == 3:
                perfect_day_count = perfect_day_count + 1
                line = "`\u2800{:2d}. {:\u2007<15} {:\u2007>5}` {}".format(
                    perfect_day_count,
                    participant["name"],
                    participant["cardsEarned"],
                    emoji_util.get_good_emote(),
                )
                lines.append(line)

        if len(lines) > 0:
            lines.insert(
                0,
                "`\u2800{:>2}\u2800 {:\u2007<15} {:\u2007^5}\u2800`".format(
                    "#", "Name", "Cards"
                ),
            )
            text = "\n".join(lines)
        else:
            text = "No perfect collection days! {}".format(emoji_util.get_bad_emote())

        embed.add_field(name="MVPs - Perfect Collection Day", value=text, inline=False)

    @staticmethod
    def add_double_final_battle_wins(embed, war):
        if not war.is_war_day():
            return

        lines = []
        double_wins = 0
        for participant in war.participants:
            if participant["wins"] > 1:
                double_wins = double_wins + 1
                line = "`\u2800{:2d}. {:\u2007<15}\u2800`{}".format(
                    double_wins, participant["name"], emoji_util.get_good_emote()
                )
                lines.append(line)

        if len(lines) > 0:
            lines.insert(0, "`\u2800{:>2}\u2800 {:\u2007<15}`".format("#", "Name"))
            text = "\n".join(lines)
            embed.add_field(name="MVPs - Double War Day Wins", value=text, inline=False)

    @staticmethod
    def add_wall_of_shame(embed, war):
        if war.is_war_day():
            expected_battles = 1
            name = "Wall of Shame - Unplayed final battles:"
        else:
            expected_battles = 3
            name = "Wall of Shame - Unplayed collection battles:"

        lines = []
        shame_count = 0
        for participant in war.participants:
            if participant["battlesPlayed"] < expected_battles:
                shame_count = shame_count + 1
                if war.is_war_day():
                    line = "`\u2800{:2d}. {:\u2007<15}\u2800`{}".format(
                        shame_count, participant["name"], emoji_util.get_bad_emote()
                    )
                else:
                    count = expected_battles - participant["battlesPlayed"]
                    line = "`\u2800{:2d}. {:\u2007<15}\u2007{:2d}`{}".format(
                        shame_count,
                        participant["name"],
                        count,
                        emoji_util.get_bad_emote(),
                    )
                lines.append(line)

        if len(lines) > 0:
            if war.is_war_day():
                lines.insert(0, "`\u2800{:>2}\u2800 {:<15}`".format("#", "Name"))
            else:
                lines.insert(
                    0,
                    "`\u2800{:>2}\u2800 {:\u2007<15} {}`".format("#", "Name", "Missed"),
                )

            text = "\n".join(lines)
        else:
            text = "No missed battles!  :)"

        embed.add_field(name=name, value=text, inline=False)

    @staticmethod
    def add_standings(embed, war):
        if not war.is_war_day():
            return

        text = ""
        for rank, standing in enumerate(war.standings, 1):
            line = (
                "`#{}` {}`{}{:2d}` {}`{}{:2d}` {} [{}](http://royaleapi.com/clan/{})\n"
            )
            line = line.format(
                rank,
                emojis["warwin"],
                "\u2800",
                standing["wins"],
                emojis["crownblue"],
                "\u2800",
                standing["crowns"],
                emoji_util.get_clan_badge(standing),
                standing["name"],
                standing["tag"],
            )

            text += line

        embed.add_field(name="Standings", value=text, inline=False)

    @staticmethod
    def add_footer(embed, war, auto):
        update_time = war.update_time
        end_time = war.end_time

        end_string = end_time.in_timezone("America/Denver").format(
            "dddd, MMMM Do @ h:mm A zz"
        )
        if auto:
            footer = "* Ended {} - last updated {} end time.".format(
                end_string, update_time.diff_for_humans(end_time)
            )
        else:
            footer = "* Ends {} ({}) - last updated {}.".format(
                end_string, end_time.diff_for_humans(), update_time.diff_for_humans()
            )

        embed.set_footer(text=footer)
