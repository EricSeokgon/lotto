---
id: SPEC-LOTTO-052
version: 0.1.0
status: Planned
created: 2026-06-09
updated: 2026-06-09
author: ircp
priority: medium
issue_number: 0
---

# SPEC-LOTTO-052 구현 계획

## 방법론

TDD (RED → GREEN → REFACTOR), 브라운필드 보강. 기존 동작을 보존하며 읽기 전용
백테스트 평가 계층만 추가한다. 데이터 계층(`run_backtest` + `BacktestResult`) →
API 계층(`/api/backtest`) → 페이지/템플릿 계층(`/backtest`) 순으로 각 계층마다
실패 테스트 작성 후 최소 구현.

핵심 재사용: `lotto/simulator.py`의 검증된 회차별 평가 패턴(평가 회차 #k에 대해
prior_draws=#1..#k-1로 `LottoAnalyzer().analyze(prior_draws)` → `LottoRecommender(stats)`).
이 패턴이 이미 look-ahead bias를 제거하므로 동일 경로를 백테스트에 적용한다.

## 변경 파일

| 파일 | 변경 내용 | 델타 |
|------|-----------|------|
| `lotto/recommender.py` | `recommend_by_strategy()` 호출만, 수정 없음 | [EXISTING] |
| `lotto/analyzer.py` | `LottoAnalyzer().analyze()` 호출만, 수정 없음 | [EXISTING] |
| `lotto/web/data.py` | `BacktestResult` 결과 타입 + `run_backtest(draws, n_past=50)` 신규 함수 + 메모리 캐시 추가 | [NEW] |
| `lotto/web/routes/pages.py` | `/backtest` 라우트 추가 — 캐시 백테스트 결과를 score 내림차순 정렬해 템플릿 컨텍스트에 전달 | [MODIFY] |
| `lotto/web/routes/api.py` | `GET /api/backtest?n=<N>` 엔드포인트 추가 — BacktestResult 직렬화 JSON 반환 | [MODIFY] |
| `lotto/web/templates/backtest.html` | 전략별 성능 표(적중 분포/평균/최고 회차/점수) 렌더링, 한계 안내 문구 포함 | [NEW] |
| `tests/test_web_data.py` | `run_backtest` 단위 테스트(look-ahead 제거, match_counts 합, 최소 회차 에러, 클램핑) | [NEW/MODIFY] |
| `tests/test_api_backtest.py` (또는 기존 API 테스트 모듈) | `/api/backtest` 통합 테스트 | [NEW/MODIFY] |
| `tests/test_web_pages.py` (또는 기존 페이지 테스트 모듈) | `/backtest` 페이지 렌더/정렬/에러 메시지 통합 테스트 | [NEW/MODIFY] |
| `mypy.ini` | 신규 테스트 모듈을 override 목록에 추가(필요 시) | [MODIFY] |

## 데이터 구조 (제안)

```python
class BacktestResult(BaseModel):
    """단일 전략의 백테스트 성능 결과."""

    strategy_label: str
    match_counts: dict[int, int]   # {0..6: count}, 합 == 평가 회차 수
    avg_match: float
    best_draw: dict[str, Any]      # {"round": int, "matched": int,
                                   #  "recommended": list[int], "actual": list[int]}
    score: float                   # 종합 점수(높을수록 우수)
```

## 함수 시그니처 (제안)

```python
def run_backtest(
    draws: list[DrawResult],
    n_past: int = 50,
) -> dict[str, BacktestResult]:
    """11개 전략을 최근 n_past개 회차에 대해 백테스트한다.

    각 평가 회차 #k에 대해 prior_draws(#1..#k-1)만으로 통계를 재구성하고
    11개 전략 추천을 실행하여 실제 당첨 번호 6개와의 적중 개수를 집계한다.
    look-ahead bias가 없도록 평가 회차 이후 데이터는 통계에 포함하지 않는다.

    Returns:
        {전략 라벨: BacktestResult} — STRATEGY_LABELS 11개 전부.

    Raises 대신 에러 결과:
        가용 회차가 최소 임계값(20) 미만이면 에러 결과를 반환한다(REQ-BT-009).
    """
```

## 설계 결정

- **look-ahead 제거(REQ-BT-002, REQ-BT-012)**: 회차마다 prior_draws로 통계를
  재구성한다. 전체 통계를 한 번만 만들어 재사용하는 최적화는 **금지**한다
  (Exclusions 3). simulator.py와 동일 경로를 사용해 검증된 안전성을 상속한다.
- **회차당 1회 통계 재구성, 전략 11회 재사용(REQ-BT-016)**: 평가 회차당
  `analyze`/`LottoRecommender` 생성은 1회만 하고, 그 recommender로 11개 전략을
  순회 추천한다. 전략마다 통계를 재구성하지 않는다(성능 예산 충족).
- **적중 계산(REQ-BT-003, REQ-BT-015)**: `set(recommended) & set(draw.numbers())`
  크기. 보너스 번호는 제외. (시뮬레이터의 등급 평가가 아닌 단순 매치 카운트.)
- **최소 회차/클램핑**: 가용 회차 < 20이면 에러 결과(REQ-BT-009). prior 히스토리
  요구를 만족하는 평가 가능 회차보다 n_past가 크면 평가 윈도를 가능한 최대로
  클램프(REQ-BT-010)하고 match_counts 합은 클램프된 윈도 수와 일치(REQ-BT-005).
- **종합 점수(score)**: 평균 적중에 고적중(3+ 매치) 빈도를 가중한 단조 점수.
  비교/정렬 용도이며 절대값 자체에 의미를 두지 않는다. 정의는 단일 상수/헬퍼로
  고정하여 페이지/API가 동일 값을 사용한다.
- **메모리 캐시(REQ-BT-008, REQ-BT-014)**: `n_past`를 키로 하는 프로세스 수명
  캐시. DB/파일 영속화 없음. 신규 데이터 적재 시 무효화되어 재계산(REQ-BT-011) —
  data.py의 기존 캐시/`invalidate_cache` 컨벤션과 정합되게 구현.
- **테스트 호환 동적 호출**: 기존 라우트 패턴과 동일하게 `from lotto.web import
  data as wd` 동적 임포트로 monkeypatch 호환성을 유지한다(pages.py/api.py).
- **결정성 주의**: `recommend_by_strategy()`는 내부 random 표본을 사용하므로
  호출마다 결과가 달라질 수 있다. 백테스트 수치는 "이번 분석 세션 기준"임을 UI
  문구로 명확히 한다(재현성 보장은 범위 밖, Exclusions 6).

## Python 3.9 호환성

- `zip(strict=True)` 사용 금지 (Python 3.10+). 필요 시 단순 루프 또는
  `# noqa: B905`로 처리.
- 런타임 위치 타입은 기존 모듈 컨벤션을 따른다(예: `Optional[...]`, `List[int]`).
- 워러스(`:=`) 연산자는 가독성 저해 시 사용하지 않음.

## MX 태그 계획

- `run_backtest`: pages.py와 api.py 두 곳에서 호출되어 fan_in >= 2 →
  `@MX:ANCHOR` 부여(공개 분석 경계 함수). @MX:REASON에 look-ahead 금지 불변식 명시.
- 회차별 통계 재구성 루프: `@MX:WARN` 후보 — "회차마다 prior_draws로 재구성,
  전체 통계 재사용 금지(look-ahead)". @MX:REASON로 사유 명시.
- 적중 계산 헬퍼: `@MX:NOTE`로 "보너스 제외, 6개 메인 번호만 비교" 의도 명시.

## 품질 게이트

- `~/.local/bin/pytest` 전체 스위트 통과 (기준 1174 → 신규 테스트 추가분 포함).
- 신규 함수/타입 커버리지 목표 90%+.
- mypy 통과(신규 테스트 모듈 mypy.ini 등록), ruff clean, 신규 외부 의존성 없음.
- 백테스트 50회차 × 11전략 < 30초(REQ-BT-018) 성능 검증.
- 함수/변수명은 영어, docstring/주석은 한국어.
