"""카드 이미지(card_01.jpg …)를 세로 릴스 영상(1080x1920, 30fps, 무음)으로 만든다.

사용법:  python3 tools/reel.py <카드 폴더> [출력 mp4]
  - 카드 폴더: render.py가 만든 card_01.jpg … 가 있는 폴더
  - 출력 기본값: <카드 폴더>/reel.mp4

구성
  - 카드를 90%로 줄여 릴스 '안전 영역'(위 230px, 아래 약 470px는 인스타 버튼·캡션에 가려짐) 안에 둔다.
  - 위: 브랜드 + 진행 막대(몇 번째 장인지), 아래: 안내 문구.
  - 첫 장(표지)은 0.4초 동안 살짝 확대됐다가 제자리로(시선 끌기), 이후 장은 0.35초 옆으로 밀려 들어온다.
  - 장마다 영상 파일 하나 → 마지막에 이어 붙이기(-c copy).
"""
import subprocess
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

TOOLS = Path(__file__).resolve().parent
FONT_CSS = (TOOLS / "fonts" / "jua" / "400.css").as_uri()
AVATAR = (TOOLS / "assets" / "avatar.png").as_uri()
W, H, FPS = 1080, 1920, 30
COVER_SEC, PAGE_SEC, END_SEC, XF = 3.2, 3.0, 3.0, 0.35
ENC = ["-c:v", "libx264", "-crf", "20", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-r", str(FPS)]

FRAME = """<!doctype html><html><head><meta charset='utf-8'><link rel='stylesheet' href='{font}'>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ width:1080px; height:1920px; overflow:hidden; font-family:'Jua','Noto Sans CJK KR',sans-serif;
  background:radial-gradient(120% 70% at 50% 40%, #1C2C5E 0%, #0E1A3A 55%, #060E24 100%); color:#FFF6E4; position:relative; }}
.top {{ position:absolute; left:54px; right:54px; top:120px; display:flex; align-items:center; gap:16px; }}
.top img {{ width:64px; height:64px; border-radius:50%; border:3px solid #FFF6E4; }}
.top .nm {{ font-size:38px; }} .top .nm b {{ color:#FFD24A; font-weight:400; }}
.top .dt {{ margin-left:auto; font-size:30px; color:#B9C2DE; }}
.bar {{ position:absolute; left:54px; right:54px; top:196px; display:flex; gap:8px; }}
.bar i {{ flex:1; height:8px; border-radius:4px; background:rgba(255,246,228,.22); }}
.bar i.on {{ background:#FFD24A; }}
.card {{ position:absolute; left:54px; top:236px; width:972px; height:1215px; border-radius:30px; overflow:hidden;
  box-shadow:0 14px 0 rgba(6,14,36,.8), 0 0 0 4px rgba(255,246,228,.9); }}
.card img {{ width:100%; height:100%; display:block; }}
.hint {{ position:absolute; left:0; right:0; top:1490px; text-align:center; font-size:40px; color:#FFD24A; }}
.hint small {{ display:block; font-size:30px; color:#B9C2DE; margin-top:10px; }}
</style></head><body>
<div class='bar'>{bar}</div>
<div class='card'><img src='{card}'></div>
<div class='hint'>{hint}</div>
</body></html>"""

END = """<!doctype html><html><head><meta charset='utf-8'><link rel='stylesheet' href='{font}'>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ width:1080px; height:1920px; overflow:hidden; font-family:'Jua',sans-serif; color:#FFF6E4; text-align:center;
  background:radial-gradient(120% 70% at 50% 40%, #1C2C5E 0%, #0E1A3A 55%, #060E24 100%); }}
.box {{ position:absolute; left:0; right:0; top:430px; }}
img.m {{ height:520px; }}
h1 {{ font-size:84px; line-height:1.25; margin-top:30px; }} h1 em {{ color:#FFD24A; font-style:normal; }}
p {{ font-size:40px; color:#B9C2DE; margin-top:28px; line-height:1.5; }}
.id {{ display:inline-block; margin-top:40px; background:#FFD24A; color:#0E1A3A; font-size:46px; padding:14px 40px; border-radius:40px; }}
</style></head><body><div class='box'>
<img class='m' src='{mascot}'>
<h1>매일 장 마감 후<br><em>주린이 눈높이</em>로 정리해요</h1>
<p>저장해 두고 뉴스 볼 때 꺼내 보세요 📌</p>
<div class='id'>@jurini.brief 팔로우</div>
</div></body></html>"""


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(r.stderr[-2000:])


def date_label(folder: Path):
    try:
        import json
        c = json.loads((folder / "content.json").read_text(encoding="utf-8"))
        return c.get("date_label", "")
    except Exception:
        return ""


def main():
    folder = Path(sys.argv[1]).resolve()
    out = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else folder / "reel.mp4"
    cards = sorted(folder.glob("card_*.jpg"))
    if not cards:
        raise SystemExit("카드 이미지(card_*.jpg)가 없어요")
    n = len(cards)
    dl = date_label(folder)
    tmp = Path(tempfile.mkdtemp(prefix="reel_"))

    # 1) 장마다 세로 프레임(png) 그리기
    frames = []
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--allow-file-access-from-files"])
        pg = b.new_page(viewport={"width": W, "height": H})
        for i, c in enumerate(cards):
            bar = "".join(f"<i class='{'on' if k <= i else ''}'></i>" for k in range(n))
            hint = ("넘겨 보면 정답이 나와요 👉<small>끝까지 보고 저장해 두세요 📌</small>" if i == 0 else
                    ("내일 장도 같이 봐요 🔔<small>@jurini.brief</small>" if i == n - 1 else ""))
            html = tmp / f"f{i}.html"
            html.write_text(FRAME.format(font=FONT_CSS, avatar=AVATAR, date=dl, bar=bar, card=c.as_uri(), hint=hint),
                            encoding="utf-8")
            pg.goto(html.as_uri()); pg.wait_for_load_state("networkidle"); pg.evaluate("document.fonts.ready")
            pg.wait_for_timeout(150)
            f = tmp / f"f{i}.png"; pg.screenshot(path=str(f)); frames.append(f)
        mascot = TOOLS / "cast" / "jurini_cheer.png"
        html = tmp / "end.html"
        html.write_text(END.format(font=FONT_CSS, mascot=mascot.as_uri()), encoding="utf-8")
        pg.goto(html.as_uri()); pg.wait_for_load_state("networkidle"); pg.evaluate("document.fonts.ready")
        pg.wait_for_timeout(150)
        end_png = tmp / "end.png"; pg.screenshot(path=str(end_png))
        b.close()
    frames.append(end_png)

    # 2) 장마다 영상 파일
    parts = []
    for i, f in enumerate(frames):
        part = tmp / f"p{i:02d}.mp4"; work = tmp / f"p{i:02d}.tmp.mp4"
        if i == 0:   # 표지: 살짝 확대 → 제자리 (0.4초)
            d = COVER_SEC
            vf = (f"format=yuv420p,loop=-1:1,trim=duration={d},setpts=PTS-STARTPTS,"
                  f"scale=w='trunc({W}*(1+0.07*max(0\\,1-t/0.4))/2)*2':h=-2:eval=frame,"
                  f"crop={W}:{H},fade=t=in:st=0:d=0.25")
            run(["ffmpeg", "-y", "-framerate", str(FPS), "-i", str(f), "-vf", vf, *ENC, "-t", str(d), str(work)])
        else:        # 앞 장에서 옆으로 밀려 들어오기
            d = END_SEC if i == len(frames) - 1 else PAGE_SEC
            prev = frames[i - 1]
            fc = (f"[0:v]format=yuv420p,loop=-1:1,trim=duration={XF},setpts=PTS-STARTPTS[a];"
                  f"[1:v]format=yuv420p,loop=-1:1,trim=duration={d + XF},setpts=PTS-STARTPTS[b];"
                  f"[a][b]xfade=transition=slideleft:duration={XF}:offset=0[v]")
            run(["ffmpeg", "-y", "-framerate", str(FPS), "-i", str(prev), "-framerate", str(FPS), "-i", str(f),
                 "-filter_complex", fc, "-map", "[v]", *ENC, "-t", str(d), str(work)])
        work.rename(part); parts.append(part)

    # 3) 이어 붙이기 + 무음 오디오 트랙(일부 앱이 오디오 없는 영상을 거부하는 경우 대비)
    lst = tmp / "list.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in parts), encoding="utf-8")
    joined = tmp / "joined.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(joined)])
    work = out.with_suffix(".tmp.mp4")
    run(["ffmpeg", "-y", "-i", str(joined), "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
         "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-shortest",
         "-movflags", "+faststart", str(work)])
    work.rename(out)
    print(f"reel -> {out}")


if __name__ == "__main__":
    main()
