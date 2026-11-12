# invention-spec — 직무발명 고안 명세서 작성 스킬 (Claude Code)

러프한 발명 아이디어를 사용자와 **대화로 함께** 다듬어 사내 제출용 **직무발명 고안 명세서(6절 양식)** 로
만드는 Claude Code 스킬이다.

- Google Patents 에서 선행 특허를 찾고 **독립항 전문을 열어** 구성요소 대조표(All Elements Rule)를 만든다.
- 겹치는 자리를 **회피 설계**(구성요소 제거 · 치환 · 우회, 새 구성 추가)로 비껴가고, 기술 축이 계속 겹치면
  **UX 진보성**으로 축을 옮긴다.
- 구조도 · 순서도 · 시퀀스도 · 와이어프레임을 **편집 가능한 원본**(Mermaid · SVG · draw.io)으로 만든다.
- 청구항 후보와 **사내 논의용 청구항 초안**(독립항 1 · 종속항 여럿), 출원 부속(선행특허 목록 · 발명 내용 표)을 낸다.
- 마지막에 검토 게이트(날조 · 근거 없는 단정 · 유보 표현 · 6절 충족 · 도면 크기)를 돈다.

이 스킬이 만드는 것은 **출원 명세서가 아니다.** 발명자가 조직에 내고 출원 전에 변리사와 논의하기 위한
정리 문서다. 출원 대리와 완성 청구범위 작성은 하지 않는다.

## 설치

Claude Code 의 사용자 스킬 폴더에 이 저장소를 `invention-spec` 이라는 이름으로 내려받는다.

macOS · Linux
```bash
git clone https://github.com/happy4ed/invention-spec-skill ~/.claude/skills/invention-spec
```

Windows (PowerShell)
```powershell
git clone https://github.com/happy4ed/invention-spec-skill "$env:USERPROFILE\.claude\skills\invention-spec"
```

Windows (명령 프롬프트)
```bat
git clone https://github.com/happy4ed/invention-spec-skill "%USERPROFILE%\.claude\skills\invention-spec"
```

한 프로젝트에서만 쓰려면 그 프로젝트의 `.claude/skills/invention-spec` 에 내려받는다.
새 Claude Code 세션을 열면 스킬 목록에 `invention-spec` 이 보인다.

업데이트
```bash
git -C ~/.claude/skills/invention-spec pull
```

### 필요한 것
- 파이썬 3.8 이상(도구는 표준 라이브러리만 쓴다. `svg_print_pt.py` 의 PNG 비율 확인만 Pillow 가 있으면 쓴다)
- 인터넷 연결(Google Patents 조회)
- 선택: Node.js(Mermaid 렌더 `npx @mermaid-js/mermaid-cli`), LibreOffice · poppler(제출본 렌더 검사)

## 쓰는 법

Claude Code 에서 아이디어를 말하면 된다. 스킬이 자동으로 잡히지 않으면 `invention-spec 스킬로` 라고 덧붙인다.

```
우산 손잡이에 센서를 넣어서 비 오는 날 우산을 두고 나가면 휴대폰이 알려 주는 아이디어가 있어.
직무발명서로 정리해 줘.
```
(위 아이디어는 사용법을 보이려고 지어낸 예시다.)

스킬은 바로 문서를 쓰지 않고 먼저 **한 번에 하나씩** 묻는다 — 없으면 안 되는 구성요소, 입력과 출력,
기존 방식, 새롭다고 느낀 지점. 그다음 라운드마다 결과를 보여 주고 방향을 받는다.

```
1  아이디어 접수 — 요지 카드
2  R0 초안
3  R1 선행기술 조사 (Google Patents · 독립항 전문 · 번호 · URL 기록)
4  독립항 구성요소 대조표 (있음 / 치환됨 / 없음)
5  라운드 보고 → 방향 확인
6  R2 회피 · 차별화 (구성요소 회피 / 기술 진보성 / UX 진보성)
7  재조사 · 수렴
8  6절 명세서 본문 + 도면
9  청구항 후보 · 사내 논의용 초안 (부록)
10 출원 부속 (선행특허 목록 · 발명 내용 표)
11 검토 게이트
12 인계
```

산출물(작업 폴더)
```
spec.md            고안 명세서 (6절 + 부록 A 청구항 후보 · B 초안 · C 대조표 · D 회피 · 기각 기록)
annex.md           출원 부속 ① 선행특허 목록과 검토의견 ② 발명 내용 표와 요약
prior-art-raw.md   조사 원자료 (검색식 · 열람 기록 · 확신도 · 한계 · 미결 쟁점)
figures/           도면 원본과 렌더
```

조직에 정해진 직무발명서 양식이 있으면 처음에 알려 준다. 그 양식의 구성을 그대로 따른다.

### 도구만 따로 쓰기

```bash
# 선행특허 검색 · 청구항 전문 · 서지
python3 tools/gp.py search "(umbrella OR parasol) AND (reminder OR alert)" --num 20
python3 tools/gp.py claims <공개번호> --independent
python3 tools/gp.py claims <공개번호> --source      # 기계 번역 페이지에서 원문 문장으로
python3 tools/gp.py meta <공개번호> <공개번호>       # 목록 표 한 줄씩

# 명세서 기계 점검 (구조 · 유보 표현 · 법률투 · 내부 메모 · 특허번호 URL · 도면 참조)
python3 tools/spec_lint.py spec.md --raw prior-art-raw.md --figdir figures

# 도면 인쇄 글자 크기 (본문 폭 · 최대 높이 · 최소 pt)
python3 tools/svg_print_pt.py figures/ --width-mm 180 --max-height-mm 260 --min-pt 8
```

## 폴더 구성

```
SKILL.md                         단계별 작업 지침
references/
  spec-template.md               6절 양식 · 부록 · 출원 부속 · 조사 원자료 뼈대
  writing-style.md               문체 · 용어 · 유보 금지 · 내부 메모 금지 · 양식 불변
  prior-art-search.md            검색식 · Google Patents · 청구항 열람 · 기록
  element-comparison.md          독립항 구성요소 대조표 (All Elements Rule · 균등론)
  design-around.md               회피 설계 세 갈래 · UX 진보성 전환 · 라운드 운영 · 분할 저울
  claim-drafting.md              청구항 후보 · 사내 논의용 초안 · 청구범위 계층
  figures.md                     구조도 · 순서도 · 시퀀스도 · 와이어프레임 · 문서 렌더 검사
  review-checklist.md            검토 게이트
  legal-boundaries.md            할 수 있는 일 · 하지 않는 일 · 고지
tools/
  gp.py                          Google Patents 조회기
  spec_lint.py                   명세서 기계 점검
  svg_print_pt.py                도면 인쇄 글자 크기 검사
```

## 한계

- **출원 대리를 하지 않는다.** 특허 관청 · 법원 대리, 출원용 완성 청구범위 작성, 제3자 대상 유상 감정은
  변리사의 일이다. 청구항 초안은 사내 논의용이며, 출원 전에 변리사 검토가 필요하다.
- **선행조사는 1차 조사다.** 전수 조사가 아니고, 등록 가능성 · 침해 여부를 보장하지 않는다.
- **KIPRIS 등 국내 특허 전용 DB 를 기본 지원하지 않는다.** API 키가 필요하다. Google Patents 가 수록한
  국내 문헌은 검색되지만 누락이 있을 수 있다.
- **Google Patents 검색은 비공개 엔드포인트**(`/xhr/query`)를 쓴다. 형식이 바뀌거나 막힐 수 있다.
  짧은 시간에 많이 부르면 자동 조회가 차단된다(HTTP 503, 수십 분). 막히면 브라우저로 검색한다.
- **Espacenet** 은 자동 조회 확인 절차 때문에 스크립트로 잘 열리지 않는다.
- 비영어 문헌은 기계 번역 페이지를 읽게 된다. 대조표 판정은 원문으로 다시 확인한다.
- 법적 경계 서술은 한국 변리사법을 기준으로 했다(2026-07 확인). 다른 나라에서 쓰면 그 나라 규정을 확인한다.
- .docx 변환 도구는 들어 있지 않다. 필요하면 pandoc · LibreOffice 등으로 변환하고, 렌더해서 쪽마다 확인한다.
- **기밀**: 출원 전 발명 내용을 공개 장소에 올리지 않는다.
