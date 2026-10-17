#!/usr/bin/env python3
"""Build, check and (only with --send) send one SMS through the smsmode REST API.

Usage:
  python3 scripts/send_sms.py --to +33600000000 --text "Votre code : 123456"
  python3 scripts/send_sms.py --to +33600000000 --text "C’est noté" --ref-client order-42 --send

Without --send nothing leaves the machine: the script prints the request it
would post and the segment count, so the text, encoding and cost can be
checked first. With --send it reads the API key from SMSMODE_API_KEY.

Options:
  --to                 recipient, international format (+33…, 0033… or 33…)
  --text               message text; UNICODE is chosen when GSM7 cannot hold it
  --from               sender: alphanumeric, short code or virtual number, max 11
  --ref-client         your own reference (3-140 characters), echoed on reports and replies
  --callback-url-status  URL for this message's delivery reports (max 255)
  --callback-url-mo    URL for replies to this message (max 255)
  --stop               append the STOP opt-out mention (marketing channels)
  --send               actually send (costs one SMS per segment)

Prints one JSON object. Exit codes:
  0 accepted (dry run, or smsmode took the message)
  1 refused by smsmode (validation, credit, limits, blacklist…)
  2 invalid input or missing SMSMODE_API_KEY (nothing was sent)
  3 authentication refused (key, channel or IP allowlist)
  4 network error or unexpected answer (the message may or may not exist:
    look it up by --ref-client before retrying)
"""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request

from sms_segments import analyse

MESSAGES_URL = "https://rest.smsmode.com/sms/v1/messages"
# The API answers in well under a second; 30 s leaves room for a slow network
# without hanging an agent indefinitely.
TIMEOUT_SECONDS = 30
# E.164: at most 15 digits; the shortest assigned numbers have 7.
PHONE_MIN_DIGITS, PHONE_MAX_DIGITS = 7, 15
SENDER_MAX = 11
REF_CLIENT_MIN, REF_CLIENT_MAX = 3, 140
CALLBACK_URL_MAX = 255
REFUSED_STATUSES = {"UNDELIVERABLE", "UNDELIVERED"}


def normalize_phone(raw):
    digits = re.sub(r"[\s.\-()]", "", raw or "")
    if digits.startswith("+"):
        digits = digits[1:]
    elif digits.startswith("00"):
        digits = digits[2:]
    elif digits.startswith("0"):
        raise ValueError(f"{raw!r} looks national: use the international format, e.g. +33 6… for France")
    if not digits.isdigit() or not PHONE_MIN_DIGITS <= len(digits) <= PHONE_MAX_DIGITS:
        raise ValueError(f"{raw!r} is not a phone number in international format (7 to 15 digits)")
    return digits


def normalize_sender(raw):
    sender = raw.strip()
    if not sender:
        raise ValueError("empty sender: omit --from to use the channel's default sender")
    if sender.startswith("+") and sender[1:].isdigit():
        sender = sender[1:]
    if len(sender) > SENDER_MAX:
        raise ValueError(f"sender {sender!r} is longer than {SENDER_MAX} characters")
    return sender


def check_url(name, url):
    if not url.startswith(("https://", "http://")):
        raise ValueError(f"{name} must be an absolute http(s) URL")
    if len(url) > CALLBACK_URL_MAX:
        raise ValueError(f"{name} is {len(url)} characters long; smsmode accepts at most {CALLBACK_URL_MAX}")
    return url


def build_request(to, text, sender=None, ref_client=None, callback_url_status=None, callback_url_mo=None, stop=False):
    """The JSON body to POST, or ValueError naming what smsmode would refuse."""
    segments = analyse(text)
    if not segments["fits"]:
        raise ValueError(f"text needs {segments['segments']} parts; smsmode accepts at most 10")
    body = {"text": text}
    if segments["encoding"] == "UNICODE":
        body["encoding"] = "UNICODE"
    if stop:
        body["stop"] = True
    request = {"recipient": {"to": normalize_phone(to)}, "body": body}
    if sender is not None:
        request["from"] = normalize_sender(sender)
    if ref_client is not None:
        if not REF_CLIENT_MIN <= len(ref_client) <= REF_CLIENT_MAX:
            raise ValueError(f"ref-client must be {REF_CLIENT_MIN} to {REF_CLIENT_MAX} characters")
        request["refClient"] = ref_client
    if callback_url_status is not None:
        request["callbackUrlStatus"] = check_url("callback-url-status", callback_url_status)
    if callback_url_mo is not None:
        request["callbackUrlMo"] = check_url("callback-url-mo", callback_url_mo)
    return request


def interpret(http_status, payload):
    """(exit code, summary) for smsmode's answer to a send."""
    summary = {"http_status": http_status}
    if http_status in (401, 403):
        summary.update(_error_fields(payload))
        return 3, summary
    if not isinstance(payload, dict):
        summary["message"] = "unexpected answer: not a JSON object"
        return 4, summary
    if http_status in (200, 201):
        status = payload.get("status") or {}
        summary.update(
            messageId=payload.get("messageId"),
            status=status.get("value"),
            detail=status.get("detail"),
            price=payload.get("price"),
            messagePartCount=(payload.get("body") or {}).get("messagePartCount"),
        )
        if not summary["messageId"]:
            summary["message"] = "unexpected answer: no messageId"
            return 4, summary
        return (1 if summary["status"] in REFUSED_STATUSES else 0), summary
    summary.update(_error_fields(payload))
    return (1 if 400 <= http_status < 500 else 4), summary


def _error_fields(payload):
    if not isinstance(payload, dict):
        return {}
    return {k: payload[k] for k in ("errorCode", "title", "message", "detail") if k in payload}


def post(api_key, request):
    data = json.dumps(request).encode()
    http_request = urllib.request.Request(
        MESSAGES_URL,
        data=data,
        method="POST",
        headers={
            "X-Api-Key": api_key,
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "smsmode-agent-skill/1.0",
        },
    )
    try:
        with urllib.request.urlopen(http_request, timeout=TIMEOUT_SECONDS) as response:
            return response.status, _json(response.read())
    except urllib.error.HTTPError as error:
        return error.code, _json(error.read())


def _json(raw):
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return None


def main(argv):
    parser = argparse.ArgumentParser(description="Send one SMS through smsmode (dry run unless --send).")
    parser.add_argument("--to", required=True)
    parser.add_argument("--text", required=True)
    parser.add_argument("--from", dest="sender")
    parser.add_argument("--ref-client")
    parser.add_argument("--callback-url-status")
    parser.add_argument("--callback-url-mo")
    parser.add_argument("--stop", action="store_true")
    parser.add_argument("--send", action="store_true")
    args = parser.parse_args(argv)

    try:
        request = build_request(
            args.to,
            args.text,
            sender=args.sender,
            ref_client=args.ref_client,
            callback_url_status=args.callback_url_status,
            callback_url_mo=args.callback_url_mo,
            stop=args.stop,
        )
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    segments = analyse(args.text)

    if not args.send:
        print(json.dumps({"dry_run": True, "request": request, "segments": segments}, ensure_ascii=False))
        return 0

    api_key = os.environ.get("SMSMODE_API_KEY", "")
    if not api_key:
        print("error: set SMSMODE_API_KEY to an smsmode API key (Settings > API keys)", file=sys.stderr)
        return 2
    try:
        http_status, payload = post(api_key, request)
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        print(json.dumps({"message": f"network error: {error}"}), file=sys.stderr)
        return 4
    code, summary = interpret(http_status, payload)
    print(json.dumps(summary, ensure_ascii=False))
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
