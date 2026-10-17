# Pricing and balance

## What is billed

- Each sent message (MT) costs one SMS per segment: a 2-part message costs 2.
  Run `scripts/sms_segments.py` to know the count before sending.
- Replies (MO) are free for the sender.
- Time2Chat and RCS conversations are billed per 24-hour session.
- Whether a refused or undelivered message is billed is not documented:
  read its `price` rather than assuming either way.

## Real cost and balance

Read prices from the API instead of a price list:

```bash
# Price of one message, once read back
curl -sS "https://rest.smsmode.com/sms/v1/messages/<messageId>" \
  -H "X-Api-Key: $SMSMODE_API_KEY" -H "Accept: application/json"      # → price.amount, price.currency

# Remaining prepaid balance
curl -sS "https://rest.smsmode.com/commons/v1/organisations" \
  -H "X-Api-Key: $SMSMODE_API_KEY" -H "Accept: application/json"      # → balance.amount, balance.paymentType
```

`python3 scripts/list_messages.py --direction MT` prints `price` and `parts`
for each recent message, both encodings included.

## Published offers (October 2026)

Volatile: check `https://www.smsmode.com/tarifs-sms/` before quoting.

- Prepaid packs (1 000 to 100 000 SMS), price per SMS decreasing with volume.
  *Observed*: 0.061 EUR per segment to France on prepaid credit.
- Monthly plans, billed on consumption on top of the fee: Basique (9 EUR excl.
  VAT per month), Classique (69 EUR), Medium (159 EUR), Premium (499 EUR),
  with lower per-SMS prices. Time2Chat and RCS are listed from Classique
  upward.
- Default account limits (daily per channel, monthly per organisation) cap
  spending; a send beyond them is refused with `DAILY_LIMIT_EXCEEDED` or
  `ORGANISATION_MONTHLY_LIMIT_EXCEEDED`.

## Estimating a campaign or a monthly volume

cost ≈ Σ segments × unit price. The usual surprise is encoding: one ’ in a
130-character template makes it 2 UNICODE parts instead of 1 GSM-7 SMS, which
doubles the bill. Check templates with `sms_segments.py`, and see
encoding.md for keeping them in GSM-7.
