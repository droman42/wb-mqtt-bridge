# Report a problem

Something misbehaved? Press the **bug button** in the top-right corner of any page, describe
the problem in your own words, and send — no account, no forms, no screenshots. Everything a
developer needs to diagnose the issue is packaged and attached automatically.

## How it works

The dialog asks one thing: *what's wrong, in your words* («свет в спальне не включается»,
"the amplifier ignored the input switch"). Where you were when you pressed the button matters:
the report is anchored to that page, so if you were on a device's remote, that device and its
signal-chain neighbors contribute extra detail. You'll see a short confirmation with a report
id when it's sent.

If the bridge can't reach the internet at that moment, the report is saved on the controller
and delivered automatically once the connection returns — you'll see that in the confirmation
too. There's also a politeness valve: at most a few reports per hour; if you hit it, the
dialog asks for a little patience.

## What gets sent

Alongside your description:

- the live state of every device, and — for the devices on the page you were looking at — a
  comparison of what the bridge *believes* against what it last *saved* (the classic symptom
  of a remote pressed behind the bridge's back);
- what the system actually did just before your report: the last few dozen executed commands
  (who asked, what ran, what failed) and the most recent MQTT traffic;
- the active scenario in each room, the day's service log, and the configuration of the
  devices involved;
- the browser's own diagnostics: the in-app action log, console errors, recent API calls,
  and the health of the live-update connections.

Before anything leaves the bridge, a scrubbing pass masks **every password, token and key** —
in configuration and in log excerpts alike. No audio or video is ever involved.

Where it goes matters: reports become tickets in a **private** repository that only the
project owner (and the automation that analyzes reports) can see. They are never posted
publicly.

## Setting it up

Reporting is off by default — the button says so honestly if you press it. Enabling it takes
a private GitHub repository to receive the reports and a fine-grained personal access token
scoped to *that repository only*, with **Issues** and **Contents** write permission.

In `system.json`:

```json
"reports": {
  "enabled": true,
  "repo": "you/your-reports-repo",
  "token_env": "WB_REPORTS_TOKEN"
}
```

Put the token in the service's environment (for a compose deployment, the service's `.env`
on the controller) — never in the config file:

```bash
WB_REPORTS_TOKEN=github_pat_...
```

With the repo or token missing, the bridge starts normally and reporting simply stays off.

## What happens to a report

Each report becomes a ticket in the reports repository, where an automated analyst reads the
bundle, tries to reproduce the problem against the bridge's own test suites, and either
proposes a fix for the maintainer's review or asks a follow-up — in the language you wrote
your description in. The richer your description (what you pressed, what you expected, what
happened instead), the shorter that loop gets.

The same evidence also serves the voice assistant: when you tell Irene about a problem that
involves the smart home, her report automatically includes the bridge's view of the house at
that moment — one ticket, both sides of the story.
