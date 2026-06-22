# SPEC-LOTTO-108 구현 계획 (Implementation Plan)

## 개발 방법론

TDD (RED → GREEN → REFACTOR). `development_mode: tdd`.

## 변경 파일

| 파일 | 변경 내용 |
|------|-----------|
| `tests/test_monthly_distribution.py` | 신규 — ~23개 테스트 (RED) |
| `lotto/web/data.py` | `get_monthly_distribution()` 함수, `_monthly_dist_cache`, 헬퍼, 면책 고지, `invalidate_cache()` 갱신 |
| `lotto/web/routes/api.py` | `GET /api/stats/monthly` 라우트 |
| `lotto/web/routes/pages.py` | `GET /stats/monthly` 페이지 라우트 |
| `lotto/web/templates/monthly_distribution.html` | 신규 템플릿 |
| `lotto/web/templates/base.html` | 내비게이션 탭·제목 추가 |

## 알고리즘 (get_monthly_distribution)

1. `MONTH_NAMES = ["Jan",...,"Dec"]` 상수.
2. 캐시 키 `f"{0 if not draws else len(draws)}:{top_n}"` 조회.
3. None/빈 입력 → 0 채움 구조 반환.
4. `draw.date.month`(1~12)로 그룹화 — 월별 회차 수, 월별 번호 카운트(`[0]*45`) 누적.
5. `monthly_summary`: 12개 `{month, month_name, draw_count}`.
6. `top_numbers_by_month[str(m)]`: `(count desc, number asc)` 정렬 후 상위 `top_n`,
   `count>0`인 번호만 포함, `pct = round(count/draw_count*100, 2)`.
7. `top_months_by_number[number-1]`: 12개월 중 count 최대인 월(동률 시 가장 작은 월).
   미출현 번호는 `best_month=0`.
8. 결과 캐시 후 반환.

## 라우트

- API: `top_n: Query(ge=1, le=45, default=5)`. 범위 초과 시 FastAPI 422.
- 페이지: `top_n: Query(ge=1, le=45, default=5)`, `active_tab="monthly"`.
- 두 라우트 모두 `from lotto.web import data as wd` 동적 호출(테스트 patch 호환).

## 검증

- `pytest tests/test_monthly_distribution.py -q --no-cov` → 전체 통과.
- `ruff check`(변경 파일) → clean.
- Python 3.9 호환, 코어 모듈 불변.

## @MX 태그

- `get_monthly_distribution`: `@MX:ANCHOR`(API·페이지 fan_in≥2, 월 그룹화·정렬 규칙이 결과 계약 불변식).
