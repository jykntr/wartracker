import sys

import click
import discord

client = discord.Client()


@client.event
async def on_ready():
    with open(client._file_name, 'w', newline='\n') as f:
        print('We have logged in as {0.user}'.format(client))
        print('')
        f.write('emojis = {\n')
        for guild in client.guilds:
            f.write("    # Emojis from server '{}'\n".format(guild.name))
            for emoji in guild.emojis:
                f.write("    '{1}': '<:{1}:{0}>',\n".format(emoji.id, emoji.name))

        f.write('}\n')

    sys.exit(0)


@click.command()
@click.option('--bot-token', envvar='BOTTOKEN', prompt='Enter the discord bot token', help='Discord bot token.')
@click.argument('output-file', type=click.Path(exists=False, file_okay=True, dir_okay=False, writable=True))
def cli(bot_token, output_file):
    client._file_name = output_file
    client.run(bot_token)


if __name__ == '__main__':
    cli()
