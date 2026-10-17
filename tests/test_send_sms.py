"""How send_sms.py can send the wrong thing, or misread what smsmode answered.

Sending costs money and reaches a real phone, so the request is built and
checked before any network call, and the answer is classified without guessing.
"""

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "smsmode" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from send_sms import build_request, interpret  # noqa: E402

TO = "33600000000"


class Recipient(unittest.TestCase):
    def test_international_formats_become_digits_only(self):
        for raw in ("+33600000000", "+33 6 00 00 00 00", "33-6-00-00-00-00", "0033600000000"):
            self.assertEqual(build_request(raw, "Bonjour")["recipient"]["to"], TO, raw)

    def test_a_national_number_is_refused(self):
        with self.assertRaisesRegex(ValueError, "international"):
            build_request("0600000000", "Bonjour")

    def test_garbage_is_refused(self):
        for raw in ("", "33abc", "3360", "3" * 16):
            with self.assertRaises(ValueError, msg=raw):
                build_request(raw, "Bonjour")


class Sender(unittest.TestCase):
    def test_no_sender_leaves_the_channel_default(self):
        self.assertNotIn("from", build_request(TO, "Bonjour"))

    def test_a_number_sender_loses_its_plus(self):
        self.assertEqual(build_request(TO, "Bonjour", sender="+33612345678")["from"], "33612345678")

    def test_senders_over_eleven_characters_are_refused(self):
        self.assertEqual(build_request(TO, "Bonjour", sender="ABCDEFGHIJK")["from"], "ABCDEFGHIJK")
        with self.assertRaisesRegex(ValueError, "11"):
            build_request(TO, "Bonjour", sender="ABCDEFGHIJKL")

    def test_an_empty_sender_is_refused(self):
        with self.assertRaises(ValueError):
            build_request(TO, "Bonjour", sender=" ")


class Body(unittest.TestCase):
    def test_gsm7_text_keeps_the_default_encoding(self):
        body = build_request(TO, "Votre code : 123456")["body"]
        self.assertEqual(body, {"text": "Votre code : 123456"})

    def test_non_gsm7_text_is_sent_as_unicode(self):
        body = build_request(TO, "C’est noté")["body"]
        self.assertEqual(body["encoding"], "UNICODE")

    def test_stop_is_only_added_on_request(self):
        self.assertNotIn("stop", build_request(TO, "Bonjour")["body"])
        self.assertIs(build_request(TO, "Bonjour", stop=True)["body"]["stop"], True)

    def test_text_beyond_ten_parts_is_refused(self):
        with self.assertRaisesRegex(ValueError, "10"):
            build_request(TO, "a" * 1531)

    def test_empty_text_is_refused(self):
        with self.assertRaises(ValueError):
            build_request(TO, "")


class Options(unittest.TestCase):
    def test_ref_client_length_is_checked(self):
        self.assertEqual(build_request(TO, "Bonjour", ref_client="abc")["refClient"], "abc")
        for bad in ("ab", "x" * 141):
            with self.assertRaises(ValueError):
                build_request(TO, "Bonjour", ref_client=bad)

    def test_callback_urls_are_checked(self):
        url = "https://example.com/smsmode/status"
        request = build_request(TO, "Bonjour", callback_url_status=url, callback_url_mo=url)
        self.assertEqual(request["callbackUrlStatus"], url)
        self.assertEqual(request["callbackUrlMo"], url)
        for bad in ("example.com/status", "https://example.com/" + "a" * 240):
            with self.assertRaises(ValueError):
                build_request(TO, "Bonjour", callback_url_status=bad)


class Interpret(unittest.TestCase):
    def test_accepted_message_exits_0_with_its_id(self):
        code, summary = interpret(201, {"messageId": "m-1", "status": {"value": "ENROUTE"}})
        self.assertEqual(code, 0)
        self.assertEqual(summary["messageId"], "m-1")
        self.assertEqual(summary["status"], "ENROUTE")

    def test_a_201_carrying_a_refusal_exits_1(self):
        payload = {"messageId": "m-2", "status": {"value": "UNDELIVERABLE", "detail": "INSUFFICIENT_CREDIT"}}
        code, summary = interpret(201, payload)
        self.assertEqual(code, 1)
        self.assertEqual(summary["detail"], "INSUFFICIENT_CREDIT")

    def test_validation_errors_exit_1_with_smsmode_s_message(self):
        payload = {"status": 400, "errorCode": "400.010", "message": "Request body: text invalid"}
        code, summary = interpret(400, payload)
        self.assertEqual(code, 1)
        self.assertEqual(summary["errorCode"], "400.010")
        self.assertIn("text invalid", summary["message"])

    def test_authentication_errors_exit_3(self):
        for status in (401, 403):
            self.assertEqual(interpret(status, {"errorCode": f"{status}.001"})[0], 3)

    def test_server_errors_and_unknown_answers_exit_4(self):
        self.assertEqual(interpret(500, None)[0], 4)
        self.assertEqual(interpret(201, None)[0], 4)


class Cli(unittest.TestCase):
    def run_cli(self, *args):
        env = {k: v for k, v in os.environ.items() if k != "SMSMODE_API_KEY"}
        return subprocess.run(
            [sys.executable, str(SCRIPTS / "send_sms.py"), *args],
            capture_output=True,
            text=True,
            env=env,
        )

    def test_dry_run_is_the_default_and_needs_no_key(self):
        result = self.run_cli("--to", "+33600000000", "--text", "C’est noté")
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertTrue(output["dry_run"])
        self.assertEqual(output["request"]["recipient"]["to"], TO)
        self.assertEqual(output["segments"]["encoding"], "UNICODE")

    def test_sending_without_a_key_exits_2(self):
        result = self.run_cli("--to", TO, "--text", "Bonjour", "--send")
        self.assertEqual(result.returncode, 2)
        self.assertIn("SMSMODE_API_KEY", result.stderr)

    def test_invalid_input_exits_2_before_any_call(self):
        result = self.run_cli("--to", "0600000000", "--text", "Bonjour", "--send")
        self.assertEqual(result.returncode, 2)
        self.assertIn("international", result.stderr)


if __name__ == "__main__":
    unittest.main()
