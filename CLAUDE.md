# 社内検索＆知恵袋アプリ

## 概要
Slack・Notionのナレッジを一元検索し、AIが要約回答する社内検索アプリ。解決しない場合は他ユーザーに回答を募集できる知恵袋機能付き。

## 技術スタック
- **UI**: Streamlit（マルチページ構成）
- **DB**: Supabase（PostgreSQL + pgvector）
- **AI**: OpenAI API（`gpt-4o-mini` / `gpt-5-nano` のみ使用可）
- **Embedding**: OpenAI `text-embedding-3-small`（1536次元、使用可）
- **データ取込**: Slack SDK / Notion REST API（requests直接呼び出し）

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
ai.py               # RAG回答生成（ストリーミング対応）＋取込データのテキスト整形
sidebar.py          # 共通サイドバー
slack_import.py     # Slackデータ一括取込
notion_import.py    # Notionデータ一括取込（requests直接呼び出し）
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
- 使用可能なOpenAI有料モデルは `gpt-4o-mini` と `gpt-5-nano` のみ
- `text-embedding-3-small` はgpt-4o-miniより安価なため使用可

## Embedding方針
- **QAデータ登録時**: `title + question + answer` を結合してembedding化（`search.get_qa_embedding`）
- **検索クエリ**: クエリ単体をembedding化（`search.get_embedding`）
- データ側は全フィールド結合で広い文脈でマッチングする

## データ取込時のテキスト整形
- Slack/Notionインポート時に `ai.clean_qa_text()` でgpt-4o-miniによるテキスト整形を実行
- 口語→丁寧語変換、略語の正式名称補足、ノイズ（挨拶・絵文字・相槌）除去
- 整形後のテキストを保存＋embedding化することで検索精度を向上

## Supabaseスキーマ
テーブル: `users`, `qa_pairs`, `pending_questions`, `search_history`
RPC関数: `match_qa`（pgvectorコサイン類似度検索）
- `qa_pairs` にSlack・Notion・手動登録のデータを統合管理（`source` カラムで区別）
- pgvector RPCにはembeddingを文字列形式（`str(list)`）で渡す

## 環境変数（.env）
- `SUPABASE_URL` / `SUPABASE_KEY` — Supabase接続（必須）
- `OPENAI_API_KEY` — OpenAI API（必須）
- `SLACK_BOT_TOKEN` / `SLACK_CHANNEL_ID` — Slackインポート用
- `NOTION_API_KEY` / `NOTION_DATABASE_ID` — Notionインポート用

## 依存パッケージ
`notion-client` ライブラリは互換性問題があるため使用せず、`requests` でNotion REST APIを直接呼び出している。
