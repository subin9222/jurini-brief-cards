"""단색 배경 캐릭터 그림에서 배경을 지워 투명 PNG로 만든다.

사용법:  python3 tools/cutout.py <입력.png> <출력.png> [허용오차=40]
네 모서리에서 시작해 배경색과 비슷한 픽셀을 이어서 지운다(flood fill).
캐릭터의 굵은 외곽선이 경계가 되므로 캐릭터 안쪽은 지워지지 않는다.
"""
import sys
from collections import deque
from PIL import Image, ImageFilter


def cutout(src, dst, tol=40):
    im = Image.open(src).convert("RGBA")
    w, h = im.size
    px = im.load()
    seeds = [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]
    bg = tuple(sum(px[s][c] for s in seeds) // 4 for c in range(3))
    mask = Image.new("L", (w, h), 255)
    mp = mask.load()
    seen = bytearray(w * h)
    q = deque(seeds)
    while q:
        x, y = q.popleft()
        i = y * w + x
        if seen[i]:
            continue
        seen[i] = 1
        r, g, b, _ = px[x, y]
        if abs(r - bg[0]) + abs(g - bg[1]) + abs(b - bg[2]) > tol:
            continue
        mp[x, y] = 0
        if x > 0: q.append((x - 1, y))
        if x < w - 1: q.append((x + 1, y))
        if y > 0: q.append((x, y - 1))
        if y < h - 1: q.append((x, y + 1))
    mask = mask.filter(ImageFilter.GaussianBlur(1.2))
    im.putalpha(mask)
    bbox = mask.point(lambda v: 255 if v > 20 else 0).getbbox()
    im.crop(bbox).save(dst)
    print("saved", dst, im.crop(bbox).size, "bg", bg)


if __name__ == "__main__":
    cutout(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 40)
