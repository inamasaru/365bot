# 365bot

このリポジトリは自動収益システム「365億Bot」のコードと設定を含みます。自動化プラットフォームとしてGitHub Actionsで実行され、LINE・Notion・（任意）Stripeと連携します。

## セットアップ手項

1. リポジトリをクローンするか、GitHub上で作成されたこのリポジトリにアクセスします。
2. GitHubのリポジトリ「Settings > Secrets and variables > Actions」で以下のリポジトリシークレットを登録します。値はシークレットとして保存され、コードに含めません。
   - `LINE_BOT_TOKEN` – LINE Messaging APIのチャネルアクセストークン。
   - `NOTION_TOKEN` – Notionの内部インテグレーショントークン。
   - `NOTION_DB_ID` – リード管理用NotionデータベースID。
   - `STRIPE_SECRET_KEY` – (任意) Stripeのシークレットキー。
3. 必要に応じて `.env.sample` をコピーして `.env` を作成し、ローカル実行用の値を記入します。
4. 依存パッケージをインストールします：
   ```bash
   pip install -r requirements.txt
   ```
5. `config.yaml` にジャンル情報（商品名、価格、通知先LINEユーザーIDなど）を設定します。複数ジャンルを追加する場合は `genre:` 配列に追記してください。

## Notionデータベース

Notionで空のデータベースを作成し、以下のプロパティを追加します。作成後のURL先頭32文字を `NOTION_DB_ID` として設定してください。

- **Name** (タイトル) – リード名または外部ID
- **External_ID** (リッチテキスト) – 重複防止キーとなる外部ID
- **Email** (Email) – メールアドレス
- **Phone** (Phone) – 電話番号
- **Product** (リッチテキスト) – 商品名
- **Price** (Number) – 価格（円）
- **CVR** (Number) – 想定CVR
- **Status** (Select) – New, Contacted, Interested, Purchased, Closed
- **Payment_Status** (Select) – Pending, Completed, Failed
- **Payment_Date** (Date) – 決済日時
- **Notes** (リッチテキスト) – メモ

## GitHub Actions ワークフロー

`.github/workflows/bot.yml` では、10分毎および `workflow_dispatch` で `main.py` を実行します。ワークフローはリード情報の集計・通知や新規リード登録を行います。手動で実行するには、GitHubの `Actions` タブで `Run workflow` をクリックしてください。

## ローカル実行

環境変数を設定した `.env` を用意した上で、次のコマンドでスクリプトを実行できます：

```bash
python main.py
```

フォームからのリード登録をテストする場合、環境変数 `FORM_EXTERNAL_ID` などを設定して実行します。

## トラブルシューティング

- NotionやLINE API呼び出しでエラーが発生する場合は、環境変数が正しく設定されているかを確認し、GitHub Actionsのログを参照してください。
- `STRIPE_SECRET_KEY` を設定していない場合は決済リンク生成がスキップされます。

---

このREADMEは基本的なセットアップと拡張方法を誠明します。詳細は `main.py` と `config.yaml` を参照してください。
