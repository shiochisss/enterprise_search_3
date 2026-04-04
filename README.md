# 社内検索＆知恵袋アプリ

社内のSlack・Notionに散在するナレッジを一元検索し、AIが要約回答するStreamlitアプリ。
検索結果に満足できない場合は、他のユーザーに回答を募集できる「知恵袋」機能付き。

---

## 技術スタック

| 項目 | 技術 |
|---|---|
| UI | Streamlit（マルチページ構成） |
| DB | Supabase（PostgreSQL + pgvector） |
| AI（回答生成） | OpenAI API `gpt-4o-mini` / `gpt-5-nano` |
| AI（ベクトル化） | OpenAI `text-embedding-3-small`（1536次元） |
| データ取込 | Slack SDK / Notion REST API（requests） |
| 認証 | bcryptハッシュ |

---

## アプリの動き（画面順の詳細説明）

### 1. ログイン（app.py）

アプリ起動時に最初に表示される画面。

#### 処理の流れ

1. **`st.set_page_config()`** — ページタイトル「社内検索＆知恵袋」、アイコン、ワイドレイアウトを設定
2. **`auth.create_user("admin", "admin", "管理者", is_admin=True)`** — 管理者アカウントの初期作成（既に存在する場合はスキップ）
3. **`st.session_state` チェック** — `"user"` キーが存在すれば既にログイン済みなので `st.switch_page()` で質問ページへリダイレクト
4. **`st.form("login_form")`** — ログインフォームを表示
   - `st.text_input("ユーザーID")` — ユーザーID入力欄
   - `st.text_input("パスワード", type="password")` — パスワード入力欄（マスク表示）
   - `st.form_submit_button("ログイン")` — 送信ボタン
5. **送信時の処理**
   - 空欄チェック → `st.error()` でエラー表示
   - `auth.authenticate(user_id, password)` を呼び出し
     - 内部で `bcrypt.checkpw()` によるパスワード検証
     - 成功時: `{id, user_id, display_name, is_admin}` の辞書を返す
     - 失敗時: `None` を返す
   - 成功: `st.session_state.user` にユーザー情報を保存 → `st.switch_page()` で質問ページへ
   - 失敗: `st.error()` でエラーメッセージ表示

#### 関連する処理関数（auth.py）

| 関数 | 処理内容 |
|---|---|
| `_hash_password(password)` | bcryptでパスワードをハッシュ化（ソルト自動生成） |
| `_verify_password(password, hash)` | bcryptでパスワードとハッシュを照合 |
| `create_user(user_id, password, display_name, is_admin)` | Supabaseの`users`テーブルにユーザーを登録。既存ならFalseを返す |
| `authenticate(user_id, password)` | `users`テーブルからユーザーを検索し、パスワード照合。成功時にユーザー辞書を返す |

---

### 2. 質問する（pages/1_質問する.py）

ログイン後のメイン画面。ユーザーがクエリを入力して検索し、AI要約を受け取る。

#### 処理の流れ

1. **認証チェック** — `st.session_state` に `"user"` がなければ `st.switch_page("app.py")` でログインへ戻す
2. **`show_sidebar()`** — サイドバーにログインユーザー名とログアウトボタンを表示
3. **`st.text_input("検索クエリ")`** — 検索クエリの入力欄（プレースホルダ: 「例: 有給休暇の申請方法は？」）
4. **`st.button("検索")`** — 検索ボタン。押下時に `st.session_state` にクエリを保存し、検索結果をリセット

#### 検索実行（ボタン押下後）

5. **`search.find_similar(query, top_k=10)`** を呼び出し
   - 内部処理:
     1. `get_embedding(query)` — OpenAI `text-embedding-3-small` でクエリを1536次元ベクトルに変換
     2. `str(embedding)` — ベクトルを文字列形式に変換（Supabase PostgREST仕様）
     3. `db.get_client().rpc("match_qa", ...)` — Supabaseの `match_qa` RPC関数を呼び出し
     4. RPC関数内部: `qa_pairs.embedding <=> query_embedding`（pgvectorのコサイン距離演算子）で類似度計算
     5. `1 - コサイン距離 = 類似度スコア` として返却
   - 返り値: `[{id, title, question, answer, source, score}, ...]`（スコア降順）
6. **`db.insert_search_history(query, results, user)`** — 検索履歴をSupabaseに保存。上位3件のqa_id・タイトル・スコアを記録。返り値は `search_history.id`

#### AI要約表示

7. **`ai.generate_answer_stream(query, top_3_results)`** をストリーミング呼び出し
   - 内部処理:
     1. `_build_messages(question, similar_qas)` — プロンプトを組み立て
        - **システムプロンプト**: 「社内ナレッジベースのアシスタント」としてのロール設定
        - **ユーザーメッセージ**: 上位3件のQAデータ（出典・類似度・タイトル・質問・回答）を参考情報として添付＋ユーザーの質問
     2. OpenAI `gpt-4o-mini` に `stream=True` でリクエスト
     3. チャンクごとに `yield` で返却
   - `st.empty()` + ループで、AIの回答をリアルタイムにマークダウン表示

#### 検索結果一覧

8. **`st.expander()`** で各検索結果を折りたたみ表示
   - 表示内容: `#番号 タイトル（類似度: X.XX / 出典: slack/notion/user）`
   - 展開時: 質問テキストと回答テキストを表示

#### 満足度評価

9. **`st.radio("満足度", [5,4,3,2,1])`** — 星評価（横並び表示、`format_func`で星マークに変換）
10. **`st.button("評価を送信")`** — 押下時に `db.rate_search(search_id, rating)` で `search_history.satisfaction_rating` を更新

#### 回答募集

11. **`st.button("回答を募集する")`** — 押下時に `db.insert_pending_question(query, display_name)` で `pending_questions` テーブルに未解決質問として登録

---

### 3. 回答募集中（pages/2_回答募集中.py）

未解決の質問を一覧表示し、他のユーザーが回答を入力できる画面。

#### 処理の流れ

1. **認証チェック** + **`show_sidebar()`**
2. **`db.fetch_pending_questions()`** — `pending_questions` テーブルから `resolved=False` のレコードを取得（新しい順）
3. **質問がない場合** — `st.info()` で「回答募集中の質問はありません」と表示
4. **質問がある場合** — 各質問を `st.expander()` で表示
   - ヘッダー: `❓ 質問テキスト（投稿者: 名前）`
   - `st.caption()` — 投稿日時
   - `st.text_area("回答を入力")` — 回答入力欄（キーは `answer_{質問ID}` でユニーク化）
   - `st.button("回答を送信")` — 回答送信ボタン（キーは `submit_{質問ID}`）

#### 回答送信時の処理

5. 空欄チェック → `st.error()`
6. **`db.resolve_pending_question(id, answer, resolved_by)`** — 質問を解決済みに更新（answer, resolved=True, resolved_by を設定）
7. **`search.get_qa_embedding(title, question, answer)`** — 回答テキストを含めてembedding生成
   - `title + question + answer` を結合 → `text-embedding-3-small` で1536次元ベクトル化
8. **`db.insert_qa()`** — 回答をQAペアとして `qa_pairs` テーブルに新規登録（source="user"）
   - これにより次回以降の検索でヒットするようになる
9. `st.success()` + `st.rerun()` で画面をリロード

---

### 4. ダッシュボード（pages/3_ダッシュボード.py）【管理者専用】

統計情報をKPI・グラフで表示する画面。

#### アクセス制御

1. **認証チェック** + **`is_admin` チェック** — 管理者でなければ `st.error()` + `st.stop()` で表示を中断

#### KPI指標（4列表示）

2. **`dashboard_stats.fetch_search_cost_stats()`** を呼び出し
   - `db.fetch_search_history(limit=10000)` で全検索履歴を取得
   - `satisfaction_rating >= 4` の件数を「AI解決」としてカウント
   - `(AI解決数 / 総検索数) * 100` = コスト削減率
   - 返り値: `{total_searches, satisfied_searches, cost_reduction_rate}`
3. **`dashboard_stats.fetch_question_cost_stats()`** を呼び出し
   - 検索履歴 + 全質問を取得
   - AI解決数、回答募集数、人的解決数を集計
   - 返り値: `{total_searches, ai_resolved, human_escalated, human_resolved}`
4. **`st.metric()`** × 4 — 総検索数、AI解決率、回答募集数、人的解決数

#### 探索コスト削減セクション

5. **`st.metric()`** × 2 — AI解決件数、コスト削減率（ヘルプテキスト付き）

#### 質問対応工数削減セクション

6. **`st.metric()`** × 2 — AI解決数、人的対応数
7. **`st.progress()`** — AI解決率をプログレスバーで表示

#### 回答数ランキング（人別）

8. **`dashboard_stats.fetch_answer_stats()`** を呼び出し
   - `db.fetch_all_pending_questions()` で全質問取得
   - `resolved=True` のレコードの `resolved_by` をカウント
   - 返り値: `[{name, count}, ...]`（回答数降順）
9. **`pd.DataFrame()` + `st.bar_chart()`** — 人別回答数を棒グラフ表示

#### 回答満足度（人別）

10. **`dashboard_stats.fetch_satisfaction_stats()`** を呼び出し
    - 解決済み質問の `satisfaction_rating` を `resolved_by` ごとに平均
    - `(value or 0)` で None を0に変換してTypeError防止
    - 返り値: `[{name, avg_rating, count}, ...]`
11. 各回答者を3列（名前・星表示・件数）で一覧表示

---

### 5. 管理（pages/4_管理.py）【管理者専用】

4つのタブで構成される管理画面。

#### アクセス制御

- 認証チェック + `is_admin` チェック（ダッシュボードと同様）

#### タブ1: 全データ一覧

1. **`db.fetch_all_qa()`** — `qa_pairs` テーブルの全レコードを新しい順で取得
2. 各QAを **`st.expander()`** で表示
   - ヘッダー: `[source] タイトル (ID: X)`
   - 本文: 質問、回答、作成者、更新者、作成日時
   - **`st.button("削除")`** → `db.delete_qa(qa_id)` で削除 + `st.rerun()`

3. **手動QA追加フォーム** — `st.form("add_qa_form")`
   - `st.text_input("タイトル")` — タイトル入力
   - `st.text_area("質問")` — 質問入力
   - `st.text_area("回答")` — 回答入力
   - `st.form_submit_button("追加")` — 送信
4. 送信時:
   - `search.get_qa_embedding(title, question, answer)` でembedding生成
   - `db.insert_qa()` で `qa_pairs` に登録（source="user"）

#### タブ2: ユーザー管理

5. **`auth.fetch_all_users()`** — 全ユーザーを取得（パスワード除外）
6. 各ユーザーを3列（名前+ID+権限、作成日、削除ボタン）で表示
   - adminユーザーの削除ボタンは非表示
   - **`st.button("削除")`** → `auth.delete_user(user_id)`

7. **ユーザー追加フォーム** — `st.form("add_user_form")`
   - `st.text_input("ユーザーID")` / `st.text_input("パスワード")` / `st.text_input("表示名")`
   - `st.checkbox("管理者権限")` — 管理者フラグ
   - `st.form_submit_button("追加")`
8. 送信時: `auth.create_user()` → 既存IDの場合はエラー表示

#### タブ3: データインポート

9. 2列レイアウトで **Slack** と **Notion** のインポートボタンを並列配置

**Slackインポート（`st.button("Slackインポート実行")`押下時）:**
- `slack_import.run_import()` を呼び出し
  1. `WebClient(token)` でSlack APIクライアント作成
  2. `conversations_history()` でチャンネルのメッセージを取得（ページネーション対応）
  3. `reply_count >= 2` のスレッドのみ対象
  4. `conversations_replies()` でスレッドのリプライを取得
  5. 変換ルール: 親メッセージ→タイトル、1番目のリプライ→質問、2番目以降→回答（改行結合）
  6. **`ai.clean_qa_text(title, question, answer)`** でAIテキスト整形
     - gpt-4o-miniで口語→丁寧語、略語補足、ノイズ除去
     - `---タイトル---` / `---質問---` / `---回答---` のフォーマットで返却をパース
  7. `search.get_qa_embedding()` で整形後テキストをembedding化
  8. `db.upsert_qa_by_source_id(source="slack", source_id=thread_ts)` でupsert（重複防止）
- 結果を `st.success()` または `st.error()` で表示

**Notionインポート（`st.button("Notionインポート実行")`押下時）:**
- `notion_import.run_import()` を呼び出し
  1. Notion REST API（`requests.post`）でデータベースをクエリ（ページネーション対応）
  2. 各ページの `properties` からタイトルを抽出（`_extract_page_title()`）
  3. `blocks/{page_id}/children` APIでページ内ブロックを取得
  4. `_extract_text_from_block()` で各ブロックの `rich_text` からプレーンテキストを抽出
  5. 変換ルール: ページタイトル→タイトル、最初のテキストブロック→質問、残り→回答
  6. 以降はSlackと同じ（AIテキスト整形 → embedding → upsert）

#### タブ4: 質問管理

10. **`db.fetch_all_pending_questions()`** — 解決済み含む全質問を取得
11. 各質問を `st.expander()` で表示
    - ヘッダー: `✅ 解決済み` または `❓ 未解決` + 質問テキスト
    - 投稿者、投稿日時、回答内容、回答者、満足度（星表示）
    - **`st.button("削除")`** → `db.delete_pending_question(id)`

---

### 共通コンポーネント: サイドバー（sidebar.py）

全ページで `show_sidebar()` を呼び出して表示。

- **`st.sidebar`** 内に以下を表示:
  - `st.markdown()` — 「**表示名** でログイン中」
  - `st.caption("管理者")` — 管理者の場合のみ表示
  - `st.button("ログアウト")` — 押下時に `st.session_state` を全クリアし `st.switch_page("app.py")` でログイン画面へ

---

## ファイル構成と役割

```
app.py              # エントリポイント（ログイン画面）
auth.py             # 認証ロジック（bcrypt）
db.py               # Supabaseクライアント＋全CRUD操作
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
.env                # 環境変数（git管理外）
.gitignore
requirements.txt
```

---

## 各モジュールの関数一覧

### db.py（Supabaseクライアント＋CRUD）

| 関数 | 処理内容 |
|---|---|
| `get_client()` | Supabaseクライアントのシングルトンを返す |
| `insert_qa(title, question, answer, source, embedding, created_by)` | QAペアを新規登録 |
| `fetch_all_qa()` | 全QAペアを取得（新しい順） |
| `update_qa(qa_id, title, question, answer, embedding, updated_by)` | QAペアを更新 |
| `delete_qa(qa_id)` | QAペアを削除 |
| `upsert_qa_by_source_id(source, source_id, ...)` | source+source_idで重複チェックしupsert |
| `insert_pending_question(question, asked_by)` | 回答募集質問を登録 |
| `fetch_pending_questions()` | 未解決の質問一覧を取得 |
| `fetch_all_pending_questions()` | 全質問一覧を取得（解決済み含む） |
| `resolve_pending_question(id, answer, resolved_by)` | 質問を解決済みに更新 |
| `rate_pending_question(id, rating)` | 回答募集質問の満足度を評価 |
| `delete_pending_question(id)` | 質問を削除 |
| `insert_search_history(query, results, searched_by)` | 検索履歴を保存しIDを返す |
| `rate_search(search_id, rating)` | 検索の満足度を評価 |
| `fetch_search_history(limit)` | 検索履歴を取得 |

### search.py（ベクトル検索）

| 関数 | 処理内容 |
|---|---|
| `get_embedding(text)` | テキストをtext-embedding-3-smallで1536次元ベクトルに変換 |
| `get_qa_embedding(title, question, answer)` | title+question+answerを結合してembedding化 |
| `find_similar(question, top_k)` | クエリをembedding化し、pgvector RPCで類似検索 |

### ai.py（RAG回答生成＋テキスト整形）

| 関数 | 処理内容 |
|---|---|
| `_build_messages(question, similar_qas)` | システムプロンプト＋参考QA＋質問のメッセージ配列を組み立て |
| `clean_qa_text(title, question, answer)` | gpt-4o-miniで取込テキストを整形（口語→丁寧語、ノイズ除去） |
| `generate_answer(question, similar_qas, model)` | 非ストリーミングでRAG回答を生成 |
| `generate_answer_stream(question, similar_qas, model)` | ストリーミングでRAG回答を生成（ジェネレータ） |

### dashboard_stats.py（ダッシュボード集計）

| 関数 | 処理内容 |
|---|---|
| `fetch_answer_stats()` | 人別の回答数を集計 |
| `fetch_satisfaction_stats()` | 人別の回答満足度を集計 |
| `fetch_search_cost_stats()` | 探索コスト削減（AI解決率）を集計 |
| `fetch_question_cost_stats()` | 質問対応工数削減を集計 |

---

## Supabaseテーブル構成

| テーブル | 用途 |
|---|---|
| `users` | ユーザー管理（user_id, password_hash, display_name, is_admin） |
| `qa_pairs` | ナレッジデータ統合管理（title, question, answer, source, embedding） |
| `pending_questions` | 回答募集中の質問（question, asked_by, answer, resolved, satisfaction_rating） |
| `search_history` | 検索履歴（query, 上位3件の結果, satisfaction_rating） |

RPC関数: `match_qa(query_embedding, match_count)` — pgvectorコサイン類似度検索

---

## 環境変数（.env）

| 変数名 | 用途 | 必須 |
|---|---|---|
| `SUPABASE_URL` | Supabase プロジェクトURL | 必須 |
| `SUPABASE_KEY` | Supabase APIキー | 必須 |
| `OPENAI_API_KEY` | OpenAI APIキー | 必須 |
| `SLACK_BOT_TOKEN` | Slack Bot Token | Slackインポート時 |
| `SLACK_CHANNEL_ID` | Slackチャンネル ID | Slackインポート時 |
| `NOTION_API_KEY` | Notion APIキー | Notionインポート時 |
| `NOTION_DATABASE_ID` | NotionデータベースID | Notionインポート時 |

---

## 起動方法

```bash
pip install -r requirements.txt
streamlit run app.py
```

初期管理者アカウント: `admin` / `admin`
