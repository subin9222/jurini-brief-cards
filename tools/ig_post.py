"""인스타그램 공식 API로 @jurini.brief에 직접 게시한다 (Metricool 대신, 무료).

사용법:
  python3 tools/ig_post.py check  --token <토큰파일>                      # 연결 확인만 (게시 안 함)
  python3 tools/ig_post.py carousel --token <토큰파일> --date YYYY-MM-DD    # 카드 7장 캐러셀 게시
  python3 tools/ig_post.py reel     --token <토큰파일> --date YYYY-MM-DD    # 릴스 게시
  (--dry-run 을 붙이면 컨테이너 준비까지만 하고 게시하지 않는다)

- 토큰은 비공개 저장소 subin9222/jurini-secrets 의 ig_token.txt (절대 이 공개 저장소에 넣지 않는다).
- 게시 직전에 토큰이 가리키는 계정 이름이 반드시 'jurini.brief'인지 확인하고, 아니면 멈춘다.
- 미디어는 이 공개 저장소의 raw.githubusercontent.com 주소를 인스타그램이 직접 가져간다(먼저 push 필요).
- 캡션: cards/<날짜>/caption.txt (캐러셀), reel_caption.txt (릴스). 해시태그 5개 초과면 멈춘다.
"""
import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://graph.facebook.com/v21.0"
IG_USER = "17841443507103115"          # @jurini.brief
EXPECTED = "jurini.brief"
RAW = "https://raw.githubusercontent.com/subin9222/jurini-brief-cards/main/"
REPO = Path(__file__).resolve().parent.parent


def call(tok, method, path, params=None):
    params = dict(params or {}); params["access_token"] = tok
    data = urllib.parse.urlencode(params).encode()
    url = f"{API}/{path}" + ("" if method == "POST" else "?" + data.decode())
    req = urllib.request.Request(url, data=data if method == "POST" else None, method=method)
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        raise SystemExit(f"API 오류 {e.code} ({path}): {body[:500]}")


def check_account(tok):
    me = call(tok, "GET", IG_USER, {"fields": "username"})
    if me.get("username") != EXPECTED:
        raise SystemExit(f"멈춤: 토큰이 가리키는 계정이 '{me.get('username')}' 입니다. '{EXPECTED}'가 아니면 게시하지 않습니다.")
    lim = call(tok, "GET", f"{IG_USER}/content_publishing_limit", {"fields": "quota_usage,config"})
    d = (lim.get("data") or [{}])[0]
    print(f"계정 확인: @{EXPECTED} · 24시간 게시 사용량 {d.get('quota_usage')}/{d.get('config', {}).get('quota_total')}")


def read_caption(folder, name):
    text = (folder / name).read_text(encoding="utf-8").strip()
    tags = re.findall(r"(?<!\w)#\w+", text)
    if len(tags) > 5:
        raise SystemExit(f"멈춤: {name}의 해시태그가 {len(tags)}개입니다(인스타 상한 5개).")
    if len(text) > 2200:
        raise SystemExit(f"멈춤: {name}이 {len(text)}자입니다(인스타 상한 2200자).")
    return text


def wait_ready(tok, cid, label, timeout=300):
    t0 = time.time()
    while time.time() - t0 < timeout:
        st = call(tok, "GET", cid, {"fields": "status_code,status"})
        code = st.get("status_code")
        if code == "FINISHED":
            return
        if code in ("ERROR", "EXPIRED"):
            raise SystemExit(f"{label} 준비 실패: {st.get('status')}")
        time.sleep(8)
    raise SystemExit(f"{label} 준비가 {timeout}초 안에 끝나지 않았어요.")


def publish(tok, cid, dry):
    if dry:
        print(f"[dry-run] 컨테이너 {cid} 준비 완료 — 게시하지 않음")
        return None
    res = call(tok, "POST", f"{IG_USER}/media_publish", {"creation_id": cid})
    mid = res["id"]
    link = call(tok, "GET", mid, {"fields": "permalink"}).get("permalink", "")
    print(f"게시 완료: {link or mid}")
    return link


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["check", "carousel", "reel"])
    ap.add_argument("--token", required=True)
    ap.add_argument("--date")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    tok = Path(a.token).read_text().strip()
    check_account(tok)
    if a.action == "check":
        return
    if not a.date:
        raise SystemExit("--date YYYY-MM-DD 가 필요해요")
    folder = REPO / "cards" / a.date
    base = RAW + f"cards/{a.date}/"

    if a.action == "carousel":
        cards = sorted(folder.glob("card_*.jpg"))
        if not 2 <= len(cards) <= 10:
            raise SystemExit(f"카드가 {len(cards)}장이에요(2~10장 필요).")
        caption = read_caption(folder, "caption.txt")
        children = []
        for c in cards:
            r = call(tok, "POST", f"{IG_USER}/media", {"image_url": base + c.name, "is_carousel_item": "true"})
            children.append(r["id"])
        for cid in children:
            wait_ready(tok, cid, "카드 이미지")
        parent = call(tok, "POST", f"{IG_USER}/media", {"media_type": "CAROUSEL", "children": ",".join(children),
                                                        "caption": caption})["id"]
        wait_ready(tok, parent, "캐러셀")
        publish(tok, parent, a.dry_run)

    elif a.action == "reel":
        if not (folder / "reel.mp4").exists():
            raise SystemExit("reel.mp4 가 없어요.")
        caption = read_caption(folder, "reel_caption.txt")
        r = call(tok, "POST", f"{IG_USER}/media", {"media_type": "REELS", "video_url": base + "reel.mp4",
                                                   "caption": caption, "share_to_feed": "true",
                                                   "thumb_offset": "1500"})
        wait_ready(tok, r["id"], "릴스", timeout=420)
        publish(tok, r["id"], a.dry_run)


if __name__ == "__main__":
    main()
