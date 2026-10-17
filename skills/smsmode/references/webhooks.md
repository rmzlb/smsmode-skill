# Webhooks: delivery reports and replies

## Contents

- What smsmode posts
- Signature
- Python handler
- Node.js handler
- Retries and idempotency
- Personal data

## What smsmode posts

Two callbacks, both `POST` with a JSON body shaped like the message resource
(api.md):

| Callback | Set with | Body |
|---|---|---|
| delivery report | `callbackUrlStatus` on the message, or channel default in Settings > Webhooks | sent message with its new `status` (`value`, `detail`, `deliveryDate`) and `refClient` |
| incoming message | `callbackUrlMo` on the message, or "Réception de SMS (MO)" in Settings > Webhooks | MO resource: `from`, `body.text`, `originMessageId`, `refClient` |

Each URL is at most 255 characters. Putting your own id in the URL
(`?job=<id>`) or in `refClient` lets the handler find the record without a
lookup. A report can name a message your system has not recorded yet (the
callback can beat your own write after the 201): tolerate it.

## Signature

smsmode's knowledge base ("Comment sécuriser vos webhooks smsmode ?"):

- Set a secret in Settings > Webhooks. Without one, callbacks are not signed.
- Each callback carries `X-Smsmode-256: sha256=<64 hex characters>`, the
  HMAC-SHA256 of the raw request body under that secret.
- Recompute it over the raw bytes, before any JSON parsing, and compare in
  constant time.
- Optional extras: up to 2 custom headers with fixed values, and the fixed
  User-Agent `smsmode-Webhooks/1.0 (+https://dev.smsmode.com)`. Both are
  spoofable; use them only on top of the signature.
- No rotation policy is published for the secret.

The Node.js sample in that article hex-decodes the header as received,
`sha256=` prefix included; `Buffer.from('sha256=…', 'hex')` is empty, so that
sample rejects every genuine call. Strip the prefix first, as below.

`scripts/verify_webhook.py` checks a captured body by hand:

```bash
SMSMODE_WEBHOOK_SECRET=… python3 scripts/verify_webhook.py --signature "sha256=…" < body.json
```

## Python handler

```python
import hashlib, hmac, json, os

SECRET = os.environ["SMSMODE_WEBHOOK_SECRET"].encode()

def is_from_smsmode(raw_body: bytes, header: str | None) -> bool:
    if not header or not header.strip().startswith("sha256="):
        return False
    try:
        received = bytes.fromhex(header.strip()[len("sha256="):])
    except ValueError:
        return False
    expected = hmac.new(SECRET, raw_body, hashlib.sha256).digest()
    return hmac.compare_digest(expected, received)

# Flask: raw = request.get_data(); header = request.headers.get("X-Smsmode-256")
# FastAPI: raw = await request.body(); header = request.headers.get("x-smsmode-256")
# if not is_from_smsmode(raw, header): return 403
# event = json.loads(raw)
```

## Node.js handler

```js
const crypto = require("crypto");

function isFromSmsmode(rawBody, header, secret) {
  if (typeof header !== "string" || !header.trim().startsWith("sha256=")) return false;
  const received = Buffer.from(header.trim().slice("sha256=".length), "hex");
  const expected = crypto.createHmac("sha256", secret).update(rawBody).digest();
  return received.length === expected.length && crypto.timingSafeEqual(received, expected);
}

// Express: keep the raw bytes for this route.
app.post("/webhooks/smsmode", express.raw({ type: "*/*" }), (req, res) => {
  if (!isFromSmsmode(req.body, req.get("X-Smsmode-256"), process.env.SMSMODE_WEBHOOK_SECRET)) {
    return res.sendStatus(403);
  }
  const event = JSON.parse(req.body);
  // record, then answer quickly
  res.sendStatus(200);
});
```

## Retries and idempotency

When a callback is not acknowledged, smsmode tries again after 30 seconds,
then 2 minutes, 10 minutes, 1 hour, 5 hours and a last time after 24 hours,
then drops the event (spec). Therefore:

- answer 2xx as soon as the event is recorded, and do slow work afterwards;
- deduplicate: the same report can arrive more than once, and reports can
  arrive out of order. Keep the first final status (`DELIVERED`,
  `UNDELIVERABLE`, `UNDELIVERED`) and ignore later changes;
- answer 2xx to events you choose to ignore (unknown message, already final),
  or they are retried for a day;
- answer 403 to a bad signature: the call did not come from smsmode, or the
  secret differs from the one set in Settings > Webhooks.

## Personal data

Callback bodies contain the phone number and the full text of the message or
reply. Keep them out of logs and error trackers; log `messageId`, `refClient`
and the status instead.
