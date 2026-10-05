"""H-DELIST step 2: parse token-level events from Binance CMS titles (cached by delist_fetch_cms.py).

Event types: 'delist' (Binance spot token delisting: "Binance Will Delist X, Y on <date>") and
'monitor' (first Monitoring Tag inclusion: "... Extend the Monitoring Tag to Include X, Y ...").
The 2023-07-26 introduction article's initial Monitoring Tag list is parsed from its body if cached.
Announcement time = CMS releaseDate (ms, UTC). Only announcements < 2026-04-01 are parsed (holdout untouched).
Maps tokens to Binance USDT-M perps by symbol existence only (no prices): <T>USDT or 1000<T>USDT
present in the data.binance.vision daily-klines cache with a bar on the announcement day.
Output: data/raw/web/delist/events.json
"""
import json, re, datetime as dt
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
CMS = ROOT / "data/raw/web/delist/cms"
KL = ROOT / "data/raw/web/momentum/klines"
START = dt.datetime(2023, 7, 26, tzinfo=dt.timezone.utc)
HOLDOUT = dt.datetime(2026, 4, 1, tzinfo=dt.timezone.utc)

MON = re.compile(r"Monitoring Tag (?:to Include|to) (.+?)(?:,? and Remove|, Remove| on \d{4}-\d{2}-\d{2}|$)", re.I)
DEL = re.compile(r"^Binance (?:Will Delist|Announced the First Batch of Vote to Delist Results and Will Delist) (.+?) on \d{4}-\d{2}-\d{2}", re.I)


def split_tokens(s):
    s = s.replace(" & ", ", ").replace(" and ", ", ")
    return [t.strip() for t in s.split(",") if t.strip()]


def text_of(node, out):
    if isinstance(node, dict):
        if node.get("node") == "text":
            out.append(node.get("text", ""))
        for c in node.get("child", []) or []:
            text_of(c, out)
    return out


def main():
    arts = {}
    for c in (161, 49):
        for a in json.loads((CMS / f"catalog_{c}.json").read_text()):
            arts[a["code"]] = a
    events = []
    for a in arts.values():
        t = a["title"]; ts = dt.datetime.fromtimestamp(a["releaseDate"] / 1e3, dt.timezone.utc)
        if ts < START or ts >= HOLDOUT:
            continue
        typ, toks = None, []
        m = MON.search(t)
        if m and re.search(r"Extend the Monitoring Tag", t, re.I):
            typ, toks = "monitor", split_tokens(m.group(1))
        m2 = DEL.search(t)
        if m2:
            typ, toks = "delist", split_tokens(m2.group(1))
        if typ:
            for tok in toks:
                events.append({"token": tok, "type": typ, "ann_ms": a["releaseDate"], "ann_utc": ts.isoformat(),
                               "title": t, "code": a["code"]})
    # 2023-07-26 introduction article: initial monitoring-tag list from body (if cached)
    intro = [a for a in arts.values() if a["title"].startswith("Introducing Seed Tags & Monitoring Tags")]
    intro_note = "not cached"
    for a in intro:
        f = CMS / "bodies" / f"{a['code']}.json"
        if f.exists():
            b = json.loads(f.read_text()); txt = " ".join(text_of(json.loads(b["body"]), []))
            intro_note = txt
    syms = {p.stem for p in KL.glob("*.parquet")}
    out = []
    for e in sorted(events, key=lambda e: e["ann_ms"]):
        cand = [s for s in (f"{e['token']}USDT", f"1000{e['token']}USDT") if s in syms]
        e["perp"] = None; e["perp_note"] = "no Binance USDT-M perp in archive"
        if cand:
            k = pd.read_parquet(KL / f"{cand[0]}.parquet", columns=["open_time"])
            day = (e["ann_ms"] // 86400000) * 86400000
            if (k.open_time == day).any():
                first = int(k.open_time.min())
                e["perp"] = cand[0]; e["perp_first_bar_ms"] = first
                e["perp_age_days_at_ann"] = (day - first) / 86400000
                e["perp_note"] = "ok"
            else:
                e["perp_note"] = f"{cand[0]} has no bar on announcement day"
        out.append(e)
    (ROOT / "data/raw/web/delist/events.json").write_text(json.dumps({"events": out, "intro_body_text": intro_note}, indent=1))
    df = pd.DataFrame(out)
    df["split"] = pd.cut(pd.to_datetime(df.ann_utc), [pd.Timestamp("2000", tz="UTC"), pd.Timestamp("2025-07-01", tz="UTC"), pd.Timestamp("2026-04-01", tz="UTC")], labels=["train", "validation"], right=False)
    print(df.groupby(["split", "type"], observed=True).agg(n=("token", "size"), with_perp=("perp", lambda s: s.notna().sum())))
    print(df[df.perp.isna()][["ann_utc", "token", "type", "perp_note"]].to_string())


if __name__ == "__main__":
    main()
