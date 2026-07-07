DIRECT_ROOM_PREFIX = "direct"
GROUP_ROOM_PREFIX = "group"
CHANNEL_ROOM_PREFIX = "channel"
USER_ROOM_PREFIX = "user"


def direct_room_name(user_a_id, user_b_id):
    first, second = sorted([user_a_id, user_b_id])
    return f"{DIRECT_ROOM_PREFIX}_{first}_{second}"


def group_room_name(group_id):
    return f"{GROUP_ROOM_PREFIX}_{group_id}"


def channel_room_name(channel_id, topic_id=None):
    if topic_id:
        return f"{CHANNEL_ROOM_PREFIX}_{channel_id}_topic_{topic_id}"
    return f"{CHANNEL_ROOM_PREFIX}_{channel_id}"


def user_room_name(user_id):
    return f"{USER_ROOM_PREFIX}_{user_id}"
