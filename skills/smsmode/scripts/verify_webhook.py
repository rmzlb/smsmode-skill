#!/usr/bin/env python3
"""Check the X-Smsmode-256 signature of a webhook body smsmode posted.

Usage:
  python3 scripts/verify_webhook.py --signature "sha256=<hex>" < body.json
  python3 scripts/verify_webhook.py --signature "sha256=<hex>" --body-file body.json

The secret is read from the environment variable SMSMODE_WEBHOOK_SECRET (or
the one named by --secret-env), never from the command line. Pass the raw
bytes smsmode sent: a body parsed and dumped again no longer matches.

Exit codes: 0 valid, 1 invalid, 2 usage error (missing secret or body).

In application code, copy verify() below: HMAC-SHA256 of the raw body under
the secret set in smsmode (Settings > Webhooks), hex-encoded, prefixed with
"sha256=", compared in constant time.
"""

import argparse
import hashlib
import hmac
import os
import sys

PREFIX = "sha256="


def verify(secret, body, header):
    """True when `header` is smsmode's signature of the raw `body` bytes."""
    if not secret:
        raise ValueError("empty webhook secret")
    if not header:
        return False
    value = header.strip()
    if not value.startswith(PREFIX):
        return False
    try:
        received = bytes.fromhex(value[len(PREFIX):])
    except ValueError:
        return False
    key = secret.encode() if isinstance(secret, str) else secret
    expected = hmac.new(key, body, hashlib.sha256).digest()
    return hmac.compare_digest(expected, received)


def main(argv):
    parser = argparse.ArgumentParser(description="Check an smsmode X-Smsmode-256 webhook signature.")
    parser.add_argument("--signature", required=True, help='value of the X-Smsmode-256 header, "sha256=<hex>"')
    parser.add_argument("--body-file", help="file holding the raw body (default: stdin)")
    parser.add_argument("--secret-env", default="SMSMODE_WEBHOOK_SECRET", help="variable holding the secret")
    args = parser.parse_args(argv)

    secret = os.environ.get(args.secret_env, "")
    if not secret:
        print(f"error: set {args.secret_env} to the webhook secret configured in smsmode", file=sys.stderr)
        return 2
    if args.body_file:
        with open(args.body_file, "rb") as handle:
            body = handle.read()
    else:
        body = sys.stdin.buffer.read()
    if not body:
        print("error: empty body; pipe the raw webhook body or use --body-file", file=sys.stderr)
        return 2

    if verify(secret, body, args.signature):
        print("valid")
        return 0
    print("invalid: the body was not signed with this secret, or was modified", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
