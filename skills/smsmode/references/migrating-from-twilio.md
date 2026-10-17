# Migrating from Twilio to smsmode

## Contents

- Concept map
- Status map
- Migration checklist
- Running both providers during the switch

## Concept map

| Twilio Programmable Messaging | smsmode SMS v1 |
|---|---|
| `POST /2010-04-01/Accounts/{AccountSid}/Messages.json`, form-encoded, HTTP Basic (SID + auth token) | `POST https://rest.smsmode.com/sms/v1/messages`, JSON, `X-Api-Key` |
| `To=+33600000000` | `"recipient": {"to": "33600000000"}`: digits, no `+` |
| `From` = Twilio number, Messaging Service or alphanumeric sender | `from` (≤ 11): channel default short code, virtual number or authorized alphanumeric sender. Twilio numbers cannot be used |
| `Body`; Twilio picks UCS-2 by itself when needed | `body.text`; set `body.encoding: "UNICODE"` yourself, or characters are replaced |
| Smart Encoding (Messaging Services) swaps lookalike characters | nothing equivalent: clean templates (encoding.md) |
| `StatusCallback` | `callbackUrlStatus` (≤ 255 characters), or channel default |
| `MessageSid` | `messageId` (UUID); `refClient` for your own id |
| `ErrorCode` (e.g. 30003) | `status.detail` (e.g. `INVALID_PHONE_NUMBER`) |
| `X-Twilio-Signature`: HMAC-SHA1, base64, over URL + sorted form parameters, keyed by the auth token | `X-Smsmode-256: sha256=<hex>`: HMAC-SHA256 over the raw JSON body, keyed by a webhook secret set in the UI |
| Inbound: webhook on the number, form fields `From`, `To`, `Body` | `callbackUrlMo` per message or channel MO webhook, JSON MO resource with `originMessageId` and `refClient` |
| Replies to your number, matched by your app on `From` and its own state | same: match on `from` and your own state. smsmode also attaches each reply to the latest message sent to that phone (`originMessageId`, `refClient`); a stable dedicated number needs Time2Chat |
| Opt-out keywords handled by Twilio | `body.stop` on marketing channels; `BLACKLISTED` detail |

## Status map

Closest equivalents:

| Twilio `MessageStatus` | smsmode `status.value` |
|---|---|
| `scheduled` | `SCHEDULED` |
| `accepted`, `queued`, `sending` | `ENROUTE` (detail `IN_PROGRESS`) |
| `sent` | `ENROUTE` (detail `DELIVERED_TO_NETWORK`) |
| `delivered` | `DELIVERED` |
| `undelivered` | `UNDELIVERED` |
| `failed` | `UNDELIVERABLE` |

Treat `DELIVERED`, `UNDELIVERABLE` and `UNDELIVERED` as final, like
`delivered`, `failed` and `undelivered`.

## Migration checklist

```
- [ ] Transactional channel created in smsmode, with its own API key (IP allowlist set)
- [ ] Sender chosen: default short code (replies), alphanumeric (brand, no replies) or dedicated number
- [ ] Credit topped up; daily and monthly limits raised to the expected volume
- [ ] Sending code: digits-only numbers, UNICODE detection, refClient = your id, 201 status checked
- [ ] Templates checked with scripts/sms_segments.py (segments, encoding)
- [ ] Delivery-report endpoint: X-Smsmode-256 verified on the raw body, idempotent, 2xx fast
- [ ] Reply endpoint (if two-way): same checks, matched by refClient / originMessageId
- [ ] Tested on your own phone: one GSM-7 message, one UNICODE message, one reply
- [ ] Provider switch is a configuration value, not a code change
```

## Running both providers during the switch

- Keep Twilio's status and inbound endpoints for a few days after the switch:
  messages sent before it still report through Twilio.
- Store which provider sent each message, and let a report change only a
  message sent by that provider: identifiers do not overlap, and a stray or
  forged report must not touch the other provider's messages.
- Keep one status vocabulary in your own data (queued, sent, delivered,
  failed) and translate each provider's values at the edge, with the tables
  above.
