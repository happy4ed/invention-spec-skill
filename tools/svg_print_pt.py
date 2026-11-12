#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""도면 SVG 의 인쇄 글자 크기 검사 — 문서에 넣었을 때 글자가 몇 pt 로 찍히는가.

  python3 svg_print_pt.py figures/
  python3 svg_print_pt.py figures/ --width-mm 170 --max-height-mm 247 --min-pt 8

계산
  인쇄 폭(mm) = min(본문 폭, 최대 높이 ÷ (세로/가로 비))
  실제 pt     = SVG 안 최소 font-size × 인쇄 폭 ÷ viewBox 폭 × 72 ÷ 25.4
같은 이름의 .png 가 있으면 그 비율을, 없으면 viewBox 비율을 쓴다(PNG 비율 확인에는 Pillow 필요).

본문 폭 기본값 180mm 는 A4(210mm) 에 좌우 여백 15mm 를 둔 값이다. 쓰는 양식의 여백에 맞춰 바꿔라.
도면 viewBox 폭을 본문 폭과 같은 pt 값(180mm = 510.24pt)으로 잡으면 SVG 의 font-size 가 곧 종이 위 pt 가 된다.
글자를 줄여 맞추지 말고 박스 수를 줄여라. 세부는 다른 도면과 본문이 맡는다.
종료 코드: 최소 pt 미달 도면이 있으면 1.
"""
import argparse
import glob
import os
import re
import sys


def png_ratio(path):
    try:
        from PIL import Image
    except ImportError:
        return None
    with Image.open(path) as im:
        w, h = im.size
    return h / w


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+", help="SVG 가 들어 있는 폴더(여러 개 가능)")
    ap.add_argument("--width-mm", type=float, default=180.0, help="본문 폭 mm (기본 180)")
    ap.add_argument("--max-height-mm", type=float, default=260.0, help="그림 최대 높이 mm (기본 260)")
    ap.add_argument("--min-pt", type=float, default=8.0, help="허용 최소 인쇄 글자 pt (기본 8)")
    a = ap.parse_args()

    bad = 0
    for d in a.dirs:
        svgs = sorted(glob.glob(os.path.join(d, "*.svg")))
        print(f"== {d} ({len(svgs)}개)")
        rows = []
        for svg in svgs:
            s = open(svg, encoding="utf-8").read()
            m = re.search(r'viewBox="\s*([-\d.]+)[ ,]+([-\d.]+)[ ,]+([\d.]+)[ ,]+([\d.]+)\s*"', s)
            if not m:
                rows.append((-1, os.path.basename(svg), "viewBox 없음 — 폭을 정할 수 없다"))
                continue
            vw, vh = float(m.group(3)), float(m.group(4))
            fs = [float(x) for x in re.findall(r'font-size\s*[:=]\s*"?\s*([\d.]+)', s)]
            if not fs:
                rows.append((99, os.path.basename(svg), "font-size 없음(글자 없는 도면이거나 외곽선 글자)"))
                continue
            png = svg[:-4] + ".png"
            ratio = png_ratio(png) if os.path.exists(png) else None
            ratio = ratio or (vh / vw)
            wmm = min(a.width_mm, a.max_height_mm / ratio)
            pt = min(fs) * wmm / vw * 72 / 25.4
            rows.append((pt, os.path.basename(svg),
                         f"최소 font-size {min(fs):.1f} · viewBox 폭 {vw:.0f} · 인쇄 폭 {wmm:.0f}mm"))
        for pt, name, info in sorted(rows):
            if pt < 0:
                flag = "X "
                bad += 1
            elif pt >= a.min_pt - 0.01:
                flag = "OK"
            else:
                flag = "X "
                bad += 1
            shown = "  -  " if pt in (-1, 99) else f"{pt:5.2f}"
            print(f"  {flag} {shown} pt  {name:<36} {info}")
    print(f"\n미달 {bad}건 (기준 {a.min_pt}pt)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
