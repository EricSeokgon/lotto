# SPEC-LOTTO-077 구현 계획

## 대상 파일

| 파일 | 변경 내용 |
|------|-----------|
| `lotto/web/data.py` | `get_single_digit_stats` 함수 + `_single_digit_cache`/`_SINGLE_DIGIT_KEYS`/`_SINGLE_DIGIT_SET` 모듈 상수 추가, `invalidate_cache`에 캐시 clear 추가 |
| `lotto/web/routes/api.py` | `GET /api/stats/single_digit` 엔드포인트 추가 |
| `lotto/web/routes/pages.py` | `GET /stats/single-digit` 페이지 라우트 추가 |
| `lotto/web/templates/single_digit.html` | 분포 분석 페이지 템플릿 (mult4.html 패턴) |
| `lotto/web/templates/base.html` | "한자리" 네비게이션 링크 추가 |
| `tests/test_single_digit_analysis.py` | RED 테스트 약 25개 |

## 알고리즘

- 1자리 집합: `{1, 2, 3, 4, 5, 6, 7, 8, 9}`
- 회차별: `sum(1 for n in draw.numbers() if n in _SINGLE_DIGIT_SET)` → 0~6
- 분포: "0".."6" 7개 고정 키, zero-fill
- `avg_single_count` = 평균(소수 2자리)
- `most_common_count` = 빈도 최댓값(동률 시 작은 키)
- `high_single_pct` = count>=3 비율(소수 2자리)

## 캐시 전략

- `_single_digit_cache: dict[str, Any]`, 키는 `str(len(draws) if draws else 0)`
- 기존 SPEC-076(`get_mult4_stats`) 패턴과 동일하게 `.get()` 후 동일 객체 반환
- `invalidate_cache()`에 `_single_digit_cache.clear()` 추가
- conftest autouse fixture가 테스트 간 캐시 격리 처리

## RED-GREEN-REFACTOR

1. RED: 테스트 작성 → 실패 확인
2. GREEN: data.py 구현 + 라우트 + 템플릿 → 테스트 통과
3. REFACTOR: mult4 패턴과 일관성 유지, 중복 제거

## 제약

- Python 3.9 호환 (walrus/match-case/zip strict 금지)
- 기존 함수 미변경
- 보너스 제외 (`draw.numbers()`는 본번호 6개만 반환)
