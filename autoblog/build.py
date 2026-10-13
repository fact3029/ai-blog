"""posts/*.md から静的サイト（_site/）を生成する。広告・アフィリエイトリンクもここで埋め込む。"""
import datetime as dt
import html
import re
import shutil
import urllib.parse
from pathlib import Path

import markdown
import yaml

from settings import load_config

ROOT = Path(__file__).parent
OUT = ROOT / "_site"

CSS = """
:root{--bg:#fff;--fg:#1f2328;--muted:#656d76;--accent:#d1242f;--card:#f6f8fa;--line:#d0d7de}
@media (prefers-color-scheme:dark){:root{--bg:#0d1117;--fg:#e6edf3;--muted:#8d96a0;--accent:#ff7b72;--card:#161b22;--line:#30363d}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.85 system-ui,-apple-system,"Hiragino Sans","Noto Sans JP",sans-serif}
.wrap{max-width:760px;margin:0 auto;padding:0 16px}header,footer{border-bottom:1px solid var(--line);padding:14px 0}
footer{border-top:1px solid var(--line);border-bottom:0;color:var(--muted);font-size:13px;margin-top:48px}
header a{color:var(--fg);text-decoration:none;font-weight:700}a{color:var(--accent)}
.pr{font-size:12px;color:var(--muted);margin:12px 0}h1{font-size:1.6rem;line-height:1.4}
h2{border-left:4px solid var(--accent);padding-left:10px;margin-top:2.2em}
.meta{color:var(--muted);font-size:13px}.card{display:block;background:var(--card);border:1px solid var(--line);border-radius:8px;padding:14px;margin:12px 0;color:var(--fg);text-decoration:none}
.card small{color:var(--muted)}.buy{display:inline-flex;gap:8px;flex-wrap:wrap;margin:6px 0}
.buy a{display:inline-block;padding:6px 12px;border-radius:6px;background:var(--card);border:1px solid var(--line);text-decoration:none;font-size:14px}
table{border-collapse:collapse;width:100%;display:block;overflow-x:auto}td,th{border:1px solid var(--line);padding:6px 10px}
img{max-width:100%}.ad{margin:24px 0;min-height:100px}
"""


def load_posts():
    posts = []
    for p in sorted((ROOT / "posts").glob("*.md"), reverse=True):
        _, front, body = p.read_text(encoding="utf-8").split("---", 2)
        meta = yaml.safe_load(front)
        meta["slug"] = p.stem
        meta["body"] = body
        posts.append(meta)
    return posts


def product_links(body, mon):
    """[[product:検索語|表示名]] をアフィリエイトリンクに置換する。"""
    def repl(m):
        query, _, label = m.group(1).partition("|")
        label = label or query
        q = urllib.parse.quote(query.strip())
        links = []
        amazon = f"https://www.amazon.co.jp/s?k={q}"
        if mon.get("amazon_tag"):
            amazon += f"&tag={urllib.parse.quote(mon['amazon_tag'])}"
        links.append(f'<a href="{amazon}" rel="sponsored noopener" target="_blank">Amazonで見る</a>')
        if mon.get("rakuten_affiliate_id"):
            target = urllib.parse.quote(f"https://search.rakuten.co.jp/search/mall/{q}/", safe="")
            rakuten = f"https://hb.afl.rakuten.co.jp/hgc/{mon['rakuten_affiliate_id']}/?pc={target}"
            links.append(f'<a href="{rakuten}" rel="sponsored noopener" target="_blank">楽天で見る</a>')
        return f'\n\n<p><strong>{html.escape(label.strip())}</strong><br><span class="buy">{"".join(links)}</span></p>\n\n'
    return re.sub(r"\[\[product:([^\]]+)\]\]", repl, body)


def ad_unit(mon):
    if not mon.get("adsense_client"):
        return ""
    return (f'<div class="ad"><ins class="adsbygoogle" style="display:block" data-ad-client="{mon["adsense_client"]}" '
            'data-ad-format="auto" data-full-width-responsive="true"></ins>'
            '<script>(adsbygoogle=window.adsbygoogle||[]).push({});</script></div>')


def page(cfg, title, desc, content, canonical):
    site, mon = cfg["site"], cfg["monetize"]
    head_extra = (f'<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={mon["adsense_client"]}" '
           'crossorigin="anonymous"></script>') if mon.get("adsense_client") else ""
    year = dt.date.today().year
    if site.get("gsc_verification"):  # Search Console の所有権確認（HTMLタグ方式）
        head_extra += f'<meta name="google-site-verification" content="{html.escape(site["gsc_verification"])}">'
    return f"""<!doctype html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title><meta name="description" content="{html.escape(desc)}">
<link rel="canonical" href="{canonical}"><link rel="alternate" type="application/rss+xml" href="{site['base_url']}/feed.xml">
<meta property="og:title" content="{html.escape(title)}"><meta property="og:description" content="{html.escape(desc)}">
<style>{CSS}</style>{head_extra}</head><body>
<header><div class="wrap"><a href="{site['base_url']}/">{html.escape(site['title'])}</a></div></header>
<main class="wrap"><p class="pr">※本ページはプロモーション（広告）を含みます。</p>{content}</main>
<footer><div class="wrap">© {year} {html.escape(site['title'])}　|　当サイトはAmazonアソシエイト等のアフィリエイトプログラムに参加しています。
記事はAIを活用して作成しています。価格・仕様は変更されることがあるため、購入前に販売ページでご確認ください。</div></footer>
</body></html>"""


def build():
    cfg = load_config()
    site, mon = cfg["site"], cfg["monetize"]
    base = site["base_url"]
    posts = load_posts()

    shutil.rmtree(OUT, ignore_errors=True)
    (OUT / "posts").mkdir(parents=True)

    for p in posts:
        body_html = markdown.markdown(product_links(p["body"], mon), extensions=["tables", "toc"])
        # 本文中ほど（2つ目の h2 の前）と末尾に広告を入れる
        parts = body_html.split("<h2", 2)
        if len(parts) == 3:
            body_html = parts[0] + "<h2" + parts[1] + ad_unit(mon) + "<h2" + parts[2]
        date = str(p["date"])[:10]
        tags = " ".join(f"#{html.escape(t)}" for t in p.get("tags", []))
        content = f'<article><h1>{html.escape(p["title"])}</h1><p class="meta">{date}　{tags}</p>{body_html}{ad_unit(mon)}</article>'
        url = f"{base}/posts/{p['slug']}.html"
        (OUT / "posts" / f"{p['slug']}.html").write_text(page(cfg, p["title"], p.get("description", ""), content, url),
                                                         encoding="utf-8")

    cards = "".join(
        f'<a class="card" href="{base}/posts/{p["slug"]}.html"><strong>{html.escape(p["title"])}</strong><br>'
        f'<small>{str(p["date"])[:10]}　{html.escape(p.get("description", ""))}</small></a>' for p in posts)
    index = f"<h1>{html.escape(site['title'])}</h1><p>{html.escape(site['description'])}</p>{cards or '<p>記事準備中</p>'}"
    (OUT / "index.html").write_text(page(cfg, site["title"], site["description"], index, base + "/"), encoding="utf-8")

    urls = [base + "/"] + [f"{base}/posts/{p['slug']}.html" for p in posts]
    (OUT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + "".join(f"<url><loc>{u}</loc></url>" for u in urls) + "</urlset>\n", encoding="utf-8")
    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {base}/sitemap.xml\n", encoding="utf-8")
    items = "".join(
        f"<item><title>{html.escape(p['title'])}</title><link>{base}/posts/{p['slug']}.html</link>"
        f"<description>{html.escape(p.get('description', ''))}</description></item>" for p in posts[:20])
    (OUT / "feed.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>{html.escape(site["title"])}</title>'
        f"<link>{base}/</link><description>{html.escape(site['description'])}</description>{items}</channel></rss>\n",
        encoding="utf-8")
    if mon.get("adsense_client"):
        pub = mon["adsense_client"].replace("ca-", "")
        (OUT / "ads.txt").write_text(f"google.com, {pub}, DIRECT, f08c47fec0942fa0\n", encoding="utf-8")
    if site.get("custom_domain"):
        (OUT / "CNAME").write_text(site["custom_domain"] + "\n", encoding="utf-8")
    (OUT / ".nojekyll").write_text("")
    print(f"{len(posts)} 記事をビルドしました → {OUT}")


if __name__ == "__main__":
    build()
