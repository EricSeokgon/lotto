---
id: SPEC-LOTTO-003
version: "0.1.0"
status: draft
created: "2026-05-21"
updated: "2026-05-21"
author: ircp
priority: medium
issue_number: 0
---

# SPEC-LOTTO-003: 보너스 번호 통계 및 스크래퍼 안정성 강화

## HISTORY

| 버전 | 일자 | 작성자 | 변경 내용 |
|------|------|--------|-----------|
| 0.1.0 | 2026-05-21 | ircp | 초기 SPEC 작성 — 보너스 빈도 통계 추가, 스크래퍼 엣지 케이스 안정화, 보너스 회피 가중치 옵션 |

---

## Overview (개요)

### What (무엇을 만드는가)

SPEC-LOTTO-001(CLI) / SPEC-WEB-001(웹 대시보드) / SPEC-LOTTO-002(설정 외부화)가 완료된 현재 코드베이스에서, 보너스 번호(7번째 추첨 번호) 정보가 통계/추천/API에 노출되지 않고 있다. 또한 스크래퍼는 일부 엣지 케이스에서 예외를 일으킬 수 있는 위험 지점이 있다. 본 SPEC은 다음 세 영역을 강화한다.

1. **보너스 빈도 통계**: `Statistics` 모델에 `bonus_frequency` 필드를 추가하고, `analyzer.analyze()`가 이를 채우도록 한다. `GET /api/stats` 응답에도 자동으로 포함된다.
2. **보너스 회피 가중치(옵션)**: 추천 점수 계산에서 보너스로 자주 등장한 번호(당첨 직전에 머문 신호)에 대해 페널티를 줄 수 있는 선택적 가중치 `bonus_avoidance_weight`를 추가한다. 기본값 0.0이므로 기존 동작은 변경되지 않는다.
3. **스크래퍼 안정성**: `_parse_draw_row`가 모든 파싱 실패를 무음 None 반환에서 `logger.warning` + None 반환으로 격상한다. `scrape_all`은 None 행을 안전하게 스킵한다. `<table>` 미발견 시에도 안전하게 빈 리스트를 반환한다(이미 가능; 회귀 보호 테스트만 추가).

### Why (왜 만드는가)

- **분석 완전성**: 7번째 번호인 보너스는 현재 데이터 모델에는 저장되지만 통계/추천 어디에도 노출되지 않는다. 사용자 입장에서는 "보너스로 자주 나오는 번호"를 시각화/탐색할 수 없어 데이터 활용도가 떨어진다.
- **추천 다양성**: "보너스로 자주 머무는 번호 = 본 추첨에서 떨어진 번호"라는 도메인 가설을 옵션 가중치로 실험 가능하게 한다. 기본 가중치 0.0으로 기존 동작은 100% 보존한다.
- **운영 안정성**: 현재 `_parse_draw_row`는 형식 불일치 시 무음으로 None을 반환한다. 디버깅 시 원인 파악이 불가능하므로, SPEC-LOTTO-002의 무음 예외 제거 원칙을 따라 `logger.warning`으로 격상한다.

### Scope (적용 범위)

- **포함**:
  - `lotto/models.py` — `Statistics.bonus_frequency` 필드 추가
  - `lotto/analyzer.py` — `analyze()` 내부에서 보너스 빈도 계산/주입
  - `lotto/config.py` — `bonus_avoidance_weight: float = 0.0` 추가 (환경 변수 `LOTTO_BONUS_AVOIDANCE_WEIGHT`)
  - `lotto/recommender.py` — 점수 계산에 보너스 회피 페널티(옵션) 적용
  - `lotto/scraper.py` — 모든 파싱 실패에 대해 `logger.warning` 기록
  - `tests/test_bonus_stats.py`, `tests/test_bonus_api.py`, `tests/test_scraper_edge.py` (신규)
- **제외**: UI 변경, 데이터 파일 마이그레이션(기존 stats.json은 다음 분석 시 자동으로 새 필드 포함), CLI 옵션 추가, 새 API 엔드포인트.
- **제약**: Python 3.9 호환 유지. 기존 256개 테스트가 모두 통과해야 함. `zip(strict=True)` 사용 금지. 함수 시그니처(외부 인터페이스) 변경 금지 — 필드/내부 동작만 추가.

---

## Glossary (용어 정의)

| 용어 | 정의 |
|------|------|
| 보너스 번호(Bonus Number) | 매 회차 6개 당첨 번호 외 별도로 추첨되는 7번째 번호. 2등 자격 결정에 사용 |
| `bonus_frequency` | `Statistics` 모델 내 신규 필드. 1~45 각 번호가 전 회차의 "보너스 번호로 등장한 횟수"의 절대/상대 빈도 |
| 보너스 회피 가중치(Bonus Avoidance Weight) | 추천 점수 계산 시 "보너스로 자주 나온 번호"에 페널티를 부여하는 가중치. 기본값 0.0 (비활성) |
| 무음 None 반환 | `except: return None` 패턴으로 로그 없이 실패를 삼키는 안티 패턴 |

---

## Functional Requirements (기능 요구사항 — EARS 형식)

### REQ-BONUS-001 — Statistics 모델 확장 (Ubiquitous)

The `Statistics` model **MUST** include a `bonus_frequency` field of type `FrequencyStats`, tracking the appearance count of each number (1~45) as the bonus ball across all draws.

- 기본값: `FrequencyStats()` (빈 dict)
- 직렬화: `model_dump()` / `model_dump_json()`에서 자동 포함

### REQ-BONUS-002 — analyzer 보너스 빈도 채우기 (Event-driven)

When `analyzer.analyze(draws)` is called, the resulting `Statistics` object **MUST** have `bonus_frequency` populated from `DrawResult.bonus` values for every draw.

- `absolute[n]`: 보너스로 나타난 절대 횟수 (1~45 키 모두 포함, 출현 없으면 0)
- `relative[n]`: `absolute[n] / total_draws` (0~1)
- 기존 `frequency`(본 추첨 6개 번호)와 독립적으로 계산

### REQ-BONUS-003 — API 응답 보너스 빈도 포함 (Ubiquitous)

The `GET /api/stats` response **MUST** include the `bonus_frequency` field in the JSON output.

- 신규 코드 작성은 불필요 — Pydantic `model_dump()`가 자동 처리
- 회귀 보호 테스트로 검증

### REQ-BONUS-004 — 보너스 회피 가중치 옵션 (State-driven, default off)

When `settings.bonus_avoidance_weight > 0`, the recommender **SHALL** subtract a penalty proportional to `bonus_frequency.absolute[n] * weight` from each number's score before final selection.

- 기본값 `0.0`: 기존 동작 보존(회귀 0)
- 환경 변수: `LOTTO_BONUS_AVOIDANCE_WEIGHT` (선택)
- 페널티는 보너스 빈도가 정규화되지 않은 상태에서 곱해진 후 다른 점수와 일관성을 위해 0~1 범위로 정규화하여 적용

### REQ-SCRAPER-001 — 스크래퍼 파싱 안정성 (Event-driven)

When `scraper._parse_draw_row(row)` encounters an unparseable row, it **MUST**:

- 처리해야 할 엣지 케이스 (예외 없이 None 반환):
  1. 행 길이 < 11 (열 부족)
  2. 회차 셀이 정수로 변환 불가
  3. 날짜 셀이 `YYYY.MM.DD` 형식이 아님 (대시 `-`, 슬래시 `/` 등)
  4. 6개 번호 셀 중 하나라도 정수로 변환 불가
  5. 보너스 셀이 정수로 변환 불가
- 모든 실패에 대해 `logger.warning(...)`로 사유와 행 첫 셀(또는 길이)을 기록
- 절대 예외를 상위로 전파하지 않음

### REQ-SCRAPER-002 — scrape_all None 행 스킵 (Event-driven)

When `scraper.scrape_all()` receives `None` from `_parse_draw_row()`, it **MUST** skip that row and continue processing remaining rows without raising.

- `<table>` 미발견 시: 빈 리스트 반환 (예외 없음)
- 유효 행과 무효 행이 혼재한 경우: 유효 행만 결과에 포함

---

## Non-Functional Requirements (비기능 요구사항)

- **호환성**: Python 3.9.25 환경에서 동작. `zip(strict=True)` / `match` 문 사용 금지.
- **회귀 0**: 기존 256개 테스트 모두 통과. 커버리지 ≥ 91% 유지.
- **API 안정성**: 함수 시그니처(외부 인터페이스) 무변경. 필드 추가만 허용.
- **데이터 호환성**: 기존 `data/stats.json`은 신규 필드 부재 시 `FrequencyStats()` 기본값으로 로드 가능해야 함 (Pydantic 기본값 처리).

---

## Acceptance Criteria

Given-When-Then 시나리오는 `acceptance.md`에 별도 명시.

핵심 통과 조건:
- [ ] `Statistics(...).bonus_frequency` 필드 존재 및 `FrequencyStats` 타입
- [ ] `analyze(draws)` 호출 후 `stats.bonus_frequency.absolute` 합계 == `len(draws)`
- [ ] `GET /api/stats` 응답 JSON에 `bonus_frequency` 키 존재
- [ ] `bonus_avoidance_weight=0.0` (기본)에서 추천 동작 회귀 없음
- [ ] `_parse_draw_row`가 5가지 엣지 케이스에서 예외 없이 None 반환 + 경고 로그
- [ ] `scrape_all`이 None 행을 스킵하고 유효 행만 반환
- [ ] 기존 256개 테스트 + 신규 테스트 모두 PASS
- [ ] 커버리지 ≥ 91%

---

## Related

- 선행: SPEC-LOTTO-001 (CLI), SPEC-WEB-001 (웹 대시보드), SPEC-LOTTO-002 (설정 외부화)
- 후속: 없음
