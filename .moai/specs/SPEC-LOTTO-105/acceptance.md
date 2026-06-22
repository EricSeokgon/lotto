---
id: SPEC-LOTTO-105
version: 0.1.0
status: draft
created: 2026-06-22
updated: 2026-06-22
author: ircp
---

# SPEC-LOTTO-105 인수 기준 (Acceptance Criteria)

번호 위치별 분포 분석(`get_position_distribution`)의 상세 인수 기준이다. 손계산으로 검증 가능한 최소 픽스처를 사용한다.

---

## 검증 픽스처 (Fixture A)

3개 회차의 본번호로 구성한다(보너스는 분석에 미사용, 참고용으로만 표기).

| 회차 | 본번호(오름차순) | 보너스 |
|------|------------------|--------|
| Draw 1 | [1, 5, 10, 20, 30, 40] | 7 |
| Draw 2 | [2, 6, 12, 22, 32, 42] | 8 |
| Draw 3 | [1, 7, 15, 25, 35, 45] | 9 |

### 위치별 관측값 (정렬된 본번호를 위치 인덱스로 펼침)

| 위치 | 관측 번호 | avg | median | min_ever | max_ever | std (표본) |
|------|-----------|-----|--------|----------|----------|------------|
| 1 | [1, 2, 1] | 1.33 | 1.0 | 1 | 2 | 0.58 |
| 2 | [5, 6, 7] | 6.0 | 6.0 | 5 | 7 | 1.0 |
| 3 | [10, 12, 15] | 12.33 | 12.0 | 10 | 15 | 2.52 |
| 4 | [20, 22, 25] | 22.33 | 22.0 | 20 | 25 | 2.52 |
| 5 | [30, 32, 35] | 32.33 | 32.0 | 30 | 35 | 2.52 |
| 6 | [40, 42, 45] | 42.33 | 42.0 | 40 | 45 | 2.52 |

### 손계산 근거 (양 끝단)

- 위치 1: 번호 = [1, 2, 1]. avg = round((1+2+1)/3, 2) = round(1.3333, 2) = **1.33**. median = sorted([1,1,2])의 중앙값 = **1.0**. min_ever = **1**, max_ever = **2**. std = round(stdev([1,2,1]), 2) = round(0.57735, 2) = **0.58**. top_numbers: 1이 2회(pct round(2/3*100,2)=**66.67**), 2가 1회(pct round(1/3*100,2)=**33.33**) → `[{1,2,66.67}, {2,1,33.33}]`.
- 위치 6: 번호 = [40, 42, 45]. avg = round((40+42+45)/3, 2) = round(42.3333, 2) = **42.33**. median = **42.0**. min_ever = **40**, max_ever = **45**. std = round(stdev([40,42,45]), 2) = **2.52**. top_numbers(top_n>=3): `[{40,1,33.33}, {42,1,33.33}, {45,1,33.33}]` (동률이므로 더 작은 번호 우선 정렬).
- 위치 2: 번호 = [5, 6, 7]. 세 번호 각 1회로 동률 → top_numbers는 작은 번호 우선 `[{5,1,33.33}, {6,1,33.33}, {7,1,33.33}]`. std = round(stdev([5,6,7]), 2) = **1.0**.

---

## AC 항목

### 핵심 함수 동작 (AC-POS-001 ~ AC-POS-010)

- **AC-POS-001** (REQ-POS-001, REQ-POS-004): Fixture A로 `get_position_distribution(draws)` 호출 시 반환 dict는 `total_draws`, `top_n`, `positions`, `disclaimer` 키를 모두 포함한다. `total_draws == 3`, `len(positions) == 6`.
- **AC-POS-002** (REQ-POS-005): `positions[0]["position"] == 1`이고 `positions[5]["position"] == 6`이다. 각 항목은 `position`, `avg`, `median`, `min_ever`, `max_ever`, `std`, `top_numbers` 키를 갖는다.
- **AC-POS-003** (REQ-POS-003, REQ-POS-006): `positions[0]["avg"] == 1.33`, `positions[0]["median"] == 1.0`.
- **AC-POS-004** (REQ-POS-005): `positions[0]["min_ever"] == 1`, `positions[0]["max_ever"] == 2`.
- **AC-POS-005** (REQ-POS-006): `positions[0]["std"] == 0.58` (표본 표준편차, 소수 2자리).
- **AC-POS-006** (REQ-POS-007, REQ-POS-008): `positions[0]["top_numbers"] == [{"number": 1, "count": 2, "pct": 66.67}, {"number": 2, "count": 1, "pct": 33.33}]`.
- **AC-POS-007** (REQ-POS-003, REQ-POS-006): `positions[5]["avg"] == 42.33`, `positions[5]["median"] == 42.0`, `positions[5]["min_ever"] == 40`, `positions[5]["max_ever"] == 45`, `positions[5]["std"] == 2.52`.
- **AC-POS-008** (REQ-POS-007): 위치 2의 `top_numbers`는 모두 동률(각 1회)이므로 번호 오름차순으로 `[{5,...}, {6,...}, {7,...}]` 순서로 반환된다.
- **AC-POS-009** (REQ-POS-002): 보너스 번호(7, 8, 9)는 어떤 위치의 `top_numbers`에도 등장하지 않는다.
- **AC-POS-010** (REQ-POS-009): 동일 입력으로 두 번 호출하면 완전히 동일한 dict를 반환한다(결정적).

### 엣지 케이스 (AC-POS-011 ~ AC-POS-015)

- **AC-POS-011** (REQ-POS-014): `get_position_distribution([])` 호출 시 `total_draws == 0`이고, 6개 위치 각각 `avg == 0.0`, `median == 0.0`, `min_ever == 0`, `max_ever == 0`, `std == 0.0`, `top_numbers == []`이다. 예외를 발생시키지 않는다.
- **AC-POS-012** (REQ-POS-014): `get_position_distribution(None)` 호출도 AC-POS-011과 동일한 빈 결과를 반환한다(예외 없음).
- **AC-POS-013** (REQ-POS-006): 단일 회차 `[[3, 8, 14, 21, 29, 41]]`로 호출 시 각 위치의 표본이 1개이므로 모든 위치의 `std == 0.0`이고, `avg`와 `median`은 그 단일 번호값(예: 위치 1 `avg == 3.0`, `median == 3.0`, `min_ever == 3`, `max_ever == 3`)이다.
- **AC-POS-014** (REQ-POS-013): 단일 회차(AC-POS-013) 입력에서 `top_n=5`로 호출해도 각 위치에는 번호가 1개뿐이므로 `top_numbers` 길이는 1이다(0 빈도 패딩 없음).
- **AC-POS-015** (REQ-POS-007, REQ-POS-012): Fixture A로 `top_n=1` 호출 시 각 위치의 `top_numbers` 길이는 정확히 1이다. 위치 1은 `[{"number": 1, "count": 2, "pct": 66.67}]`이고, 동률 위치(위치 2~6)는 가장 작은 번호 1개만 반환한다(위치 2 → `[{"number": 5, ...}]`).

### API 동작 (AC-POS-016 ~ AC-POS-020)

- **AC-POS-016** (REQ-POS-010): `GET /api/stats/position` 요청은 HTTP 200을 반환하고, 응답 JSON에 `total_draws`, `top_n`, `positions`(길이 6), `disclaimer` 키가 존재한다.
- **AC-POS-017** (REQ-POS-010, REQ-POS-012): `GET /api/stats/position?top_n=5`의 각 `positions[i]["top_numbers"]` 길이는 5 이하이며, 응답의 `top_n == 5`이다.
- **AC-POS-018** (REQ-POS-012): `top_n` 쿼리 파라미터를 생략하면 기본값 5가 적용되어 응답 `top_n == 5`이다.
- **AC-POS-019** (REQ-POS-015): `GET /api/stats/position?top_n=0` 및 `?top_n=46` 요청은 HTTP 422(검증 오류)를 반환한다.
- **AC-POS-020** (REQ-POS-011, NFR-POS-005): `GET /stats/position` 요청은 HTTP 200과 함께 `position_distribution.html`을 렌더링하며, 응답 본문에 면책 문구(`disclaimer` 텍스트)가 포함되고 `active_tab`은 `position`이다.

### 캐싱·품질 (AC-POS-021 ~ AC-POS-023)

- **AC-POS-021** (NFR-POS-006): 동일 길이의 `draws`로 반복 호출 시 캐시된 결과를 재사용하며, `invalidate_cache()` 호출 후에는 캐시가 비워져 재계산된다.
- **AC-POS-022** (NFR-POS-001, NFR-POS-002): 구현 코드에 `match/case`, `zip(strict=True)`가 없으며, 본번호 접근은 `draw.numbers()` 메서드 호출을 사용한다.
- **AC-POS-023** (NFR-POS-007): `tests/test_position_distribution.py`가 위 AC를 커버하고, mypy 타입 검사를 통과한다.

---

## Definition of Done

- [ ] AC-POS-001 ~ AC-POS-023 전부 통과
- [ ] `get_position_distribution`가 `lotto/web/data.py`에 추가됨 (코어 모듈 미수정)
- [ ] `GET /api/stats/position`, `GET /stats/position` 라우트 추가
- [ ] `position_distribution.html` 템플릿 추가, base.html `desktop_nav_items`/`nav_items`에 "위치 분포" 탭 추가
- [ ] `invalidate_cache()`에 위치 분포 캐시 무효화 추가
- [ ] 전체 테스트 통과(2902 → 증가), mypy 0건 유지
- [ ] API·웹 UI 양쪽에 disclaimer 노출
