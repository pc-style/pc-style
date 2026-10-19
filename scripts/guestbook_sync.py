"""Send everyone who signed the guestbook to 0x7f.pcstyle.dev, which renders the live window.

Usage: GITHUB_TOKEN=... GUESTBOOK_SECRET=... python3 scripts/guestbook_sync.py <user>
Signed issues (label `guestbook`) stay the source of truth; the site mirrors them.
"""

import json
import os
import sys
import urllib.request

from profile import dither_levels, gql

ENDPOINT = "https://0x7f.pcstyle.dev/api/guests"
QUERY = """query($login: String!) { repository(owner: $login, name: $login) {
  issues(labels: ["guestbook"], first: 100, states: [OPEN, CLOSED], orderBy: {field: CREATED_AT, direction: ASC}) {
    nodes { createdAt author { login avatarUrl(size: 96) } } } } }"""


def main():
    login = sys.argv[1]
    guests, seen = [], set()
    for issue in gql(QUERY, login, os.environ["GITHUB_TOKEN"])["repository"]["issues"]["nodes"]:
        author = issue["author"]
        if not author or author["login"].lower() in seen:
            continue
        seen.add(author["login"].lower())
        levels = "".join(str(v) for v in dither_levels(author["avatarUrl"], 32).ravel())
        guests.append({"login": author["login"], "at": issue["createdAt"], "levels": levels})
    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps({"guests": guests}).encode(),
        headers={"Authorization": f"Bearer {os.environ['GUESTBOOK_SECRET']}", "Content-Type": "application/json", "User-Agent": "pc-style-profile"},
    )
    with urllib.request.urlopen(req, timeout=30) as res:
        print(f"{len(guests)} signed -> {res.read().decode()}")


if __name__ == "__main__":
    main()
