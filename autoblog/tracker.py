"""watchlist.yaml の商品を楽天で毎日検索し、最安値を data/ に記録する。

ここで記録した日々の価格データが、このサイトだけが持つ“後から真似できない”資産になる。
"""
import datetime as dt
import hashlib
import json
import statistics
import sys
import unicodedata
from pathlib import Path

import yaml

import rakuten
from settings import load_config

ROOT = Path(__file__).parent
DATA = ROOT / "data"
WATCHLIST = ROOT / "watchlist.yaml"
JST = dt.timezone(dt.timedelta(hours=9))
DEFAULT_NG = ["中古", "ケース", "カバー", "フィルム", "保護", "互換", "交換用", "替え", "レンタル", "シール", "ステッカー"]


def slug(keyword):
    return hashlib.sha1(keyword.encode()).hexdigest()[:10]


def norm(s):
    return unicodedata.normalize("NFKC", s).lower().replace(" ", "")


def load_watchlist():
    if not WATCHLIST.exists():
        return []
    return yaml.safe_load(WATCHLIST.read_text(encoding="utf-8")) or []


def save_watchlist(items):
    WATCHLIST.write_text(
        "# 価格を追跡する商品。keyword で楽天を検索し、match の語をすべて含む商品だけを集計する。\n"
        "# AIが自動で追加するほか、iPhone の「Run workflow」画面から追加もできる。\n"
        + yaml.safe_dump(items, allow_unicode=True, sort_keys=False), encoding="utf-8")


def relevant(items, watch):
    """本体と関係ない商品（アクセサリーや別商品）を除く。"""
    words = [norm(w) for w in watch.get("match") or watch["keyword"].split()]
    hits = [i for i in items if all(w in norm(i["name"]) for w in words)]
    if len(hits) >= 3:  # 極端に安いもの（付属品の可能性が高い）を除く
        med = statistics.median(i["price"] for i in hits)
        hits = [i for i in hits if i["price"] >= med * 0.4]
    return hits


def fetch(watch, cfg):
    items = rakuten.search(
        watch["keyword"], cfg["site"]["base_url"], cfg["monetize"].get("rakuten_affiliate_id", ""),
        ng_words=DEFAULT_NG + watch.get("exclude", []))
    return relevant(items, watch)


def record(watch, items, today):
    path = DATA / f"{slug(watch['keyword'])}.json"
    rec = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"history": []}
    rec.update({"keyword": watch["keyword"], "label": watch.get("label", watch["keyword"]),
                "category": watch.get("category", "")})
    if items:
        best = min(items, key=lambda i: i["effective"])
        snap = {
            "date": today,
            "min": min(i["price"] for i in items),
            "min_effective": best["effective"],
            "median": round(statistics.median(i["price"] for i in items)),
            "count": len(items),
        }
        rec["history"] = [h for h in rec["history"] if h["date"] != today] + [snap]
        rec["offers"] = sorted(items, key=lambda i: i["effective"])[:8]
        rec["updated"] = today
    path.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    return rec


def main():
    if not rakuten.configured():
        print("RAKUTEN_APP_ID / RAKUTEN_ACCESS_KEY が未設定のため、価格の記録をスキップします")
        return
    cfg = load_config()
    DATA.mkdir(exist_ok=True)
    today = dt.datetime.now(JST).date().isoformat()
    ok = ng = 0
    for watch in load_watchlist():
        try:
            items = fetch(watch, cfg)
        except rakuten.RakutenError as e:
            print(f"失敗: {watch['keyword']}: {e}", file=sys.stderr)
            ng += 1
            if "403" in str(e) or "401" in str(e):
                break  # 認証の問題は全商品で同じなので打ち切る
            continue
        record(watch, items, today)
        print(f"{watch.get('label', watch['keyword'])}: {len(items)}件"
              + (f" 最安 {min(i['price'] for i in items):,}円" if items else ""))
        ok += 1
    print(f"記録 {ok}件 / 失敗 {ng}件")
    if ok == 0 and ng:
        sys.exit(1)


if __name__ == "__main__":
    main()
