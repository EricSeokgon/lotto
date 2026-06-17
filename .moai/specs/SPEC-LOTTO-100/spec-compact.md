# SPEC-LOTTO-100 Compact — 통계 기반 번호 조합 적합도 점수

## 요구사항 (REQ-FS-*)

### Ubiquitous
- **REQ-FS-U01**: 시스템은 본번호 6개(보너스 번호 제외)만을 사용하여 적합도 점수를 계산해야 한다.
- **REQ-FS-U02**: Fitness Score는 0.0 이상 100.0 이하의 실수(소수 2자리)여야 한다.
- **REQ-FS-U03**: 각 통계 항목의 가중치는 동일하게 1.0으로 설정한다.
- **REQ-FS-U04**: `fitness_score = round(sum(item_pcts) / len(item_pcts), 2)`. 각 항목에서 해당 버킷의 pct(0~100%)를 평균한 값이 Fitness Score이다.
- **REQ-FS-U05**: Fitness Score 자체는 캐시하지 않는다. 통계 캐시를 재활용한다.
- **REQ-FS-U06**: 세부 내역(breakdown)은 15개 통계 항목별 기여 pct를 포함해야 한다.

### Event-driven
- **REQ-FS-E01**: When `GET /api/stats/fitness?numbers=1,2,3,4,5,6` 호출 시, `numbers`, `fitness_score`, `grade`, `breakdown`, `disclaimer` 필드 포함 JSON 반환.
- **REQ-FS-E02**: When `GET /stats/fitness` 페이지 요청 시, `fitness.html` 렌더링, 번호 입력 폼 포함.
- **REQ-FS-E03**: When 웹 폼에서 번호 제출 시, JS fetch로 API 호출 → 페이지 새로고침 없이 점수/breakdown 표시.
- **REQ-FS-E04**: When `invalidate_cache()` 호출 시, fitness 관련 캐시 처리 (현재 캐시 없음, no-op 주석 유지).

### State-driven
- **REQ-FS-S01**: While draws가 None 또는 빈 리스트인 경우, `fitness_score=0.0`, `grade="데이터 없음"`, `breakdown={}` 반환.
- **REQ-FS-S02**: While 통계 캐시가 존재하는 경우, 캐시된 통계를 재활용한다.

### Negative
- **REQ-FS-N01**: 6개가 아닌 번호 개수 → HTTP 400 반환.
- **REQ-FS-N02**: 1~45 범위 외 번호 → HTTP 400 반환.
- **REQ-FS-N03**: 중복 번호 포함 → HTTP 400 반환.
- **REQ-FS-N04**: API 응답 및 UI에 "당첨 가능성 예측 불가" 면책 고지 필수.
- **REQ-FS-N05**: `zip(strict=True)` 미사용 — Python 3.9 호환.
- **REQ-FS-N06**: `match`/`case` 미사용 — Python 3.9 호환.

### Optional
- **REQ-FS-O01**: 등급 분류: 80+ → "매우 높음" / 60-79 → "높음" / 40-59 → "보통" / 20-39 → "낮음" / 0-19 → "매우 낮음".
- **REQ-FS-O02**: breakdown은 기여 점수 내림차순 정렬로 표시한다.

---

## 인수 기준 (Given/When/Then)

| AC | 시나리오 | 조건 | 결과 |
|----|---------|------|------|
| AC-FS-001 | 유효한 6개 번호 → 점수 반환 | `GET /api/stats/fitness?numbers=1,7,14,23,35,44`, 데이터 존재 | HTTP 200, `fitness_score` 0~100, `breakdown` 15개 항목 |
| AC-FS-002 | 점수 범위 보장 | 임의 유효 6개 번호 | `fitness_score` 항상 0.0~100.0, 소수 2자리 |
| AC-FS-003 | 개수 오류 | `numbers=1,2,3,4,5` (5개) | HTTP 400, 한국어 오류 메시지 |
| AC-FS-004 | 범위 초과 | `numbers=0,...` 또는 `...,46` | HTTP 400 |
| AC-FS-005 | 중복 번호 | `numbers=1,1,2,3,4,5` | HTTP 400 |
| AC-FS-006 | 빈 데이터 | draws=None 또는 [] | `fitness_score=0.0`, `grade="데이터 없음"`, `breakdown={}` |
| AC-FS-007 | breakdown 구조 | 유효 번호 + 데이터 존재 | 각 breakdown 항목: `label`, `bucket`, `pct` 키 포함, `pct` 0~100 |
| AC-FS-008 | 등급 분류 | 각 임계값 점수 | 80+ → 매우 높음, 60-79 → 높음, 40-59 → 보통, 20-39 → 낮음, <20 → 매우 낮음 |
| AC-FS-009 | 면책 고지 | 유효 번호 API 응답 | `disclaimer` 필드 포함, 당첨 예측 불가 문구 |
| AC-FS-010 | 흔한 패턴 → 높은 점수 | 역대 고빈도 특성 조합 | `fitness_score >= 50.0` |
| AC-FS-011 | 드문 패턴 → 낮은 점수 | 극단적 조합 (전부 홀수 등) | `fitness_score` < 전체 평균 |
| AC-FS-012 | 웹 페이지 렌더링 | `GET /stats/fitness` | HTTP 200, 번호 입력 폼 포함, 면책 고지 표시 |
| AC-FS-013 | 웹 폼 제출 흐름 | 6개 번호 입력 후 버튼 클릭 | 페이지 새로고침 없이 점수/등급/breakdown 표시 |
| AC-FS-014 | 사이드바 링크 | 임의 페이지 렌더링 | 사이드바에 `/stats/fitness` 링크 존재 |
| AC-FS-015 | `numbers` 파라미터 누락 | `GET /api/stats/fitness` | HTTP 422 |
| AC-FS-016 | 번호 순서 독립성 | 동일 번호 다른 순서 | 동일한 `fitness_score` 반환 |
| AC-FS-017 | 홀짝 breakdown 정확성 | 홀수 4개 조합 | `breakdown["odd_even"]["bucket"]="4"`, pct 일치 |
| AC-FS-018 | 사분위 breakdown 정확성 | Q1:2, Q2:1, Q3:2, Q4:1 조합 | `breakdown["quartile"]["bucket"]="2-1-2-1"` |
| AC-FS-019 | 구간 커버리지 정확성 | 5구간 커버 조합 | `breakdown["zone_coverage"]["bucket"]="5"`, pct 일치 |
| AC-FS-020 | 스팬 버킷 매핑 | 스팬=43 조합 | `breakdown["span"]["bucket"]="41 이상"` |

---

## 수정 대상 파일

| 파일 | 변경 유형 |
|------|----------|
| `lotto/web/data.py` | 수정 — `get_fitness_score()` 함수 추가 |
| `lotto/web/routes/api.py` | 수정 — `GET /api/stats/fitness` 엔드포인트 추가 |
| `lotto/web/routes/pages.py` | 수정 — `GET /stats/fitness` 페이지 라우트 추가 |
| `lotto/web/templates/fitness.html` | 신규 생성 |
| `lotto/web/templates/base.html` | 수정 — 사이드바 링크 추가 |
| `tests/web/test_fitness_score.py` | 신규 생성 (약 50개 테스트) |

---

## 제외 항목

- 번호 자동 추천/최적화
- 특정 회차와의 비교
- 사용자별 가중치 커스터마이징
- 배치 점수 계산
- Fitness Score 자체의 캐시 구현
