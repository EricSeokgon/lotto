# SPEC-LOTTO-051: Compact Spec (Run 단계용 압축본)

본 문서는 `/moai run SPEC-LOTTO-051` 실행 시 컨텍스트 효율을 위해 사용되는 압축
SPEC이다. 핵심 요구사항, 인수 기준, 파일 목록, 제외 범위만 추출한다. 상세
배경/근거는 `spec.md`, `plan.md`, `acceptance.md`, `research.md`를 참조한다.

기능: **주차 선택 주의 알림 (Cross-Strategy Consensus Alert)** — 추천 번호 표시에
"각 번호가 11개 전략 중 몇 개에 포함되는가" 합의도 오버레이를 추가하는 읽기 전용
기능. 합의도 >= 4면 주의 배지. 채택안: Option A(서버사이드 요청별 전체 전략 스캔).

---

## 1. REQ-* 요구사항 (EARS Format)

### Ubiquitous

- **REQ-CONS-001**: The system SHALL provide
  `get_cross_strategy_consensus(recommender, target_numbers)` returning
  `{number: count}` (count 0..11) for every number in `target_numbers`.
- **REQ-CONS-002**: The system SHALL compute consensus by calling
  `recommender.recommend_by_strategy(label)` once per `STRATEGY_LABELS` (11 calls);
  it SHALL NOT recompute scores directly.
- **REQ-CONS-003**: WHEN consensus is available, the display SHALL annotate every
  recommended number with its count (`N/11`).

### Event-driven

- **REQ-CONS-004**: WHEN `GET /recommend` loads with recommendations, the system
  SHALL compute consensus and pass it to the template context.
- **REQ-CONS-005**: WHEN `GET /api/recommendations` returns recommendations, each
  recommendation JSON SHALL include a `consensus` field mapping its numbers to counts.

### State-driven

- **REQ-CONS-006**: WHILE a number's consensus count >= 4, the display SHALL render
  a caution badge/highlight on that number.
- **REQ-CONS-007**: WHILE no statistics exist (recommendations None), the system
  SHALL skip consensus and render the page with HTTP 200.

### Unwanted

- **REQ-CONS-008**: The system SHALL NOT re-implement recommendation logic;
  consensus MUST go through `recommend_by_strategy()`, never `_strategy_scores`/`_pick_set`.
- **REQ-CONS-009**: Consensus computation SHALL NOT access raw draws; only via
  the `recommender` object (Statistics-only).
- **REQ-CONS-010**: The feature SHALL NOT modify the `Recommendation` dataclass nor
  add a new strategy.

### Optional

- **REQ-CONS-011**: WHERE possible, the system SHALL scan all strategies once per
  page request and reuse the result (no per-card re-scan).

---

## 2. Given-When-Then 인수 기준 (요약)

1. **정상 표시**: GIVEN 통계 존재 / WHEN `GET /recommend?count=5` / THEN 200,
   각 번호에 합의도 `N/11` 표시. (REQ-CONS-003,004)
2. **API consensus**: GIVEN 통계 존재 / WHEN `GET /api/recommendations` / THEN 각
   추천 객체에 `consensus` 필드(번호→0~11) 포함. (REQ-CONS-005)
3. **임계값 배지**: GIVEN 번호가 4개+ 전략에 포함 / WHEN 페이지 렌더 / THEN 주의
   배지 표시, 3 이하는 카운트만. (REQ-CONS-006)
4. **성능**: GIVEN 통계 존재 / WHEN 합의도 계산 포함 로드 / THEN 타임아웃 없음,
   요청당 11회 스캔만(카드 수 무관). (REQ-CONS-011)
5. **계층 경계**: GIVEN 함수 호출 / WHEN 계산 / THEN `recommend_by_strategy`만
   사용, raw draws/`_strategy_scores`/`_pick_set` 미접근. (REQ-CONS-002,008,009)
6. **빈 데이터**: GIVEN 추천 None / WHEN 페이지 로드 / THEN 200, 합의도 패널 없음.
   (REQ-CONS-007)
7. **단위**: 반환 키=target_numbers 전부, 값 0~11; 11회 호출; 다중 등장 정확
   카운트; 빈 리스트→`{}`. (REQ-CONS-001,002)
8. **제약**: `Recommendation` 불변, `recommender.py` 코어 불변, JS 추가 없음.
   (REQ-CONS-010, Exclusions)

---

## 3. 파일 생성/수정 목록 (Files to Create/Modify)

| 파일 | 변경 | 델타 |
|------|------|------|
| `lotto/recommender.py` | 호출만, 수정 없음 | [EXISTING] |
| `lotto/web/data.py` | `get_cross_strategy_consensus(recommender, target_numbers)` 추가 | [NEW] |
| `lotto/web/routes/pages.py` | `recommend` 라우트 컨텍스트에 consensus 추가 | [MODIFY] |
| `lotto/web/routes/api.py` | `/api/recommendations` 응답에 `consensus` 필드 추가 | [MODIFY] |
| `lotto/web/templates/recommend.html` | 번호별 합의도 배지(주의 하이라이트) 렌더 | [MODIFY] |
| `tests/test_web_data.py` | 단위 테스트 | [NEW/MODIFY] |
| 기존 API/페이지 테스트 모듈 | consensus 필드/배지 통합 테스트 | [NEW/MODIFY] |
| `mypy.ini` | 신규 테스트 모듈 override(필요 시) | [MODIFY] |

MX: `get_cross_strategy_consensus` fan_in >= 2(pages.py + api.py) → `@MX:ANCHOR`.

---

## 4. Exclusions (제외 범위)

구현 금지 항목:

1. **추천 코어 로직 변경 금지** — `recommender.py`의 `STRATEGY_LABELS`,
   `_strategy_scores`, `_pick_set` 수정 금지. 호출만.
2. **원본 추첨 데이터(raw draws) 웹 계층 노출 금지** — `recommender`/`Statistics`만 사용.
3. **신규 전략 추가 금지** — 표시용 보강만.
4. **JavaScript 불필요** — 서버사이드 렌더링.
5. **`Recommendation` 데이터클래스 변경 금지**.

---

## 5. Python 3.9 / 품질 게이트 (요약)

- Python 3.9.25: `zip(strict=True)` 금지(필요 시 `# noqa: B905`), 워러스 자제.
- `~/.local/bin/pytest` 전체 통과, 신규 함수 커버리지 90%+.
- mypy 통과, ruff clean, 신규 외부 의존성 없음.
- 함수/변수명 영어, docstring/주석 한국어.

---

상세 내용 참조: `spec.md`, `plan.md`, `acceptance.md`, `research.md`
