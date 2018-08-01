import random

from .emoji import emojis

good_emotes = [
    emojis["kingdollar"],
    emojis["kingdab"],
    emojis["kingthumbs"],
    emojis["princess_kiss"],
    emojis["princess_thumbsup"],
    emojis["goblin_thumbsup"],
    emojis["goblin_excited"],
    emojis["goblin_muscle"],
    emojis["goblin_smile"],
    emojis["goblin_cool"],
    emojis["giant_thumbs"],
]

bad_emotes = [
    emojis["kingconfused"],
    emojis["kingmad"],
    emojis["kingsad"],
    emojis["princess_angry"],
    emojis["goblin_tongue"],
    emojis["goblin_ohmy"],
    emojis["goblin_ohno"],
    emojis["giant_crush"],
    emojis["giant_fist"],
]


def get_bad_emote():
    return random.choice(bad_emotes)


def get_good_emote():
    return random.choice(good_emotes)


def get_clan_badge(clan_json):
    return emojis[clan_json["badge"]["name"]]
