"""config.yaml を読み、GitHub の「Variables」（環境変数）で上書きする。

iPhone だけで運用できるように、よく変える設定はファイルを編集しなくても
GitHub の Settings → Secrets and variables → Actions → Variables から入力できるようにしている。
"""
import os
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).parent

# 環境変数名 → (config のセクション, キー)
OVERRIDES = {
    "SITE_TITLE": ("site", "title"),
    "SITE_DESCRIPTION": ("site", "description"),
    "BASE_URL": ("site", "base_url"),
    "CUSTOM_DOMAIN": ("site", "custom_domain"),
    "GSC_VERIFICATION": ("site", "gsc_verification"),
    "AMAZON_TAG": ("monetize", "amazon_tag"),
    "RAKUTEN_AFFILIATE_ID": ("monetize", "rakuten_affiliate_id"),
    "ADSENSE_CLIENT": ("monetize", "adsense_client"),
    "POSTS_PER_RUN": ("generate", "posts_per_run"),
}


def default_base_url():
    """GitHub Actions 上ならリポジトリ名から GitHub Pages の URL を自動で決める。"""
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if "/" not in repo:
        return ""
    owner, name = repo.split("/", 1)
    host = f"https://{owner.lower()}.github.io"
    return host if name.lower() == f"{owner.lower()}.github.io" else f"{host}/{name}"


def load_config():
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    for env, (section, key) in OVERRIDES.items():
        value = os.environ.get(env, "").strip()
        if value:
            cfg.setdefault(section, {})[key] = int(value) if key == "posts_per_run" else value
    if os.environ.get("NICHE", "").strip():
        cfg["niche"] = os.environ["NICHE"].strip()

    site = cfg["site"]
    # Search Console の確認タグを丸ごと貼り付けても content の値だけ取り出す
    m = re.search(r'content="([^"]+)"', site.get("gsc_verification") or "")
    if m:
        site["gsc_verification"] = m.group(1)
    if site.get("custom_domain"):
        site["base_url"] = "https://" + site["custom_domain"]
    elif not site.get("base_url") or "example" in site["base_url"]:
        site["base_url"] = default_base_url() or "http://localhost:8000"
    site["base_url"] = site["base_url"].rstrip("/")
    return cfg
