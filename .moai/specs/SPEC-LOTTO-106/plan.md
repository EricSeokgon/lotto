# SPEC-LOTTO-106 구현 계획 (Implementation Plan)

## 1. 개발 방법론

TDD (RED → GREEN → REFACTOR). 손계산 가능한 3회차 픽스처로 명세 테스트를 먼저 작성한다.

## 2. 수정 대상 파일

| 파일 | 변경 내용 |
|------|-----------|
| `tests/test_cross_pattern.py` | 신규 — 약 20개 명세/API/페이지 테스트 (RED) |
| `lotto/web/data.py` | `get_cross_pattern_stats()` + 헬퍼/캐시/상수 추가, `invalidate_cache()`에 캐시 무효화 한 줄 |
| `lotto/web/routes/api.py` | `GET /api/stats/cross-pattern` 추가 |
| `lotto/web/routes/pages.py` | `GET /stats/cross-pattern` 추가 |
| `lotto/web/templates/cross_pattern.html` | 신규 — 7×7 매트릭스 테이블, 상위 조합 강조, top_n 선택기 |
| `lotto/web/templates/base.html` | 내비게이션 탭 `('/stats/cross-pattern', 'cross_pattern', '조합 매트릭스')` 추가 + 제목 매핑 |

코어 모듈(lotto.core/models/config)은 수정하지 않는다.

## 3. 함수 시그니처

```python
def get_cross_pattern_stats(
    draws: list[DrawResult] | None,
    top_n: int = 10,
) -> dict[str, Any]:
    ...
```

- 본번호: `draw.numbers()` (오름차순 list[int]).
- `high` 판정: `n > 23`.
- `odd` 판정: `n % 2 == 1`.
- matrix 키: `f"odd_{i}_high_{j}"` (i,j in 0..6) 49개 전부 생성 후 카운트 채움.
- top_combinations: count desc, tie → odd_count asc, high_count asc. pct = round(count/total*100, 2).
- marginal_odd/high: 문자열 키 "0".."6".
- avg_odd/high: round(mean, 2). 빈 입력은 0.0.
- 빈/None 입력: total_draws=0, 49 키 0, 빈 top_combinations, marginal 0, avg 0.0.

## 4. 캐시 전략

`_cross_pattern_cache: dict[str, Any] = {}` 모듈 레벨. 키 `f"{len(draws)}:{top_n}"`.
`invalidate_cache()`에 `_cross_pattern_cache.clear()` 추가 (conftest autouse fixture가 테스트 간 호출).

## 5. 테스트 전략

- data layer: AC-CROSS-001~018 (계산/정렬/빈입력)
- API: AC-CROSS-019~020 (`TestClient`, `patch("lotto.web.data.get_draws")`)
- Page: AC-CROSS-021~022 (HTML 문자열/active_tab/빈 데이터 200)

실행: `pytest tests/test_cross_pattern.py -q --no-cov` (러너: `/home/sklee/.local/bin/pytest`).
린트: `ruff check lotto/web/data.py lotto/web/routes/api.py lotto/web/routes/pages.py tests/test_cross_pattern.py`.

## 6. @MX 태그

- `get_cross_pattern_stats`는 data.py 내 신규 공개 함수 → `@MX:NOTE` + `@MX:SPEC` (api/pages 2곳 호출, fan_in<3).
