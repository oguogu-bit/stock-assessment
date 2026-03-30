"""
SubAgent F: VIX判定フラグエージェント。
VIX値に基づいて市場環境の文脈テキストを生成する。
"""
import logging

logger = logging.getLogger(__name__)


def get_vix_context(vix: float) -> str:
    """VIX値に応じた市場環境コンテキストを返す"""
    if vix >= 30:
        return f"""【極度の高ボラティリティ局面】VIX={vix:.1f}
市場は極度の恐怖状態。通常手法より、リスクオフ資産（円・金・米国債）の
動向とパニック売り収束タイミングを中心に評価してください。"""
    elif vix >= 20:
        return f"""【高ボラティリティ局面】VIX={vix:.1f}
市場の不確実性が高まっています。下方リスクシナリオを通常より高く見積もり、
為替急変動（特に円高）リスクに注意してください。"""
    elif vix >= 15:
        return f"""【やや不安定な相場環境】VIX={vix:.1f}
イベントリスクに敏感な相場です。"""
    else:
        return f"""【安定相場環境】VIX={vix:.1f}
市場は比較的落ち着いています。"""


def run(vix: float) -> dict:
    """VIX判定フラグ生成メイン処理"""
    logger.info(f"SubAgent F: VIX判定 VIX={vix:.1f}")

    if vix >= 30:
        level = "extreme"
        badge_color = "danger"
        badge_text = "極度恐怖"
    elif vix >= 20:
        level = "high"
        badge_color = "warning"
        badge_text = "高ボラ"
    elif vix >= 15:
        level = "moderate"
        badge_color = "info"
        badge_text = "やや不安定"
    else:
        level = "low"
        badge_color = "success"
        badge_text = "安定"

    return {
        "vix": vix,
        "level": level,
        "badge_color": badge_color,
        "badge_text": badge_text,
        "context_text": get_vix_context(vix),
    }
