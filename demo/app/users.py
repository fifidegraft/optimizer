from .database import find_user


def get_user(user_id):
    return find_user(user_id)


def get_users(user_ids):
    found = []
    for user_id in user_ids:
        user = get_user(user_id)
        if user is not None:
            found.append(user)
    return found


def display_name(user):
    return f"{user['name']} ({user['tier']})"
