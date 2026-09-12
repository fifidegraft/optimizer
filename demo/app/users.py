from .database import find_user


def get_user(user_id):
    return find_user(user_id)
