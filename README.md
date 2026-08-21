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
inside it. `status` is `ongoing` or `resolved`. Plain English, no
internals: name what a user experiences and what we know, never
architecture. Push to deploy.

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
