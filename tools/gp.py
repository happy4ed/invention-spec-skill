#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Google Patents 조회기 — 선행특허 검색 · 청구항 전문 열람 · 서지 확인.

표준 라이브러리만 쓴다. 키가 필요 없다.

  python3 gp.py search "umbrella handle reminder" --num 20
  python3 gp.py search "(umbrella OR parasol) AND (reminder OR alert)" --before 20200101
  python3 gp.py claims <공개번호>                 # 청구항 전문 · 독립항 표시
  python3 gp.py claims <공개번호> --independent   # 독립항만
  python3 gp.py claims <공개번호> --lang ko       # 한국어 원문 페이지
  python3 gp.py claims <공개번호> --source        # 기계 번역 페이지에서 원문 문장으로
  python3 gp.py meta <공개번호> <공개번호>        # 선행특허 목록용 서지 한 줄씩

공개번호는 Google Patents 표기 그대로 쓴다(국가코드 + 번호 + 종류코드, 예: US·KR·CN·JP·EP·WO 로 시작).

주의
- search 는 Google Patents 웹 화면이 쓰는 비공개 XHR 엔드포인트(/xhr/query)를 부른다.
  문서화된 API 가 아니므로 응답 형식이 바뀌거나 막힐 수 있다. 막히면 브라우저로
  https://patents.google.com/ 에서 같은 검색을 하고 번호만 옮겨 와 claims 로 연다.
- claims / meta 는 공개 특허 페이지(https://patents.google.com/patent/<번호>/<언어>)를 읽는다.
- 짧은 시간에 수십 번 부르면 구글이 자동 조회를 막는다(HTTP 503 'Sorry' 페이지, 수십 분 지속).
  검색은 검색식을 다듬어 횟수를 줄이고, 여러 건을 열 때는 건 사이를 띄운다(meta 는 DELAY 초 간격).
- 출력의 URL 과 조회일을 조사 원자료(prior-art-raw.md)에 그대로 남겨라.
"""
import argparse
import datetime
import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
BASE = "https://patents.google.com"
QUERY_SAFE = '():"*'
DELAY = 3.0  # 여러 건을 연달아 열 때 건 사이 쉬는 초. 줄이면 차단된다


class Blocked(Exception):
    pass


def fetch(url, timeout=30, retries=1):
    """한 번 실패하면 잠깐 쉬고 다시 시도한다. 구글의 자동 조회 차단(503 'Sorry')은 재시도하지 않는다."""
    last = None
    for i in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.8"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = r.read().decode("utf-8", errors="replace")
            if "<title>Sorry...</title>" in body[:600]:
                raise Blocked()
            return body
        except urllib.error.HTTPError as e:
            if e.code in (429, 503):
                raise SystemExit(
                    f"자동 조회 차단(HTTP {e.code}). 짧은 시간에 너무 많이 불렀다.\n"
                    "  수십 분 쉬었다가 다시 하거나, 브라우저로 같은 주소를 열어 확인하라.\n"
                    "  재시도를 연달아 하면 차단이 길어진다.\n  " + url)
            last = e
        except Blocked:
            raise SystemExit("자동 조회 차단('Sorry' 페이지). 수십 분 쉬었다가 다시 하거나 브라우저로 열어라.\n  " + url)
        except Exception as e:  # 네트워크 오류
            last = e
        time.sleep(3 * (i + 1))
    raise SystemExit(f"조회 실패: {url}\n  {last}")


def strip_tags(s):
    s = re.sub(r"<br\s*/?>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    s = re.sub(r"[ \t\r\f\v]+", " ", s)
    s = re.sub(r"\s*\n\s*", "\n", s)
    return s.strip()


# ---------------------------------------------------------------- search
def cmd_search(a):
    params = [("q", a.query), ("num", str(a.num))]
    if a.before:
        params.append(("before", "priority:" + a.before))
    if a.after:
        params.append(("after", "priority:" + a.after))
    if a.country:
        params.append(("country", a.country))
    if a.language:
        params.append(("language", a.language))
    if a.page:
        params.append(("page", str(a.page)))
    # 안쪽 검색 문자열은 한 번만 인코딩하고 괄호·콜론·따옴표는 그대로 둔다.
    # 바깥에서는 & 와 = 만 바꾼다. 콜론을 두 번 인코딩하면(%253A) 서버가 500 을 낸다(실측).
    inner = "&".join(k + "=" + urllib.parse.quote(v, safe=QUERY_SAFE) for k, v in params)
    url = f"{BASE}/xhr/query?url={inner.replace('&', '%26').replace('=', '%3D')}&exp="
    browser_url = f"{BASE}/?{inner}"  # 사람이 같은 검색을 다시 열어 볼 주소 — 원자료에는 이것을 남긴다
    raw = fetch(url)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise SystemExit("응답이 JSON 이 아니다(차단 또는 형식 변경). 브라우저 검색으로 대체하라.\n" + raw[:300])
    res = data.get("results", {})
    rows = []
    for cl in res.get("cluster", []):
        for item in cl.get("result", []):
            p = item.get("patent", {})
            rows.append({
                "number": p.get("publication_number", ""),
                "title": strip_tags(p.get("title", "")),
                "assignee": strip_tags(p.get("assignee", "")),
                "priority": p.get("priority_date", ""),
                "published": p.get("publication_date", ""),
                "snippet": strip_tags(p.get("snippet", "")),
                "url": f"{BASE}/patent/{p.get('publication_number','')}/en",
            })
    rows = rows[:a.num]  # 엔드포인트는 10건 미만 요청을 10건으로 올려 준다
    today = datetime.date.today().isoformat()
    if a.json:
        print(json.dumps({"query": a.query, "searched": today, "search_url": browser_url,
                          "total": res.get("total_num_results"), "results": rows},
                         ensure_ascii=False, indent=2))
        return
    print(f"# 검색어: {a.query}")
    print(f"# 조회일: {today} · 전체 {res.get('total_num_results')}건 중 {len(rows)}건 표시")
    print(f"# 검색 URL: {browser_url}")
    for i, r in enumerate(rows, 1):
        print(f"\n{i:>2}. {r['number']}  {r['title']}")
        print(f"    출원인 {r['assignee'] or '-'} · 우선일 {r['priority'] or '-'} · 공개 {r['published'] or '-'}")
        print(f"    {r['url']}")
        if a.snippet and r["snippet"]:
            print("    " + r["snippet"][:300])


# ---------------------------------------------------------------- patent page
def get_page(number, lang):
    url = f"{BASE}/patent/{number}/{lang}"
    return url, fetch(url)


def itemprop(page, name, tag="[a-z]+"):
    m = re.search(rf'<{tag}[^>]*itemprop="{name}"[^>]*>(.*?)</', page, re.S)
    return strip_tags(m.group(1)) if m else ""


def head_of(page):
    """서지 영역만 잘라 낸다. 인용·피인용 표에도 같은 itemprop 이 있어 섞이기 때문이다."""
    for key in ('itemprop="abstract"', 'itemprop="claims"', 'itemprop="backwardReferences'):
        i = page.find(key)
        if i > 0:
            return page[:i]
    return page


def meta_of(number, lang):
    url, page = get_page(number, lang)
    head = head_of(page)
    title = itemprop(head, "title", "span")
    assignees = [strip_tags(x) for x in re.findall(r'itemprop="assigneeOriginal"[^>]*>(.*?)</', head, re.S)]
    assignees = [x for x in assignees if x]
    pub = re.search(r'itemprop="publicationDate"[^>]*datetime="([\d-]+)"', head)
    pri = re.search(r'itemprop="priorityDate"[^>]*datetime="([\d-]+)"', head)
    return {
        "number": number,
        "title": title,
        "assignee": "; ".join(dict.fromkeys(assignees)),
        "priority": pri.group(1) if pri else "",
        "published": pub.group(1) if pub else "",
        "url": url,
    }, page


# 다른 청구항을 인용하는 문구 — 언어별. 인용하면 종속항으로 본다.
DEP_PATTERNS = [
    r"\bclaims?\s+\d+",            # of claim 1 / according to claims 1 to 3
    r"제\s*\d+\s*항",               # 제1항에 있어서
    r"청구항\s*\d+",                 # 청구항 1에 있어서
    r"权利要求\s*\d+",               # 根据权利要求1
    r"請求項\s*\d+",                 # 請求項1に記載の
    r"\bAnspruch\s+\d+",
    r"\brevendication\s+\d+",
]
DEP_RE = re.compile("|".join(DEP_PATTERNS), re.I)
DELETED_RE = re.compile(r"^\s*(\d+\s*[.)]?\s*)?[(\[]?(삭제|canceled|cancelled|deleted|删除|削除)[)\]]?\s*[.。]?\s*$", re.I)
SRC_RE = re.compile(r'<span class="google-src-text">(.*?)</span>', re.S)
MARK_RE = re.compile(
    r'<div[^>]*\bnum="(\d+)"[^>]*class="claim"[^>]*>'     # 원문 페이지: <div id="CLM-00001" num="00001" class="claim">
    r'|<div[^>]*class="claim"[^>]*\bnum="(\d+)"[^>]*>'
    r'|<claim\b[^>]*\bnum="(\d+)"[^>]*>')                # 번역 페이지: <claim num="0001">


def parse_claims(page, source=False):
    """청구항을 번호별로 나눈다. source=True 면 번역 페이지에서 원문 문장을 쓴다."""
    i = page.find('itemprop="claims"')
    if i < 0:
        return [], False
    j = page.find("</section>", i)
    sec = page[i:j if j > 0 else None]
    translated = "google-src-text" in sec
    marks = list(MARK_RE.finditer(sec))
    claims = []
    for k, m in enumerate(marks):
        end = marks[k + 1].start() if k + 1 < len(marks) else len(sec)
        chunk = sec[m.start():end]
        num = int(next(g for g in m.groups() if g))
        orig = " ".join(strip_tags(x) for x in SRC_RE.findall(chunk)) if translated else ""
        shown = SRC_RE.sub("", chunk) if translated else chunk
        text = orig if (source and orig) else strip_tags(shown)
        dependent = ("<claim-ref" in chunk) or bool(DEP_RE.search(strip_tags(shown))) or bool(DEP_RE.search(orig))
        if DELETED_RE.match(strip_tags(shown)) or DELETED_RE.match(orig or "x"):
            claims.append({"num": num, "independent": None, "deleted": True, "text": text})
            continue
        claims.append({"num": num, "independent": not dependent, "text": text})
    if not claims:
        text = strip_tags(sec)
        if text:
            claims.append({"num": 0, "independent": None, "text": text})
    return claims, translated


def cmd_claims(a):
    m, page = meta_of(a.number, a.lang)
    claims, translated = parse_claims(page, source=a.source)
    today = datetime.date.today().isoformat()
    if a.independent:
        claims = [c for c in claims if c["independent"]]
    if a.json:
        print(json.dumps({**m, "checked": today, "machine_translated": translated and not a.source,
                          "claims": claims}, ensure_ascii=False, indent=2))
        return
    print(f"# {m['number']} — {m['title']}")
    print(f"# 출원인 {m['assignee'] or '-'} · 우선일 {m['priority'] or '-'} · 공개/등록 {m['published'] or '-'}")
    print(f"# URL {m['url']} · 조회일 {today}")
    if translated and not a.source:
        print("# 주의: 이 페이지의 청구항은 기계 번역이다. 대조표 판정은 --source(원문)로 한 번 더 확인하라.")
    if not claims:
        print("\n(이 언어 페이지에 청구항 본문이 없다. --lang 을 바꾸거나 패밀리 문헌을 열어라.)")
        return
    ind = [c["num"] for c in claims if c["independent"]]
    if ind:
        print(f"# 독립항(인용 문구가 없는 항): {', '.join(map(str, ind))}")
        print("# 다른 항을 인용하는 장치·매체 청구항도 종속으로 표시된다. 판정 전에 원문을 읽어라.")
    for c in claims:
        if c.get("deleted"):
            tag = "삭제"
        else:
            tag = "독립항" if c["independent"] else ("종속항" if c["independent"] is False else "청구항")
        print(f"\n[{tag} {c['num']}]\n{c['text']}")


def cmd_meta(a):
    today = datetime.date.today().isoformat()
    print("| 특허번호 | 발명의 명칭 | 출원인 | 우선일 | 공개/등록일 | URL |")
    print("|---|---|---|---|---|---|")
    for n in a.numbers:
        m, _ = meta_of(n, a.lang)
        print(f"| {m['number']} | {m['title'] or '미확보'} | {m['assignee'] or '미확보'} | "
              f"{m['priority'] or '미확보'} | {m['published'] or '미확보'} | {m['url']} |")
        time.sleep(DELAY)
    print(f"\n조회일 {today} · Google Patents 원문 페이지 기준")


def main():
    ap = argparse.ArgumentParser(description="Google Patents 조회기")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("search", help="키워드 검색")
    s.add_argument("query", help="Google Patents 검색창과 같은 문법. 예: (umbrella OR parasol) AND reminder")
    s.add_argument("--num", type=int, default=20, help="한 쪽 결과 수(최대 100)")
    s.add_argument("--page", type=int, default=0)
    s.add_argument("--before", help="우선일 상한 YYYYMMDD")
    s.add_argument("--after", help="우선일 하한 YYYYMMDD")
    s.add_argument("--country", help="국가 코드, 예: US · KR · CN")
    s.add_argument("--language", help="문헌 언어, 예: ENGLISH,KOREAN")
    s.add_argument("--snippet", action="store_true", help="요약 일부도 출력")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_search)

    c = sub.add_parser("claims", help="청구항 전문")
    c.add_argument("number")
    c.add_argument("--lang", default="en")
    c.add_argument("--independent", action="store_true", help="독립항만")
    c.add_argument("--source", action="store_true", help="번역 페이지에서 원문 문장으로 출력")
    c.add_argument("--json", action="store_true")
    c.set_defaults(func=cmd_claims)

    m = sub.add_parser("meta", help="서지 한 줄씩(선행특허 목록용)")
    m.add_argument("numbers", nargs="+")
    m.add_argument("--lang", default="en")
    m.set_defaults(func=cmd_meta)

    a = ap.parse_args()
    a.func(a)


if __name__ == "__main__":
    sys.exit(main())
