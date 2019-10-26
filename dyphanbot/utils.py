import re

"""
DyphanBot Utility Functions
Contains functions useful for DyphanBot. Could also be used by plugins.
"""

def get_user_avatar_url(user):
    """
    Returns a URL to the user's avatar, if they have one, or the default avatar if they don't.
    """
    return user.avatar_url or user.default_avatar_url

def truncate(text, limit, ellipsis='...'):
    """Generic function that truncates long text by a specified limit"""
    return text[:limit] + (text[limit:] and ellipsis)

def parse_command(dyphanbot, message, prefix=None, force_prefix=False):
    """ Parse a command message into the command name and arguments """
    cmd = message.content.replace(dyphanbot.bot_mention(message), "").strip()
    if prefix:
        if force_prefix and not cmd.startswith(prefix):
            return None
        cmd = cmd[cmd.startswith(prefix) and len(prefix):].strip()
    args = cmd.split()[1:]
    return (cmd.split(), args)

def parse_reigon(text, start, end, strip=True):
    matches = re.findall("{0}(.*?){1}".format(start, end), text, flags=re.DOTALL)
    if strip:
        return [x.strip() for x in matches]
    return matches

def parse_codeblock(text, lang=""):
    lang = "{0}\n".format(lang) if lang else ""
    return parse_reigon(text, "```{}".format(lang), "```")