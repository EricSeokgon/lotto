---
id: SPEC-LOTTO-072
version: 0.1.0
status: Planned
created: 2026-06-12
updated: 2026-06-12
author: ircp
priority: medium
---

# SPEC-LOTTO-072 구현 계획: 끝자리 유니크 수 분포 분석

## 기술 접근

SPEC-070(AC값)·SPEC-071(중앙값)이 확립한 `lotto/web/data.py` 확장 패턴을 그대로
복제·각색한다. 코어 모듈(`analyzer.py`, `models.py`, `recommender.py`,
`simulator.py`)은 절대 수정하지 않고, 웹 레이어(`lotto/web/`)에만 신규 심볼을
추가한다. 기존 끝자리 SPEC(055·063)의 함수는 손대지 않는다.

### 핵심 계산 로직

```text
각 회차:  unique = len(set(n % 10 for n in draw.numbers()))   # 1..6
분포:     distribution[str(unique)] += 1
평균:     avg_unique_count = mean(per-draw unique)
최빈:     most_common_count = argmax(count); 동률 시 더 작은 키 우선
모두다름:  all_different_pct = (unique==6 인 회차 수) / total * 100
```

- 분포 키는 항상 `["1","2","3","4","5","6"]` 6개를 0으로 초기화 후 누적(zero-fill).
- 동률 최빈은 고정 키 순서(`"1"`..`"6"`)에서 선두 우선 — `max(_KEYS, key=...)` 의
  "iterable 선두 우선" 규칙 또는 명시적 정렬로 처리.
- `avg_unique_count`, `all_different_pct`, 각 버킷 `pct` 는 `round(x, 2)`.

## 마일스톤 (우선순위 기반, 시간 추정 없음)

### Priority High — 데이터 계층 (data.py)

1. 모듈 상단에 캐시 선언 추가: `_last_digit_unique_cache: dict[str, Any] = {}`
   (SPEC-070 `_ac_cache` / SPEC-071 `_median_cache` 와 동일한 str-키 캐시 패턴).
2. `invalidate_cache()` 함수 본문에 `_last_digit_unique_cache.clear()` 한 줄 추가.
3. `get_last_digit_unique_stats(draws: list) -> dict[str, Any]` 신규 함수 작성:
   - 캐시 키 `str(len(draws))`, 조회→히트 시 반환, 미스 시 계산→저장.
   - 빈 draws 가드: 6개 키 zero-fill + `most_common_count=1`,
     `avg_unique_count=0.0`, `all_different_pct=0.0`.
   - 본문은 SPEC-055/063 의 끝자리 함수를 호출하지 않고 독립 계산.

### Priority High — API 계층 (routes/api.py)

4. `@router.get("/stats/last_digit_unique")` 엔드포인트 추가:
   - SPEC-071 `/stats/median` 라우트와 동일 형태.
   - `return wd.get_last_digit_unique_stats(wd.get_draws())` (항상 200, JSON).
   - docstring 에 SPEC-LOTTO-072 명시 및 응답 필드 요약.

### Priority Medium — 페이지 계층 (routes/pages.py)

5. `@router.get("/stats/last-digit-unique")` 페이지 라우트 추가:
   - `stats = wd.get_last_digit_unique_stats(wd.get_draws())`
   - `last_digit_unique.html` 템플릿을 `active_tab="last_digit_unique"` 로 렌더.

### Priority Medium — 템플릿 (templates/)

6. `templates/last_digit_unique.html` 신규 작성:
   - `base.html` 상속, Tailwind 다크 모드, 서버 렌더 전용(JS 금지).
   - 요약 카드(총 회차 / 평균 유니크 개수 / 최빈 개수 / 모두 다른 비율) +
     6개 구간(1~6) count·pct 분포 테이블/바.
7. `templates/base.html` 네비게이션 두 곳(desktop_nav_items, nav_items)에
   `('/stats/last-digit-unique', 'last_digit_unique', '끝자리유니크')` 링크 추가
   하고, 헤딩 분기(`active_tab == 'last_digit_unique'`)에 페이지 제목 추가.

### Priority High — 테스트 (tests/)

8. `tests/test_last_digit_unique_analysis.py` 신규 작성 (~25개):
   - 손계산 검증 픽스처로 경계값 1·6 및 중간값 커버.
   - 구조/키/zero-fill/동률최빈/빈입력/캐시/2자리 반올림/보너스 제외 검증.
9. `mypy.ini` 에 신규 테스트 모듈 override 등록 (기존 통계 테스트와 동일 관례).

## 영향 파일 (총 6개 + 테스트)

| 파일 | 변경 유형 | 내용 |
|------|-----------|------|
| `lotto/web/data.py` | 수정(추가) | 캐시 선언 + `invalidate_cache()` 한 줄 + `get_last_digit_unique_stats` |
| `lotto/web/routes/api.py` | 수정(추가) | `/api/stats/last_digit_unique` 엔드포인트 |
| `lotto/web/routes/pages.py` | 수정(추가) | `/stats/last-digit-unique` 페이지 라우트 |
| `lotto/web/templates/last_digit_unique.html` | 신규 | 분포 시각화 페이지 |
| `lotto/web/templates/base.html` | 수정(추가) | 네비 링크 2곳 + 헤딩 분기 |
| `tests/test_last_digit_unique_analysis.py` | 신규 | ~25개 테스트 |
| `mypy.ini` | 수정(추가) | 신규 테스트 모듈 override |

## 위험 및 완화

| 위험 | 영향 | 완화 |
|------|------|------|
| SPEC-055/063 끝자리 기능과 혼동·중복 구현 | 잘못된 병합/수정 | spec.md 의 구분 표 준수, 신규 독립 함수만 추가, 기존 함수 미수정 |
| 동률 최빈 처리 불일치 | 비결정적 결과 | 고정 키 순서 선두 우선 규칙을 070/071 과 동일하게 적용 |
| 빈 draws 시 예외 | API 500 | 명시적 가드로 6키 zero-fill + 기본값 반환 |
| Python 3.9 비호환 문법 | 런타임/린트 실패 | walrus·zip(strict=)·match-case 금지 준수 |
| 캐시 무효화 누락 | stale 결과 | `invalidate_cache()` 에 `.clear()` 추가 및 테스트로 검증 |

## 검증 방법

- `/home/sklee/.local/bin/pytest tests/test_last_digit_unique_analysis.py -v` 전부 통과
- 전체 스위트 회귀 없음 (기존 끝자리 테스트 SPEC-055/063 영향 없음 확인)
- mypy 신규 모듈 클린
- `/api/stats/last_digit_unique` 200 + 6키 분포 확인, `/stats/last-digit-unique`
  페이지 정상 렌더 및 네비 활성화 확인
