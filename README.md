# smsmode agent skill

An [Agent Skill](https://agentskills.io) that teaches coding agents (Claude
Code, Codex, Cursor, OpenCode and other compatible clients) to send, receive
and troubleshoot SMS with the [smsmode](https://www.smsmode.com) REST API.

> Unofficial. Not affiliated with or endorsed by smsmode. Written from
> smsmode's public OpenAPI specs and knowledge base, and checked against the
> live API in October 2026.

## Why

An agent that reads smsmode's OpenAPI spec writes code that works in a demo
and fails quietly in production. The skill gives it what the spec does not
say, or says in places it will not look:

- **Silent character loss.** smsmode sends GSM-7 by default and replaces what
  GSM-7 cannot hold (’ becomes ', emoji become ?), while the message still
  reports `DELIVERED`. The skill picks UNICODE when the text needs it and
  counts the segments you pay for.
- **Replies that seem lost.** The message list returns one encoding per call,
  GSM-7 by default, so replies with accents or emoji only show up with an
  explicit filter.
- **Replies attached to the wrong message.** On a shared short code, smsmode
  attaches a reply to the latest message sent to that phone.
- **Webhooks.** `X-Smsmode-256` HMAC-SHA256 over the raw body, retries over
  24 hours, idempotent handlers.
- **Account traps.** Keys bound to one channel, a channel flow fixed at
  creation, IP allowlists, low default limits, 11-character senders, numbers
  without `+`, dates without offset.
- **Migration from Twilio.** Concept and status maps, and a checklist.

## Install

Claude Code, as a plugin:

```
/plugin marketplace add rmzlb/smsmode-skill
/plugin install smsmode@smsmode-skill
```

Any client supported by the [`skills` CLI](https://github.com/vercel-labs/skills):

```bash
npx skills add rmzlb/smsmode-skill
```

By hand: copy `skills/smsmode/` into your agent's skills directory (for
Claude Code, `~/.claude/skills/smsmode/` or `.claude/skills/smsmode/` in a
project).

## Configure

| Variable | Used by | Where to get it |
|---|---|---|
| `SMSMODE_API_KEY` | `send_sms.py`, `list_messages.py`, your code | smsmode > Settings > API keys. A key sends through the channel it was created in: create it in a transactional channel for notifications, and restrict it to your servers' IPs |
| `SMSMODE_WEBHOOK_SECRET` | `verify_webhook.py`, your webhook handler | the secret you set in smsmode > Settings > Webhooks |

The scripts never print these values. Keep them out of prompts and logs.

## What is inside

```
skills/smsmode/
├── SKILL.md                     # loaded when the skill triggers: rules, gotchas, workflows
├── references/                  # loaded on demand
│   ├── api.md                   # endpoints, fields, limits, statuses, errors, account calls
│   ├── encoding.md              # GSM-7 table, French characters, segment arithmetic
│   ├── replies.md               # two-way SMS, short codes, Time2Chat, matching replies
│   ├── webhooks.md              # signature checks (Python, Node.js), retries, idempotency
│   ├── pricing.md               # subscription plans (Prepaid, Basique, Classique, Medium, Premium), RCS/SMS/Time2Chat rates
│   ├── rcs.md                   # RCS v1 API: BASIC vs SINGLE tiers, buttons, rich cards, carousels
│   └── migrating-from-twilio.md # concept and status maps, checklist
├── scripts/                     # Python 3.9+, standard library only, all with --help
│   ├── sms_segments.py          # encoding + segment count, no network
│   ├── send_sms.py              # validated send, dry run unless --send
│   ├── list_messages.py         # read-only listing, both encodings merged
│   └── verify_webhook.py        # X-Smsmode-256 check, reference implementation
└── evals/
    ├── evals.json               # output-quality scenarios with assertions
    └── trigger_queries.json     # should / should not trigger
```

Examples:

```bash
cd skills/smsmode
python3 scripts/sms_segments.py "C’est noté, à demain !"
# {"encoding": "UNICODE", "characters": 22, "units": 22, "segments": 1, "non_gsm": ["’"], "fits": true}

python3 scripts/send_sms.py --to +33600000000 --text "Votre code : 123456"          # prints the request only
python3 scripts/send_sms.py --to +33600000000 --text "Votre code : 123456" --send   # sends (billed)

python3 scripts/list_messages.py --direction MO     # replies, GSM-7 and UNICODE
```

## Accuracy

Each fact comes from one of three sources, and the text says which when it
matters:

- smsmode's OpenAPI specs (`dev.smsmode.com`);
- smsmode's knowledge base (`support.smsmode.com`);
- calls to the live API with a real account, marked *observed* (October 2026):
  character replacement, the encoding filter, reply attribution, short codes
  shown on handsets, date format, error payloads.

Prices and offers change: the skill tells the agent to read prices from the
API and to check smsmode's pricing page. Corrections are welcome as issues or
pull requests, especially from smsmode.

All phone numbers and identifiers in this repository are fictional
(`33600000000` is the example number of smsmode's own spec). No account data
is included.

## Evaluate

The `evals/` files follow agentskills.io's guides on
[evaluating outputs](https://agentskills.io/skill-creation/evaluating-skills)
and [optimizing descriptions](https://agentskills.io/skill-creation/optimizing-descriptions):
run each prompt of `evals.json` with and without the skill in a fresh session,
grade the assertions, and run `trigger_queries.json` to check the skill loads
when it should and only then. The eval prompts never send an SMS.

Results of the first rounds (October 2026, one run per case, so indicative):

| Model | With the skill | Without |
|---|---|---|
| Claude Haiku, 4 scenarios | 15/20 assertions | 8/20 |
| Claude Sonnet, encoding scenario (after iteration 3) | 6/6 | not run |

Without the skill, agents invented a signature header and HMAC-SHA1, invented
status values, and blamed smsmode for "dropping" Unicode replies. Known
limit: Haiku reads a typographic apostrophe in a prompt as a straight one, so
its cost estimate for such a text is wrong; the code it writes with the skill
still picks the encoding at send time. The trigger queries have not been run
yet.

## Develop

```bash
python3 -m unittest discover -s tests            # script tests, no network
uvx --from skills-ref agentskills validate skills/smsmode
claude plugin validate .                          # if Claude Code is installed
```

Tests cover what costs money or loses data: encoding choice, segment counts,
request validation, answer classification, signature checks, list queries.

## En français

Skill pour agents de code (Claude Code, Codex, Cursor…) : envoyer, recevoir et
diagnostiquer des SMS avec l'API smsmode. Il couvre les pièges que la spec ne
signale pas (encodage GSM-7 qui remplace les caractères sans erreur, réponses
Unicode absentes de la liste par défaut, rattachement des réponses au dernier
SMS envoyé, webhooks signés) et la migration depuis Twilio. Installation :
`npx skills add rmzlb/smsmode-skill`, ou le plugin Claude Code ci-dessus.

## License

[MIT](LICENSE)
