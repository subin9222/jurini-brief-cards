"""게시 전 자체 점검표 (2026-11-26 운영자 지시: "만들 때 늘 조건들이 성립하게").

사용법:  python3 tools/check.py cards/YYYY-MM-DD[-morning]
- WORKFLOW.md '인기 계정 벤치마킹 반영' 조건 + 댓글 장치 + 기본 금지 규칙을 기계적으로 확인한다.
- ❌가 하나라도 있으면 종료 코드 1 → 고친 뒤 다시 돌린다. ❌가 남은 채로 컨펌을 요청하지 않는다.
- 👁️ 항목은 기계로 판단할 수 없어 사람이(작업자가) 직접 확인하고 컨펌 메시지에 결과를 적는다.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def strip(html):
    return re.sub(r"<[^>]+>", "", html or "").replace("&nbsp;", " ")


def main():
    d = Path(sys.argv[1])
    if not d.is_absolute():
        d = ROOT / d
    c = json.loads((d / "content.json").read_text(encoding="utf-8"))
    cards = c["cards"]
    cap = (d / "caption.txt").read_text(encoding="utf-8")
    reel = (d / "reel_caption.txt").read_text(encoding="utf-8") if (d / "reel_caption.txt").exists() else ""
    lines = [l for l in cap.splitlines()]
    first = lines[0] if lines else ""
    cover = next((x for x in cards if x["type"] in ("cover_issue", "cover")), {})
    last = cards[-1]
    res = []

    def add(ok, name, note=""):
        res.append(("✅" if ok is True else "❌" if ok is False else "👁️", name, note))

    # 1. 연재
    threads = (ROOT / "THREADS.md").read_text(encoding="utf-8")
    follow = "후속" in cap[:200] or re.search(r"\d+일째", cover.get("pill", ""))
    if follow:
        add(bool(re.search(r"\d+일째|근황|후속", cover.get("pill", ""))), "연재: 후속이면 표지 pill에 'N일째' 표시", cover.get("pill", ""))
        add("후속" in "\n".join(lines[:3]), "연재: 캡션 1~3줄에 '후속' 안내")
    add(d.name.split("-morning")[0] in threads, "연재: THREADS.md에 오늘 날짜 기록")

    # 2. 표지 숫자 + 기준 + 감정 첫 줄
    title = strip(cover.get("title_html", ""))
    add(bool(re.search(r"\d", title)), "표지: 제목에 극단 숫자가 크게 들어감", title)
    basis = cover.get("quote_by", "") + strip(cover.get("sub_html", ""))
    add(bool(re.search(r"기준|대비|이후|만에|전일|고점|공모가", basis)), "표지: 숫자의 기준을 표지에 밝힘", basis)
    add(len(cover.get("ticker", [])) == 3, "표지: 전광판 3칸")
    add(cover.get("mascot") == "surprised" or cover.get("speaker_img"), "표지: 놀란 주린이(인물 대결 구도면 생략 가능)")
    add(title.rstrip().endswith("?"), "표지: 질문형 제목")
    n_first = len(re.sub(r"[^\w가-힣%$.,'’‘\-−+ ]", "", first).strip())
    add(12 <= n_first <= 30, "캡션 첫 줄: 25자 안팎 감정·반응 한 줄", f"{n_first}자: {first}")

    # 3. 댓글 장치
    q = last.get("cta_title", "")
    add(q.startswith("💬") and q.rstrip().endswith(tuple("?？")) or bool(re.search(r"1.*2", q)), "댓글: 마지막 장 질문(cta_title)", q)
    add(len(strip(q)) <= 26, "댓글: 마지막 장 질문 26자 이내", f"{len(strip(q))}자")
    add(bool(re.search(r"1️⃣|①|\b1\b.*\b2\b|둘 중|\?.*\?|번호|이모지", cap + q)), "댓글: 한 단어·번호·이모지로 바로 답할 수 있는 형식")
    guess = next((i for i, l in enumerate(lines) if "맞혀" in l), None)
    add(guess is not None, "댓글: '정답 먼저 맞혀 보세요' 줄")
    if guess is not None:
        ans = strip(next((x for x in cards if x["type"] == "reveal"), {}).get("answer", ""))
        before = "\n".join(lines[1:guess])
        spoil = [w for w in re.split(r"\s+", ans) if len(w) >= 2 and w in before and w not in title]  # 표지 질문에 이미 나온 단어는 제외
        add(not spoil, "댓글: 맞히기 줄 앞에서 정답을 미리 말하지 않음", f"정답 '{ans}' 노출: {spoil}" if spoil else "")
    add(any(l.startswith("💬") for l in lines), "댓글: 캡션 출처 위 💬 질문")
    add("💬" in reel, "댓글: 릴스 캡션에도 질문 한 줄")
    bad_q = re.findall(r"뭐 사셨|물린|수익률|계좌|인증|좋아요 누르|댓글 달면|드려요|추첨|베팅|오를까요\? 내릴까요", cap + q)
    add(not bad_q, "댓글: 금지 질문(매매 의향·손실 고백·대가·방향 내기) 없음", ",".join(bad_q))

    # 기본 규칙
    tags = re.findall(r"#\S+", cap)
    add(len(tags) <= 5 and "#주린이" in tags, "해시태그 5개 이하 + #주린이", " ".join(tags))
    add(tags == re.findall(r"#\S+", reel), "릴스 캡션 해시태그가 게시물과 같음")
    add(len(cap) <= 2200, "캡션 2200자 이하", f"{len(cap)}자")
    banned = re.findall(r"사세요|파세요|목표가|반토막|확률 100%|무조건|급등 예정|오를 거예요|내릴 거예요", cap + json.dumps(c, ensure_ascii=False))
    add(not banned, "금지 표현(투자 권유·단정·과장) 없음", ",".join(banned))
    add("속보" not in cap or None, "'속보)'는 24시간 이내·2곳 이상 확인 시만", "속보 사용 → 직접 확인" if "속보" in cap else "")
    for x in cards:
        if x["type"] in ("reveal", "timeline", "issue", "market", "flows", "bars"):
            add(len(x.get("bullets", [])) == 3, f"3줄 요약 정확히 3개 ({x.get('tag', x['type'])})")
    faces = [x.get("mascot") for x in cards[1:]]
    add(not any(faces[i] and faces[i] == faces[i + 1] == faces[i + 2] for i in range(len(faces) - 2)), "주린이 같은 표정 3연속 없음", " ".join(map(str, faces)))
    add("투자 권유가 아닙니다" in cap, "캡션 면책 문구")

    # 사람이 확인할 것
    add(None, "흥미 점검: 표지에 인물·사건·반전·큰 숫자 중 2개 이상?")
    add(None, "표지 숫자가 02~05장에서 Python으로 검증한 값과 같은가?")
    add(None, "모든 사실 2곳 이상 확인, 기사 문장 복사 없음, 렌더 결과 눈으로 확인")

    print(f"## 자체 점검표 — {d.name}")
    for mark, name, note in res:
        print(f"{mark} {name}" + (f"  ({note})" if note else ""))
    fails = [r for r in res if r[0] == "❌"]
    print(f"\n결과: ❌ {len(fails)}개, 👁️ {sum(r[0] == '👁️' for r in res)}개(직접 확인)")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
