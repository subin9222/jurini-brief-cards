"""인스타그램 공식 API로 @jurini.brief에 직접 게시한다 (Metricool 대신, 무료).

사용법:
  python3 tools/ig_post.py check  --token <토큰파일>                      # 연결 확인만 (게시 안 함)
  python3 tools/ig_post.py carousel --token <토큰파일> --date YYYY-MM-DD    # 카드 7장 캐러셀 게시
  python3 tools/ig_post.py reel     --token <토큰파일> --date YYYY-MM-DD    # 릴스 게시
  python3 tools/ig_post.py recent   --token <토큰파일>                      # 최근 게시물 3개 보기
  python3 tools/ig_post.py metrics  --token <토큰파일>                      # 최근 게시물 10개의 좋아요·댓글 수 (METRICS.md 기록용)
  (--dry-run 을 붙이면 컨테이너 준비까지만 하고 게시하지 않는다)

- 토큰은 비공개 저장소 subin9222/jurini-secrets 의 ig_token.txt (절대 이 공개 저장소에 넣지 않는다).
- 게시 직전에 토큰이 가리키는 계정 이름이 반드시 'jurini.brief'인지 확인하고, 아니면 멈춘다.
- 미디어는 이 공개 저장소의 raw.githubusercontent.com 주소를 인스타그램이 직접 가져간다(먼저 push 필요).
- 캡션: cards/<날짜>/caption.txt (캐러셀), reel_caption.txt (릴스). 해시태그 5개 초과면 멈춘다.
- media_publish 가 오류를 돌려줘도 실제로는 게시되는 경우가 있다(2026-11-24 두 번 발생, 403 code 4 / 2207051).
  그래서 게시 오류가 나면 최근 게시물을 조회해 같은 캡션의 새 게시물이 있으면 '게시 확인'으로 처리하고 그 링크를 출력한다.
  없을 때만 오류로 끝난다(그때 한 번만 재시도).
"""
import argparse
import calendar
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


class ApiError(SystemExit):
    """API 오류. 잡지 않으면 예전처럼 메시지를 출력하고 종료한다."""


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
        raise ApiError(f"API 오류 {e.code} ({path}): {body[:500]}")


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


def recent_media(tok, limit=3):
    r = call(tok, "GET", f"{IG_USER}/media", {"fields": "timestamp,media_type,permalink,caption", "limit": limit})
    return r.get("data", [])


def find_published(tok, caption, since, tries=4, wait=10):
    """since(유닉스 시각) 이후에 올라온, 캡션 첫 줄이 같은 게시물을 찾는다. 없으면 None."""
    first = caption.strip().splitlines()[0].strip()
    for i in range(tries):
        time.sleep(wait)
        for m in recent_media(tok, 5):
            ts = calendar.timegm(time.strptime(m["timestamp"][:19], "%Y-%m-%dT%H:%M:%S"))
            cap = (m.get("caption") or "").strip().splitlines()
            if ts >= since - 60 and cap and cap[0].strip() == first:
                return m.get("permalink") or m.get("id")
    return None


def publish(tok, cid, dry, caption):
    if dry:
        print(f"[dry-run] 컨테이너 {cid} 준비 완료 — 게시하지 않음")
        return None
    started = time.time()
    try:
        res = call(tok, "POST", f"{IG_USER}/media_publish", {"creation_id": cid})
    except ApiError as e:
        print(f"게시 요청이 오류를 돌려줬어요: {e}")
        print("실제로 올라갔는지 최근 게시물을 확인할게요…")
        link = find_published(tok, caption, started)
        if link:
            print(f"게시 확인(오류가 났지만 실제로 올라갔어요 — 재시도하지 마세요): {link}")
            return link
        raise ApiError(f"{e}\n→ 최근 게시물에 없어요. 실제로 게시되지 않았으니 한 번만 재시도해도 돼요.")
    mid = res["id"]
    link = call(tok, "GET", mid, {"fields": "permalink"}).get("permalink", "")
    print(f"게시 완료: {link or mid}")
    return link


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["check", "recent", "metrics", "carousel", "reel"])
    ap.add_argument("--token", required=True)
    ap.add_argument("--date")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    tok = Path(a.token).read_text().strip()
    check_account(tok)
    if a.action == "check":
        return
    if a.action == "recent":
        for m in recent_media(tok, 3):
            print(m["timestamp"], m["media_type"], m.get("permalink"), (m.get("caption") or "")[:40].replace("\n", " "))
        return
    if a.action == "metrics":  # 좋아요·댓글만 (공유·저장·도달은 앱 권한이 없어 API로 못 가져옴)
        r = call(tok, "GET", f"{IG_USER}/media", {"fields": "timestamp,media_product_type,like_count,comments_count,permalink,caption", "limit": 10})
        for m in r.get("data", []):
            print(m["timestamp"], m.get("media_product_type"), f"좋아요 {m.get('like_count')} 댓글 {m.get('comments_count')}",
                  m.get("permalink"), (m.get("caption") or "")[:30].replace("\n", " "))
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
        publish(tok, parent, a.dry_run, caption)

    elif a.action == "reel":
        if not (folder / "reel.mp4").exists():
            raise SystemExit("reel.mp4 가 없어요.")
        caption = read_caption(folder, "reel_caption.txt")
        r = call(tok, "POST", f"{IG_USER}/media", {"media_type": "REELS", "video_url": base + "reel.mp4",
                                                   "caption": caption, "share_to_feed": "true",
                                                   "thumb_offset": "1500"})
        wait_ready(tok, r["id"], "릴스", timeout=420)
        publish(tok, r["id"], a.dry_run, caption)


if __name__ == "__main__":
    main()
