"""One-time, idempotent STEP 8.2 enrichment of the 64-Gate reference JSON."""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from zero_market_lab.transit.calendar import GATE_SEQUENCE
from zero_market_lab.transit.quarters import load_quarters

CENTER_KO = {
    "Head": "머리 센터", "Ajna": "아즈나 센터", "Throat": "목 센터",
    "G": "G 센터", "Heart": "의지 센터", "Spleen": "비장 센터",
    "Solar Plexus": "감정 센터", "Sacral": "천골 센터", "Root": "뿌리 센터",
}
KEYNOTE_KO = {
    1: "자기표현", 2: "방향", 3: "질서 잡기", 4: "해답의 구성",
    5: "리듬", 6: "마찰", 7: "리더십", 8: "기여", 9: "집중",
    10: "자기 행동", 11: "아이디어", 12: "신중함", 13: "경청",
    14: "자원", 15: "극단", 16: "기술", 17: "의견", 18: "교정",
    19: "필요", 20: "현재의 존재", 21: "통제", 22: "개방성",
    23: "이해와 표현", 24: "합리화", 25: "순수함", 26: "설득",
    27: "돌봄", 28: "투쟁", 29: "끈기", 30: "욕망", 31: "영향력",
    32: "지속성", 33: "사생활", 34: "힘", 35: "변화", 36: "위기",
    37: "우정", 38: "맞섬", 39: "자극", 40: "휴식", 41: "축소",
    42: "성장", 43: "통찰", 44: "경계심", 45: "자원", 46: "몸의 경험",
    47: "깨달음", 48: "깊이", 49: "원칙", 50: "가치", 51: "충격",
    52: "고요함", 53: "시작", 54: "야망", 55: "정신", 56: "이야기",
    57: "직관", 58: "활력", 59: "친밀감", 60: "한계", 61: "신비",
    62: "세부", 63: "의심", 64: "혼란",
}


def main() -> None:
    path = ROOT / "data/reference/human_design_gates.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    _, quarter_by_gate = load_quarters(ROOT)
    if {row["gate"] for row in document["gates"]} != set(range(1, 65)):
        raise ValueError("Expected 64 unique Gates")
    if set(GATE_SEQUENCE) != set(KEYNOTE_KO):
        raise ValueError("Every Gate requires a reviewed short Korean label")
    for row in document["gates"]:
        gate = row["gate"]
        keyword = row["short_keynote"]
        keyword_ko = KEYNOTE_KO[gate]
        row.update({
            "center_ko": CENTER_KO[row["center"]],
            "gate_name_ko": f"관문 {gate}",
            "short_keynote_ko": keyword_ko,
            "short_description": ("A symbolic theme of continuity and perceived risk of failure."
                                  if gate == 32 else f"A symbolic theme of {keyword.lower()}."),
            "short_description_ko": ("무엇이 지속될 수 있고 무엇이 실패할 위험이 있는지를 감지하는 주제와 연결됩니다."
                                     if gate == 32 else f"{keyword_ko}이라는 주제를 상징적으로 살펴보는 관문입니다."),
            "theme": row["short_theme"],
            "theme_ko": keyword_ko,
            "fear_theme_ko": "실패에 대한 두려움" if gate == 32 else None,
            "quarter_id": quarter_by_gate[gate]["id"],
            "version": "hd-gate-metadata-v0.2",
        })
    document["version"] = "hd-gate-metadata-v0.2"
    document["source_note"] = ("Short English labels paraphrased from the cited Gate table; "
                               "short Korean translations and descriptions are original research UI labels. "
                               "No market causal claim.")
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
