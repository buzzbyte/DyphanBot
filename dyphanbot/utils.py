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
