#!/usr/bin/env python3

import asyncio
import logging
import os

import click
import discord
import pendulum
from discord.ext import commands

from wartracker import tags
from wartracker.db import DB
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


class WarLog:
    """War log commands"""

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setwarlog(self, ctx, *, channel: discord.TextChannel):
        log.debug('Setting war log to: {}, {}.'.format(channel.name, channel.id))
        self.bot.db.set_war_log_channel('GJ98VC', channel.id)

    @setwarlog.error
    async def setwarlog_error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            await ctx.send(error)
        else:
            log.debug('Error setting')

    async def send_war_battle(self, battle):
        log.debug('{}?type=war'.format(battle['team'][0]['deckLink']))

        channel = self.bot.get_channel(330528722211962880)
        if channel:
            await channel.send('{}'.format(battle['team'][0]['deckLink']))

    def create_war_summary(self):
        war = self.bot.db.get_latest_war()

        embed = discord.Embed(color=0x8000ff)
        WarLog.set_author(embed, war)
        WarLog.add_summary_line(embed, war)
        WarLog.add_double_final_battle_wins(embed, war)
        WarLog.add_perfect_days(embed, war)
        WarLog.add_wall_of_shame(embed, war)
        WarLog.add_footer(embed, war)

        return embed

    async def war_summary_auto(self, clantag):
        channel_id = self.bot.db.get_war_log_channel(clantag)
        channel = self.bot.get_channel(channel_id)
        if channel:
            await channel.send(embed=self.create_war_summary())

    @commands.command(name='warsum')
    async def war_summary_command(self, ctx):
        await ctx.send(embed=self.create_war_summary())

    @staticmethod
    def set_author(embed, war):
        if WarLog.is_war_day(war):
            name = '{} {}'.format(war['clan']['name'], 'War Day')
        else:
            name = '{} {}'.format(war['clan']['name'], 'Collection Day')

        embed.set_author(name=name, url='http://royaleapi.com/clan/{}/'.format(war['clan']['tag']),
                         icon_url=war['clan']['badge']['image'])

    @staticmethod
    def add_summary_line(embed, war):
        participants = war['clan']['participants']
        wins = war['clan']['wins']
        battles = war['clan']['battlesPlayed']
        if WarLog.is_war_day(war):
            possible_battles = max(participants, battles)
        else:
            possible_battles = participants * 3

        line = '{} participants - {} wins, {} of {} battles played'.format(participants, wins, battles,
                                                                           possible_battles)

        embed.add_field(name='Summary', value=line, inline=False)

    @staticmethod
    def add_perfect_days(embed, war):
        if WarLog.is_war_day(war):
            return

        lines = []
        perfect_day_count = 0
        for participant in war['participants']:
            if participant['wins'] == 3:
                perfect_day_count = perfect_day_count + 1
                line = '`{:02d}. {:<15} {:>4} {:>5}`'.format(perfect_day_count, participant['name'],
                                                             participant['wins'],
                                                             participant['cardsEarned'])
                lines.append(line)

        if len(lines) > 0:
            lines.insert(0, '`{:<2}  {:^15} {:^4} {:^5}`'.format('##', 'Name', 'Wins', 'Cards'))
            text = '\n'.join(lines)
        else:
            text = 'No perfect collection days!  :('

        embed.add_field(name='MVPs - Perfect Collection Day', value=text, inline=False)

    @staticmethod
    def add_double_final_battle_wins(embed, war):
        if not WarLog.is_war_day(war):
            return

        lines = []
        double_wins = 0
        for participant in war['participants']:
            if participant['wins'] > 1:
                double_wins = double_wins + 1
                line = '`{:02d}. {:<15} {:>4}`'.format(double_wins, participant['name'], participant['wins'])
                lines.append(line)

        if len(lines) > 0:
            lines.insert(0, '`{:<2}  {:^15} {:^4}`'.format('##', 'Name', 'Wins'))
            text = '\n'.join(lines)
            embed.add_field(name='MVPs - Double War Day Wins', value=text, inline=False)

    @staticmethod
    def add_wall_of_shame(embed, war):
        if WarLog.is_war_day(war):
            expected_battles = 1
            name = 'Wall of Shame - Missed final battles:'
        else:
            expected_battles = 3
            name = 'Wall of Shame - Unplayed collection battles:'

        lines = []
        shame_count = 0
        for participant in war['participants']:
            if participant['battlesPlayed'] < expected_battles:
                shame_count = shame_count + 1
                if WarLog.is_war_day(war):
                    line = '`{:02d}. {:<15}`'.format(shame_count, participant['name'])
                else:
                    count = '{} of {}'.format(participant['battlesPlayed'], expected_battles)
                    line = '`{:02d}. {:<15} {:^14}`'.format(shame_count, participant['name'], count)
                lines.append(line)

        if len(lines) > 0:
            if WarLog.is_war_day(war):
                lines.insert(0, '`{:<2}  {:^15}`'.format('##', 'Name'))
            else:
                lines.insert(0, '`{:<2}  {:^15} {:^14}`'.format('##', 'Name', 'Battles Played'))

            text = '\n'.join(lines)
        else:
            text = 'No missed battles!  :)'

        embed.add_field(name=name, value=text, inline=False)

    @staticmethod
    def add_footer(embed, war):
        update_time = pendulum.from_timestamp(war['_update_utc_timestamp'])

        if WarLog.is_war_day(war):
            end_time = pendulum.from_timestamp(war['warEndTime'])
        else:
            end_time = pendulum.from_timestamp(war['collectionEndTime'])

        end_string = end_time.in_timezone('America/Denver').format('dddd, MMMM Do @ h:mm A zz')
        footer = '* Ended {} - last updated {} end time.'.format(end_string, update_time.diff_for_humans(end_time))

        embed.set_footer(text=footer)

    @staticmethod
    def is_war_day(war):
        return 'warEndTime' in war


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
