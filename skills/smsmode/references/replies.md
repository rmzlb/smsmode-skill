# Replies and two-way SMS

## Contents

- Who can be answered
- Shared short code
- Matching a reply to its message
- Dedicated number (Time2Chat)
- RCS
- Receiving replies in code

## Who can be answered

| Sender (`from`) | Replies |
|---|---|
| alphanumeric (brand name) | impossible: the phone has no number to answer |
| custom numeric | replaced by a short code (knowledge base) |
| channel default shared short code (5 digits) | yes, metropolitan France only |
| dedicated virtual number (Time2Chat) | yes, conversation-grade |

Replies are free for the sender; the person pays a normal SMS. smsmode's
knowledge base says operators only guarantee that a reply is linked to the
original message if it comes within 24 hours.

## Shared short code

The default sender of a channel is a shared 5-digit short code (the spec uses
36034 as its example). *Observed* on a transactional channel:

- the API answer showed `from: 36034`, while the handset showed other short
  codes (38164, 36954), not always the same from one message to the next;
- replies arrived as MO within seconds, including UNICODE ones (accents,
  emoji), which the list only returns with `searchBy[encoding]=UNICODE`.

A shared short code is enough for one-off confirmations ("reply YES") and for
one question at a time. It is a poor fit for open conversations: people
cannot save a stable number or write first.

## Matching a reply to its message

Each MO carries `originMessageId` and the `refClient` of the sent message
smsmode attached it to. *Observed*: smsmode attached every reply to the most
recent message sent to that phone, not to the message the person was looking
at when answering. With two questions in flight to the same person, the
answer to the first is attributed to the second.

This is not specific to smsmode: an SMS reply carries no reference to the
message it answers, on any provider and any number. `originMessageId` is
smsmode's attribution, not the person's intent. Apps that "match each answer
to its question" on Twilio do it from their own state (the question still
open for that number), and the same works here.

Design around it:

- keep at most one open question per recipient, and ask the next one after
  the answer arrives;
- set `refClient` to your own id (conversation, order, appointment) on every
  message and use it from the MO;
- store the open question per phone number on your side; treat
  `originMessageId` as a hint.

A dedicated number does not change this rule. What it adds is a stable number
people can save and write to first, and session pricing.

## Dedicated number (Time2Chat)

Time2Chat is smsmode's conversational SMS: a dedicated virtual number (French
"09" numbers) that sends and receives, with 24-hour sessions.

- A session opens when the person sends a message (MO), either answering
  your message or writing first, and closes 24 hours after the last message;
  inside it, exchanges are billed as a session rather than per message.
- It is not self-service: there is no API or UI to rent the number; it goes
  through smsmode's sales team. The pricing page lists Time2Chat with the
  monthly plans from "Classique" upward, not with prepaid packs (October 2026).
- Once assigned, the number is used as `from` like any sender.

## RCS

smsmode also sends RCS (rich messages, conversational agents with 24-hour
sessions) through a separate API: `https://dev.smsmode.com/rcs/openapi/rest-rcs.yml`.
It needs a registered brand agent and a subscription; SMS remains the
fallback for phones without RCS.

## Receiving replies in code

- Push: set `callbackUrlMo` on each message, or the channel-wide
  "Réception de SMS (MO)" webhook in Settings > Webhooks. smsmode POSTs the MO
  resource as JSON. Verify the signature (webhooks.md), answer 2xx quickly,
  deduplicate on `messageId`.
- Pull: `python3 scripts/list_messages.py --direction MO`, or
  `--origin-message-id <messageId>` for the replies attached to one message.
