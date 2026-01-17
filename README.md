# ai-b2b-revenue-engine

B2B向け「成果報酬型AI集客／営業エンジン」をGitHub Actions中心で自動運用するための最小構成です。公開情報のみを扱い、Secretsが未設定でも完走します。

## 実行
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/pipeline.py --mode run
```

## 環境変数
- `OPENAI_API_KEY` : LLMによる仮説/コピー生成（未設定ならテンプレ）
- `NOTION_API_KEY` : Notion連携（未設定ならローカル保存）
- `NOTION_PAGE_ID` : Notion保存先（任意）
- `PRICE_YEN` : KPI判定の価格基準（デフォルト1,000,000）

## ディレクトリ
- `collector/` : リード収集（デフォルトseed生成）
- `kpi/` : KPI判定とdecision生成
- `optimizer/` : 仮説生成
- `generator/` : LP HTML生成
- `deployer/` : docs/生成
- `reporter/` : Notion送信 or ローカル保存
- `scripts/` : パイプライン/テスト
- `reports/` : レポート出力
- `data/` : 入力/中間データ
