---
id: SPEC-LOTTO-046
version: 0.1.0
status: Planned
created: 2026-06-02
updated: 2026-06-02
author: ircp
priority: medium
---

# SPEC-LOTTO-046 인수 기준

## 단위 테스트 (`tests/test_yearly_prize.py`)

| AC | 시나리오 | 기대 결과 |
|----|----------|-----------|
| AC-1 | 다년도 픽스처 (2022/2023, 연도별 2회) | 연도별 avg/max/min 정확, years 오름차순 |
| AC-2 | overall_avg_prize1 | prize 보유 전체 회차 평균(floor) |
| AC-3 | highest/lowest_avg_year | 평균 최고/최저 연도 정확 |
| AC-4 | prize 없는 연도 | avg/max/min=0, prize_draws=0 |
| AC-5 | total_draws | 연도 내 전체 회차 수 (prize 무관) |
| AC-6 | total_winners | prize1Winners 합계, None은 0 |
| AC-7 | 빈 리스트 | total_years=0, 빈 구조, 예외 없음 |
| AC-8 | None draws | 빈 구조, 예외 없음 |
| AC-9 | 결정론 + 인자 생략 | 2회 동일 출력, get_draws() 자동 호출 |

## API 테스트 (`tests/test_api_yearly_prize.py`)

| AC | 시나리오 | 기대 결과 |
|----|----------|-----------|
| AC-10 | GET /api/stats/yearly-prize (데이터 있음) | 200 + 최상위 키 |
| AC-11 | years 리스트 구조 | 모든 연도 키 포함, 연도 오름차순 |
| AC-12 | get_draws=None | 200 + 빈 구조 |
| AC-13 | 응답 Content-Type | application/json |

## 페이지 테스트 (`tests/test_yearly_prize_page.py`)

| AC | 시나리오 | 기대 결과 |
|----|----------|-----------|
| AC-14 | GET /stats/yearly-prize (데이터 있음) | 200 HTML, 차트/테이블 마커, 연도 라벨 |
| AC-15 | get_draws=None | 200 (빈 상태) |
| AC-16 | GET / 네비 링크 | `href="/stats/yearly-prize"` 포함 |
| AC-17 | 빈 상태 메시지 | "데이터가 없습니다" 노출 |

## 품질 게이트

- [x] 신규 테스트 18개 전부 통과 (RED → GREEN 확인)
- [x] `mypy .` = Success (0 errors)
- [x] ruff clean (변경 파일)
- [x] 전체 테스트 회귀 없음 (1087 → 1105)
- [x] 신규 외부 의존성 없음
