"""
V6 & Velugu News Desk: collects headlines from many outlets, groups the same
story together, and ranks stories by how many outlets are carrying them.

Runs automatically every 15 minutes on GitHub (see .github/workflows/update.yml)
and writes docs/data/news.json, which the dashboard page reads.
"""
import calendar
import hashlib
import json
import os
import re
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import feedparser
import requests
import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "feeds.yaml"
OUT = ROOT / "docs" / "data" / "news.json"

SECTIONS = ["National", "International", "Business", "Tech",
            "Lifestyle", "Entertainment", "Telangana & Hyd"]
MAX_AGE_HOURS = 30          # ignore anything older than this
PER_SECTION = 40            # stories kept per section
TELUGU_LIMIT = 60           # most stories to draft Telugu headlines for per run
UA = "Mozilla/5.0 (compatible; V6NewsDesk/1.0; +https://github.com)"

STOP = set("""
a an the of in on at to for from by with and or but is are was were be been being
as it its this that these those after before over under into about amid says said
say will would can could may might new news live updates update latest today
video watch photos check here how why what who when where vs his her their they he
she we you our your not no more than up out off top first one two three year years
day days week time report reports know all just get gets got has have had do does
""".split())

SPLIT = re.compile(r"[\s\-\u2013\u2014:;,.!?'\"\u201c\u201d\u2018\u2019()\[\]|/&#%+*=<>]+")


def now_utc():
    return datetime.now(timezone.utc)


def tokens(title):
    out = set()
    for w in SPLIT.split(title.lower()):
        if len(w) < 3 or w in STOP or w.isdigit():
            continue
        # light stemming so "attacks"/"attacked"/"attack" match
        for suf in ("ing", "ed", "es", "s"):
            if w.isascii() and len(w) > 5 and w.endswith(suf):
                w = w[: -len(suf)]
                break
        out.add(w)
    return out


def norm_outlet(name):
    n = (name or "").strip()
    n = re.sub(r"^the\s+", "", n, flags=re.I)
    aliases = {
        "times of india": "Times of India", "toi": "Times of India",
        "economic times": "Economic Times", "et": "Economic Times",
        "ndtv.com": "NDTV", "ndtv profit": "NDTV", "gadgets 360": "NDTV",
        "hindu": "The Hindu", "hindu businessline": "The Hindu BusinessLine",
        "indian express": "Indian Express", "hindustan times": "Hindustan Times",
        "bbc": "BBC News", "bbc.com": "BBC News",
    }
    return aliases.get(n.lower(), n if n else "Unknown")


def fetch(url):
    r = requests.get(url, headers={"User-Agent": UA}, timeout=20)
    r.raise_for_status()
    return feedparser.parse(r.content)


def entry_time(e):
    for key in ("published_parsed", "updated_parsed"):
        t = e.get(key)
        if t:
            return datetime.fromtimestamp(calendar.timegm(t), timezone.utc)
    return None


def read_source(src):
    """Return (items, error) for one feed."""
    try:
        feed = fetch(src["url"])
    except Exception as ex:  # network problems, 404s, blocked sites
        return [], f"{type(ex).__name__}"
    if not feed.entries:
        return [], "no stories in feed"
    items = []
    is_google = "news.google.com" in src["url"]
    cutoff = now_utc().timestamp() - MAX_AGE_HOURS * 3600
    for e in feed.entries[:60]:
        title = (e.get("title") or "").strip()
        link = e.get("link") or ""
        if not title or not link:
            continue
        outlet = src["name"]
        if is_google:
            # Google News titles end with " - Outlet"; the real outlet is in <source>
            src_tag = e.get("source") or {}
            gname = src_tag.get("title") if isinstance(src_tag, dict) else None
            if " - " in title:
                head, tail = title.rsplit(" - ", 1)
                gname = gname or tail
                title = head.strip()
            outlet = gname or outlet
        when = entry_time(e) or now_utc()
        if when.timestamp() < cutoff:
            continue
        items.append({
            "title": re.sub(r"\s+", " ", title),
            "link": link,
            "outlet": norm_outlet(outlet),
            "section": src["section"],
            "time": when,
            "tokens": tokens(title),
        })
    return items, None


def same_story(a, b):
    shared = len(a & b)
    if shared < 2:
        return False
    return shared / len(a | b) >= 0.3 or shared >= 4


def cluster(items):
    clusters = []
    for it in sorted(items, key=lambda x: x["time"], reverse=True):
        if not it["tokens"]:
            continue
        best = None
        for c in clusters:
            if same_story(it["tokens"], c["core"]):
                best = c
                break
        if best is None:
            clusters.append({"items": [it], "core": set(it["tokens"])})
        else:
            best["items"].append(it)
            # keep the cluster's word set close to its first headline so it doesn't drift
            if len(best["items"]) <= 3:
                best["core"] |= it["tokens"]
    return clusters


def pick_section(c, tg_words):
    text = " ".join(i["title"].lower() for i in c["items"])
    if any(w in text for w in tg_words):
        return "Telangana & Hyd"
    votes = Counter(i["section"] for i in c["items"] if i["section"] in SECTIONS)
    if not votes:
        return "National"
    top = max(votes.values())
    for s in SECTIONS:  # tie-break in section order
        if votes.get(s) == top:
            return s


def buzz_level(n):
    return 1 if n <= 1 else 2 if n == 2 else 3 if n <= 4 else 4 if n <= 7 else 5


def build_story(c, tg_words, priority):
    items = c["items"]
    now = now_utc()
    outlets = {}
    for i in sorted(items, key=lambda x: x["time"]):
        outlets.setdefault(i["outlet"], i["link"])
    n = len(outlets)
    first = min(i["time"] for i in items)
    last = max(i["time"] for i in items)
    recent = len({i["outlet"] for i in items if (now - i["time"]).total_seconds() < 3 * 3600})
    hours_old = max((now - last).total_seconds() / 3600, 0)
    score = n * (1 / (1 + hours_old / 12)) + 0.5 * recent
    # headline from the most trusted outlet in the list (order in feeds.yaml), else newest
    lead = sorted(items, key=lambda i: (priority.get(i["outlet"], 999), -i["time"].timestamp()))[0]
    sid = hashlib.sha1(" ".join(sorted(c["core"]))[:200].encode()).hexdigest()[:10]
    return {
        "id": sid,
        "section": pick_section(c, tg_words),
        "headline": lead["title"],
        "link": lead["link"],
        "telugu": None,
        "outlet_count": n,
        "buzz": buzz_level(n),
        "score": round(score, 3),
        "rising": (now - first).total_seconds() < 3 * 3600 and n >= 3,
        "status": "Confirmed" if n >= 2 else "Single source",
        "first_seen": first.isoformat(timespec="seconds"),
        "last_seen": last.isoformat(timespec="seconds"),
        "outlets": [{"name": k, "link": v} for k, v in list(outlets.items())[:12]],
    }


def read_trends(url):
    try:
        feed = fetch(url)
    except Exception:
        return []
    out = []
    for e in feed.entries[:20]:
        out.append({
            "title": e.get("title", ""),
            "traffic": e.get("ht_approx_traffic", ""),
            "link": "https://www.google.com/search?q=" + requests.utils.quote(e.get("title", "")),
        })
    return out


def add_telugu(stories, previous):
    """Draft Telugu headlines with Claude, if an API key is set. Reuses earlier drafts."""
    cache = {s["headline"]: s.get("telugu") for s in previous if s.get("telugu")}
    for s in stories:
        s["telugu"] = cache.get(s["headline"])
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        return
    todo = [s for s in stories if not s["telugu"] and not re.search(r"[\u0C00-\u0C7F]", s["headline"])]
    todo = todo[:TELUGU_LIMIT]
    if not todo:
        return
    prompt = (
        "You are a sub-editor at a Telugu news channel in Hyderabad. Write a short, natural "
        "Telugu TV headline for each English headline below. Keep names correct, no extra facts, "
        "no quotes or emojis. Reply with ONLY a JSON array of strings, same order, same count.\n\n"
        + json.dumps([s["headline"] for s in todo], ensure_ascii=False)
    )
    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            json={"model": os.environ.get("TELUGU_MODEL", "claude-haiku-5-5"),
                  "max_tokens": 4000,
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=90,
        )
        r.raise_for_status()
        text = "".join(b.get("text", "") for b in r.json().get("content", []))
        text = text[text.find("["): text.rfind("]") + 1]
        drafts = json.loads(text)
        if len(drafts) == len(todo):
            for s, t in zip(todo, drafts):
                s["telugu"] = str(t).strip() or None
    except Exception as ex:
        print("Telugu drafts skipped:", type(ex).__name__, file=sys.stderr)


def main():
    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    sources = cfg["sources"]
    tg_words = [w.lower() for w in cfg.get("telangana_keywords", [])]
    priority = {}
    for i, s in enumerate(sources):
        priority.setdefault(norm_outlet(s["name"]), i)

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(read_source, sources))

    items, failed = [], []
    for src, (its, err) in zip(sources, results):
        items.extend(its)
        if err:
            failed.append({"name": src["name"], "section": src["section"], "error": err})

    clusters = cluster(items)
    stories = [build_story(c, tg_words, priority) for c in clusters]
    stories.sort(key=lambda s: s["score"], reverse=True)

    kept, per = [], Counter()
    for s in stories:
        if per[s["section"]] < PER_SECTION:
            kept.append(s)
            per[s["section"]] += 1

    previous = []
    if OUT.exists():
        try:
            previous = json.loads(OUT.read_text(encoding="utf-8")).get("stories", [])
        except Exception:
            previous = []
    add_telugu(kept, previous)

    data = {
        "updated_at": now_utc().isoformat(timespec="seconds"),
        "sources": {"total": len(sources), "ok": len(sources) - len(failed), "failed": failed},
        "headlines_read": len(items),
        "trends": read_trends(cfg["trends_url"]) if cfg.get("trends_url") else [],
        "stories": kept,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(items)} headlines from {data['sources']['ok']}/{len(sources)} sources "
          f"-> {len(kept)} stories in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
