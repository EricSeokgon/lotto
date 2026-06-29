# SPEC-LOTTO-150: 19의 배수 분포 분석

## 메타데이터

| 항목 | 값 |
|------|-----|
| SPEC ID | SPEC-LOTTO-150 |
| 제목 | 19의 배수 분포 분석 |
| 상태 | DONE |
| 우선순위 | Medium |
| 생성일 | 2026-06-29 |

## 개요

1~45 범위에서 19의 배수(19, 38)가 각 로또 회차 당첨 번호 6개에 얼마나 포함되는지 분포를 분석한다. 이론적 기댓값(2/45×6 = 0.267)과 실제 데이터를 비교한다.

## 요구사항 (EARS 형식)

### REQ-150-001: 19의 배수 집합 정의
WHEN 분석이 실행되면 THEN 시스템은 1~45 범위에서 19의 배수 집합 {19, 38} (2개)를 사용해야 한다.

### REQ-150-002: 기댓값 계산
WHEN 분석이 실행되면 THEN 시스템은 기댓값을 round(2/45×6, 3) = 0.267로 계산해야 한다.

### REQ-150-003: 분포 목록
WHEN 분석이 실행되면 THEN 시스템은 0개~2개까지 3개 구간의 dist_list를 반환해야 한다.

### REQ-150-004: 빈도 목록
WHEN 분석이 실행되면 THEN 시스템은 2개 배수 번호(19,38) 각각의 freq_list를 반환해야 한다.

### REQ-150-005: 최근 20회차
WHEN 분석이 실행되면 THEN 시스템은 최근 20회차 이하의 recent 목록을 반환해야 한다.

### REQ-150-006: 빈 데이터 처리
WHEN 데이터가 없으면 THEN 시스템은 None을 반환해야 한다.

### REQ-150-007: HTTP 엔드포인트
WHEN GET /stats/multiples-19 요청이 들어오면 THEN 시스템은 200 OK와 multiples19.html 템플릿을 반환해야 한다.

## 구현 파일

- `lotto/web/data.py`: `get_multiples19_analysis()` 함수
- `lotto/web/routes/pages.py`: `/stats/multiples-19` 라우트
- `lotto/web/templates/multiples19.html`: Bootstrap 5 템플릿
- `lotto/web/templates/base.html`: 네비게이션 항목 추가
- `tests/test_multiples19.py`: 10개 테스트
