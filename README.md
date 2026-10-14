# 買い時ウォッチ（初期費用0円・iPhoneだけで運用する価格推移サイト）

人気商品の**楽天市場での最安値を毎日自動で記録**し、価格推移のグラフと「今が買い時か」の判定を載せたサイトを自動で公開します。
商品リンクは最初から楽天アフィリエイトリンクになっていて、そこから買われると報酬が入ります。

```
毎朝 6:17 ─▶ AIが追跡商品を追加・解説を作成 ─▶ 楽天APIで全商品の価格を記録 ─▶ サイトを作り直して公開
            (無料AI。楽天で実在確認したものだけ)   (data/ に毎日たまる)           (GitHub Pages)
```

## なぜ新規参入でも戦えるのか

AIに一般知識で記事を書かせるだけでは、誰が作っても同じ内容になり埋もれます。
このサイトの中身は**毎日記録した実際の価格データ**です。データは日がたつほど増え、あとから始めた人には過去の記録を作れません。
「〇〇 最安値」「〇〇 値下がり」「〇〇 買い時」と検索する人は購入直前なので、アフィリエイトとの相性も良いです。
価格・判定はすべて実データから計算し、AIには数字を作らせません（AIの担当は商品の追加候補と解説文だけ）。

## 0円で使うもの

| 用途 | サービス | 費用 |
|---|---|---|
| 価格データ | 楽天ウェブサービス 商品検索API | 0円 |
| 収益化 | 楽天アフィリエイト | 0円 |
| AI（商品追加・解説） | GitHub Models（登録不要）/ Gemini API 無料枠 | 0円 |
| 自動実行・公開 | GitHub Actions + GitHub Pages（公開リポジトリ） | 0円 |

## 初回セットアップ（iPhone の Safari で約20分）

> GitHub の設定画面（Settings）は GitHub アプリには無いので Safari で開きます。
> 項目が見つからないときは、アドレスバー左の「ぁあ」→「デスクトップ用Webサイトを表示」。

1. **Pages をオンにする**
   `github.com/fact3029/ai-blog/settings/pages` →「Build and deployment」の Source を **GitHub Actions** に。
2. **楽天ウェブサービスでアプリを登録する（無料）**
   Safari で [楽天ウェブサービス](https://webservice.rakuten.co.jp/) を開き、楽天会員でログイン →「アプリID発行」。
   - アプリ名：買い時ウォッチ（何でもOK）
   - **許可されたWebサイト：`https://fact3029.github.io/ai-blog/`**（ここが違うと楽天APIが使えません）
   - 発行後の画面に出る **アプリID（applicationId）**・**アクセスキー（accessKey）**・**アフィリエイトID** をメモ。
3. **キーを GitHub に登録する**
   `github.com/fact3029/ai-blog/settings/secrets/actions` →「**Secrets**」タブ → New repository secret で2つ登録：
   - `RAKUTEN_APP_ID` … アプリID
   - `RAKUTEN_ACCESS_KEY` … アクセスキー
   続けて「**Variables**」タブ → New repository variable：
   - `RAKUTEN_AFFILIATE_ID` … アフィリエイトID（これで商品リンクが報酬対象になります）
4. **（おすすめ）無料AIのキーを登録する**
   [Google AI Studio](https://aistudio.google.com/apikey) でキーを発行し、Secrets に `GEMINI_API_KEY` として登録。
   無くても GitHub Models で動きますが、あると無料枠の上限で止まりにくくなります。
5. **初回を手動で動かす**
   GitHub アプリ → ai-blog → Actions →「買い時ウォッチ（価格記録と公開）」→ **Run workflow**。
   緑のチェックが付けば成功。サイトは `https://fact3029.github.io/ai-blog/` で見られます。
6. **Google に知らせる**
   [Search Console](https://search.google.com/search-console) で「URLプレフィックス」にサイトのURLを入力 →
   確認方法「HTMLタグ」のタグをコピーして Variables の `GSC_VERIFICATION` に保存 → もう一度 Run workflow →「確認」。
   確認できたら「サイトマップ」に `sitemap.xml` を送信。

## 運用（ふだんは何もしなくてOK）

- 毎朝、全商品の価格が記録され、AIが新しい商品を最大3件追加します（楽天で3件以上見つかった実在商品だけ）。
- 追跡したい商品があるとき：Actions → Run workflow →「追跡したい商品名」に入力（複数は「、」区切り）。
- 記録が7日分たまると「買い時」の判定が始まり、トップページに「今が買い時の商品」「今日値下がりした商品」が並びます。
- 実行結果は GitHub アプリの Actions 画面で見られます。失敗したときはアプリに通知が届きます。
- 収益は楽天アフィリエイトのサイト／アプリで確認できます。

## 現実的な期待値

- データがたまり、検索エンジンに評価されるまで **3〜6か月** はほぼ収益0円です。
- 楽天アフィリエイトの報酬率は多くのジャンルで売上の数％、報酬は楽天ポイントで受け取ります。
- 楽天APIの仕様（2026年に新方式へ移行済み）や無料AIの無料枠は、提供元の都合で変わることがあります。

## ファイル構成

| ファイル | 役割 |
|---|---|
| `autoblog/watchlist.yaml` | 追跡する商品の一覧（AIと手動で増える） |
| `autoblog/tracker.py` | 楽天APIで価格を取って `data/` に記録 |
| `autoblog/generate.py` | AIで商品を追加・`notes/` に解説を作成 |
| `autoblog/build.py` | グラフ・買い時判定付きのサイトを `_site/` に生成 |
| `autoblog/config.yaml` | サイト名・ジャンルなど（Variables で上書き可） |
