# AI 自動ブログ（初期費用0円・放置型の収益化サイト）

GitHub Actions が毎朝、無料のAIに購入ガイド記事を1本書かせて、静的サイトとして GitHub Pages に自動で公開します。
収益源は **Amazonアソシエイト** と **楽天アフィリエイト** です（どちらも登録無料）。
最初の設定さえ終われば、記事テーマの補充・執筆・公開・サイトマップの更新まで全部自動で動きます。

```
毎日 7:17 JST ─▶ generate.py ─▶ posts/*.md をコミット ─▶ build.py ─▶ GitHub Pages に公開
                 (無料AI)                                 (アフィリエイトリンク埋め込み)
```

## 0円で使うもの

| 用途 | サービス | 費用 |
|---|---|---|
| 文章生成AI | GitHub Models（登録不要）/ Gemini API 無料枠 | 0円（1日の回数制限内） |
| 自動実行 | GitHub Actions（公開リポジトリ） | 0円 |
| サイト公開 | GitHub Pages（`ユーザー名.github.io/リポジトリ名`） | 0円 |
| 収益化 | Amazonアソシエイト・楽天アフィリエイト | 0円 |

AIは `config.yaml` の `providers` を上から順に試し、無料枠の上限などで失敗したら次を使います。
全部失敗した日は記事を書かずに終わり、そのテーマは翌日に回されます（エラーで止まることはありません）。

## iPhone だけで使う前提の設計

- **パソコン不要**：記事の生成・公開はすべて GitHub のサーバー上で動きます。iPhone の電源が切れていても毎日動きます。
- **ファイル編集不要**：設定は GitHub の「Variables」画面に入力するだけ（`config.yaml` を開く必要なし）。
- **サイトのURLは自動設定**：リポジトリ名から `https://ユーザー名.github.io/リポジトリ名` を自動で決めます。
- **テーマ追加はボタンから**：「Run workflow」画面の入力欄に書くだけで、次の記事から優先して使われます。
- **結果は GitHub アプリで確認**：実行ごとに「公開した記事・総記事数・残りテーマ」の概要が表示されます。
  失敗したときは GitHub アプリにプッシュ通知が届きます（アプリの通知設定で Actions をオン）。

> ⚠️ 下の設定画面（Settings）は GitHub アプリには無いので、**Safari で github.com を開いて**操作します。
> 画面が狭くて項目が見つからないときは、Safari のアドレスバー左の「ぁあ」→「デスクトップ用Webサイトを表示」。

## 初回セットアップ（iPhone の Safari で約30分・すべて無料）

1. **公開リポジトリを用意する** … ✅ 済み（このリポジトリ）
2. **Pages をオンにする**
   リポジトリ → Settings → Pages → 「Build and deployment」の Source を **GitHub Actions** に変更。
3. **（おすすめ）無料AIのキーを登録する**
   Safari で [Google AI Studio](https://aistudio.google.com/apikey) を開き、Googleアカウントでログイン →「APIキーを作成」→ コピー。
   リポジトリ → Settings → Secrets and variables → Actions →「**Secrets**」タブ → New repository secret
   → Name に `GEMINI_API_KEY`、Secret に貼り付けて保存。
   （登録しなくても GitHub Models で動きますが、2つあると片方の上限に達しても止まりにくくなります）
4. **サイトの設定を入力する**
   同じ画面の「**Variables**」タブ → New repository variable で、必要なものだけ追加：

   | Name | 入力例 | 内容 |
   |---|---|---|
   | `SITE_TITLE` | 暮らしの道具ラボ | サイト名 |
   | `SITE_DESCRIPTION` | 家電・日用品の選び方を解説 | サイトの説明 |
   | `NICHE` | 一人暮らし向け家電の選び方と比較 | 記事のジャンル（AIはこれに沿ってテーマを考える） |
   | `RAKUTEN_AFFILIATE_ID` | 1a2b3c4d.5e6f7a8b.… | 楽天アフィリエイトID |
   | `AMAZON_TAG` | yourname-22 | Amazonアソシエイトのタグ |
   | `GSC_VERIFICATION` | `<meta name="google-site-verification" …>` | Search Console の確認タグ（丸ごと貼ってOK） |

5. **初回を手動で動かす**
   GitHub アプリ（または Safari）→ リポジトリ → Actions →「AI 自動ブログ」→ **Run workflow**。
   数分後に緑のチェックが付けば成功。実行結果の画面に公開された記事のリンクが出ます。
6. **アフィリエイトに登録する（Safari で）**
   - [楽天アフィリエイト](https://affiliate.rakuten.co.jp/)：楽天会員ならすぐ使えます。IDは楽天アフィリエイトのサイトの「サイト登録・ID確認」付近で確認できます。
   - [Amazonアソシエイト](https://affiliate.amazon.co.jp/)：記事が10本ほどたまってから申請すると審査に通りやすいです。
     登録するサイトURLは手順5の実行結果に出る `https://…github.io/…` です。
7. **Google に知らせる**
   Safari で [Search Console](https://search.google.com/search-console) →「URLプレフィックス」にサイトのURLを入力
   → 確認方法「HTMLタグ」のタグをコピーして、手順4の `GSC_VERIFICATION` に保存 → Run workflow をもう一度実行 → 「確認」。
   確認できたら「サイトマップ」に `sitemap.xml` と入力して送信。

## 運用（ふだんは何もしなくてOK）

- 毎朝 7:17 ごろに1記事ずつ自動で増えます。
- 書いてほしいテーマがあるとき：Actions →「AI 自動ブログ」→ Run workflow →「書いてほしいテーマ」欄に入力して実行
  （複数は「、」区切り。記事は書かずにテーマだけ追加したいときは「記事を生成する」をオフ）。
- テーマが少なくなると、AIがジャンルに合った新テーマを20個自動で補充します。
- 1日の記事数を増やしたいとき：Variables に `POSTS_PER_RUN` を追加（無料AIの回数制限があるので 2〜3 まで推奨）。
- 収益の確認：楽天アフィリエイト・Amazonアソシエイトのアプリやサイトでレポートを見られます。

## 費用と現実的な期待値

- **ずっと0円で運用できます。** 無料AIの1日の回数制限は、1日1本のペースなら十分に収まる見込みです
  （GitHub・Google 側が無料枠の内容を変えることはあります）。
- **無料AIの弱点**：Web検索ができず、最新の価格や新製品には弱いため、「選び方・比べるポイント」中心の記事にしてあります。
  収益が出てきたら、有料の Claude（`providers` の anthropic）に切り替えると、Web検索付きで質の高い記事になります（1記事あたり数十円程度）。
- **広告（AdSense）**：独自ドメイン（年1,000〜2,000円）が必要なため、0円構成では使いません。収益が出てから追加できます。
- **収益**：検索エンジンに評価されるまで通常 **3〜6か月** かかり、最初の数か月はほぼ0円です。
  AIが書いた記事は世の中に大量にあるため、ジャンル選びと記事の質で結果が大きく変わります。
  「確実に稼げる」ものではなく、0円で自動運転できる“宝くじ付きの資産”と考えてください。
- Amazonアソシエイトは登録後180日以内に3件の売上がないとアカウントが閉鎖されます（再申請は可能）。

## 守っていること（BANされないために）

- 全ページに「プロモーションを含みます」と表示（2023年10月施行のステマ規制対応）。
- 架空の体験談やレビューは書かせない、不確かな仕様は断定しない、という執筆ルールをプロンプトに組み込み済み。
- アフィリエイトリンクに `rel="sponsored"` を付与（Google のガイドライン対応）。
- 量産しすぎるとスパム判定されやすいため、初期設定は1日1本です。

## パソコンがある場合（任意）

```bash
cd autoblog
pip install -r requirements.txt
GEMINI_API_KEY=... python generate.py   # 記事を1本生成
python build.py && python -m http.server -d _site 8000
```
