# Keepa 利益検知 Bot (Render 対応)

Keepa API を使って Amazon.co.jp の価格を取得し、仕入れ原価・手数料を考慮した利益が出る商品を Slack Webhook へ通知する常時運用 Bot です。Render の Cron Job（無料プラン想定）でそのまま動きます。

## アーキテクチャ概要
- **実行方式:** Render Cron Job。30 分ごとに `python main.py` を実行。
- **外部サービス:** Keepa API、Slack Incoming Webhook（Webhook URL を差し替えれば他サービスでも利用可）。
- **リトライ:** Keepa API/通知の両方でリトライと指数バックオフを実装。
- **ログ:** 標準出力へ出力。Render のログビューアで確認可能。

## セットアップ
1. 必要な環境変数を `.env` または Render ダッシュボードで設定します。雛形は `.env.example` を参照。
2. 監視対象の商品を `PRODUCT_CATALOG` に JSON 配列で定義します（例は下記）。
3. ローカル動作確認: `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`。
4. テスト実行: `.env` を用意した上で `python main.py`。`DRY_RUN=true` を設定すると通知を送らずログのみ確認できます。

### PRODUCT_CATALOG の例
```json
[
  {
    "asin": "B000000000",
    "cost_price": 1200,
    "min_profit": 300,
    "min_margin": 0.15,
    "min_sale_price": 1800,
    "title": "サンプル商品"
  },
  {
    "asin": "B000111111",
    "cost_price": 2500,
    "min_profit": 500,
    "min_margin": 0.18,
    "title": "別商品のメモ"
  }
]
```
- `asin` / `cost_price`: 必須。
- `min_profit` / `min_margin`: 最低利益額と利益率（いずれも満たした場合のみ通知）。
- `min_sale_price`: 売価がこの金額未満なら除外。
- `title`: 任意のメモ。Keepa の商品名が取得できない場合の保険として利用。

## Render へのデプロイ
1. リポジトリを Render に接続。
2. ルートに置いた `render.yaml` を検出させると、Cron Job `keepa-profit-bot` が自動作成されます。
3. Render の環境変数設定で `KEEPA_API_KEY` / `PRODUCT_CATALOG` / `NOTIFY_WEBHOOK_URL` を登録（**sync: false** のままにしてください）。
4. デプロイ後はスケジュールに沿って自動実行され、条件を満たした商品が Webhook に通知されます。

## 利益判定ロジック
1. Keepa から `buyBox` → `new` → `used` の順で現在価格を取得（履歴から最新値をバックアップ）。
2. 価格を 1/100 して通貨（JPY）へ変換。
3. `revenue_after_fee = current_price * (1 - PROFIT_FEE_RATE) - PROFIT_FBA_FEE`
4. `profit = revenue_after_fee - cost_price`
5. `margin = profit / current_price`
6. `profit >= min_profit` **かつ** `margin >= min_margin` **かつ** `price >= min_sale_price`（指定されている場合）のとき通知。

手数料・FBA 料金は環境変数で調整可能。無料プランを考慮し、各リクエスト間に `RATE_LIMIT_INTERVAL` 秒のスリープを挿入しています。

## ファイル構成
- `main.py`: 実装本体。
- `requirements.txt`: 依存ライブラリ定義。
- `.env.example`: 必要な環境変数のサンプル。
- `render.yaml`: Render Cron Job 用設定。

## テスト方法
- ローカル: `.env` を用意し、`python -m compileall main.py` で構文チェック、`DRY_RUN=true python main.py` で通知なし実行を確認。
- Render: デプロイ後にログを確認し、Webhook 先にメッセージが届くことを確認。
