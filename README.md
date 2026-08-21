# Lyrenth status page

status.lyrenth.com. One static HTML file, no framework, no build: a
status page must be the last thing that can break. It is deliberately
hosted away from Lyrenth's own infrastructure (Vercel project, GitHub
prober) so it stays up when we are down.

Two jobs:

1. `index.html` shows live reachability, probed from the visitor's own
   browser (the page cannot pretend), plus the incident history from
   `incidents.json`.
2. `.github/workflows/probe.yml` probes every 5 minutes from GitHub's
   side and pushes a phone notification via ntfy.sh when something is
   down. Setup steps are at the top of that file.

## Updating incidents

Edit `incidents.json`, newest incident first, newest update first
inside it. Plain English, no internals: name what a user experiences
and what we know, never architecture. Push to deploy.

Fields, and why the machine-readable ones matter:

    date        the day it began, YYYY-MM-DD
    title       one line a customer would recognise
    status      investigating | identified | monitoring | resolved
    severity    major (served nothing) | degraded (served, badly)
    started     ISO 8601 UTC, e.g. 2026-08-21T12:55:00Z
    resolved    same, omitted while the incident is open
    components  which of website, api, reads, mcp were affected
    updates     newest first, each with a human time and text

`severity`, `started`, `resolved` and `components` are what the uptime
bars are computed from, and they exist because the probe cannot report
an outage it was not running for. Recording began on 21 August, hours
after that day's outage ended, so the samples for that day hold no
failures at all: without the incident record the page would have shown
100 percent for a day we served nothing for nearly four hours. A day
carrying an incident is always counted from the incident. Fill these
fields in, or the page will quietly overstate the service.

## Deploy (owner, once)

1. Create a GitHub repository (public keeps Actions minutes unlimited;
   the content is public anyway) under the `lyrenth` org and push this
   folder to it.
2. In Vercel: Add New Project, import that repository, framework
   preset "Other", no build command, output directory left empty.
3. Add the domain `status.lyrenth.com` to the project; create the DNS
   record Vercel shows.
4. Add the repository secret `NTFY_TOPIC` (a long random string) and
   subscribe to it in the ntfy app on your phone.
