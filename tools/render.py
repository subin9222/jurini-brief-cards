"""주린이 브리핑 카드뉴스 렌더러 (네이비·크림·옐로 / 1080x1350 JPEG 7장)

사용법:  python3 tools/render.py <content.json> <출력 폴더>
content.json 구조:
  - 평일: tools/sample_content.json
  - 토요일(미국 주간 결산): tools/sample_saturday.json
  - 일요일(미국 경제 공부): tools/sample_sunday.json
  평일(2026-11-23 개편 이후)과 주말 모두 "cards" 배열에 카드 종류(type)를 순서대로 적는다.
  type: cover, market, flows, bars, issue, rows, indicators, list, stocks, term, preview
  옛 평일 형식(domestic/flows/us/... 키)도 계속 렌더링된다.
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
.bubble { position:absolute; left:84px; bottom:150px; background:var(--yellow); color:var(--navy); font-size:58px;
  padding:26px 40px 22px; border-radius:40px; box-shadow:0 10px 0 #B8901F; line-height:1.1; }
.bubble em { font-style:normal; color:#C2410C; }
.bubble::after { content:''; position:absolute; right:-34px; bottom:44px; border:20px solid transparent;
  border-left:30px solid var(--yellow); }
.bubble-sub { display:block; font-size:28px; color:#5A4A12; margin-top:10px; letter-spacing:-0.5px; }
.pv-item { padding:14px 0; }
.pv-label { font-size:34px; }
.pv-text { font-size:28px; line-height:1.48; color:#3A4462; margin-top:6px; letter-spacing:-0.8px; }
.pv-text b { color:var(--navy); }
.pv-sep { height:2px; background:#EADFC8; }
.watch { margin-top:26px; background:rgba(255,210,74,.14); border:3px solid var(--yellow); color:var(--yellow);
  border-radius:24px; padding:20px 30px 16px; font-size:36px; line-height:1.3; }
.cta { position:absolute; left:84px; right:84px; bottom:124px; display:flex; align-items:center; gap:22px; }
.cta img { width:96px; height:96px; border-radius:50%; border:4px solid var(--cream); flex:none; }
.bul { list-style:none; margin-top:26px; }
.bul li { position:relative; padding-left:30px; font-size:28px; line-height:1.45; color:#DCE2F2; margin-top:10px; letter-spacing:-0.8px; }
.bul li::before { content:''; position:absolute; left:4px; top:15px; width:12px; height:12px; background:var(--yellow); border-radius:3px; }
.bul b { color:var(--yellow); font-weight:700; }
.tagrow { display:flex; align-items:center; gap:16px; margin-top:50px; }
.cat { font-size:26px; color:var(--yellow); border:2px solid var(--yellow); border-radius:10px; padding:4px 14px 2px; }
.chart-cap { font-size:24px; color:#6B7390; margin-bottom:6px; letter-spacing:-0.5px; }
.idx { display:flex; gap:18px; }
.idx > div { flex:1; background:#fff; border-radius:20px; padding:16px 22px 14px; border:2px solid #EADFC8; }
.idx .nm { font-size:30px; }
.idx .vl { font-family:'Noto Sans CJK KR',sans-serif; font-weight:900; font-size:46px; letter-spacing:-1.5px; line-height:1.15; }
.idx .ch { font-family:'Noto Sans CJK KR',sans-serif; font-weight:800; font-size:28px; }
.stats { display:flex; gap:16px; }
.stats > div { flex:1; background:#fff; border-radius:20px; padding:18px 18px 16px; border:2px solid #EADFC8; text-align:center; }
.stats .lb { font-size:26px; color:#4A5470; letter-spacing:-0.6px; }
.stats .vl { font-family:'Noto Sans CJK KR',sans-serif; font-weight:900; font-size:46px; letter-spacing:-1.5px; line-height:1.2; margin-top:4px; }
.stats .sb { font-size:23px; color:#6B7390; margin-top:4px; letter-spacing:-0.5px; line-height:1.35; }
.qbub { position:absolute; left:250px; top:0; max-width:520px; background:#fff; color:var(--navy); border-radius:28px;
  padding:20px 26px 18px; font-size:30px; line-height:1.4; letter-spacing:-0.8px; box-shadow:0 8px 0 #060E24; }
.qbub::after { content:''; position:absolute; left:40px; bottom:-28px; border:16px solid transparent; border-top:20px solid #fff; }
.qbub b { color:var(--up); }
.nametag { position:absolute; bottom:110px; background:var(--cream); color:var(--navy); font-size:28px; font-weight:800;
  padding:8px 20px 6px; border-radius:12px; box-shadow:0 6px 0 #060E24; letter-spacing:-0.6px; }
.quote-by { margin-top:14px; font-size:28px; color:#CBD3EA; letter-spacing:-0.6px; }
.tl-row { display:flex; gap:22px; }
.tl-rail { width:30px; flex:none; display:flex; flex-direction:column; align-items:center; }
.tl-dot { width:24px; height:24px; border-radius:50%; border:5px solid var(--yellow); margin-top:18px; flex:none; }
.tl-line { flex:1; width:4px; background:rgba(255,210,74,.45); margin-top:4px; }
.tl-body { flex:1; background:var(--cream); color:var(--navy); border-radius:22px; padding:12px 24px 12px; margin-bottom:14px;
  box-shadow:0 6px 0 #060E24; }
.tl-now { background:var(--yellow); }
.tl-date { font-size:24px; color:#6B7390; }
.tl-now .tl-date { color:#5A4A12; }
.tl-title { font-size:32px; margin-top:0; }
.tl-text { font-size:25px; line-height:1.42; color:#3A4462; margin-top:4px; letter-spacing:-0.8px; }
.tl-now .tl-text { color:#3A2E08; }
.cover-q { position:absolute; left:84px; right:84px; bottom:130px; text-align:center; background:var(--yellow); color:var(--navy);
  font-size:44px; padding:18px 20px 14px; border-radius:24px; box-shadow:0 8px 0 #B8901F; }
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
    question = cv.get("question_html", "그래서 <em>내일은?</em>")
    cards.append((f"""
<div style='position:relative;margin-top:70px'>
  <div class='tag jua' style='margin-top:0'>{cv.get('pill', '오늘의 증시 3분 정리')}</div>
  {sparkle(640, 120, 20)}
  <h1 class='jua' style='font-size:112px;line-height:1.12;margin-top:40px;text-shadow:0 8px 0 #060E24'>{cv['title_html']}</h1>
  <p style='font-size:36px;line-height:1.55;color:#CBD3EA;margin-top:30px'>{cv['sub_html']}</p>
</div>
<div class='bubble jua'>{question}<span class='bubble-sub'>마지막 장에서 알려드려요 👉</span></div>
<img src='{AVATAR}' style='position:absolute;right:56px;bottom:120px;width:330px;height:330px;border-radius:50%;
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

    pv = c["preview"]
    items = ""
    for i, it in enumerate(pv["items"]):
        sep = "" if i == 0 else "<div class='pv-sep'></div>"
        items += f"""{sep}
  <div class='pv-item'><div class='pv-label jua'>{it['emoji']} {it['label']}</div>
  <div class='pv-text'>{it['text_html']}</div></div>"""
    cards.append((f"""
<div class='tag jua'>06 · 그래서 내일은?</div>
<h2 class='jua' style='font-size:68px;margin-top:22px'>{pv['title_html']}</h2>
<div class='card' style='margin-top:26px;padding:14px 40px'>{items}
</div>
<div class='watch jua'>👀 {pv['watch_html']}</div>
<div class='cta'><img src='{AVATAR}'><div><span class='jua' style='font-size:32px;color:var(--cream)'>내일 브리핑도 놓치지 마세요 🔔</span><br>
  <span style='font-size:25px;color:var(--mute)'>※ 예측이 아닌 관전 포인트예요 · @jurini.brief</span></div></div>""", pv["source"], False))
    return cards


# ---------------------------------------------------------------------------
# 주말용 범용 카드 (content.json 에 "cards": [...] 가 있으면 이 방식으로 그린다)
# type: cover / rows / indicators / list / stocks / term / preview
# ---------------------------------------------------------------------------

def _tag(t):
    return f"<div class='tag jua'>{t}</div>"


def _bullets(d):
    """mr.market식 3줄 요약: d['bullets'] = ["...", "...", "..."] (각 1~2줄, <b> 강조 가능)"""
    if not d.get("bullets"):
        return ""
    return "<ul class='bul'>" + "".join(f"<li>{b}</li>" for b in d["bullets"]) + "</ul>"


def _memo(d, size=None):
    out = ""
    if d.get("memo_html"):
        st = f" style='font-size:{size}px'" if size else ""
        out = f"<p class='memo'{st}>{d['memo_html']}</p>"
    return out + _bullets(d)


def _title(d, size=None):
    cat = f"<span class='cat jua'>{d['category']}</span>" if d.get("category") else ""
    st = f" style='font-size:{size}px'" if size else ""
    return (f"<div class='tagrow'><div class='tag jua' style='margin-top:0'>{d['tag']}</div>{cat}</div>"
            f"<h2 class='jua'{st}>{d['title_html']}</h2>")


# ---- SVG 차트 -------------------------------------------------------------
UP, DOWN, NAVY, GRID, MUTE = "#E5483A", "#2E6BE0", "#0E1A3A", "#E7DCC6", "#6B7390"
SVG_FONT = "font-family=\"'Noto Sans CJK KR',sans-serif\""


def _fmt(v, dec):
    return f"{v:,.{dec}f}"


def svg_line(spec, w=820, h=240):
    """꺾은선: {"labels":[...], "values":[...], "decimals":2, "caption":"..."}
    처음·마지막·최고·최저 값에 숫자를 단다. 마지막 점이 처음보다 높으면 빨강, 낮으면 파랑."""
    labels, vals = spec["labels"], [float(v) for v in spec["values"]]
    dec = spec.get("decimals", 2)
    pl, pr, pt, pb = 20, 150, 40, 40
    lo, hi = min(vals), max(vals)
    pad = (hi - lo) * 0.12 or 1
    lo, hi = lo - pad, hi + pad
    n = len(vals)
    xs = [pl + (w - pl - pr) * i / (n - 1) for i in range(n)]
    ys = [pt + (h - pt - pb) * (1 - (v - lo) / (hi - lo)) for v in vals]
    color = UP if vals[-1] >= vals[0] else DOWN
    out = [f"<svg width='{w}' height='{h}' viewBox='0 0 {w} {h}' xmlns='http://www.w3.org/2000/svg'>"]
    for k in range(4):
        y = pt + (h - pt - pb) * k / 3
        out.append(f"<line x1='{pl}' x2='{w-pr}' y1='{y:.1f}' y2='{y:.1f}' stroke='{GRID}' stroke-width='2'/>")
    area = " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))
    out.append(f"<polygon points='{xs[0]:.1f},{h-pb} {area} {xs[-1]:.1f},{h-pb}' fill='{color}' fill-opacity='0.10'/>")
    out.append(f"<polyline points='{area}' fill='none' stroke='{color}' stroke-width='5' stroke-linejoin='round' stroke-linecap='round'/>")
    imax, imin = vals.index(max(vals)), vals.index(min(vals))
    mark = {0, n - 1, imax, imin}
    for i, (x, y) in enumerate(zip(xs, ys)):
        r = 9 if i == n - 1 else 5
        out.append(f"<circle cx='{x:.1f}' cy='{y:.1f}' r='{r}' fill='{color if i == n-1 else '#fff'}' stroke='{color}' stroke-width='3'/>")
        if i == n - 1:
            out.append(f"<text x='{x+18:.1f}' y='{y+9:.1f}' text-anchor='start' {SVG_FONT} font-size='27' font-weight='900' fill='{color}'>{_fmt(vals[i], dec)}</text>")
        elif i in mark:
            anchor = "start" if i == 0 else "middle"
            above = i == imax or (i != imin and y > pt + 40)
            ty = y - 16 if above else y + 34
            out.append(f"<text x='{x:.1f}' y='{ty:.1f}' text-anchor='{anchor}' {SVG_FONT} font-size='22' font-weight='700' fill='{NAVY}'>{_fmt(vals[i], dec)}</text>")
    step = max(1, (n + 5) // 6)
    for i in range(n):
        if i % step == 0 or i == n - 1:
            if i != n - 1 and n - 1 - i < step:
                continue
            anchor = "start" if i == 0 else ("end" if i == n - 1 else "middle")
            out.append(f"<text x='{xs[i]:.1f}' y='{h-10}' text-anchor='{anchor}' {SVG_FONT} font-size='21' fill='{MUTE}'>{labels[i]}</text>")
    out.append("</svg>")
    return "".join(out)


def svg_diverge(spec, w=820):
    """등락 막대: {"items":[{"label":"나스닥","value":-2.25,"text":"−2.25%"}], "caption":"..."}
    0을 가운데 두고 상승은 오른쪽 빨강, 하락은 왼쪽 파랑."""
    items = spec["items"]
    row, lab_w = 54, 250
    h = row * len(items) + 8
    zero = lab_w + (w - lab_w) / 2
    half = (w - lab_w) / 2 - 125
    m = max(abs(float(it["value"])) for it in items) or 1
    out = [f"<svg width='{w}' height='{h}' viewBox='0 0 {w} {h}' xmlns='http://www.w3.org/2000/svg'>",
           f"<line x1='{zero:.1f}' x2='{zero:.1f}' y1='0' y2='{h}' stroke='#C9BDA4' stroke-width='2' stroke-dasharray='4 5'/>"]
    for i, it in enumerate(items):
        v = float(it["value"])
        y = i * row + 8
        bw = max(6, abs(v) / m * half)
        c = UP if v > 0 else DOWN
        x = zero if v > 0 else zero - bw
        out.append(f"<text x='0' y='{y+30}' {SVG_FONT} font-size='28' font-weight='700' fill='{NAVY}'>{it['label']}</text>")
        out.append(f"<rect x='{x:.1f}' y='{y+6}' width='{bw:.1f}' height='32' rx='8' fill='{c}'/>")
        tx, anc = (zero + bw + 10, "start") if v > 0 else (zero - bw - 10, "end")
        out.append(f"<text x='{tx:.1f}' y='{y+32}' text-anchor='{anc}' {SVG_FONT} font-size='26' font-weight='900' fill='{c}'>{it['text']}</text>")
    out.append("</svg>")
    return "".join(out)


def _chart(spec):
    cap = f"<div class='chart-cap'>{spec['caption']}</div>" if spec.get("caption") else ""
    body = svg_line(spec) if spec["type"] == "line" else svg_diverge(spec)
    return cap + body


def _dir_cls(d):
    return {"up": "up", "down": "down"}.get(d, "flat")


def g_cover(d):
    question = d.get("question_html", "그래서 <em>다음 주는?</em>")
    bsub = d.get("bubble_sub", "마지막 장에서 알려드려요 👉")
    return (f"""
<div style='position:relative;margin-top:70px'>
  <div class='tag jua' style='margin-top:0'>{d.get('pill', '이번 주 미국 경제 결산')}</div>
  {sparkle(640, 120, 20)}
  <h1 class='jua' style='font-size:{d.get('title_size', 108)}px;line-height:1.12;margin-top:40px;text-shadow:0 8px 0 #060E24'>{d['title_html']}</h1>
  <p style='font-size:36px;line-height:1.55;color:#CBD3EA;margin-top:30px'>{d['sub_html']}</p>
</div>
<div class='bubble jua'>{question}<span class='bubble-sub'>{bsub}</span></div>
<img src='{AVATAR}' style='position:absolute;right:56px;bottom:120px;width:330px;height:330px;border-radius:50%;
  border:8px solid var(--cream);box-shadow:0 12px 0 #060E24'>""", "", False)


def g_rows(d):
    rows = ""
    for i, r in enumerate(d["rows"]):
        mt = "0" if i == 0 else "26px"
        rows += (f"<div class='row' style='margin-top:{mt}'><span class='label jua'>{r['name']}</span>"
                 f"<span class='chg jua {r['dir']}'>{r['value']} · {r['pct']}</span></div>")
    return (f"""{_tag(d['tag'])}
<h2 class='jua'>{d['title_html']}</h2>
<div class='card' style='margin-top:36px'>{rows}</div>
{_memo(d)}""", d.get("source", ""))


def g_indicators(d):
    items = ""
    for i, it in enumerate(d["items"]):
        sep = "" if i == 0 else "<div class='pv-sep'></div>"
        note = f"<div class='pv-text'>{it['note_html']}</div>" if it.get("note_html") else ""
        items += f"""{sep}
  <div class='pv-item'><div class='row'><span class='label jua'>{it['name']}</span>
  <span class='jua {it.get('dir', '')}' {NUM_STYLE_BIG}>{it['value']}</span></div>{note}</div>"""
    return (f"""{_tag(d['tag'])}
<h2 class='jua'>{d['title_html']}</h2>
<div class='card' style='margin-top:32px;padding:14px 40px'>{items}</div>
{_memo(d)}""", d.get("source", ""))


def g_list(d):
    items = ""
    for i, it in enumerate(d["items"]):
        sep = "" if i == 0 else "<div class='pv-sep'></div>"
        items += f"""{sep}
  <div class='pv-item'><div class='pv-label jua'>{it['emoji']} {it['label']}</div>
  <div class='pv-text'>{it['text_html']}</div></div>"""
    return (f"""{_tag(d['tag'])}
<h2 class='jua' style='font-size:{d.get('title_size', 70)}px'>{d['title_html']}</h2>
<div class='card' style='margin-top:30px;padding:14px 40px'>{items}</div>
{_memo(d)}""", d.get("source", ""))


def g_stocks(d):
    items = ""
    for i, it in enumerate(d["items"]):
        mt = "36px" if i == 0 else "24px"
        items += f"""
<div class='card' style='margin-top:{mt}'>
  <div class='label jua'>{it['emoji']} {it['name']} <span class='{it['dir']}' {NUM}>{it['price']} ({it['pct']})</span></div>
  <div class='note' style='font-size:31px'>{it['desc_html']}</div>
</div>"""
    memo = d.get("memo_html", "※ 특정 종목의 매수·매도를 권유하는 내용이 아닙니다.")
    return (f"""{_tag(d['tag'])}
<h2 class='jua'>{d['title_html']}</h2>
{items}
<p class='memo' style='font-size:27px'>{memo}</p>""", d.get("source", ""))


def g_term(d):
    return (f"""{_tag(d['tag'])}
<div style='position:relative'>{sparkle(560, 20, 25)}
<h2 class='jua' style='font-size:{d.get('term_size', 116)}px;margin-top:26px'><em>{d['term']}</em></h2></div>
<p style='font-size:38px;line-height:1.5;margin-top:22px'>{d['def_html']}</p>
<div class='card' style='margin-top:40px'>
  <div class='label jua'>{d['analogy_title']}</div>
  <div class='note' style='font-size:33px;color:#2A3555'>{d['analogy_html']}</div>
</div>
{_memo(d)}""", d.get("source", ""))


def g_preview(d):
    items = ""
    for i, it in enumerate(d["items"]):
        sep = "" if i == 0 else "<div class='pv-sep'></div>"
        items += f"""{sep}
  <div class='pv-item'><div class='pv-label jua'>{it['emoji']} {it['label']}</div>
  <div class='pv-text'>{it['text_html']}</div></div>"""
    note = d.get("cta_note", "※ 예측이 아닌 관전 포인트예요")
    return (f"""{_tag(d['tag'])}
<h2 class='jua' style='font-size:68px;margin-top:22px'>{d['title_html']}</h2>
<div class='card' style='margin-top:26px;padding:14px 40px'>{items}
</div>
<div class='watch jua'>👀 {d['watch_html']}</div>
<div class='cta'><img src='{AVATAR}'><div><span class='jua' style='font-size:32px;color:var(--cream)'>{d.get('cta_title', '다음 브리핑도 놓치지 마세요 🔔')}</span><br>
  <span style='font-size:25px;color:var(--mute)'>{note} · @jurini.brief</span></div></div>""", d.get("source", ""), False)


def svg_person(x, y, s, body, face_q=False, point=False, tie=None):
    """얼굴 없는 실루엣 인물. (x, y)=머리 중심, s=크기 배율. 실존 인물의 얼굴은 그리지 않는다."""
    hr = 62 * s
    parts = []
    if point:  # 오른쪽으로 뻗은 팔(지목)
        ax, ay = x + 70 * s, y + 175 * s
        parts.append(f"<g transform='rotate(-14 {ax:.0f} {ay:.0f})'><rect x='{ax:.0f}' y='{ay-24*s:.0f}' width='{230*s:.0f}' height='{48*s:.0f}' rx='{24*s:.0f}' fill='{body}'/>"
                     f"<circle cx='{ax+232*s:.0f}' cy='{ay:.0f}' r='{30*s:.0f}' fill='{body}'/>"
                     f"<rect x='{ax+236*s:.0f}' y='{ay-12*s:.0f}' width='{58*s:.0f}' height='{20*s:.0f}' rx='{10*s:.0f}' fill='{body}'/></g>")
    parts.append(f"<path d='M{x-150*s:.0f},{y+420*s:.0f} C{x-150*s:.0f},{y+190*s:.0f} {x-95*s:.0f},{y+105*s:.0f} {x:.0f},{y+105*s:.0f} "
                 f"C{x+95*s:.0f},{y+105*s:.0f} {x+150*s:.0f},{y+190*s:.0f} {x+150*s:.0f},{y+420*s:.0f} Z' fill='{body}'/>")
    if tie:
        parts.append(f"<path d='M{x:.0f},{y+112*s:.0f} l{-16*s:.0f},{22*s:.0f} l{16*s:.0f},{130*s:.0f} l{16*s:.0f},{-130*s:.0f} Z' fill='{tie}'/>")
    parts.append(f"<circle cx='{x:.0f}' cy='{y:.0f}' r='{hr:.0f}' fill='{body}'/>")
    if face_q:
        parts.append(f"<text x='{x:.0f}' y='{y+34*s:.0f}' text-anchor='middle' font-family=\"'Jua'\" font-size='{100*s:.0f}' fill='#FFD24A'>?</text>")
    return "".join(parts)


def g_cover_issue(d):
    """이슈 표지: 질문형 제목 + '누가 누구를' 장면(실루엣) + 말풍선 인용.
    d: pill, title_html, speaker(이름표), quote_html(말풍선), target(물음표 인물 이름표), sub_html, question_html"""
    w, h = 912, 640
    scene = (f"<svg width='{w}' height='{h}' viewBox='0 0 {w} {h}' xmlns='http://www.w3.org/2000/svg'>"
             f"<defs><radialGradient id='spot' cx='50%' cy='40%' r='60%'><stop offset='0%' stop-color='#FFD24A' stop-opacity='.38'/>"
             f"<stop offset='100%' stop-color='#FFD24A' stop-opacity='0'/></radialGradient></defs>"
             f"<ellipse cx='690' cy='330' rx='200' ry='290' fill='url(#spot)'/>"
             + ("" if d.get("speaker_img") else svg_person(205, 250, 0.92, "#E9E1CF", point=True, tie="#E5483A"))
             + svg_person(690, 250, 0.92, "#25365F", face_q=True)
             + "</svg>")
    bub = f"<div class='qbub'>{d['quote_html']}</div>" if d.get("quote_html") else ""
    who = f"<div class='quote-by'>{d['quote_by']}</div>" if d.get("quote_by") else ""
    scene_top = d.get("scene_top", 16)
    speaker_img = ""
    if d.get("speaker_img"):  # AI로 그린 캐리커처(배경 제거 PNG). content.json 기준 상대 경로
        src = (CONTENT_DIR / d["speaker_img"]).resolve().as_uri()
        speaker_img = (f"<img src='{src}' style='position:absolute;left:{d.get('speaker_x', -10)}px;bottom:-30px;"
                       f"height:{d.get('speaker_h', 600)}px;filter:drop-shadow(0 10px 0 #060E24)'>")
    return (f"""
<div class='tag jua' style='margin-top:44px'>{d.get('pill', '오늘의 이슈')}</div>
<h1 class='jua' style='font-size:{d.get('title_size', 96)}px;line-height:1.16;margin-top:24px;text-shadow:0 8px 0 #060E24'>{d['title_html']}</h1>
{who}
<div style='position:relative;margin-top:{scene_top}px;height:{h - 40}px;overflow:hidden'>
  <div style='position:absolute;left:-16px;top:0'>{scene}</div>
  {speaker_img}
  {bub}
  <div class='nametag' style='left:60px'>{d['speaker']}</div>
  <div class='nametag' style='left:556px;background:#FFD24A;color:#0E1A3A'>{d['target']}</div>
</div>
<div class='cover-q jua'>{d.get('question_html', '정답은 안에서 👉')}</div>""", d.get("source", ""), False)


def g_timeline(d):
    """이야기 흐름 카드: 날짜별 사건을 세로 타임라인으로. items: [{date, title, text_html, dir?}]
    마지막 항목이 '지금'이며 노란색으로 강조된다."""
    rows = ""
    n = len(d["items"])
    for i, it in enumerate(d["items"]):
        last = i == n - 1
        dot = "var(--yellow)" if last else "#fff"
        line = "" if last else "<div class='tl-line'></div>"
        rows += f"""
<div class='tl-row'>
  <div class='tl-rail'><div class='tl-dot' style='background:{dot}'></div>{line}</div>
  <div class='tl-body{' tl-now' if last else ''}'><div class='tl-date jua'>{it['date']}</div>
    <div class='tl-title jua'>{it['title']}</div><div class='tl-text'>{it['text_html']}</div></div>
</div>"""
    return (f"""{_title(d, 60)}
<div style='margin-top:22px'>{rows}</div>
{_bullets(d)}""", d.get("source", ""))


def g_market(d):
    """국내 증시: 지수 박스 2개 + 최근 흐름 꺾은선 + 3줄 요약"""
    boxes = "".join(
        f"<div><div class='nm jua'>{x['name']}</div><div class='vl'>{x['close']}</div>"
        f"<div class='ch {_dir_cls(x['dir'])}'>{ARROW.get(x['dir'], '')} {x['chg']} ({x['pct']})</div></div>"
        for x in d["indices"])
    return (f"""{_title(d, 66)}
<div class='card' style='margin-top:26px;padding:24px 30px 18px'>
  <div class='idx'>{boxes}</div>
  <div style='margin-top:18px'>{_chart(d['chart'])}</div>
</div>
{_bullets(d)}""", d.get("source", ""))


def g_flows(d):
    """투자자별 매매: 막대 + 3줄 요약"""
    bars = ""
    for r in d["rows"]:
        color = "var(--down)" if r["dir"] == "down" else "var(--up)"
        bars += f"""
<div style='margin-top:24px'>
  <div class='row'><span class='label jua' style='font-size:36px'>{r['name']}</span><span class='chg jua {r['dir']}' style='font-size:36px'>{r['amount']} {r['verb']}</span></div>
  <div style='height:30px;background:#EADFC8;border-radius:999px;margin-top:10px;overflow:hidden'>
    <div style='height:100%;width:{max(r['width'], 3)}%;background:{color};border-radius:999px'></div></div>
</div>"""
    extra = f"<div class='chart-cap' style='margin-top:18px'>{d['caption']}</div>" if d.get("caption") else ""
    return (f"""{_title(d, 66)}
<div class='card' style='margin-top:26px;padding:6px 40px 30px'>{bars}{extra}</div>
{_bullets(d)}""", d.get("source", ""))


def g_bars(d):
    """등락 막대 그래프(미국장 등) + 3줄 요약"""
    return (f"""{_title(d, 66)}
<div class='card' style='margin-top:26px;padding:24px 30px 20px'>{_chart(d['chart'])}</div>
{_bullets(d)}""", d.get("source", ""))


def g_issue(d):
    """오늘의 이슈: 수치 박스 2~3개(+선택 꺾은선/막대) + 3줄 요약"""
    stats = "".join(
        f"<div><div class='lb'>{s['label']}</div><div class='vl {_dir_cls(s.get('dir'))}'>{s['value']}</div>"
        f"<div class='sb'>{s.get('sub', '')}</div></div>" for s in d["stats"])
    chart = f"<div style='margin-top:18px'>{_chart(d['chart'])}</div>" if d.get("chart") else ""
    return (f"""{_title(d, 64)}
<div class='card' style='margin-top:26px;padding:24px 26px 22px'><div class='stats'>{stats}</div>{chart}</div>
{_bullets(d)}""", d.get("source", ""))


NUM_STYLE_BIG = "style=\"font-family:'Noto Sans CJK KR',sans-serif;font-weight:900;font-size:44px;letter-spacing:-1.5px\""
GENERIC = {"cover": g_cover, "rows": g_rows, "indicators": g_indicators, "list": g_list,
           "stocks": g_stocks, "term": g_term, "preview": g_preview,
           "market": g_market, "flows": g_flows, "bars": g_bars, "issue": g_issue,
           "cover_issue": g_cover_issue, "timeline": g_timeline}


def build_generic(c):
    return [GENERIC[d["type"]](d) for d in c["cards"]]


CONTENT_DIR = Path(".")


def main():
    global CONTENT_DIR
    CONTENT_DIR = Path(sys.argv[1]).resolve().parent
    content = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    out = Path(sys.argv[2]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    cards = build_generic(content) if "cards" in content else build(content)
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
