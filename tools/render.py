"""주린이 브리핑 카드뉴스 렌더러 (네이비·크림·옐로 / 1080x1350 JPEG 7장)

사용법:  python3 tools/render.py <content.json> <출력 폴더>
content.json 구조는 tools/sample_content.json 참고.
문자열 필드 중 *_html 은 <br>, <em>(노란 강조), <b> 를 쓸 수 있다.
"""
import json
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

TOOLS = Path(__file__).resolve().parent
AVATAR = (TOOLS / "assets" / "avatar.png").as_uri()
FONT_CSS = (TOOLS / "fonts" / "jua" / "400.css").as_uri()
NUM = "style=\"font-family:'Noto Sans CJK KR',sans-serif;font-weight:900\""

CSS = """
* { margin:0; padding:0; box-sizing:border-box; }
:root { --navy:#0E1A3A; --cream:#FFF6E4; --yellow:#FFD24A; --up:#E5483A; --down:#2E6BE0; --mute:#8E98B8; }
body { width:1080px; height:1350px; background:var(--navy); color:var(--cream); overflow:hidden; position:relative;
  font-family:'Noto Sans CJK KR',sans-serif; letter-spacing:-0.6px; }
.bg { position:absolute; inset:0;
  background:
    radial-gradient(circle at 85% 12%, rgba(64,110,220,.35), transparent 45%),
    radial-gradient(circle at 10% 95%, rgba(255,210,74,.10), transparent 40%),
    linear-gradient(rgba(255,255,255,.035) 2px, transparent 2px) 0 0/100% 90px,
    linear-gradient(90deg, rgba(255,255,255,.035) 2px, transparent 2px) 0 0/90px 100%; }
.candles { position:absolute; right:70px; top:150px; display:flex; gap:14px; align-items:flex-end; opacity:.16; }
.candles i { display:block; width:16px; border-radius:4px; }
.frame { position:absolute; inset:0; padding:80px 84px; display:flex; flex-direction:column; }
.jua { font-family:'Jua','Noto Sans CJK KR',sans-serif; letter-spacing:-1px; font-weight:400; }
.top { display:flex; justify-content:space-between; align-items:center; }
.brand { display:flex; align-items:center; gap:18px; font-size:40px; }
.brand img { width:84px; height:84px; border-radius:50%; border:4px solid var(--cream); }
.brand b { color:var(--yellow); font-weight:400; }
.date { font-size:28px; color:var(--mute); }
.tag { align-self:flex-start; width:fit-content; margin-top:50px; background:var(--yellow); color:var(--navy); font-size:32px;
  padding:10px 26px 8px; border-radius:999px; box-shadow:0 6px 0 #B8901F; }
h2 { font-size:74px; line-height:1.18; margin-top:26px; position:relative; }
h1 em, h2 em { font-style:normal; color:var(--yellow); }
.spark { position:absolute; width:70px; height:70px; }
.spark i { position:absolute; left:50%; bottom:0; width:10px; height:30px; background:var(--yellow); border-radius:6px; transform-origin:50% 60px; }
.card { background:var(--cream); color:var(--navy); border-radius:34px; padding:32px 44px; box-shadow:0 10px 0 #060E24; border:4px solid #fff; }
.row { display:flex; justify-content:space-between; align-items:baseline; }
.label { font-size:40px; }
.big { font-size:84px; line-height:1.05; margin-top:4px; }
.chg { font-size:40px; }
.big.jua, .chg.jua { font-family:'Noto Sans CJK KR',sans-serif; font-weight:900; letter-spacing:-1.5px; }
.up { color:var(--up); } .down { color:var(--down); } .flat { color:#6B7280; }
.note { font-size:31px; line-height:1.55; color:#4A5470; margin-top:12px; }
.memo { font-size:30px; line-height:1.55; color:#CBD3EA; margin-top:30px; }
.memo b { color:var(--yellow); font-weight:700; }
.foot { position:absolute; left:84px; right:84px; bottom:58px; display:flex; justify-content:space-between;
  font-size:23px; color:var(--mute); border-top:2px solid rgba(255,255,255,.12); padding-top:22px; }
"""

ARROW = {"up": "▲", "down": "▼", "flat": "–"}


def sparkle(x, y, rot=0):
    rays = "".join(f"<i style='transform:translateX(-50%) rotate({a}deg)'></i>" for a in (-40, 0, 40))
    return f"<div class='spark' style='left:{x}px;top:{y}px;transform:rotate({rot}deg)'>{rays}</div>"


def candles():
    spec = [(70, 1), (110, 1), (90, 0), (150, 1), (130, 0), (190, 1), (230, 1), (210, 0), (280, 1)]
    bars = "".join(f"<i style='height:{h}px;background:{'#FF6B5B' if u else '#5B8CFF'}'></i>" for h, u in spec)
    return f"<div class='candles'>{bars}</div>"


def page(date_label, inner, n, total, source="", deco=True):
    foot_left = f"출처: {source}" if source else "투자 판단과 책임은 본인에게 있습니다"
    return f"""<!doctype html><html><head><meta charset='utf-8'>
<link rel='stylesheet' href='{FONT_CSS}'><style>{CSS}</style></head>
<body><div class='bg'></div>{candles() if deco else ''}
<div class='frame'>
<div class='top'><div class='brand jua'><img src='{AVATAR}'>주린이 <b>브리핑</b></div><span class='date jua'>{date_label}</span></div>
{inner}
</div>
<div class='foot'><span>{foot_left}</span><span class='jua' style='font-size:26px'>{n} / {total}</span></div>
</body></html>"""


def build(c):
    cards = []
    cv = c["cover"]
    cards.append((f"""
<div style='position:relative;margin-top:70px'>
  <div class='tag jua' style='margin-top:0'>{cv.get('pill', '오늘의 증시 3분 정리')}</div>
  {sparkle(640, 120, 20)}
  <h1 class='jua' style='font-size:118px;line-height:1.12;margin-top:40px;text-shadow:0 8px 0 #060E24'>{cv['title_html']}</h1>
  <p style='font-size:38px;line-height:1.6;color:#CBD3EA;margin-top:36px'>{cv['sub_html']}</p>
</div>
<img src='{AVATAR}' style='position:absolute;right:56px;bottom:120px;width:360px;height:360px;border-radius:50%;
  border:8px solid var(--cream);box-shadow:0 12px 0 #060E24'>""", "", False))

    d = c["domestic"]
    idx_html = ""
    for i, key in enumerate(["kospi", "kosdaq"]):
        x = d[key]
        name = "코스피" if key == "kospi" else "코스닥"
        note = f"<div class='note'>{x['note_html']}</div>" if x.get("note_html") else ""
        mt = "36px" if i == 0 else "24px"
        idx_html += f"""
<div class='card' style='margin-top:{mt}'>
  <div class='row'><span class='label jua'>{name}</span><span class='chg jua {x['dir']}'>{ARROW[x['dir']]} {x['chg']} ({x['pct']})</span></div>
  <div class='big jua'>{x['close']}</div>{note}
</div>"""
    cards.append((f"""
<div class='tag jua'>01 · 오늘의 국내 증시</div>
<h2 class='jua'>{d['title_html']}</h2>
{idx_html}
<p class='memo'>{d['memo_html']}</p>""", d["source"]))

    f = c["flows"]
    bars = ""
    for r in f["rows"]:
        color = "var(--down)" if r["dir"] == "down" else "var(--up)"
        bars += f"""
<div style='margin-top:36px'>
  <div class='row'><span class='label jua'>{r['name']}</span><span class='chg jua {r['dir']}' style='font-size:40px'>{r['amount']} {r['verb']}</span></div>
  <div style='height:34px;background:#EADFC8;border-radius:999px;margin-top:14px;overflow:hidden'>
    <div style='height:100%;width:{max(r['width'], 3)}%;background:{color};border-radius:999px'></div></div>
</div>"""
    cards.append((f"""
<div class='tag jua'>02 · 누가 사고, 누가 팔았나</div>
<h2 class='jua'>{f['title_html']}</h2>
<div class='card' style='margin-top:36px;padding-top:12px;padding-bottom:48px'>{bars}</div>
<p class='memo'>{f['memo_html']}</p>""", f["source"]))

    u = c["us"]
    rows = ""
    for i, r in enumerate(u["rows"]):
        mt = "0" if i == 0 else "26px"
        rows += f"<div class='row' style='margin-top:{mt}'><span class='label jua'>{r['name']}</span><span class='chg jua {r['dir']}'>{r['value']} · {r['pct']}</span></div>"
    cards.append((f"""
<div class='tag jua'>03 · 간밤의 미국 증시 ({u['session_label']})</div>
<h2 class='jua'>{u['title_html']}</h2>
<div class='card' style='margin-top:36px'>{rows}</div>
<p class='memo'>{u['memo_html']}</p>""", u["source"]))

    s = c["stocks"]
    items = ""
    for i, it in enumerate(s["items"]):
        mt = "36px" if i == 0 else "24px"
        items += f"""
<div class='card' style='margin-top:{mt}'>
  <div class='label jua'>{it['emoji']} {it['name']} <span class='{it['dir']}' {NUM}>{it['price']} ({it['pct']})</span></div>
  <div class='note' style='font-size:33px'>{it['desc_html']}</div>
</div>"""
    cards.append((f"""
<div class='tag jua'>04 · 오늘 눈에 띈 종목</div>
<h2 class='jua'>{s['title_html']}</h2>
{items}
<p class='memo' style='font-size:27px'>※ 특정 종목의 매수·매도를 권유하는 내용이 아닙니다.</p>""", s["source"]))

    t = c["term"]
    cards.append((f"""
<div class='tag jua'>05 · 오늘의 주린이 용어</div>
<div style='position:relative'>{sparkle(560, 20, 25)}
<h2 class='jua' style='font-size:{t.get('term_size', 116)}px;margin-top:26px'><em>{t['term']}</em></h2></div>
<p style='font-size:38px;line-height:1.5;margin-top:22px'>{t['def_html']}</p>
<div class='card' style='margin-top:40px'>
  <div class='label jua'>{t['analogy_title']}</div>
  <div class='note' style='font-size:33px;color:#2A3555'>{t['analogy_html']}</div>
</div>
<p class='memo'>{t['memo_html']}</p>""", ""))

    m = c["summary"]
    cards.append((f"""
<div style='position:relative;margin-top:60px'>
  <div class='tag jua' style='margin-top:0'>오늘의 한 줄 요약</div>
  <h2 class='jua' style='font-size:92px;margin-top:32px;text-shadow:0 8px 0 #060E24'>{m['title_html']}</h2>
  <p class='memo' style='font-size:36px'>{m['sub_html']}</p>
</div>
<div class='card' style='position:absolute;left:84px;right:84px;bottom:140px;display:flex;align-items:center;gap:30px;padding:30px 36px'>
  <img src='{AVATAR}' style='width:150px;height:150px;border-radius:50%;flex:none'>
  <div><div class='jua' style='font-size:42px'>평일 장 마감 후, 3분이면 충분!</div>
  <div style='font-size:29px;color:#4A5470;margin-top:8px'>팔로우하고 내일 브리핑도 받아보세요 🔔<br><b>@jurini.brief</b></div></div>
</div>""", "", False))
    return cards


def main():
    content = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    cards = build(content)
    total = len(cards)
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--allow-file-access-from-files"])
        pg = b.new_page(viewport={"width": 1080, "height": 1350})
        for i, (inner, src, *rest) in enumerate(cards, 1):
            deco = rest[0] if rest else True
            f = out / f"card_{i:02d}.html"
            f.write_text(page(content["date_label"], inner, i, total, src, deco), encoding="utf-8")
            pg.goto(f.as_uri())
            pg.wait_for_load_state("networkidle")
            pg.evaluate("document.fonts.ready")
            pg.wait_for_timeout(200)
            pg.screenshot(path=str(out / f"card_{i:02d}.jpg"), type="jpeg", quality=92)
            f.unlink()
        b.close()
    print(f"rendered {total} cards -> {out}")


if __name__ == "__main__":
    main()
