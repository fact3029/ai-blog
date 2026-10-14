"""data/*.json（毎日の価格記録）と notes/*.md（AIの解説）から静的サイト（_site/）を生成する。"""
import datetime as dt
import html
import json
import shutil
import statistics
from pathlib import Path

import markdown

from settings import load_config

ROOT = Path(__file__).parent
OUT = ROOT / "_site"

CSS = """
:root{--bg:#fff;--fg:#1f2328;--muted:#656d76;--accent:#bf0000;--card:#f6f8fa;--line:#d0d7de;--good:#1a7f37;--bad:#cf222e;--mid:#9a6700;--chart:#bf0000;--chart2:#8c959f}
@media (prefers-color-scheme:dark){:root{--bg:#0d1117;--fg:#e6edf3;--muted:#8d96a0;--accent:#ff7b72;--card:#161b22;--line:#30363d;--good:#3fb950;--bad:#f85149;--mid:#d29922;--chart:#ff7b72;--chart2:#6e7681}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.8 system-ui,-apple-system,"Hiragino Sans","Noto Sans JP",sans-serif}
.wrap{max-width:760px;margin:0 auto;padding:0 16px}header,footer{border-bottom:1px solid var(--line);padding:14px 0}
footer{border-top:1px solid var(--line);border-bottom:0;color:var(--muted);font-size:13px;margin-top:48px}
header a{color:var(--fg);text-decoration:none;font-weight:700}a{color:var(--accent)}
.pr{font-size:12px;color:var(--muted);margin:12px 0}h1{font-size:1.5rem;line-height:1.4}
h2{border-left:4px solid var(--accent);padding-left:10px;margin-top:2em;font-size:1.2rem}
.muted{color:var(--muted);font-size:13px}
.card{display:flex;gap:12px;align-items:center;background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px;margin:10px 0;color:var(--fg);text-decoration:none}
.card img{width:64px;height:64px;object-fit:contain;background:#fff;border-radius:6px;flex:none}
.card .t{font-weight:600;line-height:1.4}.price{font-size:1.6rem;font-weight:700}
.badge{display:inline-block;padding:2px 10px;border-radius:999px;font-size:13px;font-weight:700;color:#fff}
.good{background:var(--good)}.bad{background:var(--bad)}.mid{background:var(--mid)}.wait{background:var(--chart2)}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px;margin:12px 0}
.stats div{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px}.stats b{display:block;font-size:1.15rem}
.chart{width:100%;height:auto;background:var(--card);border:1px solid var(--line);border-radius:8px}
.chart text{fill:var(--muted);font-size:22px}.chart .l1{stroke:var(--chart);fill:none;stroke-width:2.5}.chart .l2{stroke:var(--chart2);fill:none;stroke-width:1.5;stroke-dasharray:4 3}
table{border-collapse:collapse;width:100%;font-size:14px}td,th{border-bottom:1px solid var(--line);padding:8px 6px;text-align:left;vertical-align:top}
.btn{display:inline-block;padding:6px 12px;border-radius:6px;background:var(--accent);color:#fff;text-decoration:none;font-size:14px;white-space:nowrap}
.down{color:var(--good);font-weight:700}.up{color:var(--bad);font-weight:700}
"""


def yen(n):
    return f"{n:,}円"


def load_products():
    products = []
    for p in sorted((ROOT / "data").glob("*.json")):
        rec = json.loads(p.read_text(encoding="utf-8"))
        if not rec.get("history"):
            continue
        rec["slug"] = p.stem
        note = ROOT / "notes" / f"{p.stem}.md"
        rec["note"] = note.read_text(encoding="utf-8") if note.exists() else ""
        rec["verdict"] = verdict(rec["history"])
        products.append(rec)
    return products


def verdict(history):
    """記録から「今が買い時か」を判定する（AIではなく実データで計算）。"""
    h = history[-90:]
    cur = h[-1]["min_effective"]
    low = min(x["min_effective"] for x in history)
    avg = statistics.mean(x["min_effective"] for x in h)
    prev = history[-2]["min_effective"] if len(history) >= 2 else cur
    v = {"current": cur, "low": low, "avg": round(avg), "days": len(history), "diff_prev": cur - prev,
         "vs_avg": (cur - avg) / avg * 100 if avg else 0}
    if len(history) < 7:
        v.update(label="データ収集中", cls="wait", score=0,
                 text=f"記録開始から{len(history)}日目です。1週間ほどで買い時の判定を始めます。")
    elif cur <= low * 1.02:
        v.update(label="記録上の最安値圏", cls="good", score=3,
                 text=f"現在の実質最安値 {yen(cur)} は、記録期間中の最安値 {yen(low)} とほぼ同じ水準です。")
    elif cur <= avg * 0.97:
        v.update(label="平均より安い", cls="good", score=2,
                 text=f"直近の平均 {yen(round(avg))} より {abs(v['vs_avg']):.0f}% 安くなっています。")
    elif cur >= avg * 1.05:
        v.update(label="平均より高い", cls="bad", score=-1,
                 text=f"直近の平均 {yen(round(avg))} より {v['vs_avg']:.0f}% 高めです。急がなければ値下がりを待つのも手です。")
    else:
        v.update(label="平均的な価格", cls="mid", score=1,
                 text=f"直近の平均 {yen(round(avg))} と同程度の価格です。")
    return v


def chart(history):
    """価格推移の折れ線グラフ（JavaScript不要のSVG）。"""
    h = history[-180:]
    if len(h) < 2:
        return '<p class="muted">グラフは記録が2日分たまると表示されます。</p>'
    W, H, L, R, T, B = 700, 300, 104, 14, 20, 40
    vals = [x["min_effective"] for x in h] + [x["min"] for x in h]
    lo, hi = min(vals), max(vals)
    pad = max((hi - lo) * 0.1, hi * 0.01)
    lo, hi = lo - pad, hi + pad

    def pts(key):
        return " ".join(f"{L + i * (W - L - R) / (len(h) - 1):.1f},{T + (hi - x[key]) * (H - T - B) / (hi - lo):.1f}"
                        for i, x in enumerate(h))
    grid = "".join(
        f'<line x1="{L}" x2="{W - R}" y1="{T + k * (H - T - B) / 3:.1f}" y2="{T + k * (H - T - B) / 3:.1f}" stroke="currentColor" opacity=".12"/>'
        f'<text x="{L - 6}" y="{T + k * (H - T - B) / 3 + 4:.1f}" text-anchor="end">{round(hi - k * (hi - lo) / 3):,}</text>'
        for k in range(4))
    return (f'<svg class="chart" viewBox="0 0 {W} {H}" role="img" aria-label="価格推移グラフ">{grid}'
            f'<polyline class="l2" points="{pts("min")}"/><polyline class="l1" points="{pts("min_effective")}"/>'
            f'<text x="{L}" y="{H - 10}">{h[0]["date"]}</text><text x="{W - R}" y="{H - 8}" text-anchor="end">{h[-1]["date"]}</text></svg>'
            '<p class="muted">赤線: ポイント還元後の実質最安値 / 灰色の点線: 表示価格の最安値（楽天市場・在庫ありの新品）</p>')


def page(cfg, title, desc, content, canonical):
    site = cfg["site"]
    extra = ""
    if site.get("gsc_verification"):
        extra += f'<meta name="google-site-verification" content="{html.escape(site["gsc_verification"])}">'
    return f"""<!doctype html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title><meta name="description" content="{html.escape(desc)}">
<link rel="canonical" href="{canonical}">
<meta property="og:title" content="{html.escape(title)}"><meta property="og:description" content="{html.escape(desc)}">
<style>{CSS}</style>{extra}</head><body>
<header><div class="wrap"><a href="{site['base_url']}/">{html.escape(site['title'])}</a></div></header>
<main class="wrap"><p class="pr">※本ページはプロモーション（広告）を含みます。</p>{content}</main>
<footer><div class="wrap">© {dt.date.today().year} {html.escape(site['title'])}　|　当サイトは楽天アフィリエイトに参加しています。
価格は楽天市場の商品検索APIから毎日取得した記録時点のものです。最新の価格・在庫・送料は販売ページでご確認ください。
解説文はAIを活用して作成しています。</div></footer>
</body></html>"""


def product_page(cfg, p):
    v, base = p["verdict"], cfg["site"]["base_url"]
    change = ""
    if v["days"] >= 2 and v["diff_prev"]:
        cls, sign = ("down", "▼") if v["diff_prev"] < 0 else ("up", "▲")
        change = f'<br><span class="{cls}" style="font-size:1rem">前日比 {sign}{abs(v["diff_prev"]):,}円</span>'
    rows = "".join(
        f'<tr><td>{html.escape(o["name"][:70])}<br><span class="muted">{html.escape(o["shop"])}'
        f'{"・送料込" if o.get("postage_included") else ""}・ポイント{o["point_rate"]}倍</span></td>'
        f'<td><b>{yen(o["price"])}</b><br><span class="muted">実質 {yen(o["effective"])}</span></td>'
        f'<td><a class="btn" href="{html.escape(o["url"])}" rel="sponsored noopener" target="_blank">楽天で見る</a></td></tr>'
        for o in p.get("offers", []))
    note = markdown.markdown(p["note"]) if p["note"] else ""
    first = p["history"][0]["date"]
    content = f"""<h1>{html.escape(p['label'])} の最安値・価格推移</h1>
<p class="muted">楽天市場の価格を毎日記録（{first}〜{p['history'][-1]['date']}・{v['days']}日分）</p>
<p><span class="badge {v['cls']}">{v['label']}</span></p>
<p class="price">実質 {yen(v['current'])}{change}</p>
<p>{v['text']}</p>
<div class="stats"><div>記録上の最安値<b>{yen(v['low'])}</b></div><div>直近の平均<b>{yen(v['avg'])}</b></div>
<div>出品数（本日）<b>{p['history'][-1]['count']}件</b></div></div>
<h2>価格推移</h2>{chart(p['history'])}
<h2>現在の安い順（ポイント還元込み）</h2><table>{rows}</table>
{('<h2>この商品について</h2>' + note) if note else ''}
<p><a href="{base}/">← 他の商品の買い時を見る</a></p>"""
    desc = f"{p['label']}の楽天市場での最安値と価格推移を毎日記録。現在は{v['label']}（実質{yen(v['current'])}）。"
    return page(cfg, f"{p['label']} 最安値と価格推移【毎日更新】", desc, content, f"{base}/p/{p['slug']}.html")


def card(base, p, extra=""):
    v = p["verdict"]
    img = p.get("offers", [{}])[0].get("image", "") if p.get("offers") else ""
    return (f'<a class="card" href="{base}/p/{p["slug"]}.html">'
            + (f'<img src="{html.escape(img)}" alt="" loading="lazy">' if img else "")
            + f'<div><div class="t">{html.escape(p["label"])}</div><span class="badge {v["cls"]}">{v["label"]}</span> '
            f'<b>実質 {yen(v["current"])}</b> {extra}</div></a>')


def build():
    cfg = load_config()
    site, base = cfg["site"], cfg["site"]["base_url"]
    products = load_products()
    shutil.rmtree(OUT, ignore_errors=True)
    (OUT / "p").mkdir(parents=True)

    for p in products:
        (OUT / "p" / f"{p['slug']}.html").write_text(product_page(cfg, p), encoding="utf-8")

    deals = sorted([p for p in products if p["verdict"]["score"] >= 2], key=lambda p: p["verdict"]["vs_avg"])
    drops = sorted([p for p in products if p["verdict"]["diff_prev"] < 0], key=lambda p: p["verdict"]["diff_prev"])[:10]
    cats = {}
    for p in sorted(products, key=lambda p: p["label"]):
        cats.setdefault(p.get("category") or "その他", []).append(p)
    content = f"<h1>{html.escape(site['title'])}</h1><p>{html.escape(site['description'])}</p>"
    if deals:
        content += "<h2>🟢 今が買い時の商品</h2>" + "".join(card(base, p) for p in deals)
    if drops:
        content += "<h2>📉 今日値下がりした商品</h2>" + "".join(
            card(base, p, f'<span class="down">▼{abs(p["verdict"]["diff_prev"]):,}円</span>') for p in drops)
    for cat, ps in cats.items():
        content += f"<h2>{html.escape(cat)}</h2>" + "".join(card(base, p) for p in ps)
    if not products:
        content += "<p>価格データを収集中です。</p>"
    (OUT / "index.html").write_text(page(cfg, site["title"], site["description"], content, base + "/"), encoding="utf-8")

    urls = [base + "/"] + [f"{base}/p/{p['slug']}.html" for p in products]
    (OUT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + "".join(f"<url><loc>{u}</loc></url>" for u in urls) + "</urlset>\n", encoding="utf-8")
    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {base}/sitemap.xml\n", encoding="utf-8")
    if site.get("custom_domain"):
        (OUT / "CNAME").write_text(site["custom_domain"] + "\n", encoding="utf-8")
    (OUT / ".nojekyll").write_text("")
    print(f"{len(products)} 商品のページをビルドしました → {OUT}")


if __name__ == "__main__":
    build()
