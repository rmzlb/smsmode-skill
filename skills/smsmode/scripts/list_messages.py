#!/usr/bin/env python3
"""List sent (MT) or received (MO) smsmode messages, both encodings at once.

Usage:
  python3 scripts/list_messages.py --direction MO
  python3 scripts/list_messages.py --direction MO --origin-message-id <uuid>
  python3 scripts/list_messages.py --direction MT --ref-client order-42

Read-only (GET). Reads the API key from SMSMODE_API_KEY.

The list endpoint returns one encoding per call and defaults to GSM7, so a
reply with an accent outside GSM7 or an emoji is missing from an unfiltered
call although smsmode received it. This script queries GSM7 and UNICODE and
merges them, newest first.

Options:
  --direction          MO (replies, default) or MT (sent)
  --encoding           both (default), GSM7 or UNICODE
  --origin-message-id  replies smsmode attached to this sent message (MO only)
  --ref-client         messages tagged with this reference
  --to                 messages to this number
  --page-size          items per call, 1-100 (default 20)
  --pages              pages to read per encoding (default 1)

Prints one JSON object per line: messageId, direction, sentDate, from, to,
encoding, parts, status, detail, price, refClient, originMessageId, text.
smsmode's dates carry no offset (observed: Europe/Paris local time).

Exit codes: 0 ok, 2 invalid input or missing key, 3 authentication refused,
4 network error or unexpected answer.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

MESSAGES_URL = "https://rest.smsmode.com/sms/v1/messages"
TIMEOUT_SECONDS = 30  # same rationale as send_sms.py
PAGE_SIZE_MAX = 100  # API limit
DIRECTIONS = ("MO", "MT")
ENCODINGS = ("GSM7", "UNICODE")


def build_query(direction, encoding, page, page_size, ref_client=None, to=None, origin_message_id=None):
    if direction not in DIRECTIONS:
        raise ValueError(f"direction must be one of {', '.join(DIRECTIONS)}")
    if encoding not in ENCODINGS:
        raise ValueError(f"encoding must be one of {', '.join(ENCODINGS)}")
    if page < 1:
        raise ValueError("page starts at 1")
    if not 1 <= page_size <= PAGE_SIZE_MAX:
        raise ValueError(f"page-size must be 1 to {PAGE_SIZE_MAX}")
    if origin_message_id and direction != "MO":
        raise ValueError("origin-message-id only filters replies: use --direction MO")
    params = [
        ("searchBy[direction]", direction),
        ("searchBy[encoding]", encoding),
        ("page", str(page)),
        ("pageSize", str(page_size)),
    ]
    if ref_client:
        params.append(("searchBy[refClient]", ref_client))
    if to:
        params.append(("searchBy[to]", to.strip().lstrip("+")))
    if origin_message_id:
        params.append(("searchBy[originMessageId]", origin_message_id))
    # The server answers 400 to raw brackets: encode the names as well.
    return urllib.parse.urlencode(params, quote_via=urllib.parse.quote)


def merge(pages):
    seen, merged = set(), []
    for items in pages:
        for item in items:
            if item.get("messageId") not in seen:
                seen.add(item.get("messageId"))
                merged.append(item)
    return sorted(merged, key=lambda m: m.get("sentDate") or "", reverse=True)


def summarize(item):
    body = item.get("body") or {}
    status = item.get("status") or {}
    return {
        "messageId": item.get("messageId"),
        "direction": item.get("direction"),
        "sentDate": item.get("sentDate"),
        "from": item.get("from"),
        "to": (item.get("recipient") or {}).get("to"),
        "encoding": body.get("encoding"),
        "parts": body.get("messagePartCount"),
        "status": status.get("value"),
        "detail": status.get("detail"),
        "price": item.get("price"),
        "refClient": item.get("refClient"),
        "originMessageId": item.get("originMessageId"),
        "text": body.get("text"),
    }


class ApiError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def fetch(api_key, query):
    request = urllib.request.Request(
        f"{MESSAGES_URL}?{query}",
        headers={"X-Api-Key": api_key, "Accept": "application/json", "User-Agent": "smsmode-agent-skill/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read())
    except urllib.error.HTTPError as error:
        raise ApiError(3 if error.code in (401, 403) else 4, f"HTTP {error.code}: {error.read()[:300]!r}") from error
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise ApiError(4, f"network error: {error}") from error
    except ValueError as error:
        raise ApiError(4, "unexpected answer: not JSON") from error
    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        raise ApiError(4, "unexpected answer: no items list")
    return items, payload.get("totalCount")


def main(argv):
    parser = argparse.ArgumentParser(description="List smsmode messages in both encodings (read-only).")
    parser.add_argument("--direction", default="MO", choices=DIRECTIONS)
    parser.add_argument("--encoding", default="both", choices=("both",) + ENCODINGS)
    parser.add_argument("--origin-message-id")
    parser.add_argument("--ref-client")
    parser.add_argument("--to")
    parser.add_argument("--page-size", type=int, default=20)
    parser.add_argument("--pages", type=int, default=1)
    args = parser.parse_args(argv)

    encodings = ENCODINGS if args.encoding == "both" else (args.encoding,)
    try:
        queries = [
            (
                f"{encoding} page {page}",
                build_query(
                    args.direction, encoding, page, args.page_size,
                    ref_client=args.ref_client, to=args.to, origin_message_id=args.origin_message_id,
                ),
            )
            for encoding in encodings
            for page in range(1, max(args.pages, 1) + 1)
        ]
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    api_key = os.environ.get("SMSMODE_API_KEY", "")
    if not api_key:
        print("error: set SMSMODE_API_KEY to an smsmode API key (Settings > API keys)", file=sys.stderr)
        return 2

    pages = []
    try:
        for label, query in queries:
            items, total = fetch(api_key, query)
            pages.append(items)
            print(f"{label}: {len(items)} of {total}", file=sys.stderr)
    except ApiError as error:
        print(f"error: {error}", file=sys.stderr)
        return error.code
    for item in merge(pages):
        print(json.dumps(summarize(item), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
