import os
import tempfile
import unittest

os.environ["TRACEBORROW_TEST"] = "1"

import database
import queries
from auth import hash_password, verify_password


class TraceBorrowTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        database.DATABASE_DIR = self.temp_dir.name
        database.DATABASE_PATH = os.path.join(self.temp_dir.name, "traceborrow.db")
        database.init_db()

    def tearDown(self):
        self.temp_dir.cleanup()

    def user(self, username):
        return queries.create_user(username, hash_password("password123"))

    def test_direct_lending_counters(self):
        human2 = self.user("human2")
        human1 = self.user("human1")
        ok, _ = queries.create_transfer(human2, human1, "Pentonic pen blue")
        self.assertTrue(ok)
        self.assertEqual(queries.get_dashboard_counts(human2), {"with_me": 0, "with_others": 1})
        self.assertEqual(queries.get_dashboard_counts(human1), {"with_me": 1, "with_others": 0})

    def test_owner_getting_own_item_back_does_not_count_as_borrowed(self):
        human3 = self.user("human3")
        human2 = self.user("human2")
        human1 = self.user("human1")
        queries.create_transfer(human3, human2, "Pentonic pen blue")
        queries.create_transfer(human2, human1, "Pentonic pen blue")
        queries.create_transfer(human1, human3, "Pentonic pen blue")
        self.assertEqual(queries.get_dashboard_counts(human3), {"with_me": 0, "with_others": 0})
        self.assertEqual(queries.get_dashboard_counts(human1), {"with_me": 1, "with_others": 0})

    def test_owner_sees_entire_custody_chain(self):
        human3 = self.user("human3")
        human2 = self.user("human2")
        human1 = self.user("human1")
        queries.create_transfer(human3, human2, "HDMI cable")
        queries.create_transfer(human2, human1, "HDMI cable")
        history = queries.get_user_lending_history(human3)
        self.assertEqual(len(history), 2)
        self.assertEqual((history[0]["from_username"], history[0]["to_username"]), ("human2", "human1"))
        self.assertEqual((history[1]["from_username"], history[1]["to_username"]), ("human3", "human2"))
        self.assertEqual(queries.get_dashboard_counts(human3), {"with_me": 0, "with_others": 1})
        self.assertEqual(queries.get_dashboard_counts(human2), {"with_me": 0, "with_others": 0})
        self.assertEqual(queries.get_dashboard_counts(human1), {"with_me": 1, "with_others": 0})

    def test_borrowing_history(self):
        human3 = self.user("human3")
        human2 = self.user("human2")
        human1 = self.user("human1")
        queries.create_transfer(human3, human2, "HDMI cable")
        queries.create_transfer(human2, human1, "HDMI cable")
        history = queries.get_user_borrowing_history(human1)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["lender_username"], "human2")

    def test_intermediary_does_not_count_someone_elses_item_as_lent_out(self):
        human3 = self.user("human3")
        human2 = self.user("human2")
        human1 = self.user("human1")
        queries.create_transfer(human3, human2, "HDMI cable")
        queries.create_transfer(human2, human1, "HDMI cable")
        self.assertEqual(queries.get_dashboard_counts(human2), {"with_me": 0, "with_others": 0})
        self.assertEqual(queries.get_dashboard_counts(human1), {"with_me": 1, "with_others": 0})

    def test_return_to_previous_holder_clears_counters(self):
        human3 = self.user("human3")
        human2 = self.user("human2")
        human1 = self.user("human1")
        queries.create_transfer(human3, human2, "HDMI cable")
        queries.create_transfer(human2, human1, "HDMI cable")
        queries.create_transfer(human1, human2, "HDMI cable")
        self.assertEqual(queries.get_dashboard_counts(human1), {"with_me": 0, "with_others": 0})
        self.assertEqual(queries.get_dashboard_counts(human2), {"with_me": 1, "with_others": 0})
        self.assertEqual(queries.get_dashboard_counts(human3), {"with_me": 0, "with_others": 1})

    def test_return_all_the_way_to_origin(self):
        human3 = self.user("human3")
        human2 = self.user("human2")
        human1 = self.user("human1")
        queries.create_transfer(human3, human2, "HDMI cable")
        queries.create_transfer(human2, human1, "HDMI cable")
        queries.create_transfer(human1, human2, "HDMI cable")
        queries.create_transfer(human2, human3, "HDMI cable")
        self.assertEqual(queries.get_dashboard_counts(human1), {"with_me": 0, "with_others": 0})
        self.assertEqual(queries.get_dashboard_counts(human2), {"with_me": 0, "with_others": 0})
        self.assertEqual(queries.get_dashboard_counts(human3), {"with_me": 1, "with_others": 0})

    def test_current_holder_must_transfer_item(self):
        human2 = self.user("human2")
        human1 = self.user("human1")
        human3 = self.user("human3")
        queries.create_transfer(human2, human1, "Pentonic pen blue")
        ok, message = queries.create_transfer(human3, human2, "Pentonic pen blue")
        self.assertFalse(ok)
        self.assertIn("currently with human1", message)

    def test_return_request_targets_current_holder(self):
        human3 = self.user("human3")
        human2 = self.user("human2")
        human1 = self.user("human1")
        queries.create_transfer(human3, human2, "HDMI cable")
        queries.create_transfer(human2, human1, "HDMI cable")
        ok, message = queries.create_return_request(human3, "HDMI cable")
        self.assertTrue(ok)
        self.assertIn("current holder", message)
        requests = queries.get_pending_return_requests(human1)
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0]["requester_username"], "human3")

    def test_request_fulfills_when_item_reaches_requester(self):
        human3 = self.user("human3")
        human2 = self.user("human2")
        human1 = self.user("human1")
        queries.create_transfer(human3, human2, "HDMI cable")
        queries.create_transfer(human2, human1, "HDMI cable")
        queries.create_return_request(human3, "HDMI cable")
        self.assertEqual(len(queries.get_pending_return_requests(human1)), 1)
        queries.create_transfer(human1, human3, "HDMI cable")
        self.assertEqual(len(queries.get_pending_return_requests(human1)), 0)
        self.assertEqual(queries.get_dashboard_counts(human3), {"with_me": 1, "with_others": 0})

    def test_request_cannot_be_created_by_unrelated_user(self):
        human3 = self.user("human3")
        human2 = self.user("human2")
        stranger = self.user("stranger")
        queries.create_transfer(human3, human2, "HDMI cable")
        ok, message = queries.create_return_request(stranger, "HDMI cable")
        self.assertFalse(ok)
        self.assertIn("not part", message)

    def test_password_hashing(self):
        hashed = hash_password("password123")
        self.assertTrue(verify_password("password123", hashed))
        self.assertFalse(verify_password("wrong", hashed))


if __name__ == "__main__":
    unittest.main()
