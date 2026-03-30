# 日米株価・為替 × ニュース・政治イベント 日次アセスメントシステム

Claude Code CLI（Pro/Maxサブスクリプション枠）を使った、**API追加課金ゼロ**の株式・為替分析システムです。

---

## システム概要

毎日の日米株価・為替データ、RSSニュースを収集し、Claude に分析させて
HTMLレポートを自動生成します。GitHub Actions での自動実行にも対応しています。

### サブエージェント構成

```
main.py（オーケストレーター）
├── Phase 1: 並列データ収集
│   ├── SubAgent A: agent_stocks.py   — 日米株価・指数（yfinance）
│   ├── SubAgent B: agent_fx.py       — 為替・VIX・マクロ指標（yfinance）
│   └── SubAgent C: agent_news.py     — ニュース収集（RSS + NewsAPI）
│
├── Phase 2: 順次処理
│   ├── SubAgent E: agent_technical.py — RSI/MACD/BB/相関係数
│   ├── SubAgent F: agent_vix_flag.py  — VIX水準判定
│   └── SubAgent G: agent_sentiment.py — 感情スコア（Claude CLI）
│
├── Phase 3: DB管理
│   └── SubAgent H: agent_pattern_db.py — 過去パターンDB・Few-shot生成
│
├── Phase 4: メイン分析
│   └── SubAgent J: agent_analyst.py  — 総合分析レポート（Claude CLI）
│
└── Phase 5: 並列出力
    └── SubAgent K: agent_reporter.py — HTMLレポート生成（Plotly）
```

### API課金なし設計

Claude の呼び出しは `anthropic` SDK（API課金）を使わず、
**Claude Code CLI を subprocess で呼び出す**方式を採用しています。

```python
# claude_client.py
result = subprocess.run(
    ["claude", "-p", full_prompt],
    capture_output=True, text=True, timeout=120
)
```

Claude Pro / Max のサブスクリプション枠を使用するため、**API追加課金は一切発生しません**。

---

## 前提条件

- **Claude Pro または Max サブスクリプション**（必須）
- **Claude Code CLI** インストール済み
- Python 3.11 以上
- Git

---

## セットアップ手順

### 1. Claude Code CLI のインストール

```bash
npm install -g @anthropic-ai/claude-code
# インストール確認
claude --version
```

### 2. リポジトリのクローン

```bash
git clone <your-repo-url>
cd stock_analyzer
```

### 3. Python 依存ライブラリのインストール

```bash
pip install -r requirements.txt
```

### 4. 環境変数の設定（任意）

```bash
cp .env.example .env
# .env をエディタで開いて設定（すべて任意）
```

設定できる環境変数:

| 変数名 | 説明 | 必須 |
|--------|------|------|
| `NEWS_API_KEY` | [NewsAPI](https://newsapi.org/) キー | 任意 |
| `SLACK_WEBHOOK_URL` | Slack Incoming Webhook URL | 任意 |
| `LINE_NOTIFY_TOKEN` | LINE Notify トークン | 任意 |
| `ANTHROPIC_API_KEY` | **不要** | 不要 |

---

## 動作確認

### モックデータで動作確認（推奨: 初回）

APIキーやネット接続なしで全フローを確認できます:

```bash
python main.py --mock
```

正常に完了すると `reports/YYYY-MM-DD.html` が生成されます。

### ライブデータで実行

```bash
python main.py --date today
```

特定日付を指定する場合:

```bash
python main.py --date 2026-03-31
```

---

## GitHub Actions 自動実行

### セットアップ手順

1. このリポジトリを GitHub にプッシュ

2. リポジトリの **Settings → Secrets and variables → Actions** を開く

3. 以下のシークレットを登録（任意）:

   | シークレット名 | 説明 |
   |---------------|------|
   | `NEWS_API_KEY` | NewsAPI キー |
   | `SLACK_WEBHOOK_URL` | Slack Webhook URL |
   | `LINE_NOTIFY_TOKEN` | LINE Notify トークン |

4. `.github/workflows/daily_run.yml` が自動実行されます

### 実行スケジュール

| 実行時刻（JST） | タイミング |
|----------------|-----------|
| 15:35 | 東証大引け後（平日） |
| 22:00 | NY市場開場後（平日） |

手動実行: GitHub の **Actions タブ → Daily Stock Analysis → Run workflow**

---

## config.py のカスタマイズ

`config.py` を編集することで、監視銘柄・通貨ペアを自由に変更できます:

```python
# 日本個別銘柄の追加例
JP_STOCKS = {
    "7203.T": "トヨタ",
    "6758.T": "ソニー",
    "7974.T": "任天堂",
    "9984.T": "ソフトバンクG",  # 追加
}

# 米国個別銘柄の追加例
US_STOCKS = {
    "AAPL": "Apple",
    "NVDA": "NVIDIA",
    "MSFT": "Microsoft",
    "TSLA": "Tesla",  # 追加
}
```

---

## パターンDB（Few-shot学習）について

`data/news_patterns.csv` に毎日の分析結果が蓄積されます。

### 蓄積される情報

| カラム | 説明 |
|--------|------|
| `date` | 日付 |
| `news_headline` | ニュースヘッドライン |
| `impact_category` | 影響カテゴリ（金融政策・地政学など）|
| `sentiment_score` | 感情スコア（-1.0〜+1.0）|
| `nikkei_1d_change_pct` | 翌日の日経変動率（実績）|
| `predicted_direction` | 予測方向 |
| `actual_direction` | 実際の方向 |
| `accuracy_label` | 的中 / 外れ |

### 精度向上の仕組み

1. 毎日、当日ニュースを `predicted_direction` 付きで仮登録
2. 翌日に実際の価格変動と照合して `accuracy_label` を更新
3. 分析時に同カテゴリの「的中」パターンを Few-shot 例として Claude に提供
4. **データが蓄積されるほど、過去の類似局面を参照した精度の高い分析が可能**になります

---

## ファイル構成

```
stock_analyzer/
├── main.py                     # オーケストレーター
├── agents/
│   ├── agent_stocks.py         # SubAgent A: 株価取得
│   ├── agent_fx.py             # SubAgent B: 為替取得
│   ├── agent_news.py           # SubAgent C: ニュース収集
│   ├── agent_technical.py      # SubAgent E: テクニカル指標
│   ├── agent_vix_flag.py       # SubAgent F: VIX判定
│   ├── agent_sentiment.py      # SubAgent G: 感情スコア（Claude）
│   ├── agent_pattern_db.py     # SubAgent H: パターンDB
│   ├── agent_analyst.py        # SubAgent J: メイン分析（Claude）
│   └── agent_reporter.py       # SubAgent K: HTMLレポート生成
├── claude_client.py            # Claude CLI 呼び出しユーティリティ
├── config.py                   # 設定（銘柄・通貨ペア等）
├── mock_data.py                # モックデータ
├── notifier.py                 # 通知（Slack/LINE）
├── data/
│   ├── news_patterns.csv       # パターンDB（自動蓄積）
│   └── cache/                  # 前日データキャッシュ
├── reports/                    # 生成HTMLレポート
├── logs/                       # 日次ログ
├── .github/workflows/
│   └── daily_run.yml           # GitHub Actions 設定
├── requirements.txt
├── .env.example
└── README.md
```

---

## ライセンス

MIT License
