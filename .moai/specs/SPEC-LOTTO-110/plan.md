# SPEC-LOTTO-110 구현 계획 (Implementation Plan)

## 방법론: TDD (RED → GREEN → REFACTOR)

## 대상 파일

| 파일 | 변경 |
|------|------|
| `tests/test_yearly_distribution.py` | 신규 (~18 테스트) |
| `lotto/web/data.py` | `get_yearly_distribution()` + 헬퍼 + 캐시 추가 |
| `lotto/web/routes/api.py` | `GET /stats/yearly` 추가 |
| `lotto/web/routes/pages.py` | `GET /stats/yearly` 페이지 추가 |
| `lotto/web/templates/yearly_distribution.html` | 신규 템플릿 |
| `lotto/web/templates/base.html` | 내비게이션 탭 2곳 추가 |

## 핵심 로직 (data.py)

```
get_yearly_distribution(draws, top_n=5):
  1. None/빈 → 0 채움 구조 (yearly_summary=[], top_numbers_by_year={},
     top_years_by_number 45개 best_year=None)
  2. 연도별 회차 수(year_draw_count) + 연도별 번호 카운트(year_number_counts) 누적
  3. yearly_summary: 연도 오름차순 [{year, draw_count}, ...]
  4. top_numbers_by_year[str(year)]: count desc, 동률 number asc, top_n개
     (count=0 번호 제외)
  5. top_years_by_number[idx]: 최대 count 연도. 연도 오름차순 순회 +
     "더 큰 count일 때만 갱신" → 동률 시 이른 연도 유지. 미출현 → best_year=None
  6. 캐시 키 f"{len(draws)}:{top_n}"
```

## 정렬·동률 불변식

- top_numbers_by_year: `(-count, number)` 키 정렬 (count desc, number asc)
- top_years_by_number: 연도 오름차순 순회, `count > best_count`일 때만 갱신
  → 동률 시 가장 이른(작은) 연도 유지

## monthly(108)와의 차이

- 월: 고정 12 버킷, best_month=0(미출현). 연도: 가변 버킷, best_year=None(미출현)
- 연도는 데이터 있는 연도만 top_numbers_by_year/yearly_summary에 포함

## 검증

- `pytest tests/test_yearly_distribution.py -q --no-cov` → 전체 통과
- `ruff check` 대상 파일 → clean
- 회귀: 변경 파일 인접 테스트 모듈 타깃 실행
