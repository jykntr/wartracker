import click

from wartracker.cli import validate_player_tag_input
from .refresher import OFFICIAL_API, ROYALE_API, Refresher


@click.command()
@click.option(
    "--api",
    envvar="API",
    type=click.Choice([OFFICIAL_API, ROYALE_API]),
    default="official",
    help="Which API to use for initial clan member data.",
)
@click.option("--key", envvar="APIKEY", help="Authorization key for chosen API.")
@click.argument("clantag", envvar="CLANTAG", callback=validate_player_tag_input)
def main(api, key, clantag):
    refresher = Refresher(clantag, key, api, 0)
    refresher.run()


if __name__ == "__main__":
    main()
