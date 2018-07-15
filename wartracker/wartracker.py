#!/usr/bin/env python3

import asyncio
import logging
import os

import click
import discord
import pendulum
from discord.ext import commands

from . import emoji_util
from . import tags
from .db import DB
from .emoji import emojis
from .scheduler import Scheduler
from .tracker import Tracker

logging.basicConfig(level=os.getenv('LOG_LEVEL', logging.DEBUG),
                    format='%(asctime)s:%(levelname)s:%(module)s:%(module)s:%(funcName)s:%(lineno)d - %(message)s')

log = logging.getLogger(__name__)
logging.getLogger('discord').setLevel(logging.INFO)
logging.getLogger('requests').setLevel(logging.INFO)
logging.getLogger('urllib3').setLevel(logging.INFO)
logging.getLogger('websockets').setLevel(logging.INFO)
logging.getLogger('asyncio').setLevel(logging.INFO)


def validate_player_tag_input(ctx, param, value):
    tag = tags.normalize_tag(value)
    valid_tag = tags.is_tag_valid(tag)

    if not valid_tag:
        raise click.BadParameter(
            'Tags may only contain the following characters: \'{}\''.format(tags.get_legal_tag_chars()))

    return tag


class War:
    def __init__(self, war_json):
        self.json = war_json

    def is_war_day(self):
        return 'warEndTime' in self.json

    def is_collection_day(self):
        return 'collectionEndTime' in self.json

    @property
    def clan_name(self):
        return self.json['clan']['name']

    @property
    def clan_tag(self):
        return self.json['clan']['tag']

    @property
    def clan_badge(self):
        return self.json['clan']['badge']['image']

    @property
    def participant_count(self):
        return self.json['clan']['participants']

    @property
    def wins(self):
        return self.json['clan']['wins']

    @property
    def possible_battles(self):
        if self.is_war_day():
            return max(self.participant_count, self.battles_played)
        else:
            return self.participant_count * 3

    @property
    def battles_played(self):
        return self.json['clan']['battlesPlayed']

    @property
    def update_time(self):
        return pendulum.from_timestamp(self.json['_update_utc_timestamp'])

    @property
    def end_time(self):
        if self.is_war_day():
            return pendulum.from_timestamp(self.json['warEndTime'])
        else:
            return pendulum.from_timestamp(self.json['collectionEndTime'])

    @property
    def total_cards_earned(self):
        cards_earned = 0
        for participant in self.participants:
            cards_earned = cards_earned + participant['cardsEarned']

        return cards_earned

    @property
    def participants(self):
        return self.json['participants']

    @property
    def standings(self):
        if self.is_war_day():
            return self.json['standings']
        else:
            return None


class WarLog:
    """War log commands"""

    # The space below is a ZERO WIDTH SPACE (U+200B)
    # It looks like a space, but Discord's code block system will not trim it from the start of strings
    SPACE = '​'

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setwarlog(self, ctx, *, channel: discord.TextChannel):
        log.debug('Setting war log to: {}, {}, {}, {}, {}.'.format('GJ98VC',
                                                                   channel.guild.name,
                                                                   channel.name,
                                                                   channel.guild.id,
                                                                   channel.id))
        self.bot.db.set_war_log_channel('GJ98VC', channel.guild.id, channel.id)

    @setwarlog.error
    async def setwarlog_error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            await ctx.send(error)
        else:
            log.debug('Error setting')
            log.debug(error)

    async def send_war_battle(self, battle):
        log.debug('{}?type=war'.format(battle['team'][0]['deckLink']))

        channel = self.bot.get_channel(330528722211962880)
        if channel:
            await channel.send('{}'.format(battle['team'][0]['deckLink']))

    def create_war_summary(self):
        war = War(self.bot.db.get_latest_war())

        embed = discord.Embed(color=0x8000ff)
        WarLog.set_author(embed, war)
        WarLog.add_summary_line(embed, war)
        WarLog.add_standings(embed, war)
        WarLog.add_double_final_battle_wins(embed, war)
        WarLog.add_perfect_days(embed, war)
        WarLog.add_wall_of_shame(embed, war)
        WarLog.add_footer(embed, war)

        return embed

    async def war_summary_auto(self, clantag):
        channel_ids = self.bot.db.get_war_log_channels(clantag)
        embed = self.create_war_summary()

        for channel_id in channel_ids:
            channel = self.bot.get_channel(channel_id)
            if channel:
                await channel.send(embed=embed)

    @commands.command(name='warsum')
    async def war_summary_command(self, ctx):
        await ctx.send(embed=self.create_war_summary())

    @staticmethod
    def set_author(embed, war):
        if war.is_war_day():
            name = '{} {}'.format(war.clan_name, 'War Day')
        else:
            name = '{} {}'.format(war.clan_name, 'Collection Day')

        embed.set_author(name=name, url='http://royaleapi.com/clan/{}/'.format(war.clan_tag),
                         icon_url=war.clan_badge)

    @staticmethod
    def add_summary_line(embed, war):
        embed.add_field(name='Participants',
                        value='{} {}'.format(emojis['participant'], war.participant_count),
                        inline=True)
        embed.add_field(name='Wins',
                        value='{} {}'.format(emojis['warwin'], war.wins),
                        inline=True)
        embed.add_field(name='Battles played',
                        value='{} {}/{}'.format(emojis['battle'], war.battles_played, war.possible_battles),
                        inline=True)
        embed.add_field(name='Cards collected',
                        value='{} {}'.format(emojis['cards'], war.total_cards_earned),
                        inline=True)
        embed.add_field(name='Average cards per player',
                        value='{} {:.0f}'.format(emojis['cards'], war.total_cards_earned / war.participant_count),
                        inline=True)

    @staticmethod
    def add_perfect_days(embed, war):
        if war.is_war_day():
            return

        lines = []
        perfect_day_count = 0
        for participant in war.participants:
            if participant['wins'] == 3:
                perfect_day_count = perfect_day_count + 1
                line = '`{}{:2d}. {:<15} {:>4} {:>5}` {}'.format(WarLog.SPACE, perfect_day_count, participant['name'],
                                                                 participant['wins'], participant['cardsEarned'],
                                                                 emoji_util.get_good_emote())
                lines.append(line)

        if len(lines) > 0:
            lines.insert(0, '`{}{:>2}  {:<15} {:^4} {:^5}`'.format(WarLog.SPACE, '#', 'Name', 'Wins', 'Cards'))
            text = '\n'.join(lines)
        else:
            text = 'No perfect collection days! {}'.format(emoji_util.get_bad_emote())

        embed.add_field(name='MVPs - Perfect Collection Day', value=text, inline=False)

    @staticmethod
    def add_double_final_battle_wins(embed, war):
        if not war.is_war_day():
            return

        lines = []
        double_wins = 0
        for participant in war.participants:
            if participant['wins'] > 1:
                double_wins = double_wins + 1
                line = '`{}{:2d}. {:<15} {:>4}` {}'.format(WarLog.SPACE, double_wins, participant['name'],
                                                           participant['wins'], emoji_util.get_good_emote())
                lines.append(line)

        if len(lines) > 0:
            lines.insert(0, '`{}{:>2}  {:<15} {:^4}`'.format(WarLog.SPACE, '#', 'Name', 'Wins'))
            text = '\n'.join(lines)
            embed.add_field(name='MVPs - Double War Day Wins', value=text, inline=False)

    @staticmethod
    def add_wall_of_shame(embed, war):
        if war.is_war_day():
            expected_battles = 1
            name = 'Wall of Shame - Missed final battles:'
        else:
            expected_battles = 3
            name = 'Wall of Shame - Unplayed collection battles:'

        lines = []
        shame_count = 0
        for participant in war.participants:
            if participant['battlesPlayed'] < expected_battles:
                shame_count = shame_count + 1
                if war.is_war_day():
                    line = '`{}{:2d}. {:<15}`'.format(WarLog.SPACE, shame_count, participant['name'],
                                                      emoji_util.get_bad_emote())
                else:
                    count = '{} of {}'.format(participant['battlesPlayed'], expected_battles)
                    line = '`{}{:2d}. {:<15} {:^14}`'.format(WarLog.SPACE, shame_count, participant['name'], count)
                lines.append(line + ' {}'.format(emoji_util.get_bad_emote()))

        if len(lines) > 0:
            if war.is_war_day():
                lines.insert(0, '`{}{:>2}  {:<15}`'.format(WarLog.SPACE, '#', 'Name'))
            else:
                lines.insert(0, '`{}{:>2}  {:<15} {:^14}`'.format(WarLog.SPACE, '#', 'Name', 'Battles Played'))

            text = '\n'.join(lines)
        else:
            text = 'No missed battles!  :)'

        embed.add_field(name=name, value=text, inline=False)

    @staticmethod
    def add_standings(embed, war):
        if not war.is_war_day():
            return

        text = ''
        for rank, standing in enumerate(war.standings, 1):
            text += '`#{}` {}`{}{:2d}` {}`{}{:2d}` [{}](http://royaleapi.com/clan/{})\n'.format(rank,
                                                                                                emojis['warwin'],
                                                                                                WarLog.SPACE,
                                                                                                standing['wins'],
                                                                                                emojis['crownblue'],
                                                                                                WarLog.SPACE,
                                                                                                standing['crowns'],
                                                                                                standing['name'],
                                                                                                standing['tag'])

        embed.add_field(name='Standings', value=text, inline=False)

    @staticmethod
    def add_footer(embed, war):
        update_time = war.update_time
        end_time = war.end_time

        end_string = end_time.in_timezone('America/Denver').format('dddd, MMMM Do @ h:mm A zz')
        footer = '* Ended {} - last updated {} end time.'.format(end_string, update_time.diff_for_humans(end_time))

        embed.set_footer(text=footer)


@click.command()
@click.option('--bot-token', envvar='BOTTOKEN', default=None,
              help='Discord bot token. If not specified bot will not start.')
@click.option('--command-prefix', envvar='BOT_PREFIX', default='$', help='The bots command prefix.')
@click.option('--key', envvar='ROYALEAPIKEY', prompt='Enter the key for RoyaleAPI', help='RoyaleAPI authorization key.')
@click.option('--database', envvar='MONGODBURI', default='mongodb://localhost:27017/',
              help='MongoDB Database URI.  E.g. "mongodb://localhost:27017/"')
@click.option('--dbname', envvar='DBNAME', default='clashtracker', help='Name of database to connect with.')
@click.argument('clantag', envvar='CLANTAG', callback=validate_player_tag_input)
def cli(clantag, key, database, dbname, bot_token, command_prefix):
    Tracker.set_key(key)

    db = DB(database, dbname)
    db.connect()

    bot = commands.Bot(command_prefix=command_prefix)
    bot.add_cog(WarLog(bot))
    bot.db = db

    if bot_token:
        @bot.event
        async def on_ready():
            log.info('We have logged in as {0.user}'.format(bot))
            scheduler = Scheduler(clantag, db, bot)
            scheduler.start_scheduler()

        bot.run(bot_token)
    else:
        try:
            scheduler = Scheduler(clantag, db, bot)
            scheduler.start_scheduler()

            asyncio.get_event_loop().run_forever()
        except (KeyboardInterrupt, SystemExit):
            pass


if __name__ == '__main__':
    cli()
