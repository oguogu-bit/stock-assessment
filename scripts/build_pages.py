"""
GitHub Pages 用ファイル生成スクリプト。
daily_run.yml から呼び出される。
引数: python scripts/build_pages.py YYYY-MM-DD
"""
import os
import sys
import glob
import shutil

today = sys.argv[1] if len(sys.argv) > 1 else ""
if not today:
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")

src = f"reports/{today}.html"
if not os.path.exists(src):
    print(f"ERROR: {src} が見つかりません")
    sys.exit(1)

os.makedirs("docs/reports", exist_ok=True)

# 最新レポートを index.html に配置（GitHub Pages トップがそのままレポート）
shutil.copy(src, "docs/index.html")
print(f"✓ docs/index.html <- {src}")

# 日付別アーカイブにもコピー
shutil.copy(src, f"docs/reports/{today}.html")
print(f"✓ docs/reports/{today}.html")

# 過去レポート一覧ページ生成
report_files = sorted(glob.glob("docs/reports/[0-9]*.html"), reverse=True)

rows = ""
for path in report_files[:30]:
    fname = os.path.basename(path)
    date = fname.replace(".html", "")
    rows += f'<tr><td><a href="reports/{fname}">📄 {date}</a></td></tr>\n'

archive_html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>レポート一覧 — 株式・為替アセスメント</title>
  <style>
    body{{font-family:sans-serif;max-width:600px;margin:2rem auto;padding:0 1rem;background:#f5f7fa;}}
    h2{{color:#1565c0;}}
    table{{width:100%;border-collapse:collapse;background:white;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.1);}}
    td{{padding:.75rem 1rem;border-bottom:1px solid #f0f0f0;}}
    tr:hover td{{background:#f5f5f5;}}
    a{{color:#1565c0;text-decoration:none;font-size:1rem;}}
    a:hover{{text-decoration:underline;}}
  </style>
</head>
<body>
  <h2>📊 レポート一覧</h2>
  <p><a href="index.html">← 最新レポートに戻る</a></p>
  <table><tbody>{rows}</tbody></table>
</body>
</html>"""

with open("docs/archive.html", "w", encoding="utf-8") as f:
    f.write(archive_html)

print(f"✓ docs/archive.html 生成完了 ({len(report_files)}件)")
