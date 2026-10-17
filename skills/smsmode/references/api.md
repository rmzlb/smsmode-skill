# smsmode REST API: SMS v1 and account

## Contents

- Base URL, headers, specs
- Send: `POST /sms/v1/messages`
- Read one message: `GET /sms/v1/messages/{messageId}`
- List messages: `GET /sms/v1/messages`
- Statuses and details
- Errors
- Account, channels, keys and balance

## Base URL, headers, specs

- Base URL: `https://rest.smsmode.com`. SMS under `/sms/v1`, account under
  `/commons/v1`.
- `X-Api-Key: <key>` on every call. A key belongs to one channel; plain
  `/sms/v1/messages` sends through that channel. `/channels/{channelId}/messages`
  targets another channel when the key's role allows it.
- `Accept: application/json` is required (406 otherwise), and
  `Content-Type: application/json` on POST (415 otherwise).
- OpenAPI specs: `https://dev.smsmode.com/sms/openapi/rest-sms.yml`,
  `https://dev.smsmode.com/commons/openapi/rest-commons.yml`,
  `https://dev.smsmode.com/rcs/openapi/rest-rcs.yml`. Human-readable docs at
  `https://dev.smsmode.com/sms/v1/`.

## Send: `POST /sms/v1/messages`

One JSON object sends one message; a JSON array sends a batch of up to 1000.

| Field | Constraint | Notes |
|---|---|---|
| `recipient.to` | international number, digits only | `33600000000`. No `+`, no national `0…` form |
| `body.text` | 1 to 1530 characters (GSM7) / 670 (UNICODE) | at most 10 concatenated parts |
| `body.encoding` | `GSM7` (default) or `UNICODE` | not chosen for you: see encoding.md |
| `body.stop` | boolean, default `false` | appends "STOP" and a short code; required on marketing channels with a custom sender |
| `from` | 1 to 11 characters | alphanumeric, short code or virtual number, authorized by smsmode; default: the channel's sender |
| `refClient` | 3 to 140 characters | your reference; returned on reports and attached replies; filterable |
| `sentDate` | ISO 8601, future, within 10 years | schedules the message (status `SCHEDULED`) |
| `callbackUrlStatus` | at most 255 characters | delivery reports for this message |
| `callbackUrlMo` | at most 255 characters | replies attached to this message |

Answer 201 (*observed* shape; identifiers fictional):

```json
{
  "messageId": "67c15045-1067-4588-ba3c-737cc5051438",
  "acceptedAt": "2026-10-17T10:30:00",
  "channel": {"channelId": "…", "name": "…", "type": "SMS", "flow": "TRANSACTIONAL"},
  "type": "SMS",
  "direction": "MT",
  "recipient": {"to": "33600000000"},
  "from": "36034",
  "body": {"text": "…", "encoding": "GSM7", "messagePartCount": 1, "length": 85},
  "status": {"value": "ENROUTE", "deliveryDate": "…"},
  "refClient": "order-42",
  "href": "https://rest.smsmode.com/sms/v1/messages/67c15045-1067-4588-ba3c-737cc5051438"
}
```

`price` (`{"amount": 0.061, "currency": "EUR"}`) appears on the message once
read back, not in the 201. `from` in the answer is the sender requested,
which may differ from what the handset shows when a shared short code is
used.

## Read one message: `GET /sms/v1/messages/{messageId}`

Same resource as above, with the latest `status` (`value`, `detail`,
`deliveryDate`, and `lookup`: operator, country, MCC/MNC) and `price`.

## List messages: `GET /sms/v1/messages`

| Query parameter | Values | Default |
|---|---|---|
| `page` | ≥ 1 | 1 |
| `pageSize` | 1 to 100 | 10 |
| `searchBy[direction]` | `MT` (sent) or `MO` (received) | `MT` |
| `searchBy[encoding]` | `GSM7` or `UNICODE` | `GSM7` |
| `searchBy[refClient]` | 3 to 140 characters | |
| `searchBy[to]` | number, digits only | |
| `searchBy[originMessageId]` | UUID of a sent message; requires `searchBy[direction]=MO` | |
| `sortBy[sentDate]`, `sortBy[refClient]` | `ASC` or `DESC` | |

- Percent-encode the bracketed names (`searchBy%5Bdirection%5D=MO`): raw
  brackets get an HTML 400 page from the server (*observed*; the spec also
  says to encode them).
- One call returns one encoding. Call once with `GSM7` and once with
  `UNICODE`, or a reply such as "Très bien 👍" is silently absent
  (*observed*).
- The answer: `startDate`, `endDate` (the window covered), `page`,
  `pageSize`, `count`, `totalCount`, `links` (`first`, `last`, `previous`,
  `next`) and `items`.
- A received message (`direction: MO`) has `from` (the person's number),
  `recipient.to` (the short code or number it was sent to), `body.text`,
  `body.encoding`, `originMessageId` and `refClient` of the sent message
  smsmode attached it to.

## Statuses and details

`status.value`:

| Value | Final | Meaning (spec) |
|---|---|---|
| `SCHEDULED` | no | scheduled, not started |
| `ENROUTE` | no | in retry or handed to an operator |
| `DELIVERED` | yes | delivered to the handset |
| `UNDELIVERABLE` | yes | permanently undeliverable: unrecognized number format or destination not covered |
| `UNDELIVERED` | yes | not delivered within the validity or retry period |

`status.detail` (spec):

| Detail | Meaning | Fix |
|---|---|---|
| `IN_PROGRESS` | being processed | wait |
| `DELIVERED_TO_NETWORK` | accepted by the operator | wait |
| `INSUFFICIENT_CREDIT` | prepaid balance too low | top up |
| `DAILY_LIMIT_EXCEEDED` | channel daily limit reached | raise it (channel API or UI) |
| `ORGANISATION_MONTHLY_LIMIT_EXCEEDED` | organisation monthly limit reached | ask smsmode support |
| `ROUTE_NOT_AVAILABLE` | destination not routed for this channel | ask smsmode support |
| `SPAM` | message flagged as spam | ask support; often an unauthorized sender |
| `INVALID_PHONE_NUMBER` | not a phone number | fix the number |
| `BLACKLISTED` | recipient unsubscribed from marketing | do not resend marketing |

## Errors

Errors are `application/problem+json`:

```json
{"title": "Bad Request", "message": "Request body: recipient invalid", "detail": "Must be specified",
 "type": "https://dev.smsmode.com/sms/errors/400.027", "status": "400", "errorCode": "400.027"}
```

`status` (a string in the body) is one of 400, 401, 402, 403, 404, 405, 406,
409, 415, 500. `errorCode` is stable and specific (`401.001` = invalid
`X-Api-Key`, `400.027` = missing recipient, both *observed*); `message` names
the field at fault.

## Account, channels, keys and balance

| Call | Gives |
|---|---|
| `GET /commons/v1/organisations` | organisations visible to the key, with `balance` (`amount`, `currency`, `paymentType` such as `PRE_PAY`) and `monthlyConsumptionLimit` / `monthlyConsumption` |
| `GET /commons/v1/organisations/{organisationId}/channels` | channels: `flow` (`TRANSACTIONAL`, `MARKETING`, `OTP`), `defaultFromField`, `fromFieldList` (authorized senders), `dailyConsumptionLimit`, `dailyConsumption`, `monthlyConsumptionLimit`, `defaultCallbackUrlStatus`, `defaultCallbackUrlMo` |
| `GET /commons/v1/channels/{channelId}/credentials` | the channel's API keys with `authorizedIps` and `lastIpAddress`. The items include the key itself (`value`): never print or log this answer whole |
| `GET /commons/v1/channels/{channelId}/consumptions` | consumption per period |
| `GET /commons/v1/lookup/{msisdn}` | operator and country of a French number; premium subscriptions only |

Checking `balance.amount`, the channel `flow`, `fromFieldList` and the limits
before a first production send avoids the most common refusals.
