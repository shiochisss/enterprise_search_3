# 社内検索＆知恵袋アプリ

## 概要
Slack・Notionのナレッジを一元検索し、AIが要約回答する社内検索アプリ。解決しない場合は他ユーザーに回答を募集できる知恵袋機能付き。

## 技術スタック
- **UI**: Streamlit（マルチページ構成）
- **DB**: Supabase（PostgreSQL + pgvector）
- **AI**: OpenAI API（`gpt-4o-mini` / `gpt-5-nano` のみ使用可）
- **Embedding**: OpenAI `text-embedding-3-small`（1536次元）
- **データ取込**: Slack SDK / Notion Client

## 起動方法
```bash
pip install -r requirements.txt
streamlit run app.py
```
初期管理者アカウント: `admin` / `admin`

## ファイル構成
```
app.py              # エントリポイント（ログイン画面）
auth.py             # 認証ロジック（bcrypt）
db.py               # Supabaseクライアント＋全CRUD
search.py           # embedding生成＋pgvector類似検索
ai.py               # RAG回答生成（ストリーミング対応）
sidebar.py          # 共通サイドバー
slack_import.py     # Slackデータ一括取込
notion_import.py    # Notionデータ一括取込
dashboard_stats.py  # ダッシュボード集計ロジック
pages/
  1_質問する.py      # 検索→結果→AI要約→評価→回答募集
  2_回答募集中.py    # 未解決質問一覧＋回答入力
  3_ダッシュボード.py # 管理者専用：統計
  4_管理.py          # 管理者専用：データ・ユーザー・インポート
```

## 設計原則
- 処理ロジックはページファイルに直接書かず、モジュールに分離する
- 環境変数は `.env` で管理（git管理外）
- 使用可能なOpenAIモデルは `gpt-4o-mini` と `gpt-5-nano` のみ

## Supabaseスキーマ
テーブル: `users`, `qa_pairs`, `pending_questions`, `search_history`
RPC関数: `match_qa`（pgvectorコサイン類似度検索）

## 環境変数（.env）
- `SUPABASE_URL` / `SUPABASE_KEY` — Supabase接続（必須）
- `OPENAI_API_KEY` — OpenAI API（必須）
- `SLACK_BOT_TOKEN` / `SLACK_CHANNEL_ID` — Slackインポート用
- `NOTION_API_KEY` / `NOTION_DATABASE_ID` — Notionインポート用
