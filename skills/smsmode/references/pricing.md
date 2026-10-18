# Pricing, subscription plans and balance

## Core rule for agents

Unit euro prices on smsmode are **never** a single fixed number: they depend on
the account's **payment formula** (prepaid pack size, monthly plan `Basique`,
`Classique`, `Medium`, `Premium`, or negotiated contract) and on the
**destination country**.

- Always state the **structural billing unit** first:
  - **SMS:** number of segments (`1`, `2`, …, `10`) and encoding (`GSM7` vs
    `UNICODE`), computed by `scripts/sms_segments.py`.
  - **RCS:** message tier — `BASIC` (`text` `<= 160` chars, no buttons),
    `SINGLE` (`TEXT` `> 160` chars or with buttons, `FILE`,
    `STANDALONE_RICH_CARD`, `CAROUSEL_RICH_CARD`), or 24h `SESSION`.
  - **Time2Chat (dedicated 09/04 conversational SMS):** outbound `MT` vs 24h
    `Session` (opened when the recipient replies).
- For the **exact euro cost** on the live account, read `price.amount` from the
  API on a sent message rather than guessing which plan the account is on.
- When estimating a budget before sending, either ask which plan/rate applies
  or give the breakdown across the published plans below (marking them as
  public reference rates from `https://www.smsmode.com/tarifs-sms/`, subject to
  change).

## Real cost and balance from the API

```bash
# Exact billed price of one SMS, once read back
curl -sS "https://rest.smsmode.com/sms/v1/messages/<messageId>" \
  -H "X-Api-Key: $SMSMODE_API_KEY" -H "Accept: application/json"      # → price.amount, price.currency

# Exact billed price of one RCS message, once read back
curl -sS "https://rest.smsmode.com/rcs/v1/messages/<messageId>" \
  -H "X-Api-Key: $SMSMODE_API_KEY" -H "Accept: application/json"      # → price.amount, price.currency

# Remaining balance and payment type (e.g. PRE_PAY)
curl -sS "https://rest.smsmode.com/commons/v1/organisations" \
  -H "X-Api-Key: $SMSMODE_API_KEY" -H "Accept: application/json"      # → balance.amount, balance.paymentType
```

`python3 scripts/list_messages.py --direction MT` prints `price` and `parts`
for each recent SMS message, both encodings included.

## What is billed

- **SMS:** each sent message (MT) costs 1 SMS per segment (`body.messagePartCount`):
  a 2-part message costs 2 × the plan's unit SMS price. Inbound replies (MO) are
  free for the sender.
- **RCS:** UTF-8 is native (accents like `’`, `ê`, `ç`, `« »` and emoji never
  halve the character limit). A plain text `<= 160` chars without suggestions
  sent with `body.type: "BASIC"` is billed at the **RCS Basic** rate; longer
  text (`<= 1000` chars), buttons, rich cards, carousels or files are billed at
  the **RCS Single** rate (or **RCS Session** inside a 24-hour conversational
  window).
- **Time2Chat:** a 24-hour session opens when the recipient sends a reply (MO)
  and closes 24 hours after the last message; exchanges inside the window are
  billed as a session rather than per message.
- **Account limits:** default limits (daily per channel, monthly per
  organisation) cap spending; a send beyond them is refused with
  `DAILY_LIMIT_EXCEEDED` or `ORGANISATION_MONTHLY_LIMIT_EXCEEDED`.

## Published reference rates — metropolitan France (`+33`, EUR excl. VAT, Oct 2026)

Source: `https://www.smsmode.com/tarifs-sms/` (volatile — verify live before
quoting contractually; custom/negotiated rates override these).

### 1. Prepaid packs (no monthly fee; SMS & TTS only)

RCS, Time2Chat and WhatsApp Business are not available on prepaid packs.

| Prepaid pack | SMS unit price (FR, HT) | TTS unit price (FR, HT) |Pack total (HT) |
|---|---:|---:|---:|
| 1 000 SMS | 0,0610 € | 0,122 € | 61 € |
| 5 000 SMS | 0,0580 € | 0,116 € | 290 € |
| 10 000 SMS | 0,0560 € | 0,112 € | 560 € |
| 20 000 SMS | 0,0550 € | 0,110 € | 1 100 € |
| 50 000 SMS | 0,0530 € | 0,106 € | 2 650 € |
| 100 000 SMS | 0,0450 € | 0,090 € | 4 500 € |

### 2. Monthly subscription plans (monthly fee + consumption)

| Plan | Monthly fee (HT) | SMS unit (FR) | RCS Basic (`<= 160` c., no button) | RCS Single (`TEXT` > 160 c., buttons, card, carousel) | RCS Session MT | Time2Chat MT | Time2Chat Session (24h) | TTS |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **Basique** (from 500 msg/mo) | 9 € | 0,0445 € | — | — | — | — | — | 0,0880 € |
| **Classique** (from 7 000 msg/mo) | 69 € | 0,0348 € | 0,0350 € | 0,0500 € | 0,0360 € | 0,0466 € | 0,0690 € | 0,0690 € |
| **Medium** (from 50 000 msg/mo) | 159 € | 0,0327 € | 0,0340 € | 0,0480 € | 0,0340 € | 0,0437 € | 0,0648 € | 0,0648 € |
| **Premium** (from 200 000 msg/mo) | 499 € | 0,0315 € | 0,0330 € | 0,0460 € | 0,0340 € | 0,0421 € | 0,0624 € | 0,0624 € |

## Cost comparison: SMS vs RCS on French texts

1. **1-segment GSM-7 SMS vs 2-segment Unicode SMS:** one `’` or `ê` in a
   130-character French SMS forces `UNICODE` (70 chars/segment, 67 once split)
   and **doubles** the SMS cost (`2 × unit price`, e.g. `0,0696 €` on Classique
   or `0,0630 €` on Premium).
2. **RCS Basic vs Unicode SMS:** because RCS uses UTF-8 natively, a
   130-character French message with `’`, `ê`, `ç` or emoji sent as
   `body.type = "BASIC"` costs **1 RCS Basic** (`0,0350 €` on Classique,
   `0,0330 €` on Premium) — roughly **half** the cost of the same text over
   Unicode SMS.
3. **RCS Single vs 2-segment SMS:** even an RCS Single (`0,0500 €` on Classique,
   `0,0460 €` on Premium, up to 1 000 characters + quick-reply buttons or a
   rich card) costs **less** than a 2-segment SMS on every subscription plan.
