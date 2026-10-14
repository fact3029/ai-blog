"""楽天市場 商品検索API（2026年の新API）の呼び出し。

必要なもの（すべて無料）:
- RAKUTEN_APP_ID      : 楽天ウェブサービスで発行するアプリID（applicationId）
- RAKUTEN_ACCESS_KEY  : 同じく発行されるアクセスキー（accessKey）
- 楽天アフィリエイトID : 渡すと、返ってくる商品URLが最初からアフィリエイトリンクになる
アプリ登録時の「許可されたWebサイト」にはこのサイトのURLを登録し、同じURLを Referer/Origin として送る。
"""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

ENDPOINT = "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20220601"
_last_call = 0.0


class RakutenError(RuntimeError):
    pass


def configured():
    return bool(os.environ.get("RAKUTEN_APP_ID") and os.environ.get("RAKUTEN_ACCESS_KEY"))


def search(keyword, site_url, affiliate_id="", ng_words=(), hits=30):
    """キーワードで在庫ありの新品を検索し、扱いやすい dict のリストで返す。"""
    global _last_call
    params = {
        "applicationId": os.environ["RAKUTEN_APP_ID"],
        "accessKey": os.environ["RAKUTEN_ACCESS_KEY"],
        "format": "json",
        "formatVersion": 2,
        "keyword": keyword,
        "hits": hits,
        "availability": 1,
    }
    if affiliate_id:
        params["affiliateId"] = affiliate_id
    if ng_words:
        params["NGKeyword"] = " ".join(ng_words)
    origin = "/".join(site_url.split("/")[:3])
    req = urllib.request.Request(
        ENDPOINT + "?" + urllib.parse.urlencode(params),
        headers={"Referer": site_url.rstrip("/") + "/", "Origin": origin, "User-Agent": "price-tracker/1.0"},
    )
    # 楽天APIは1秒に1回まで
    wait = 1.1 - (time.time() - _last_call)
    if wait > 0:
        time.sleep(wait)
    _last_call = time.time()
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        body = e.read()[:300].decode(errors="replace")
        if e.code == 404:  # 該当商品なし
            return []
        raise RakutenError(f"楽天API HTTP {e.code}: {body}") from e
    except urllib.error.URLError as e:
        raise RakutenError(f"楽天API 接続エラー: {e}") from e

    items = []
    for it in data.get("Items", []):
        it = it.get("Item", it)  # formatVersion 1/2 の両方に対応
        price = int(it.get("itemPrice") or 0)
        if not price:
            continue
        point_rate = int(it.get("pointRate") or 1)
        images = it.get("mediumImageUrls") or []
        image = images[0] if images else ""
        if isinstance(image, dict):
            image = image.get("imageUrl", "")
        items.append({
            "name": it.get("itemName", ""),
            "price": price,
            "effective": round(price * (1 - point_rate / 100)),  # ポイント還元後の実質価格
            "point_rate": point_rate,
            "postage_included": it.get("postageFlag") == 0,
            "shop": it.get("shopName", ""),
            "url": it.get("affiliateUrl") or it.get("itemUrl", ""),
            "review_count": int(it.get("reviewCount") or 0),
            "review_average": float(it.get("reviewAverage") or 0),
            "image": image,
            "code": it.get("itemCode", ""),
        })
    return items
