# Encoding and segments

## Contents

- What smsmode does with the text
- GSM-7 alphabet
- French text
- Segment arithmetic
- Keeping messages in GSM-7

## What smsmode does with the text

`body.encoding` defaults to `GSM7`. A character GSM-7 cannot represent is not
refused: it is replaced, and the message is still sent, billed and reported
`DELIVERED`. *Observed*: a typographic apostrophe ’ arrived as ', an emoji as
?. Nothing in the 201 or in the delivery report signals the loss.

So the sender decides: run `python3 scripts/sms_segments.py "<text>"`, and set
`"encoding": "UNICODE"` when it answers `UNICODE` (`scripts/send_sms.py` does
this itself).

## GSM-7 alphabet

Basic table (one septet each), 3GPP TS 23.038:

```
@ £ $ ¥ è é ù ì ò Ç LF Ø ø CR Å å Δ _ Φ Γ Λ Ω Π Ψ Σ Θ Ξ Æ æ ß É
space ! " # ¤ % & ' ( ) * + , - . / 0-9 : ; < = > ?
¡ A-Z Ä Ö Ñ Ü § ¿ a-z ä ö ñ ü à
```

Extension table (escape + character, two septets each): `€ [ ] { } ^ ~ \ |`
and form feed.

Everything else needs UNICODE, including tab, `’ ‘ “ ” « » … – —`, and
most accented letters.

## French text

| In GSM-7 | Not in GSM-7 (forces UNICODE) |
|---|---|
| é è à ù ì ò É Ç æ Æ ä ö ü ñ Ä Ö Ü Ñ | ê â î ô û ë ï ÿ ç À Â È Ê Î Ô Ù Û Ë Ï œ Œ |
| ' " ? ! : ; ( ), and € (2 septets) | ’ ‘ “ ” « » … – —, tab, non-breaking space |

`ç` (lowercase) is not in the table; only `Ç` is. Treat it as UNICODE.

Text typed on phones and in word processors often contains ’ and
non-breaking spaces (before `:` `?` `!` in French typography): one such
character switches the whole message to UNICODE.

## Segment arithmetic

| Encoding | One SMS | Each part of a long SMS | smsmode maximum |
|---|---|---|---|
| GSM7 | 160 septets | 153 septets | 10 parts, 1530 characters |
| UNICODE | 70 UTF-16 units | 67 UTF-16 units | 10 parts, 670 characters |

- Each part is billed as one SMS.
- Extension characters (`€`, `[`, …) count 2 septets; emoji outside the
  Basic Multilingual Plane count 2 UTF-16 units (👍🏽 is 4).
- A two-unit character is never split across parts, so a long message can
  need one part more than `ceil(units / 153)` or `ceil(units / 67)`.
  `sms_segments.py` packs parts that way.
- *Observed*: a 90-character UNICODE message was billed 2 parts; GSM-7
  messages up to 116 characters were billed 1.
- The `messagePartCount` smsmode returns on the sent message is the
  authoritative count.

## Keeping messages in GSM-7

When a template is under your control, replacing typographic punctuation keeps
it in GSM-7 at no loss of meaning: ’ ‘ → ', “ ” « » → ", … → ..., – — → -,
non-breaking space → space. Do this in the template, not by rewriting a
person's free text, and keep real letters (ê, ç) as they are: dropping their
accents changes the words, and UNICODE is the right choice for them.
