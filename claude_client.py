"""
Claude Code CLI 経由で Claude を呼び出すユーティリティ。
Claude Pro サブスクリプション枠を使用し、API追加課金は発生しない。
"""
import subprocess
import tempfile
import os
import time
import logging

logger = logging.getLogger(__name__)


def call_claude(prompt: str, system: str = "", max_retries: int = 3) -> str:
    """
    Claude Code CLI 経由で Claude を呼び出す。
    失敗時は exponential backoff で最大3回リトライ。
    """
    full_prompt = f"{system}\n\n{prompt}" if system else prompt

    for attempt in range(max_retries):
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode='w', suffix='.md', delete=False, encoding='utf-8'
            ) as f:
                f.write(full_prompt)
                tmp_path = f.name

            result = subprocess.run(
                ["claude", "-p", full_prompt],
                capture_output=True, text=True, timeout=120
            )

            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
            else:
                logger.warning(f"Claude CLI 呼び出し失敗 (試行{attempt+1}/{max_retries}): {result.stderr}")

        except subprocess.TimeoutExpired:
            logger.warning(f"Claude CLI タイムアウト (試行{attempt+1}/{max_retries})")
        except Exception as e:
            logger.warning(f"Claude CLI エラー (試行{attempt+1}/{max_retries}): {e}")
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

        if attempt < max_retries - 1:
            wait_time = 2 ** attempt  # 1→2→4秒
            logger.info(f"{wait_time}秒後にリトライします...")
            time.sleep(wait_time)

    logger.error("Claude CLI 呼び出しが全試行で失敗しました")
    return ""
