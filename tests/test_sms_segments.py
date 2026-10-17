"""How sms_segments.py can get a message wrong, and what it must answer.

A wrong answer either corrupts the text (GSM-7 chosen for a character smsmode
would replace) or misprices it (wrong segment count: billing is per segment).
"""

import json
import subprocess
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "smsmode" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from sms_segments import analyse  # noqa: E402


class Encoding(unittest.TestCase):
    def test_french_letters_inside_gsm7_keep_gsm7(self):
        result = analyse("Votre rendez-vous est confirmé à 10 h.")
        self.assertEqual(result["encoding"], "GSM7")
        self.assertEqual(result["non_gsm"], [])

    def test_typographic_apostrophe_needs_unicode(self):
        result = analyse("C’est noté")
        self.assertEqual(result["encoding"], "UNICODE")
        self.assertEqual(result["non_gsm"], ["’"])

    def test_letters_missing_from_gsm7_need_unicode(self):
        for text in ("ça marche", "fenêtre", "œuvre", "« oui »", "À demain", "bientôt"):
            self.assertEqual(analyse(text)["encoding"], "UNICODE", text)

    def test_capital_c_cedilla_is_gsm7(self):
        self.assertEqual(analyse("Ça marche")["encoding"], "GSM7")

    def test_tab_is_not_gsm7_but_newlines_are(self):
        self.assertEqual(analyse("a\nb\r\nc")["encoding"], "GSM7")
        self.assertEqual(analyse("a\tb")["encoding"], "UNICODE")

    def test_non_gsm_lists_each_character_once_in_order(self):
        self.assertEqual(analyse("’a’ê👍")["non_gsm"], ["’", "ê", "👍"])


class GsmSegments(unittest.TestCase):
    def test_single_segment_holds_160(self):
        self.assertEqual(analyse("a" * 160)["segments"], 1)

    def test_concatenated_parts_hold_153(self):
        self.assertEqual(analyse("a" * 161)["segments"], 2)
        self.assertEqual(analyse("a" * 306)["segments"], 2)
        self.assertEqual(analyse("a" * 307)["segments"], 3)

    def test_extension_characters_count_twice(self):
        self.assertEqual(analyse("€" * 80)["units"], 160)
        self.assertEqual(analyse("€" * 80)["segments"], 1)
        self.assertEqual(analyse("€" * 81)["segments"], 2)

    def test_an_escape_pair_never_straddles_two_parts(self):
        # 306 septets: naive ceil(306 / 153) says 2, but the euro sign cannot
        # be cut, so the first part closes at 152 and a third part is needed.
        self.assertEqual(analyse("a" * 152 + "€" + "a" * 152)["segments"], 3)


class UnicodeSegments(unittest.TestCase):
    def test_single_segment_holds_70(self):
        self.assertEqual(analyse("’" * 70)["segments"], 1)
        self.assertEqual(analyse("’" * 71)["segments"], 2)

    def test_ninety_characters_take_two_parts(self):
        # Observed on smsmode: a 90-character UNICODE message billed 2 parts.
        self.assertEqual(analyse("’" + "a" * 89)["segments"], 2)

    def test_concatenated_parts_hold_67(self):
        self.assertEqual(analyse("’" * 134)["segments"], 2)
        self.assertEqual(analyse("’" * 135)["segments"], 3)

    def test_emoji_take_two_utf16_units(self):
        self.assertEqual(analyse("👍🏽")["units"], 4)

    def test_a_surrogate_pair_never_straddles_two_parts(self):
        self.assertEqual(analyse("’" * 66 + "👍" + "’" * 66)["segments"], 3)


class Limits(unittest.TestCase):
    def test_empty_text_is_refused(self):
        with self.assertRaises(ValueError):
            analyse("")

    def test_more_than_ten_parts_is_flagged(self):
        self.assertTrue(analyse("a" * 1530)["fits"])
        self.assertFalse(analyse("a" * 1531)["fits"])
        self.assertTrue(analyse("’" * 670)["fits"])
        self.assertFalse(analyse("’" * 671)["fits"])


class Cli(unittest.TestCase):
    def run_cli(self, *args, stdin=""):
        return subprocess.run(
            [sys.executable, str(SCRIPTS / "sms_segments.py"), *args],
            input=stdin,
            capture_output=True,
            text=True,
        )

    def test_argument_and_stdin_give_the_same_json(self):
        by_arg = self.run_cli("C’est noté")
        by_stdin = self.run_cli(stdin="C’est noté")
        self.assertEqual(by_arg.returncode, 0, by_arg.stderr)
        self.assertEqual(json.loads(by_arg.stdout), json.loads(by_stdin.stdout))
        self.assertEqual(json.loads(by_arg.stdout)["encoding"], "UNICODE")

    def test_empty_input_exits_2_with_a_message(self):
        result = self.run_cli(stdin="")
        self.assertEqual(result.returncode, 2)
        self.assertIn("empty", result.stderr)


if __name__ == "__main__":
    unittest.main()
