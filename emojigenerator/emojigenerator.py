import click
import discord


class EmojiClient(discord.Client):
    def __init__(self, output_file):
        super().__init__()
        self.output_file = output_file

    async def on_ready(self):
        print("We have logged in as {0.user}".format(self))
        print("")

        with open(self.output_file, "w", newline="\n") as f:
            start = "emojis = {\n"
            f.write(start)
            print(start)

            for guild in self.guilds:
                name_comment = "    # Emojis from server '{}'\n".format(guild.name)
                f.write(name_comment)
                print(name_comment)

                for emoji in guild.emojis:
                    key_value = '    "{1}": "<:{1}:{0}>",\n'.format(
                        emoji.id, emoji.name
                    )
                    f.write(key_value)
                    print(key_value)

            end = "}\n"
            f.write(end)
            print(end)

            print("Successfully wrote {}.".format(self.output_file))

        self.loop.stop()


@click.command()
@click.option(
    "--bot-token",
    envvar="BOT_TOKEN",
    prompt="Enter the discord bot token",
    help="Discord bot token.",
)
@click.argument(
    "output-file",
    type=click.Path(exists=False, file_okay=True, dir_okay=False, writable=True),
)
def cli(bot_token, output_file):
    client = EmojiClient(output_file)
    client.run(bot_token)


if __name__ == "__main__":
    cli()
