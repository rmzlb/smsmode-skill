---
name: smsmode
description: Sends, receives and troubleshoots SMS through the smsmode REST API (rest.smsmode.com, a French SMS provider). Use when code or an agent sends transactional or marketing SMS with smsmode, reads replies (MO), handles delivery reports or signed webhooks, picks a sender ID, checks GSM-7 vs Unicode encoding and segment cost, sets up two-way SMS, or migrates from Twilio or another provider to smsmode, even when the user only says "SMS" and the project uses an smsmode key or a French short code.
license: MIT
compatibility: Needs network access to rest.smsmode.com and an smsmode API key in SMSMODE_API_KEY. Bundled scripts need Python 3.9+ and only the standard library.
metadata:
  author: rmzlb
  version: "1.0.0"
  verified-against-api: "2026-10-17"
---

# smsmode SMS API

Facts below come from smsmode's OpenAPI specs, its knowledge base and calls
made against the live API (marked *observed*). Paths are relative to this
skill's directory.

## Spending rules

Every sent message (MT) is billed per segment; replies (MO) are free.

- Run `scripts/sms_segments.py` on the text before sending.
- `scripts/send_sms.py` only prints the request unless given `--send`.
- Test only on a phone you own, one message at a time, and say how many SMS
  a test will cost before running it.

## Quick start

```bash
python3 scripts/send_sms.py --to +33600000000 --text "Votre code : 123456"          # dry run
python3 scripts/send_sms.py --to +33600000000 --text "Votre code : 123456" --send   # sends
```

The same request by hand:

```bash
curl -sS https://rest.smsmode.com/sms/v1/messages \
  -H "X-Api-Key: $SMSMODE_API_KEY" -H "Accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{"recipient":{"to":"33600000000"},"body":{"text":"Votre code : 123456"},"refClient":"order-42"}'
```

A 201 returns `messageId`, `status.value` (`ENROUTE` or `SCHEDULED`) and
`body.messagePartCount`. Keep `messageId`; set `refClient` to your own id so
reports and replies can be matched without it.

## In application code

Copy `scripts/sms_segments.py` into the project and decide the encoding for
every message at send time, whatever the template looks like today:

```python
from sms_segments import analyse  # copied from this skill's scripts/

def smsmode_body(text: str) -> dict:
    body = {"text": text}
    if analyse(text)["encoding"] == "UNICODE":  # ’ « » … ê ç emoji, etc.
        body["encoding"] = "UNICODE"            # else smsmode replaces them silently
    return body
```

Then check `status.value` of the 201 (gotcha 3) and keep `messageId`.

## Gotchas

1. **Encoding is the caller's job.** smsmode sends GSM-7 unless the request
   sets `"body": {"encoding": "UNICODE"}`, and replaces the characters GSM-7
   lacks instead of refusing the message (*observed*: ’ became ', an emoji
   became ?; the message was still `DELIVERED`). In French, é è à ù É Ç are in
   GSM-7 but ê â î ô û ë ï ç À œ « » ’ … are not. UNICODE fits 70 characters
   per segment (67 once split) instead of 160 (153): a 90-character UNICODE
   text is billed as 2 SMS (*observed*). See
   [references/encoding.md](references/encoding.md).
   - Check the text exactly as given. Retyping it turns ’ into ' without
     anyone noticing, and the check then answers for a different text. If the
     user's text shows ’ « » … or ê, they must appear in `non_gsm`.
   - In application code, choose the encoding at send time from the text
     actually sent (copy the two character sets of `scripts/sms_segments.py`),
     never from a sample: a GSM-7 template gets a ’ the day someone edits it.
   - If you suggest straightening ’ to ' to stay at 1 SMS, say so and give
     both costs; do not change a user's text silently.
2. **Numbers go without `+`.** `recipient.to` is the international number as
   digits only: `33600000000`, not `+33600000000` or `0600000000`.
3. **A 201 is not a delivery.** Read `status.value` in the answer, then the
   delivery reports. `UNDELIVERABLE` / `UNDELIVERED` are final failures and
   `status.detail` says why: `INSUFFICIENT_CREDIT`, `DAILY_LIMIT_EXCEEDED`,
   `ORGANISATION_MONTHLY_LIMIT_EXCEEDED`, `SPAM`, `ROUTE_NOT_AVAILABLE`,
   `INVALID_PHONE_NUMBER`, `BLACKLISTED`. New accounts start with low daily
   and monthly limits: raise them before going live.
4. **The message list hides Unicode messages.** `GET /sms/v1/messages`
   defaults to `searchBy[direction]=MT` and `searchBy[encoding]=GSM7`, so a
   reply containing ê or an emoji is missing from an unfiltered call although
   it arrived. Query both encodings (`scripts/list_messages.py` does). The
   bracketed names must be percent-encoded (`searchBy%5Bencoding%5D`): raw
   brackets get an HTML 400 page (*observed*).
5. **Replies need a number as sender.** Nobody can answer an alphanumeric
   sender, and a custom numeric sender is replaced by a short code. With the
   default shared short code, replies work in metropolitan France only,
   within 24 h, and smsmode attaches each reply (`originMessageId`) to the
   latest message sent to that phone, not necessarily the one being answered
   (*observed*). An SMS reply never says which message it answers, on any
   provider: keep one open question per recipient and match by your own
   state. The short code shown on the handset can also differ between
   messages. For conversations, see [references/replies.md](references/replies.md).
6. **A key belongs to one channel, and a channel's flow is fixed.** The flow
   (MARKETING, TRANSACTIONAL or OTP) is chosen when the channel is created and
   cannot change; create a transactional channel and its own key for
   notifications. Marketing messages with a custom sender must set
   `"stop": true` (adds the STOP opt-out), or they may be blocked or get
   their sender replaced.
7. **Keys can be locked to source IPs** (Settings > API keys). When a key that
   works elsewhere fails with 401 or 403 from a new server, check its IP
   allowlist before anything else.
8. **Sender IDs are at most 11 characters and must be authorized by
   smsmode.** The API can accept an undeclared sender (*observed*), so
   acceptance proves nothing: declare custom senders and check what a handset
   displays.
9. **Dates carry no offset.** `sentDate`, `acceptedAt` and `deliveryDate`
   look like `2026-10-17T10:30:00` and are Europe/Paris local time
   (*observed*).
10. **Webhook signatures cover the raw body.** `X-Smsmode-256:
    sha256=<hex>` is an HMAC-SHA256 of the exact bytes received, under the
    secret set in Settings > Webhooks; without a secret nothing is signed.
    Strip `sha256=` before hex-decoding. Failed calls are retried up to 24 h,
    so handlers must be idempotent. See
    [references/webhooks.md](references/webhooks.md).

## Send a message

```
Progress:
- [ ] Key of the right channel (transactional for notifications and codes)
- [ ] python3 scripts/sms_segments.py "<text>"  → encoding, segments, fits
- [ ] python3 scripts/send_sms.py ... (dry run) → review the request
- [ ] python3 scripts/send_sms.py ... --send    → exit code 0 and a messageId
- [ ] Delivery: webhook, or list_messages.py --direction MT --ref-client <id>
```

`send_sms.py` exit codes: 0 accepted, 1 refused by smsmode (read `detail`),
2 bad input or no key (nothing sent), 3 authentication refused, 4 network
error or unexpected answer. On 4 the message may exist: look it up by
`--ref-client` before sending again, or the recipient gets it twice.

## Track delivery

Ask for reports per message with `callbackUrlStatus` (max 255 characters) or
for the whole channel in Settings > Webhooks. Map statuses this way:

| smsmode `status.value` | Meaning | Final |
|---|---|---|
| `SCHEDULED`, `ENROUTE` | waiting, or handed to the operator | no |
| `DELIVERED` | reached the handset | yes |
| `UNDELIVERABLE` | permanent error (number format, uncovered destination…); `detail` gives the reason | yes |
| `UNDELIVERED` | not delivered within the validity period | yes |

Reports can arrive late, twice or out of order: keep the first final status.

## Read replies

```bash
python3 scripts/list_messages.py --direction MO                       # newest replies, both encodings
python3 scripts/list_messages.py --direction MO --origin-message-id <messageId>
```

To be called instead of polling, set `callbackUrlMo` on the message or the
"Réception de SMS (MO)" webhook in Settings > Webhooks, then match each reply
by `refClient` (copied from the message it is attached to, *observed*) or
`originMessageId`.

## Scripts

- `scripts/sms_segments.py "<text>"`: encoding, segment count, characters
  that force UNICODE, 10-part limit. Run it; no network.
- `scripts/send_sms.py --to … --text … [--from …] [--ref-client …]
  [--callback-url-status …] [--callback-url-mo …] [--stop] [--send]`:
  validated send, dry run by default.
- `scripts/list_messages.py [--direction MO|MT] [--ref-client …] [--to …]
  [--origin-message-id …]`: read-only listing, both encodings merged, one JSON
  object per line.
- `scripts/verify_webhook.py --signature "sha256=…" < body`: checks a webhook
  body against `SMSMODE_WEBHOOK_SECRET`. Also the reference implementation to
  copy into a handler.

All print `--help`.

## References

- [references/api.md](references/api.md): endpoints, request and response
  fields, limits, error format, balance. Read when writing an integration by
  hand or decoding an error.
- [references/encoding.md](references/encoding.md): GSM-7 table, French
  characters, segment arithmetic. Read when a text has accents, symbols or
  emoji, or when cost matters.
- [references/replies.md](references/replies.md): two-way SMS, shared short
  codes, dedicated numbers (Time2Chat), conversation matching.
- [references/webhooks.md](references/webhooks.md): signature checks in
  Python and Node.js, retries, idempotency, personal data in callbacks.
- [references/pricing.md](references/pricing.md): what is billed and how to
  read the real cost and balance from the API.
- [references/migrating-from-twilio.md](references/migrating-from-twilio.md):
  Twilio concepts and fields mapped to smsmode.
