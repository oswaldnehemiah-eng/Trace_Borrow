"""Create a small chain-of-custody demo dataset for TraceBorrow."""

import database
import queries
from auth import hash_password


def seed():
    database.init_db()

    if queries.get_user_by_username("human1"):
        print("Demo data already exists.")
        return

    users = {}
    for username in ("human1", "human2", "human3"):
        users[username] = queries.create_user(username, hash_password("password123"))

    # Human3's item moves through Human2 to Human1.
    queries.create_transfer(users["human3"], users["human2"], "Pentonic pen blue")
    queries.create_transfer(users["human2"], users["human1"], "Pentonic pen blue")

    # Human3's HDMI cable moves through Human2 to Human1 as well.
    queries.create_transfer(users["human3"], users["human2"], "HDMI cable")
    queries.create_transfer(users["human2"], users["human1"], "HDMI cable")

    print("Demo data created.")
    print("Demo password for all users: password123")


if __name__ == "__main__":
    seed()
