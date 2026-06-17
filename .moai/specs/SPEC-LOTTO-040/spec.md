---
id: SPEC-LOTTO-040
version: 0.1.0
status: completed
created: 2026-06-01
updated: 2026-06-01
author: ircp
priority: medium
---

# SPEC-LOTTO-040: 번호 비교 분석기

## 개요

사용자가 입력한 6개 번호 조합을 전체 과거 추첨 회차와 비교하여, 일치 수준별 회차
통계, 번호별 출현 빈도, 종합 등급을 산출하는 비교 분석기를 제공한다.

기존 `analyze-combination`(SPEC-LOTTO-028)이 조합의 통계적 특성(합/홀짝/빈도 점수)에
초점을 맞춘 것과 달리, 본 기능은 "내 번호가 역대 회차와 얼마나 겹쳤는가"를 일치 수준별로
명확히 보여 주는 것에 초점을 둔다.

## 배경

- 사용자는 자신의 번호 조합이 과거에 몇 번 당첨권에 근접했는지 직관적으로 알고 싶어 한다.
- 일치 개수(3/4/5/6)별로 어떤 회차에서 근접했는지 회차 목록을 제공하면 신뢰도가 높아진다.
- 무작위 기대치 대비 상위/하위 백분율 등급으로 조합의 상대적 위치를 요약한다.

## 요구사항 (EARS)

### Ubiquitous (상시)

- REQ-CMP40-001: 시스템은 입력 6개 번호를 정렬한 `numbers` 배열을 항상 응답에 포함해야 한다.
- REQ-CMP40-002: 시스템은 비교에 사용한 전체 회차 수 `total_draws_checked`를 항상 포함해야 한다.

### Event-driven (이벤트)

- REQ-CMP40-003: WHEN 사용자가 6개 번호를 제출하면, 시스템은 전체 회차를 단일 패스로 순회하여
  일치 개수 3/4/5/6 회차를 집계한 `match_summary`를 반환해야 한다. 일치는 본번호 6개 기준이며
  보너스 번호는 일치 계산에 포함하지 않는다.
- REQ-CMP40-004: WHEN 비교가 수행되면, 시스템은 각 일치 수준별 `count`와 회차 목록
  `draws`(각 항목 `{drwNo, date}`)를 포함해야 한다.
- REQ-CMP40-005: WHEN 비교가 수행되면, 시스템은 입력 6개 번호 각각의 전체 출현 빈도
  `number_frequency`(`{number, count, rank}`, 번호 오름차순)를 반환해야 한다.
- REQ-CMP40-006: WHEN 비교가 수행되면, 시스템은 3개 이상 일치 비율 기반의 종합 등급
  `grade`("상위 N%" 또는 "하위 N%")를 반환해야 한다.

### State-driven (상태)

- REQ-CMP40-007: WHILE 추첨 데이터가 부재(None)하거나 빈 리스트인 동안, 시스템은 예외 없이
  `total_draws_checked=0`, 모든 `match_summary` 수준 `count=0`/`draws=[]`,
  6개 입력 번호의 `count=0`, 일관된 `grade` 값을 가진 구조를 반환해야 한다.

### Unwanted (금지)

- REQ-CMP40-008: 시스템은 6개가 아닌 입력, 1~45 범위를 벗어난 번호, 중복 번호에 대해
  HTTP 422를 반환해야 한다(저장하거나 부분 처리하지 않는다).
- REQ-CMP40-009: 시스템은 비교 호출 시 어떤 데이터 파일도 생성/변경하지 않아야 한다(읽기 전용).

### Optional (선택)

- REQ-CMP40-010: WHERE 페이지가 제공되는 경우, `/compare` 페이지는 6개 번호 입력 폼과
  결과 표시 영역을 제공하고, 메인 네비게이션에 `/compare` 링크를 노출해야 한다.

## 인터페이스

### 집계 함수

`compare_numbers(numbers: list[int], draws=_UNSET) -> dict`

- `_UNSET` 센티넬: 인자 생략 시 `get_draws()` 자동 로드, 명시적 None은 데이터 없음 처리.
- 단일 O(N) 패스로 일치 수준 집계 및 번호 빈도 산출.

### API

`POST /api/compare`

- 요청: `{"numbers": [n1,...,n6]}`
- 검증 실패 시 422 (Pydantic)
- 데이터 부재 시에도 200 + 빈 구조

### 응답 스키마

```json
{
  "numbers": [정렬된 입력],
  "total_draws_checked": 0,
  "match_summary": {
    "6": {"count": 0, "draws": []},
    "5": {"count": 0, "draws": []},
    "4": {"count": 0, "draws": []},
    "3": {"count": 0, "draws": []}
  },
  "number_frequency": [{"number": 0, "count": 0, "rank": 0}],
  "grade": "상위 N%"
}
```

## 비고

- 등급 계산: 3개 이상 일치 비율(actual)을 무작위 기대치(약 0.0186)와 비교하여
  actual >= expected이면 "상위", 아니면 "하위"로 분류한다. 결정론적이며 외부 난수 미사용.
- Python 3.9 호환: `zip(strict=...)` 미사용, `from __future__ import annotations` 사용.
