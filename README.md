# Auto Revenue Framework

外部売上 API から取得したデータを Notion の data source に記録し、集計結果を LINE で通知するフレームワークです。GitHub Actions のスケジュール実行により毎日自動で処理されます。

## アーキテクチャ概要
1. スキル層: 外部 API から売上を取得 (`HttpJsonSalesSourceClient`)、Notion へ売上行を追加 (`NotionLogger`)、LINE でサマリを通知 (`LineNotifier`)。
2. ジョブ層: `auto_rev.jobs.daily_affiliate_report` が前日の売上を取得し、Notion への登録と LINE 通知をまとめて実行します。
3. オーケストレーション: GitHub Actions が毎日 UTC 0:00（日本時間 9:00）にジョブを起動します。`workflow_dispatch` による手動実行も可能です。

## Notion の準備
1. Notion Integration を作成し、シークレットを取得して `NOTION_API_KEY` として保存します。
2. 対象の data source を作成し、以下のプロパティを用意します。
   - Name: タイトル型
   - Amount: 数値型
   - Commission: 数値型
   - Occurred: 日付型
3. data_source_id は対象 data source ページを開き、URL 末尾から ID をコピーします。
4. Integration に対して data source への編集権限を共有します。

## LINE の準備
1. LINE Official Account / Messaging API チャネルを作成します。
2. チャネルアクセストークンを取得し、`LINE_CHANNEL_ACCESS_TOKEN` として保存します。
3. 友だち追加した自分のユーザー ID など通知先となる ID を `LINE_TO_USER_ID` に設定します。

## 環境変数と GitHub Secrets
ローカル実行や GitHub Actions で使用する環境変数は以下です。

- `AFFILIATE_API_BASE_URL`
- `AFFILIATE_API_KEY`
- `NOTION_API_KEY`
- `NOTION_DATA_SOURCE_ID`
- `LINE_CHANNEL_ACCESS_TOKEN`
- `LINE_TO_USER_ID`
- `TIMEZONE` (省略時は `Asia/Tokyo`)

GitHub Actions では上記をリポジトリの Secrets として設定してください。

## ローカル実行
```bash
python -m auto_rev.jobs.daily_affiliate_report
```

## GitHub Actions の実行タイミング
ワークフローは UTC 0:00 に1日1回実行されます。これは日本時間で 09:00 に相当します。
