#!/usr/bin/env python3
"""Pick the encoding of an SMS text and count the parts it will be billed for.

Usage:
  python3 scripts/sms_segments.py "Votre code : 123456"
  echo "C’est noté" | python3 scripts/sms_segments.py

Prints one JSON object:
  encoding   "GSM7", or "UNICODE" when a character is outside GSM 03.38
  characters number of characters (code points)
  units      septets (GSM7, extension characters count 2) or UTF-16 units
  segments   parts the message is split into, i.e. how many SMS are billed
  non_gsm    characters that forced UNICODE, in order of appearance
  fits       false beyond smsmode's 10-part limit (1530 GSM7 / 670 UNICODE)

Exit codes: 0 ok, 2 empty input.

smsmode sends GSM7 unless the request says "encoding": "UNICODE", and replaces
characters it cannot encode instead of refusing the message, so the choice must
be made before sending. Counts follow 3GPP TS 23.038 / 23.040; the
messagePartCount smsmode returns for a sent message is authoritative.
"""

import json
import sys

# GSM 03.38 default alphabet: one septet each.
GSM7_BASIC = set(
    "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?"
    "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà"
)
# GSM 03.38 extension table: an escape septet plus the character, so two.
GSM7_EXTENSION = set("\f^{}\\[~]|€")

# A single SMS carries 140 bytes: 160 septets or 70 UTF-16 units. A
# concatenated part spends 6 bytes on its header, leaving 153 septets or 67
# units. smsmode caps a message at 10 parts (text max 1530 GSM7 / 670 UNICODE).
GSM7_SINGLE, GSM7_PART = 160, 153
UNICODE_SINGLE, UNICODE_PART = 70, 67
MAX_PARTS = 10


def _gsm7_cost(char):
    return 2 if char in GSM7_EXTENSION else 1


def _utf16_cost(char):
    return 2 if ord(char) > 0xFFFF else 1


def _count_parts(costs, single, part):
    """Parts needed when no character (escape pair, surrogate pair) is split."""
    if sum(costs) <= single:
        return 1
    parts, used = 1, 0
    for cost in costs:
        if used + cost > part:
            parts, used = parts + 1, 0
        used += cost
    return parts


def analyse(text):
    if not text:
        raise ValueError("empty text: an SMS needs at least one character")
    non_gsm = []
    for char in text:
        if char not in GSM7_BASIC and char not in GSM7_EXTENSION and char not in non_gsm:
            non_gsm.append(char)
    if non_gsm:
        encoding, costs = "UNICODE", [_utf16_cost(c) for c in text]
        segments = _count_parts(costs, UNICODE_SINGLE, UNICODE_PART)
    else:
        encoding, costs = "GSM7", [_gsm7_cost(c) for c in text]
        segments = _count_parts(costs, GSM7_SINGLE, GSM7_PART)
    return {
        "encoding": encoding,
        "characters": len(text),
        "units": sum(costs),
        "segments": segments,
        "non_gsm": non_gsm,
        "fits": segments <= MAX_PARTS,
    }


def main(argv):
    if any(arg in ("-h", "--help") for arg in argv):
        print(__doc__.strip())
        return 0
    text = argv[0] if argv else sys.stdin.read()
    if not argv and text.endswith("\n"):
        text = text[:-1]  # the newline echo or a heredoc appends
    try:
        result = analyse(text)
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
