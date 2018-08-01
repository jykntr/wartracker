import re


def get_legal_tag_chars():
    return "0289PpYyLlQqGgRrJjCcUuVv"


def normalize_tag(tag):
    """Replaces common typos in tags, removes '#', capitalizes letters.

    Letter o is changed to a zero.  Number one is changed to letter L.
    """

    # Substitutions should only use capitalized letters because tag will be converted to upper case before corrections
    subs = {"O": "0", "1": "L", "B": "8"}

    tag = tag.upper().lstrip("#")
    for key, value in subs.items():
        tag = tag.replace(key, value)

    return tag


def is_tag_valid(tag):
    """Tags can optionally start with a hash tag, must be at least 3 characters long and only contain the following
    set of characters: '0289PpYyLlQqGgRrJjCcUuVv'
    """
    match = re.match("^[" + get_legal_tag_chars() + "]{3,}$", tag.lstrip("#"))

    if match:
        return True

    return False
