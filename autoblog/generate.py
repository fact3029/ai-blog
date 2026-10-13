"""AIで記事を自動生成して posts/ に Markdown で保存する。

使い方:  GEMINI_API_KEY=... python generate.py   （使えるAIは llm.py を参照）
"""
import datetime as dt
import hashlib
import os
import re
import sys
from pathlib import Path

import yaml

import llm
from settings import load_config

ROOT = Path(__file__).parent
POSTS = ROOT / "posts"
KEYWORDS = ROOT / "keywords.txt"
JST = dt.timezone(dt.timedelta(hours=9))

SYSTEM = """あなたは日本語の悩み解決記事を書く編集者です。読者は今まさに困っていて、すぐ実行できる具体的な答えを探している人です。
大手サイトの一般論ではなく、そのテーマの「具体的な状況」に正面から答えることで選ばれる記事にします。

品質ルール（厳守）:
- 読者が実際に判断できる具体的な情報（選ぶ基準、数値、注意点、向き不向き）を中心に書く。水増しや同じ内容の繰り返しはしない。
- 事実・仕様・価格は不確かなら断定しない。具体的な価格や型番より「選ぶ基準」と「確認すべき点」を重視する。Web検索が使える場合は最新情報を確認する。
- 実在する特定の個人の体験談や、架空のレビュー・使用感をでっち上げない（「実際に使ってみた」等の虚偽は禁止）。
- 医療・法律・金融の断定的助言はしない。
- 安全上の注意（洗剤を混ぜると危険、素材を傷める、換気が必要など）があれば必ず目立つように書く。
- 手順は番号付きリストで、家にある物でできる方法を先に、専用の道具や洗剤を使う方法を後に書く。
- 商品紹介には次の記法を使う（自動でアフィリエイトリンクに変換される）:
    [[product:Amazonや楽天で検索するキーワード|表示名]]
  例: [[product:電気ケトル 0.8L 空焚き防止|0.8Lクラスの空焚き防止付きケトル]]
  型番を断定できない場合はカテゴリ名や条件でキーワードを作る。1記事あたり3〜6個まで。
- 見出しは ## と ### を使う。冒頭に結論（一番おすすめの方法）を書き、最後に「まとめ」を置く。
- 本文は2500〜3500字程度。

出力形式（この形式以外は出力しない）:
TITLE: 記事タイトル（32字前後、検索されやすい語を含める）
DESCRIPTION: 120字以内の要約
TAGS: タグ1, タグ2, タグ3
---
（ここから Markdown 本文。H1 は書かない）
"""


def add_topics(comments, kws):
    """「Run workflow」画面で入力されたテーマ（改行・読点・カンマ区切り）を先頭に追加する。"""
    raw = os.environ.get("ADD_TOPICS", "")
    new = [t.strip() for t in re.split(r"[\n,、，]", raw) if t.strip()]
    if new:
        print("テーマを追加:", new)
        kws = new + [k for k in kws if k not in new]
        write_keywords(comments, kws)
    return kws


def summary(lines):
    """実行結果を GitHub のジョブ概要（iPhone の GitHub アプリでも見られる）に書く。"""
    print("\n".join(lines))
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")


def read_keywords():
    if not KEYWORDS.exists():
        return [], []
    lines = KEYWORDS.read_text(encoding="utf-8").splitlines()
    comments = [l for l in lines if l.startswith("#")]
    kws = [l.strip() for l in lines if l.strip() and not l.startswith("#")]
    return comments, kws


def write_keywords(comments, kws):
    KEYWORDS.write_text("\n".join(comments + kws) + "\n", encoding="utf-8")


def existing_titles():
    titles = []
    for p in sorted(POSTS.glob("*.md")):
        front = p.read_text(encoding="utf-8").split("---", 2)[1]
        titles.append(yaml.safe_load(front).get("title", ""))
    return titles


def call_ai(cfg, system, prompt, use_search=False):
    text, used = llm.complete(cfg["generate"]["providers"], system, prompt, use_search)
    print(f"  使用AI: {used['name']} / {used['model']}")
    return text


def refill_keywords(cfg, kws):
    avoid = "\n".join(existing_titles()[-200:] + kws)
    prompt = (
        f"ジャンル: {cfg['niche']}\n\n"
        "このジャンルで、実際に人が検索しそうな悩みの記事テーマを20個考えてください。\n"
        "条件: 大手サイトが一般論でしか扱っていない「具体的な組み合わせ」にする"
        "（例: 汚れの種類×素材×場所×時間経過）。ビッグワードは避け、1テーマ1つの具体的な悩みに絞る。"
        "解決に市販の道具や洗剤が役立つテーマを優先。\n"
        "次の既存テーマと重複しないこと:\n" + avoid +
        "\n\n1行1テーマで、テーマだけを出力（番号・記号なし）。"
    )
    text = call_ai(cfg, "あなたはSEOに詳しい日本語メディアの編集長です。", prompt)
    new = [l.strip(" -・*0123456789.、)") for l in text.splitlines()]
    new = [n for n in new if 4 <= len(n) <= 60 and not n.startswith("#")]
    return kws + [n for n in new if n and n not in kws]


def parse_article(text):
    head, sep, body = text.partition("\n---")
    if not sep:
        raise ValueError("出力形式が不正です:\n" + text[:500])
    meta = {}
    for line in head.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip().upper()] = v.strip()
    if not meta.get("TITLE") or len(body.strip()) < 1500:
        raise ValueError("タイトルなし、または本文が短すぎます")
    return meta, body.strip()


def save_post(keyword, meta, body):
    now = dt.datetime.now(JST)
    slug = now.strftime("%Y%m%d") + "-" + hashlib.sha1(keyword.encode()).hexdigest()[:8]
    tags = [t.strip() for t in meta.get("TAGS", "").split(",") if t.strip()]
    front = {
        "title": meta["TITLE"],
        "description": meta.get("DESCRIPTION", ""),
        "date": now.isoformat(timespec="seconds"),
        "tags": tags,
        "keyword": keyword,
    }
    path = POSTS / f"{slug}.md"
    path.write_text("---\n" + yaml.safe_dump(front, allow_unicode=True, sort_keys=False) + "---\n\n" + body + "\n",
                    encoding="utf-8")
    return path


def main():
    cfg = load_config()
    POSTS.mkdir(exist_ok=True)
    comments, kws = read_keywords()
    kws = add_topics(comments, kws)
    base = cfg["site"]["base_url"]
    report = ["## 📝 AI自動ブログ 実行結果", ""]

    if len(kws) < cfg["generate"].get("min_keywords", 5):
        print("キーワードを補充中…")
        kws = refill_keywords(cfg, kws)
        write_keywords(comments, kws)

    made = 0
    for _ in range(cfg["generate"].get("posts_per_run", 1)):
        if not kws:
            break
        keyword = kws[0]
        print(f"生成中: {keyword}")
        try:
            text = call_ai(cfg, SYSTEM, f"記事テーマ: {keyword}", cfg["generate"].get("web_search", True))
            meta, body = parse_article(text)
        except ValueError as e:
            print(f"スキップ: {e}", file=sys.stderr)
            report.append(f"- ⚠️ スキップ: {keyword}（{str(e)[:80]}）")
            kws.pop(0)  # 同じテーマで失敗し続けないように除外
            write_keywords(comments, kws)
            continue
        path = save_post(keyword, meta, body)
        print("保存:", path)
        report.append(f"- ✅ [{meta['TITLE']}]({base}/posts/{path.stem}.html)")
        kws.pop(0)
        write_keywords(comments, kws)
        made += 1
    report += ["", f"今回 {made} 件を公開 / 総記事数 {len(list(POSTS.glob('*.md')))} 件 / 残りテーマ {len(kws)} 件",
               f"サイト: {base}/"]
    summary(report)


if __name__ == "__main__":
    try:
        main()
    except llm.LLMError as e:
        # 無料枠の上限などで今日は書けなかった。テーマは残して明日また試す（公開処理は続行）
        print(f"本日の生成を見送りました: {e}", file=sys.stderr)
        summary(["## ⏸ 本日の記事生成は見送り", "", "無料AIの回数制限などで書けませんでした。テーマは残してあり、明日また試します。",
                 "", f"詳細: {str(e)[:300]}"])
