#!/usr/bin/env python3
"""
Sample every component, append the result to history.json, and rebuild
rss.xml from incidents.json.

Run from GitHub Actions every 30 minutes (see .github/workflows/
record.yml). Two reasons it lives there rather than on our own
infrastructure: a status page must not depend on the thing it reports
on, and a probe from outside is the only one that proves what a
customer would experience.

The page reads this file straight from raw.githubusercontent.com, so a
commit here shows up without a redeploy. Thirty minutes is the cadence
because Vercel counts every push as a deployment; the five-minute
alerting probe (probe.yml) is separate and commits nothing.

What is kept, and why the file stays small:

  samples  the last 336 checks, which is seven days at this cadence.
           Fine detail for the response-time chart.
  days     one rollup per day for 90 days: checks, failures and average
           response per component. This is what the uptime bars and the
           uptime percentage are computed from, so the file does not
           grow with time.

Honesty rules this script exists to keep: uptime is only ever computed
from days we actually recorded, and recording_since is published on the
page. A day with no samples is drawn as "no data", never as green.
"""

import json
import os
import pathlib
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent
HISTORY = ROOT / "history.json"
INCIDENTS = ROOT / "incidents.json"
RSS = ROOT / "rss.xml"

SAMPLE_CAP = 336  # seven days at one sample every 30 minutes
DAY_CAP = 90

# A component is "ok" when its endpoint answers with one of the codes
# that mean the service is doing its job. Not every healthy answer is a
# 200: GET on the MCP endpoint is a method the transport does not
# accept, and answering 405 proves the service is there and speaking.
CHECKS = [
    {"id": "website", "url": "https://www.lyrenth.com/", "ok": [200]},
    {"id": "api", "url": "https://api.lyrenth.com/healthz", "ok": [200]},
    {"id": "reads", "url": "https://api.lyrenth.com/v1/stats", "ok": [200]},
    {"id": "mcp", "url": "https://api.lyrenth.com/mcp", "ok": [200, 400, 405]},
]

USER_AGENT = "Lyrenth-status-recorder (+https://status.lyrenth.com)"


def probe(url: str, ok_codes: list[int]) -> tuple[int, int, bool, bytes]:
    """Return (status, milliseconds, ok, body). A transport failure is
    status 0, which the page renders as down rather than as a gap."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read(65536)
            ms = int((time.monotonic() - started) * 1000)
            return resp.status, ms, resp.status in ok_codes, body
    except urllib.error.HTTPError as e:
        ms = int((time.monotonic() - started) * 1000)
        return e.code, ms, e.code in ok_codes, b""
    except Exception:
        ms = int((time.monotonic() - started) * 1000)
        return 0, ms, False, b""


def load(path: pathlib.Path, fallback):
    try:
        return json.loads(path.read_text())
    except Exception:
        return fallback


def main() -> None:
    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    today = now.strftime("%Y-%m-%d")

    history = load(HISTORY, {})
    history.setdefault("recording_since", stamp)
    history.setdefault("samples", [])
    history.setdefault("days", {})

    results = {}
    docs = None
    for check in CHECKS:
        status, ms, ok, body = probe(check["url"], check["ok"])
        results[check["id"]] = [status, ms]
        if check["id"] == "reads" and ok and body:
            # The corpus counter comes from the same call that proves the
            # read path serves, so the number on the page is never older
            # than the check next to it.
            try:
                docs = int(json.loads(body).get("indexed_documents") or 0) or None
            except Exception:
                docs = None

        day = history["days"].setdefault(today, {})
        prev = day.get(check["id"], [0, 0, 0])
        checks, fails, avg = prev[0], prev[1], prev[2]
        day[check["id"]] = [
            checks + 1,
            fails + (0 if ok else 1),
            # Running average, so a day's row stays three numbers however
            # many samples it holds.
            int(round((avg * checks + ms) / (checks + 1))),
        ]

    sample = {"t": stamp, "r": results}
    if docs:
        sample["docs"] = docs
    history["samples"].append(sample)
    history["samples"] = history["samples"][-SAMPLE_CAP:]
    history["days"] = dict(sorted(history["days"].items())[-DAY_CAP:])
    history["updated"] = stamp
    history["components"] = [c["id"] for c in CHECKS]

    HISTORY.write_text(json.dumps(history, separators=(",", ":")) + "\n")
    write_rss(now)

    down = [cid for cid, (status, _) in results.items() if status == 0 or not any(
        status in c["ok"] for c in CHECKS if c["id"] == cid)]
    print(f"recorded {stamp}: " + ", ".join(
        f"{cid}={v[0]}/{v[1]}ms" for cid, v in results.items()
    ) + (f"; DOWN: {down}" if down else ""))


def write_rss(now: datetime) -> None:
    """One item per incident update, newest first. A feed reader is the
    only way to follow this page without visiting it, and it costs a few
    lines to keep one."""
    incidents = load(INCIDENTS, {"incidents": []}).get("incidents", [])
    items = []
    for inc in incidents:
        for upd in inc.get("updates", []):
            title = f"{inc.get('status', 'update').title()}: {inc.get('title', '')}"
            items.append(
                "<item>"
                f"<title>{esc(title)}</title>"
                f"<description>{esc(upd.get('text', ''))}</description>"
                f"<pubDate>{esc(upd.get('time', ''))}</pubDate>"
                f"<guid isPermaLink=\"false\">{esc(inc.get('date', '') + upd.get('time', ''))}</guid>"
                "<link>https://status.lyrenth.com</link>"
                "</item>"
            )
    RSS.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0"><channel>'
        "<title>Lyrenth status</title>"
        "<link>https://status.lyrenth.com</link>"
        "<description>Incidents and maintenance for the Lyrenth API and website.</description>"
        f"<lastBuildDate>{now.strftime('%a, %d %b %Y %H:%M:%S +0000')}</lastBuildDate>"
        + "".join(items)
        + "</channel></rss>\n"
    )


def esc(s: str) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


if __name__ == "__main__":
    main()
