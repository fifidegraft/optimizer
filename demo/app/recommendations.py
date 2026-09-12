from .users import get_user


def generate_feed(user_ids):
    """Intentional bottleneck: looks up each user one at a time instead of batching."""
    feed = []
    for user_id in user_ids:
        user = get_user(user_id)
        if user:
            feed.append(user)
    return feed
