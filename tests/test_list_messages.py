"""How list_messages.py can miss messages that smsmode did receive.

The list endpoint filters on one encoding at a time (GSM7 by default) and
answers 400 when the bracketed filter names are not percent-encoded.
"""

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "smsmode" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from list_messages import build_query, merge  # noqa: E402


class Query(unittest.TestCase):
    def test_filter_names_are_percent_encoded(self):
        query = build_query(direction="MO", encoding="UNICODE", page=1, page_size=100)
        self.assertNotIn("[", query)
        self.assertIn("searchBy%5Bdirection%5D=MO", query)
        self.assertIn("searchBy%5Bencoding%5D=UNICODE", query)
        self.assertIn("pageSize=100", query)

    def test_optional_filters_are_added_only_when_given(self):
        query = build_query(direction="MT", encoding="GSM7", page=2, page_size=10, ref_client="job-123", to="+33600000000")
        self.assertIn("searchBy%5BrefClient%5D=job-123", query)
        self.assertIn("searchBy%5Bto%5D=33600000000", query)
        self.assertIn("page=2", query)
        self.assertNotIn("originMessageId", query)

    def test_origin_message_id_requires_incoming_messages(self):
        query = build_query(direction="MO", encoding="GSM7", page=1, page_size=10, origin_message_id="m-1")
        self.assertIn("searchBy%5BoriginMessageId%5D=m-1", query)
        with self.assertRaisesRegex(ValueError, "MO"):
            build_query(direction="MT", encoding="GSM7", page=1, page_size=10, origin_message_id="m-1")

    def test_out_of_range_values_are_refused(self):
        for kwargs in ({"page_size": 0}, {"page_size": 101}, {"page": 0}, {"direction": "IN"}, {"encoding": "UTF8"}):
            args = {"direction": "MO", "encoding": "GSM7", "page": 1, "page_size": 10, **kwargs}
            with self.assertRaises(ValueError, msg=kwargs):
                build_query(**args)


class Merge(unittest.TestCase):
    def test_both_encodings_come_back_newest_first_without_duplicates(self):
        gsm = [{"messageId": "a", "sentDate": "2026-10-17T10:45:00"}, {"messageId": "b", "sentDate": "2026-10-17T10:35:00"}]
        unicode = [{"messageId": "c", "sentDate": "2026-10-17T10:40:00"}, {"messageId": "a", "sentDate": "2026-10-17T10:45:00"}]
        self.assertEqual([m["messageId"] for m in merge([gsm, unicode])], ["a", "c", "b"])


if __name__ == "__main__":
    unittest.main()
