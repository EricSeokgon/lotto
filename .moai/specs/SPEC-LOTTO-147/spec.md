# SPEC-LOTTO-147: 11의 배수 분포 분석

## 메타데이터

| 항목 | 값 |
|------|-----|
| SPEC ID | SPEC-LOTTO-147 |
| 제목 | 11의 배수 분포 분석 |
| 상태 | DONE |
| 우선순위 | Medium |
| 생성일 | 2026-06-29 |

## 개요

1~45 범위에서 11의 배수(11, 22, 33, 44)가 각 로또 회차 당첨 번호 6개에 얼마나 포함되는지 분포를 분석한다. 이론적 기댓값(4/45×6 ≈ 0.533)과 실제 데이터를 비교한다.

## 요구사항 (EARS 형식)

### REQ-147-001: 11의 배수 집합 정의

WHEN 분석이 실행되면 THEN 시스템은 1~45 범위에서 11의 배수 집합 {11, 22, 33, 44} (4개)를 사용해야 한다.

### REQ-147-002: 기댓값 계산

WHEN 분석이 실행되면 THEN 시스템은 기댓값을 round(4/45×6, 3) = 0.533으로 계산해야 한다.

### REQ-147-003: 분포 목록

WHEN 분석이 실행되면 THEN 시스템은 0개~4개까지 5개 구간의 dist_list를 반환해야 한다.

### REQ-147-004: 빈도 목록

WHEN 분석이 실행되면 THEN 시스템은 4개 배수 번호(11,22,33,44) 각각의 freq_list를 반환해야 한다.

### REQ-147-005: 최근 20회차

WHEN 분석이 실행되면 THEN 시스템은 최근 20회차 이하의 recent 목록을 반환해야 한다.

### REQ-147-006: 빈 데이터 처리

WHEN 데이터가 없으면 THEN 시스템은 None을 반환해야 한다.

### REQ-147-007: HTTP 엔드포인트

WHEN GET /stats/multiples-11 요청이 들어오면 THEN 시스템은 200 OK와 multiples11.html 템플릿을 반환해야 한다.

## 인수 조건

- [ ] `get_multiples11_analysis()` 반환 타입: `dict | None`
- [ ] 빈 데이터 시 None 반환
- [ ] `mult11_count` 키 값 = 4
- [ ] `expected` = round(4/45*6, 3) ≈ 0.533
- [ ] `dist_list` 길이 = 5 (0개~4개)
- [ ] `freq_list` 길이 = 4 (11,22,33,44)
- [ ] `diff` = round(avg - expected, 3)
- [ ] `recent` 길이 ≤ 20
- [ ] GET /stats/multiples-11 → 200 OK

## 구현 파일

- `lotto/web/data.py`: `get_multiples11_analysis()` 함수
- `lotto/web/routes/pages.py`: `/stats/multiples-11` 라우트
- `lotto/web/templates/multiples11.html`: Bootstrap 5 템플릿
- `lotto/web/templates/base.html`: 네비게이션 항목 추가
- `tests/test_multiples11.py`: 10개 테스트
