"""AIの担当: 追跡する商品を増やす ＋ 各商品の解説文を書く。

価格データそのものは tracker.py が楽天APIから取る（AIは数字を作らない）。
"""
import datetime as dt
import os
import re
import traceback
from pathlib import Path

import llm
import rakuten
import tracker
from settings import load_config

ROOT = Path(__file__).parent
NOTES = ROOT / "notes"
JST = dt.timezone(dt.timedelta(hours=9))

NOTE_SYSTEM = """あなたは家電・日用品の購入アドバイザーです。指定された商品について、購入を検討している人向けの解説を日本語で書きます。

ルール（厳守）:
- 価格・発売日・スペックの具体的な数値は書かない（価格はサイト側が実データで表示する。不確かな数値は誤情報になる）。
- 架空の体験談・レビューは書かない。
- 構成: 「どんな商品か」「向いている人・向いていない人」「買う前に確認したいポイント（3〜5個）」「比較されやすい選択肢」の4つの ### 見出し。
- 600〜1000字。前置きや締めの挨拶は不要。Markdown で出力。"""


def summary(lines):
    print("\n".join(lines))
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")


def verify_and_add(cfg, watchlist, candidates, limit):
    """楽天で実際に3件以上見つかった商品だけを追加する（AIの思い込みの型番を防ぐ）。"""
    known = {tracker.norm(w["keyword"]) for w in watchlist}
    added = []
    for c in candidates:
        if len(added) >= limit:
            break
        if tracker.norm(c["keyword"]) in known:
            continue
        try:
            items = tracker.fetch(c, cfg)
        except rakuten.RakutenError as e:
            print(f"  確認失敗: {c['keyword']}: {e}")
            break
        if len(items) >= 3:
            watchlist.append(c)
            known.add(tracker.norm(c["keyword"]))
            added.append(c)
            print(f"  追加: {c['label']}（{len(items)}件）")
        else:
            print(f"  見送り: {c['label']}（該当 {len(items)}件）")
    return added


def parse_candidates(text):
    """「表示名 | 検索キーワード | 必須語,必須語 | カテゴリ」形式の行を読む。"""
    out = []
    for line in text.splitlines():
        parts = [p.strip() for p in line.strip(" -・*").split("|")]
        if len(parts) < 3 or not parts[1]:
            continue
        match = [m.strip() for m in re.split(r"[,、]", parts[2]) if m.strip()]
        out.append({"label": parts[0], "keyword": parts[1], "match": match or parts[1].split(),
                    "category": parts[3] if len(parts) > 3 else ""})
    return out


def expand_watchlist(cfg, watchlist):
    gen = cfg["generate"]
    if len(watchlist) >= gen.get("max_products", 80):
        return []
    have = "\n".join(w["label"] for w in watchlist)
    prompt = (
        f"ジャンル: {cfg['niche']}\n\n"
        "このジャンルで、楽天市場で多く売られていて価格が変動しやすく、購入前に「最安値」や「買い時」を調べられやすい"
        "人気商品を15個挙げてください。実在が確実なロングセラー・定番品を優先し、存在があいまいな新製品や型番は挙げないこと。\n"
        f"既に追跡中（重複禁止）:\n{have}\n\n"
        "出力形式（1行1商品、説明不要）:\n表示名 | 楽天での検索キーワード | 商品名に必ず含まれる語（カンマ区切り、2〜3語） | カテゴリ\n"
        "例: ダイソン V12 Detect Slim | ダイソン V12 Detect Slim 本体 | V12,Detect | コードレス掃除機"
    )
    text, used = llm.complete(gen["providers"], "あなたは家電・日用品の市場に詳しいバイヤーです。", prompt)
    print(f"  使用AI: {used['name']}")
    return verify_and_add(cfg, watchlist, parse_candidates(text), gen.get("add_per_run", 3))


def write_notes(cfg, watchlist):
    NOTES.mkdir(exist_ok=True)
    done = []
    for w in watchlist:
        if len(done) >= cfg["generate"].get("notes_per_run", 2):
            break
        path = NOTES / f"{tracker.slug(w['keyword'])}.md"
        if path.exists():
            continue
        text, used = llm.complete(cfg["generate"]["providers"], NOTE_SYSTEM,
                                  f"商品: {w['label']}（カテゴリ: {w.get('category', '')}）")
        if len(text) < 300:
            print(f"  解説が短すぎるため保留: {w['label']}")
            continue
        path.write_text(text.strip() + "\n", encoding="utf-8")
        print(f"  解説を作成: {w['label']}（{used['name']}）")
        done.append(w)
    return done


def main():
    cfg = load_config()
    watchlist = tracker.load_watchlist()
    report = ["## 📈 価格トラッカー AI作業の結果", ""]

    # iPhone の「Run workflow」画面から入力された商品を追加
    manual = [t.strip() for t in re.split(r"[\n,、，]", os.environ.get("ADD_PRODUCTS", "")) if t.strip()]
    if manual and rakuten.configured():
        cands = [{"label": t, "keyword": t, "match": t.split(), "category": ""} for t in manual]
        for c in verify_and_add(cfg, watchlist, cands, len(cands)):
            report.append(f"- ➕ 手動追加: {c['label']}")

    try:
        if rakuten.configured():
            for c in expand_watchlist(cfg, watchlist):
                report.append(f"- ➕ AIが追加: {c['label']}")
        for w in write_notes(cfg, watchlist):
            report.append(f"- 📝 解説を作成: {w['label']}")
    except llm.LLMError as e:
        report.append(f"- ⏸ AIの作業は見送り（無料枠の上限など）: {str(e)[:150]}")
    tracker.save_watchlist(watchlist)
    report += ["", f"追跡中の商品: {len(watchlist)}件 / サイト: {cfg['site']['base_url']}/"]
    summary(report)


if __name__ == "__main__":
    try:
        main()
    except Exception:  # AIの作業が失敗しても価格の記録と公開は止めない
        traceback.print_exc()
        summary(["## ⚠️ AIの作業でエラー", "", "価格の記録と公開は続行しました。詳細はログを確認してください。"])
