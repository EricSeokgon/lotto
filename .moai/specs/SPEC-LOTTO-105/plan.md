---
id: SPEC-LOTTO-105
version: 0.1.0
status: draft
created: 2026-06-22
updated: 2026-06-22
author: ircp
priority: medium
---

# SPEC-LOTTO-105 구현 계획 (Implementation Plan)

번호 위치별 분포 분석 기능의 구현 계획이다. 기존 통계 SPEC(특히 SPEC-LOTTO-104 recency)의 3계층 구조와 캐시 관례를 그대로 따른다.

---

## 기술 접근 (Technical Approach)

당첨번호 본번호 6개를 오름차순 정렬하면 위치(1~6)가 곧 정렬 인덱스(0~5)가 된다. 전체 회차를 1회 순회하며 6개 위치별 번호 리스트를 누적한 뒤, 위치별로 평균·중앙값·최소·최대·표준편차와 빈도 상위 N개를 계산한다.

핵심 계산 규칙:
- 본번호는 `draw.numbers()`(메서드 호출)로 가져와 `sorted(...)`로 정렬한다.
- 위치별 번호 리스트 6개를 만든다: `position_values[i]`는 모든 회차의 i번째 정렬 번호 모음.
- `avg = round(sum/len, 2)`, `median = round(statistics.median(values), 2)`.
- `std`: 표본 1개면 `0.0`, 그 외 `round(statistics.stdev(values), 2)`.
- `top_numbers`: `collections.Counter(values)`로 빈도 집계 후, `sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))[:top_n]`로 빈도 내림차순·번호 오름차순 정렬. `pct = round(count/total_draws*100, 2)`.
- 빈/None 입력: `total_draws=0`, 6개 위치 모두 0 기본값과 빈 `top_numbers`.

---

## 영향 파일 (Files to Modify / Create)

| 파일 | 작업 | 내용 |
|------|------|------|
| `lotto/web/data.py` | 수정(추가) | `get_position_distribution(draws=_UNSET, top_n=5)` 함수 추가, `_position_cache: dict[str, Any] = {}` 추가, `invalidate_cache()`에 `_position_cache.clear()` 추가 |
| `lotto/web/routes/api.py` | 수정(추가) | `@router.get("/stats/position")` 엔드포인트 추가, `top_n: int = Query(5, ge=1, le=45)` |
| `lotto/web/routes/pages.py` | 수정(추가) | `GET /stats/position` 페이지 라우트 추가, `active_tab="position"` |
| `lotto/web/templates/position_distribution.html` | 생성 | 위치별 분포 표 + disclaimer를 서버 렌더링 |
| `lotto/web/templates/base.html` | 수정 | `desktop_nav_items`와 `nav_items`에 `('/stats/position', 'position', '위치 분포')` 추가, `active_tab == 'position'` 페이지 제목 분기 추가 |
| `tests/test_position_distribution.py` | 생성 | AC-POS-001~023 검증 테스트 |
| `mypy.ini` | 필요시 수정 | 신규 테스트 모듈 override 등록(기존 관례 따름) |

코어 모듈(`lotto/models.py`, `lotto/web/` 외부 `lotto/*.py`)은 수정하지 않는다.

---

## 함수 시그니처 (Signature)

```python
def get_position_distribution(
    draws: list[DrawResult] | None = _UNSET,
    top_n: int = 5,
) -> dict[str, Any]:
    ...
```

반환 구조는 spec.md 본문 및 인수 기준에 정의된 형태를 따른다(`total_draws`, `top_n`, `positions`[6], `disclaimer`).

---

## 캐시 전략

- 키: `f"{len(draws)}:{top_n}"` 형태 권장(또는 기존 관례대로 `str(len(draws))` + top_n 별도 보관). top_n에 따라 `top_numbers`가 달라지므로 캐시 키에 top_n을 반드시 포함한다.
- `invalidate_cache()`에 `_position_cache.clear()`를 추가한다(다른 캐시들과 동일 패턴).

---

## 테스트 전략 (Test Strategy)

- **단위 테스트**: Fixture A(3회차)로 위치 1·6의 avg/median/min/max/std/top_numbers를 손계산 기대값과 정확히 비교(AC-POS-001~010).
- **엣지 테스트**: 빈 리스트, None, 단일 회차, `top_n=1` 경계(AC-POS-011~015).
- **동률 정렬 테스트**: 위치 2~6의 동률 번호가 오름차순으로 정렬되는지 검증(AC-POS-008, AC-POS-015).
- **API 테스트**: `TestClient`로 `/api/stats/position` 200·키 존재·`top_n` 기본값·검증 오류(422), `/stats/position` 페이지 200·disclaimer 포함(AC-POS-016~020).
- **캐시·품질 테스트**: 캐시 재사용/무효화, `match/case`·`zip(strict=)` 미사용, mypy 통과(AC-POS-021~023).

---

## 마일스톤 (우선순위 기반)

1. **Priority High** — `get_position_distribution` 데이터 함수 + 단위/엣지 테스트(AC-POS-001~015, 021~023). 핵심 로직 확정.
2. **Priority Medium** — API·페이지 라우트 추가 + API 테스트(AC-POS-016~020).
3. **Priority Medium** — `position_distribution.html` 템플릿 + base.html 네비게이션 탭("위치 분포") 추가.
4. **Priority Low** — 전체 회귀 테스트·mypy 확인, disclaimer 문구 일관성 점검.

---

## 위험 요소 (Risks)

- **기존 by_position와의 혼동**: `number_stats`(SPEC-030)의 `by_position`(번호 중심)와 본 SPEC(위치 중심)은 집계 축이 다르다. 구현 시 기존 함수를 재사용하지 말고 독립 함수로 작성한다.
- **캐시 키 누락**: top_n이 캐시 키에 빠지면 다른 top_n 요청이 잘못된 캐시를 반환할 수 있다. 키에 top_n 포함 필수.
- **표준편차 표본 처리**: `statistics.stdev`는 표본 1개에서 `StatisticsError`를 던지므로 길이 1 이하 분기를 명시적으로 처리한다.
- **반올림 일관성**: avg/median/std/pct 모두 소수 2자리 반올림 규칙을 동일하게 적용한다.
