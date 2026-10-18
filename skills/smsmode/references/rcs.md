# smsmode RCS REST API (`rest.smsmode.com/rcs/v1`)

Source: smsmode OpenAPI spec `specs/rest-rcs.yml` (v1.8) and
`https://www.smsmode.com/tarifs-sms/` (October 2026).

## Prerequisites

- An active subscription plan that includes RCS (`Classique`, `Medium`,
  `Premium`, or a custom contract — RCS is not available on prepaid packs or the
  `Basique` plan).
- A verified and launched **RCS agent** on smsmode (brand name, logo, banner,
  use case validated by the French carriers).
- The API key of that RCS channel (`X-Api-Key`), which has a fixed flow
  (`TRANSACTIONAL`, `MARKETING`, or `OTP`) just like an SMS channel.

## Endpoint

`POST https://rest.smsmode.com/rcs/v1/messages`

Headers:
- `X-Api-Key: <rcs_channel_api_key>`
- `Content-Type: application/json`
- `Accept: application/json`

Common envelope fields (identical to `/sms/v1/messages`):
- `recipient.to`: international digits without `+` (`"33600000000"`).
- `sender.from`: optional (`<= 11` chars).
- `refClient`: optional caller correlation id (`<= 35` chars).
- `callbackUrlStatus`: optional delivery/read webhook URL (`<= 255` chars).
- `callbackUrlMo`: optional inbound reply/postback webhook URL (`<= 255` chars).

## Message types (`body.type`) and billing tiers

Unlike SMS, RCS uses UTF-8 natively (no GSM-7 vs `UNICODE` split) and bills by
`body.type` and by subscription plan (see [references/pricing.md](pricing.md)
for exact rates per plan):

| `body.type` | Constraints | Suggestions allowed | Billing tier | Published FR rate (`Classique` / `Medium` / `Premium`, HT) |
|---|---|---|---|---|
| `BASIC` | `text` `1..=160` characters (UTF-8 and emoji included) | No | **RCS Basic** | `0,0350 €` / `0,0340 €` / `0,0330 €` |
| `TEXT` | `text` `1..=1000` characters (`<= 160` if `suggestions` is omitted) | Yes (`<= 11`) | **RCS Single** (or Session) | `0,0500 €` / `0,0480 €` / `0,0460 €` |
| `FILE` | `file.url` (`<= 255` chars) | Yes (`<= 11`) | **RCS Single** (or Session) | `0,0500 €` / `0,0480 €` / `0,0460 €` |
| `STANDALONE_RICH_CARD` | `richCard.title` (`<= 200`), `description` (`<= 2000`), `file`, `suggestions` (`<= 4`) | Yes (`<= 4` inside card + `<= 11` top-level) | **RCS Single** (or Session) | `0,0500 €` / `0,0480 €` / `0,0460 €` |
| `CAROUSEL_RICH_CARD` | `richCards` (`2..=10` cards), `width` (`SMALL` or `MEDIUM`) | Yes (`<= 4` per card + `<= 11` top-level) | **RCS Single** (or Session) | `0,0500 €` / `0,0480 €` / `0,0460 €` |

**Cost rules:**
- **Always use `"type": "BASIC"` when `text` is `<= 160` characters and there
  are no suggestion buttons.** Sending the same message with `"type": "TEXT"` is
  valid in the schema (`rest-rcs.yml` allows `TEXT` without `suggestions` when
  `text <= 160`), but bills it as **RCS Single** instead of **RCS Basic** (~30 %
  more expensive on every plan).
- **French accents and emoji are free in RCS:** a 140-character French message
  with `’`, `ê`, `ç` or `👍` costs 1 RCS Basic (whereas over SMS it forces
  `UNICODE` and costs 2 SMS segments). Even an **RCS Single** (up to 1 000 chars
  with quick-reply buttons or a rich card) is cheaper than a 2-segment SMS on
  every subscription plan (`Classique`, `Medium`, `Premium`).
- **Never quote a single euro figure without naming the subscription plan** (or
  reading `price.amount` on `GET /rcs/v1/messages/{messageId}`).

## Suggestions (buttons and quick replies)

Every suggestion object in `body.suggestions` or `richCard.suggestions`
**requires** `type`, `text` (`1..=25` characters) and `postbackData`
(`1..=2048` characters, sent back to `callbackUrlMo` when the user taps the
button):

```json
{
  "recipient": { "to": "33600000000" },
  "refClient": "appt-42",
  "body": {
    "type": "TEXT",
    "text": "Rendez-vous demain à 14h30 au Centre Foch. Confirmez-vous votre présence ?",
    "suggestions": [
      { "type": "REPLY", "text": "Oui, je confirme", "postbackData": "confirm:42" },
      { "type": "REPLY", "text": "Annuler / déplacer", "postbackData": "reschedule:42" },
      { "type": "OPEN_URL", "text": "Voir le plan", "url": "https://example.com/plan", "postbackData": "map:42" },
      { "type": "DIAL_PHONE", "text": "Appeler", "phone": "+33140000000", "postbackData": "call:42" }
    ]
  }
}
```

Other suggestion types in `rest-rcs.yml`:
- `SHOW_LOCATION`: `latitude`, `longitude`, optional `label` (`<= 100` chars).
- `REQUEST_LOCATION`: asks the user to share their location.
- `CREATE_CALENDAR_EVENT`: `title` (`<= 100`), `description` (`<= 500`),
  `startDate`, `endDate` (`YYYY-MM-DDTHH:mm:ssZ`).

## Standalone rich card

```json
{
  "recipient": { "to": "33600000000" },
  "body": {
    "type": "STANDALONE_RICH_CARD",
    "richCard": {
      "orientation": "VERTICAL",
      "height": "MEDIUM",
      "title": "Confirmation de rendez-vous",
      "description": "Dr Martin — Mardi 14h30",
      "file": { "url": "https://example.com/banner.jpg" },
      "suggestions": [
        { "type": "REPLY", "text": "Confirmer", "postbackData": "confirm" },
        { "type": "OPEN_URL", "text": "Itinéraire", "url": "https://example.com/map", "postbackData": "map" }
      ]
    }
  }
}
```

- When `orientation` is `HORIZONTAL`, `thumbnailAlignment` (`LEFT` or `RIGHT`)
  is required.
- When `file.thumbnailUrl` is set, `height` is required (`SHORT`, `MEDIUM`, or
  `TALL`).

## Delivery and read statuses

RCS uses the same webhook format and `X-Smsmode-256: sha256=<hex>` signature as
SMS, adding `READ` and RCS-specific refusal details:

| `status.value` | `status.detail` examples | Meaning |
|---|---|---|
| `SCHEDULED`, `ENROUTE` | `ACCEPTED` | In transit |
| `DELIVERED` | — | Delivered to handset |
| `READ` | — | Opened/read by recipient (RCS read receipt) |
| `UNDELIVERABLE` | `PHONE_NOT_SUITABLE`, `NETWORK_NOT_SUITABLE`, `AGENT_NOT_LAUNCHED`, `SPAM`, `INSUFFICIENT_CREDIT` | Handset/carrier does not support RCS or permanent refusal |
| `UNDELIVERED` | `VALIDITY_EXPIRED`, `OPERATOR_ERROR`, `TEMP_PHONE_ERROR` | Not delivered in time |
