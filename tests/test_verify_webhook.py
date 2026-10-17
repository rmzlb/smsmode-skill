"""How verify_webhook.py can let a forged callback in, or turn a real one away.

The vector below was computed apart from the script (Python hmac + hashlib)
over a fictional delivery report with a fictional secret.
"""

import os
import subprocess
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "smsmode" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from verify_webhook import verify  # noqa: E402

SECRET = "fictional-smsmode-secret"
BODY = (
    b'{"messageId":"67c15045-1067-4588-ba3c-737cc5051438","direction":"MT",'
    b'"recipient":{"to":"33600000000"},"from":"36034","status":{"value":"DELIVERED",'
    b'"deliveryDate":"2026-10-17T22:30:08"},"refClient":"7d9f0c2e-1b3a-4c5d-8e6f-0a1b2c3d4e5f"}'
)
SIGNATURE = "sha256=e635721b6f055fbb11e5a01f8f6eb488a12b42d263817be2c07e791e0affe036"


class Verify(unittest.TestCase):
    def test_the_independent_vector_is_accepted(self):
        self.assertTrue(verify(SECRET, BODY, SIGNATURE))

    def test_uppercase_hex_and_surrounding_spaces_are_accepted(self):
        upper = "sha256=" + SIGNATURE[len("sha256="):].upper()
        self.assertTrue(verify(SECRET, BODY, upper))
        self.assertTrue(verify(SECRET, BODY, f"  {SIGNATURE} "))

    def test_another_secret_is_refused(self):
        self.assertFalse(verify("another-secret", BODY, SIGNATURE))

    def test_a_modified_body_is_refused(self):
        tampered = BODY.replace(b"DELIVERED", b"UNDELIVERED")
        self.assertFalse(verify(SECRET, tampered, SIGNATURE))

    def test_a_reserialized_body_is_refused(self):
        # Parsing then re-dumping the JSON changes the bytes: verify the raw body.
        self.assertFalse(verify(SECRET, BODY.replace(b'","', b'", "'), SIGNATURE))

    def test_malformed_headers_are_refused(self):
        bare_hex = SIGNATURE[len("sha256="):]
        for header in (None, "", bare_hex, "sha256=", "sha256=not-hex", SIGNATURE[:-2], "sha1=" + bare_hex):
            self.assertFalse(verify(SECRET, BODY, header), header)

    def test_an_empty_secret_is_refused(self):
        with self.assertRaises(ValueError):
            verify("", BODY, SIGNATURE)


class Cli(unittest.TestCase):
    def run_cli(self, *args, env_secret=SECRET, body=BODY):
        env = {k: v for k, v in os.environ.items() if k != "SMSMODE_WEBHOOK_SECRET"}
        if env_secret is not None:
            env["SMSMODE_WEBHOOK_SECRET"] = env_secret
        return subprocess.run(
            [sys.executable, str(SCRIPTS / "verify_webhook.py"), *args],
            input=body,
            capture_output=True,
            env=env,
        )

    def test_valid_signature_exits_0(self):
        result = self.run_cli("--signature", SIGNATURE)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_invalid_signature_exits_1(self):
        result = self.run_cli("--signature", SIGNATURE[:-1] + "0")
        self.assertEqual(result.returncode, 1)

    def test_missing_secret_exits_2_and_names_the_variable(self):
        result = self.run_cli("--signature", SIGNATURE, env_secret=None)
        self.assertEqual(result.returncode, 2)
        self.assertIn(b"SMSMODE_WEBHOOK_SECRET", result.stderr)


if __name__ == "__main__":
    unittest.main()
