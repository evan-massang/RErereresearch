"""Identity verification pass (2026-10-01): primary sources replace search leads.

Sources fetched: each trader's X profile (via the public fxtwitter JSON API),
Decu's wallet post, and kolscan's tracked-wallet list (wallet <-> X handle).
Re-runnable: fetches again and records new snapshots.
"""
import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pipeline import annotations, db, observations  # noqa: E402
from pipeline.ingest_web import ingest_web  # noqa: E402
from pipeline.sources import get_web_adapter  # noqa: E402

con = db.connect()
con.execute("DELETE FROM observations WHERE extractor = 'claude:verify-pass-2026-10-01'")   # re-runnable
http = get_web_adapter("http")
EX = "claude:verify-pass-2026-10-01"
T = {s: annotations.trader_by_slug(con, s) for s in ("decu", "cupsey", "leck", "setuh")}


def snap(url, canonical):
    import time
    from pipeline.provenance import SourceUnavailable
    for attempt in range(4):
        try:
            return ingest_web(con, url, http, canonical_url=canonical, notes="identity verification pass")
        except SourceUnavailable:
            if attempt == 3:
                raise
            time.sleep(3 * (attempt + 1))


def obs(slug, sid, snap_id, content, quote):
    return observations.add_observation(con, source_id=sid, snapshot_id=snap_id, modality="document",
                                        kind="identity_link", content=content, quote=quote,
                                        trader_id=T[slug], extractor=EX, status="reviewed")


def identity(slug, platform, handle, url, status, notes, sid):
    iid = annotations.add_trader_identity(con, T[slug], platform, handle=handle, url=url,
                                          evidence_source_id=sid, verification_status="lead")
    annotations.set_identity_status(con, iid, status, notes, evidence_source_id=sid)
    return iid


def reject_or_keep(slug, platform, handle_like, status, notes):
    for (iid,) in con.execute("SELECT identity_id FROM trader_identities WHERE trader_id=? AND platform=? "
                              "AND lower(handle) LIKE lower(?)", [T[slug], platform, handle_like]).fetchall():
        annotations.set_identity_status(con, iid, status, notes)


# --- X profiles (the traders' own accounts) ---
profiles = {"decu": "notdecu", "cupsey": "Cupseyy", "leck": "LeckSol", "setuh": "Setuhx"}
prof = {}
for slug, h in profiles.items():
    sid, s = snap(f"https://api.fxtwitter.com/{h}", f"https://x.com/{h}")
    prof[slug] = (sid, s)
    text = con.execute("SELECT text FROM web_snapshots WHERE snapshot_id=?", [s]).fetchone()[0]
    obs(slug, sid, s, f"X profile @{h} fetched (fxtwitter JSON mirror of the profile)", f'"screen_name": "{h}"')
    identity(slug, "x", f"@{h}", f"https://x.com/{h}", "verified",
             f"Profile @{h} fetched 2026-10-01; links below are this account's own profile fields.", sid)

d_sid, d_s = prof["decu"]
obs("decu", d_sid, d_s, "Decu's X profile website field links the Twitch channel", "https://www.twitch.tv/decu")
identity("decu", "twitch", "decu", "https://www.twitch.tv/decu", "verified",
         "Linked as the website of X @notdecu (fetched 2026-10-01).", d_sid)
c_sid, c_s = prof["cupsey"]
obs("cupsey", c_sid, c_s, "Cupsey's X profile website field links an Axiom referral page", "https://axiom.trade/@cupsey")
l_sid, l_s = prof["leck"]
obs("leck", l_sid, l_s, "Leck's X profile website field links the YouTube channel", "https://youtube.com/@lecksol")
identity("leck", "youtube", "@LeckSol", "https://youtube.com/@lecksol", "verified",
         "Linked as the website of X @LeckSol (fetched 2026-10-01).", l_sid)
s_sid, s_s = prof["setuh"]
obs("setuh", s_sid, s_s, "Setuh's X bio links the YouTube channel", "https://www.youtube.com/@setuhh")
identity("setuh", "youtube", "@setuhh", "https://www.youtube.com/@setuhh", "verified",
         "Linked in the bio of X @Setuhx (fetched 2026-10-01).", s_sid)
identity("setuh", "telegram", "SetuhTrades", "https://t.me/SetuhTrades", "verified",
         "Website field of X @Setuhx (fetched 2026-10-01).", s_sid)

# --- Decu's own wallet post ---
w_sid, w_s = snap("https://api.fxtwitter.com/notdecu/status/2049865699598672039",
                  "https://x.com/notdecu/status/2049865699598672039")
o = observations.add_observation(con, source_id=w_sid, snapshot_id=w_s, modality="said", kind="quote",
                                 content="Decu posts their trading wallet address on X (2026-04-30)",
                                 quote="My wallet (check for yourself): 4vw54BmAogeRV3vPKWyFet5yf8DTLcREzdSzx4rw9Ud9",
                                 trader_id=T["decu"], extractor=EX, status="reviewed")
identity("decu", "wallet", "4vw54BmAogeRV3vPKWyFet5yf8DTLcREzdSzx4rw9Ud9", None, "verified",
         "Posted by X @notdecu on 2026-04-30 as 'My wallet (check for yourself)'; kolscan also lists it as decu.", w_sid)

# --- kolscan tracked-wallet list (third party, operated by pump.fun) ---
k_sid, k_s = ingest_web(con, str(ROOT / "sources/kolscan_kols.json"), get_web_adapter("file"),
                        canonical_url="https://kolscan.io/leaderboard",
                        notes="KOL list extracted from kolscan.io page data on 2026-10-01")
kol = {k["wallet"]: k for k in json.loads((ROOT / "sources/kolscan_kols.json").read_text())}
for slug, wallet, note in [
    ("cupsey", "2fg5QD1eD7rzNNCsvnhmXFm5hqNgwTTG8p7kQ6f3rx6f", "kolscan lists it as 'Cupsey' with X @Cupseyy"),
    ("leck", "98T65wcMEjoNLDTJszBHGZEX75QRe8QaANXokv4yw3Mp", "kolscan lists it as 'Leck' with X @LeckSol and t.me/LeckSol"),
    ("setuh", "62N1K57D37AUDGp68tnDYKPjGDsaAAtmo357nBtEtuR", "kolscan lists it as 'set' with X @Setuhx"),
]:
    obs(slug, k_sid, k_s, f"kolscan maps wallet {wallet} to {kol[wallet]['name']} / {kol[wallet]['twitter']}", wallet)
    identity(slug, "wallet", wallet, None, "probable",
             note + " (kolscan, pump.fun-operated tracker, 2026-10-01). Not yet claimed by the trader in a fetched post.", k_sid)

reject_or_keep("cupsey", "wallet", "suqh5%", "lead",
               "Not in kolscan's current list (2026-10-01); the older-wallet claim remains an unconfirmed inference.")
reject_or_keep("decu", "x", "@decurionz%", "rejected", "Different account; Decu's verified X is @notdecu.")
reject_or_keep("decu", "youtube", "@DecuTV%", "rejected", "No link from @notdecu (whose website is twitch.tv/decu).")
print(json.dumps(con.execute("SELECT t.slug, i.platform, i.handle, i.verification_status FROM trader_identities i "
                             "JOIN traders t USING (trader_id) WHERE i.verification_status IN ('verified','probable') "
                             "ORDER BY 1,4 DESC,2").fetchall(), indent=0))
