#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""고안 명세서(.md) 기계 점검 — 검토 게이트의 첫 단계.

  python3 spec_lint.py spec.md
  python3 spec_lint.py spec.md --raw prior-art-raw.md --figdir figures

무엇을 보나
  [구조]   6절 제목과 청구항 후보·초안 부록이 있는가, 순서가 맞는가
  [유보]   명세서에 남으면 안 되는 유보·조사 상태 표현 (원자료로 옮길 것)
  [문체]   법률투·특허투·CYA 사족
  [메모]   내부 논의 메모·구현 여부 태그·각주
  [출처]   본문에 나온 특허번호마다 열람 URL 이 명세서나 원자료에 있는가
  [도면]   본문이 참조한 도 N 이 도면 목록에 있는가, 목록의 파일이 figures/ 에 있는가

기계 점검은 사람의 정독을 대신하지 않는다. 걸린 줄은 문맥을 보고 고쳐라.
종료 코드: 오류(구조·출처·도면·메모)가 있으면 1, 경고만 있으면 0.
"""
import argparse
import os
import re
import sys

STRUCTURE = [
    ("1. 발명의 배경", r"^#+\s*1\.\s*발명의\s*배경"),
    ("가. 본 발명의 기술 분야", r"^#+\s*가\.\s*(본\s*발명의\s*)?기술\s*분야"),
    ("나. 종래 기술의 설명", r"^#+\s*나\.\s*종래\s*기술의\s*설명"),
    ("다. 종래 기술의 문제점 및 본 발명의 목적", r"^#+\s*다\.\s*종래\s*기술의\s*문제점"),
    ("2. 발명의 구체적 설명", r"^#+\s*2\.\s*발명의\s*구체적\s*설명"),
    ("가. 발명의 구성", r"^#+\s*가\.\s*발명의\s*구성"),
    ("나. 발명의 동작 설명", r"^#+\s*나\.\s*발명의\s*동작"),
    ("다. 발명의 효과", r"^#+\s*다\.\s*발명의\s*효과"),
    ("부록 · 청구항 후보", r"^#+\s*.*청구항\s*후보"),
    ("부록 · 청구항 초안", r"^#+\s*.*청구항\s*초안"),
]

# (분류, 정규식, 설명) — 분류가 오류면 종료 코드 1
RULES = [
    # 유보 · 조사 상태 — prior-art-raw.md 로 옮긴다
    ("유보", r"미발견|미조사|미열람|미확인", "조사 상태 표현은 원자료로"),
    ("유보", r"조사의\s*한계|검색\s*범위|상위\s*\d+\s*건|희석", "조사 방법·한계 서술은 원자료로"),
    ("유보", r"확신도|\((높음|중간|낮음)\)", "확신도 표기는 원자료로"),
    ("유보", r"최종\s*판단은\s*변리사|변리사\s*검토가?\s*필요|출원\s*전\s*변리사", "변리사 고지는 원자료·인계 메모에 한 번"),
    ("유보", r"애매|일\s*수\s*있다|(으)?로\s*보인다|것\s*같다|아마도?\b|추정된다", "단정형으로 — 우리가 그렇게 만들었다"),
    # 법률투 · 특허투
    ("문체", r"하지\s*아니|하고자\s*함|하는\s*바(이다|와|,)|함에\s*있어|로써\s*하여", "평이한 문어체로"),
    ("문체", r"화상", "사진·이미지로"),
    ("문체", r"(?<!항)에\s*있어서", "청구항 인용(제N항에 있어서) 밖에서는 풀어 쓴다"),
    ("문체", r"책임지지\s*않|면책", "CYA 사족 삭제"),
    # 내부 메모 · 태그 · 각주
    ("메모", r"〔|〕|논의\s*메모|TODO|FIXME|XXX", "내부 논의 메모가 새어 나왔다"),
    ("메모", r"\[(구현|구상|미구현)\]", "구현 여부 태그 금지 — 구현물은 실시예 하나일 뿐"),
    ("메모", r"\[\^\w+\]|^\s*\[\^\w+\]:", "각주 금지 — 본문에 녹인다"),
    ("메모", r"(문언|실질)\s*(회피|위험)\s*(높음|중간|낮음)", "내부 위험 등급 약칭 금지"),
]
ERROR_KINDS = {"구조", "출처", "도면", "메모"}

PATNO = re.compile(r"\b(US|KR|CN|JP|EP|WO|AU|TW|DE|GB|FR|CA|IN)\s?(\d{4}/?\d{3,}|\d{5,})\s?([A-Z]\d?)\b")


def norm(m):
    return (m.group(1) + m.group(2) + m.group(3)).replace("/", "").replace(" ", "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("--raw", help="조사 원자료(prior-art-raw.md) — 특허번호 URL 을 여기서도 찾는다")
    ap.add_argument("--figdir", help="도면 폴더(기본: 명세서 옆 figures/)")
    a = ap.parse_args()

    text = open(a.spec, encoding="utf-8").read()
    lines = text.splitlines()
    raw = open(a.raw, encoding="utf-8").read() if a.raw and os.path.exists(a.raw) else ""
    figdir = a.figdir or os.path.join(os.path.dirname(os.path.abspath(a.spec)), "figures")
    out = []

    # 구조
    pos = []
    for name, pat in STRUCTURE:
        idx = next((i for i, l in enumerate(lines) if re.search(pat, l)), None)
        if idx is None:
            out.append(("구조", 0, f"'{name}' 제목이 없다", ""))
        pos.append(idx)
    found = [p for p in pos if p is not None]
    if found != sorted(found):
        out.append(("구조", 0, "6절·부록 순서가 양식과 다르다", ""))

    # 표현 규칙 — 코드 블록 안은 건너뛴다(도면 원본·예시)
    in_code = False
    for i, l in enumerate(lines, 1):
        if l.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        for kind, pat, why in RULES:
            m = re.search(pat, l)
            if m:
                out.append((kind, i, why, l.strip()[:120]))

    # 출처 — 특허번호마다 URL
    nums = {}
    for i, l in enumerate(lines, 1):
        for m in PATNO.finditer(l):
            nums.setdefault(norm(m), i)
    urls = re.findall(r"https?://\S+", text + "\n" + raw)
    for n, i in sorted(nums.items(), key=lambda x: x[1]):
        if not any(n in u for u in urls):
            out.append(("출처", i, f"{n} 의 열람 URL 이 명세서·원자료 어디에도 없다", ""))

    # 도면 — 본문 참조와 목록, 파일
    refs = set(re.findall(r"도\s?(\d+)", text))
    listed = set(re.findall(r"^\|\s*도\s?(\d+)\s*\|", text, re.M))
    if refs and not listed:
        out.append(("도면", 0, "본문이 도면을 참조하는데 '도면의 간단한 설명' 목록 표가 없다", ""))
    for n in sorted(refs - listed, key=int):
        if listed:
            out.append(("도면", 0, f"도 {n} 이 본문에 나오는데 도면 목록에 없다", ""))
    for fn in sorted(set(re.findall(r"`([\w.\-]+\.(?:svg|png|mmd|drawio|excalidraw))`", text))):
        if not os.path.exists(os.path.join(figdir, fn)):
            out.append(("도면", 0, f"목록의 파일 {fn} 이 {figdir} 에 없다", ""))

    # 출력
    errors = [o for o in out if o[0] in ERROR_KINDS]
    for kind, i, why, src in sorted(out, key=lambda o: (o[0] not in ERROR_KINDS, o[1])):
        level = "오류" if kind in ERROR_KINDS else "경고"
        loc = f"{i}행" if i else "-"
        print(f"[{level}·{kind}] {loc}  {why}" + (f"\n      {src}" if src else ""))
    print(f"\n합계: 오류 {len(errors)} · 경고 {len(out) - len(errors)} · 특허번호 {len(nums)}건 · 도면 참조 {len(refs)}개")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
