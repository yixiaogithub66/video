from __future__ import annotations

from dataclasses import dataclass

from video_platform.config import settings


@dataclass
class SafetyResult:
    allowed: bool
    blocked_rules: list[str]
    reason: str
    risk_level: str
    override_applied: bool = False


BLOCK_RULES: dict[str, tuple[str, ...]] = {
    "high_risk_face_swap": (
        "face swap",
        "deepfake",
        "celebrity",
        "public figure",
        "换脸",
        "仿冒",
    ),
    "explicit_violence": (
        "gore",
        "beheading",
        "dismember",
        "blood explosion",
        "虐杀",
        "血腥",
    ),
    "sexual_content": (
        "nude",
        "explicit sexual",
        "porn",
        "色情",
        "裸露",
    ),
    "hate_or_terror": (
        "terror",
        "isis",
        "hate speech",
        "纳粹",
        "恐怖袭击",
    ),
}


HIGH_RISK_KEYWORDS: tuple[str, ...] = (
    "public figure",
    "politician",
    "minor",
    "medical",
    "financial advice",
    "breaking news",
    "名人",
    "未成年人",
    "医疗",
    "金融",
)


def classify_risk(instruction: str) -> str:
    text = instruction.lower()
    configured = settings.high_risk_review_keywords()
    high_risk_keywords = list(HIGH_RISK_KEYWORDS) + configured
    if any(keyword in text for keyword in high_risk_keywords):
        return "high"
    if any(keyword in text for keyword in ("brand", "trademark", "logo", "watermark", "商标", "水印")):
        return "medium"
    return "low"


def evaluate_instruction(
    instruction: str,
    *,
    admin_override: bool = False,
    override_reason: str | None = None,
) -> SafetyResult:
    text = instruction.lower()
    risk_level = classify_risk(instruction)
    matched: list[str] = []
    for rule_id, keywords in BLOCK_RULES.items():
        if any(keyword in text for keyword in keywords):
            matched.append(rule_id)

    if matched:
        allowlist = settings.safety_override_allow_rules()
        override_ok = (
            admin_override
            and bool(override_reason and override_reason.strip())
            and bool(allowlist)
            and set(matched).issubset(allowlist)
        )
        if override_ok:
            return SafetyResult(
                allowed=True,
                blocked_rules=matched,
                reason="Blocked rules overridden by admin whitelist",
                risk_level=risk_level,
                override_applied=True,
            )
        return SafetyResult(
            allowed=False,
            blocked_rules=matched,
            reason="Instruction hit strict safety policy rules",
            risk_level=risk_level,
        )

    return SafetyResult(allowed=True, blocked_rules=[], reason="Allowed", risk_level=risk_level)
