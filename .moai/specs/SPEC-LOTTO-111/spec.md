---
id: SPEC-LOTTO-111
version: 1.0.0
status: draft
created: 2026-06-23
updated: 2026-06-23
author: ircp
priority: high
issue_number: 0
---

# SPEC-LOTTO-111: Playwright 기반 동행복권 크롤러

## 개요 (Overview)

동행복권 공식 API(`https://www.dhlottery.co.kr/common.do?method=getLottoNumber&drwNo={N}`)가
JavaScript 기반 RSA 세션 인증 도입으로 인해 JSON 대신 HTML을 반환하기 시작했다.
이로 인해 기존 `LottoCollector._fetch_with_retry`가 파싱에 실패하고 `None`을 반환하여
1226회차 이후 데이터를 수집할 수 없는 상태이다.

본 SPEC은 Playwright를 사용하는 브라우저 기반 크롤러(`PlaywrightCollector`)를 도입하여
기존 HTTP 수집기가 실패할 경우 자동으로 폴백하는 이중 수집 전략을 구현한다.

기존 기능과의 관계:
- `LottoCollector` (HTTP 수집기): 우선 시도, JSON 응답 시 그대로 사용
- `PlaywrightCollector` (Playwright 수집기): HTTP가 HTML 반환 시 폴백으로 동작
- 두 수집기는 동일한 `DrawResult` 모델을 반환하며 상호 교환 가능하다

## EARS 요구사항 (Requirements)

- **REQ-PW-001**: WHEN Playwright가 설치되어 있고 AND HTTP API가 JSON이 아닌 HTML을
  반환할 때, THEN 시스템은 Playwright 기반 브라우저 세션을 사용하여 회차 데이터를 수집해야 한다.

- **REQ-PW-002**: 시스템은 `lotto/playwright_collector.py`에 `PlaywrightCollector` 클래스를
  구현해야 하며, `fetch_draw(drw_no: int) -> DrawResult | None` 메서드를 제공해야 한다.

- **REQ-PW-003**: `PlaywrightCollector`는 async Playwright를 사용하여
  `https://www.dhlottery.co.kr/common.do?method=getLottoNumber&drwNo={N}`에 접속하고
  페이지 응답에서 JSON 데이터를 추출해야 한다.
  추출 전략은 다음 순서로 시도한다:
  1. 페이지 내 `<pre>` 태그 텍스트를 JSON으로 파싱
  2. 페이지 본문(body) 전체를 JSON으로 파싱
  3. 두 방법 모두 실패하면 `None` 반환

- **REQ-PW-004**: `LottoCollector._fetch_with_retry`는 HTTP 응답이 JSON이 아님을
  감지해야 한다. 감지 조건은 다음 중 하나이다:
  - `Content-Type` 헤더에 `application/json`이 포함되지 않음
  - 응답 본문이 `<!DOCTYPE`으로 시작함
  감지 시 `HTMLResponseError`를 발생시켜 호출자에게 폴백 필요성을 알려야 한다.

- **REQ-PW-005**: `lotto/web/routes/api.py`의 `_collect_worker`는 HTTP 수집기가
  3회 이상 연속으로 `None`을 반환하거나 `HTMLResponseError`가 발생할 경우,
  `PlaywrightCollector`로 폴백하여 수집을 계속해야 한다.

- **REQ-PW-006**: IF Playwright가 설치되지 않은 경우, THEN 시스템은 경고 로그를 출력하고
  Playwright 폴백 없이 기존 HTTP 수집기만으로 동작을 계속해야 한다.
  (`ImportError` / `playwright._impl._errors.Error` 발생 시 graceful 처리)

- **REQ-PW-007**: `tests/test_playwright_collector.py`에 최소 8개 테스트 케이스를
  작성해야 하며, Playwright를 실제 실행하지 않도록 mock 처리해야 한다.
  테스트 케이스 목록:
  1. `PlaywrightCollector.fetch_draw()` - pre 태그에서 JSON 추출 성공
  2. `PlaywrightCollector.fetch_draw()` - body에서 JSON 추출 성공 (pre 없음)
  3. `PlaywrightCollector.fetch_draw()` - HTML 파싱 실패 시 None 반환
  4. `PlaywrightCollector.fetch_draw()` - returnValue != "success" 시 None 반환
  5. `PlaywrightCollector.fetch_draw()` - Playwright 미설치 시 None 반환 + 경고 로그
  6. `LottoCollector._fetch_with_retry` - HTML 응답 감지 → `HTMLResponseError` 발생
  7. `_collect_worker` - 3회 연속 실패 시 PlaywrightCollector 폴백 동작
  8. `_collect_worker` - Playwright 폴백 성공 후 정상 저장 확인

- **REQ-PW-008**: `pyproject.toml`에 Playwright를 선택적 의존성으로 추가해야 한다.
  `[project.optional-dependencies]` 섹션에 `playwright = ["playwright>=1.44"]`를
  등록하고, 기본 의존성(`dependencies`)에는 포함하지 않는다.

## 기술 설계 (Technical Design)

### 새로 추가되는 파일

| 파일 | 역할 |
|------|------|
| `lotto/playwright_collector.py` | `PlaywrightCollector` 클래스 |
| `tests/test_playwright_collector.py` | Playwright 크롤러 테스트 (8개 이상) |

### 수정되는 파일

| 파일 | 변경 내용 |
|------|-----------|
| `lotto/collector.py` | `HTMLResponseError` 추가, `_fetch_with_retry` HTML 감지 로직 추가 |
| `lotto/web/routes/api.py` | `_collect_worker` Playwright 폴백 로직 추가 |
| `pyproject.toml` | `[project.optional-dependencies]` playwright 항목 추가 |

### PlaywrightCollector 클래스 설계

```python
# lotto/playwright_collector.py

class PlaywrightCollector:
    """Playwright 기반 동행복권 크롤러."""

    async def fetch_draw(self, drw_no: int) -> DrawResult | None:
        """브라우저를 통해 단일 회차 데이터를 수집한다."""
        ...

    def fetch_draw_sync(self, drw_no: int) -> DrawResult | None:
        """동기 래퍼 — asyncio.run()으로 async fetch_draw를 호출한다."""
        ...
```

### HTMLResponseError 설계

```python
# lotto/collector.py

class HTMLResponseError(Exception):
    """HTTP API가 JSON 대신 HTML을 반환할 때 발생합니다."""
```

### 폴백 로직 (pseudocode)

```
consecutive_failures = 0
playwright_mode = False

for drw_no in range(start, end):
    if playwright_mode:
        draw = PlaywrightCollector().fetch_draw_sync(drw_no)
    else:
        try:
            draw = collector.fetch_draw(drw_no)  # HTMLResponseError 발생 가능
        except HTMLResponseError:
            consecutive_failures += 1
        if consecutive_failures >= 3:
            playwright_mode = True
            continue

    if draw is None:
        consecutive_failures += 1
    else:
        consecutive_failures = 0
        save(draw)
```

## 인수 기준 (Acceptance Criteria)

- **AC-001**: `PlaywrightCollector().fetch_draw(1226)`을 mock Playwright 환경에서 호출하면
  유효한 `DrawResult`(drwNo=1226, 6개 번호 포함)를 반환한다.

- **AC-002**: `LottoCollector._fetch_with_retry`가 `<!DOCTYPE html>` 본문을 수신하면
  `HTMLResponseError`를 발생시킨다.

- **AC-003**: `Content-Type: text/html` 응답 수신 시에도 `HTMLResponseError`를 발생시킨다.

- **AC-004**: Playwright가 미설치된 환경에서 `PlaywrightCollector().fetch_draw()`를 호출하면
  `None`을 반환하고 경고 로그가 출력된다.

- **AC-005**: `_collect_worker`가 3회 연속 실패 후 Playwright 폴백으로 전환되고
  이후 회차는 정상 수집된다.

- **AC-006**: `tests/test_playwright_collector.py`에 8개 이상의 테스트가 존재하며
  모두 통과한다.

- **AC-007**: 기존 테스트 3041개에 리그레션이 없다 (`pytest tests/ -x`로 확인).

- **AC-008**: `pyproject.toml`에 `[project.optional-dependencies]`의 `playwright` 항목이
  존재하며, `pip install lotto[playwright]`로 설치 가능한 형태이다.

## 제약 사항 (Constraints)

- Python 3.9 호환성: `asyncio.run()`은 3.9에서 지원됨 (사용 가능)
- `playwright>=1.44`는 선택적 의존성으로만 등록 — 기본 설치에 영향 없음
- 기존 `LottoCollector` 클래스 시그니처 변경 금지 (기존 테스트 보호)
- `HTMLResponseError`는 `lotto/collector.py`에 추가 (새 파일 불필요)
- Playwright 브라우저는 headless 모드로 실행 (`headless=True`)
- 실제 브라우저 실행 테스트 금지 — 모든 테스트는 mock 사용

## 관련 SPEC

- SPEC-LOTTO-001: 기본 수집기 (`LottoCollector`) 구현
- SPEC-LOTTO-002: 설정 외부화 (`LOTTO_API_URL` 환경 변수)
