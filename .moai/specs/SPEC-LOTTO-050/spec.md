---
id: SPEC-LOTTO-050
version: 0.1.0
status: completed
created: 2026-06-02
updated: 2026-06-05
author: ircp
priority: medium
---

# SPEC-LOTTO-050: 데이터 기반 스마트 추천 전략

## 1. 개요 (Overview)

기존 추천기는 단일 축(빈도/최근/동반/갭 중 하나에 치우친 4-튜플 가중치)을
중심으로 동작하는 10개 전략을 제공한다. 본 SPEC은 추천기 내부에 이미 존재하는
다축 신호를 정규화하여 가중 합산한 **데이터 기반 종합 전략("데이터스마트")**을
하나 추가한다. 단일 축 전략 대비 더 균형 잡힌 고품질 추천을 목표로 한다.

## 2. 레이어링 결정 (Layering Decision)

- [HARD] "데이터스마트" 전략은 **추천기 계층 내부**에서만 구현한다.
- 추천기는 `Statistics`(lotto.analyzer 산출물)를 입력으로 받는다. 원시 `draws`를
  소비하는 웹 분석 함수(lotto/web/data.py: prediction_report, cycle_analysis 등)에
  의존하지 **않는다**. 이는 계층 침범(layering violation)을 피하기 위함이다.
- 따라서 스마트 전략의 "다축"은 `Statistics`/`_strategy_scores`에서 이미 산출 가능한
  신호만으로 구성한다.

## 3. 합성 가중치 설계 (Composite Weight Blend)

"데이터스마트"는 6개 지표를 0~1로 정규화한 뒤 가중 합산한다.

| 축 | 출처 (Statistics 내부) | 가중치 |
|----|------------------------|--------|
| frequency (고빈도) | `frequency.absolute` | 0.22 |
| recency (최근편향) | `recent_pattern.counts` | 0.22 |
| pair/affinity (동반패턴) | `pair_analysis.top_pairs` | 0.18 |
| gap (갭분석, 미출현) | `consecutive_pattern.current_streak` 음수 | 0.18 |
| odd/even balance (홀짝균형) | 빈도 분포의 홀/짝 그룹 사전확률 | 0.10 |
| range balance (번호대균형) | 빈도 분포의 5개 구간 그룹 사전확률 | 0.10 |

- 홀짝/번호대 축은 개별 번호의 속성(홀/짝, 소속 구간)에 대해, 관측 빈도 분포에서
  유도한 그룹 사전확률(group prior)을 부여하여 균형 신호로 사용한다. 외부 draws에
  의존하지 않고 `Statistics`만으로 결정적으로 계산된다.
- 가중치 합 = 0.22+0.22+0.18+0.18+0.10+0.10 = 1.00.
- 픽 로직은 기존 "앙상블" 경로(상위 25개 후보)를 재사용한다.

## 4. EARS 요구사항 (Requirements)

### Ubiquitous

- REQ-SMART-001: 시스템은 항상 "데이터스마트" 전략을 `STRATEGY_LABELS`에 포함한다.
- REQ-SMART-002: 시스템은 항상 "데이터스마트"에 대한 비어있지 않은 한국어 설명을
  `STRATEGY_DESCRIPTIONS`에 제공한다.

### Event-driven

- REQ-SMART-010: `recommend_by_strategy("데이터스마트")`가 호출되면, 시스템은 1~45
  범위의 서로 다른 6개 번호를 오름차순으로 담은 유효한 `Recommendation`을 반환한다.
- REQ-SMART-011: `recommend_by_strategy("데이터스마트")`가 호출되면, 반환 `scores`
  딕셔너리는 추천된 6개 번호에 대한 항목만 가진다.
- REQ-SMART-012: `recommend(count=N)`이 호출되고 N이 전략 수 이상이면, 결과 라벨
  순환에 "데이터스마트"가 1회 이상 포함된다.

### State-driven

- REQ-SMART-020: 동일 `Statistics`로 두 번 호출되는 동안, 시스템은 동일한 6개 번호를
  반환한다(결정적). 기존 전략의 시드 정책을 그대로 따른다.

### Unwanted

- REQ-SMART-030: 시스템은 기존 10개 전략의 가중치/로직/순환 순서를 변경하지 않는다.

### Optional

- REQ-SMART-040: 가능한 경우, "데이터스마트"는 축이 상충하는 입력에서 최소 1개의
  단일 축 전략과 다른 추천 결과를 산출한다(실제 혼합 동작 확인).

## 5. 영향 범위 (Impact)

- `lotto/recommender.py`: STRATEGY_LABELS(+1), STRATEGY_DESCRIPTIONS(+1),
  `_strategy_scores` 스마트 분기 추가, `_pick_set` 앙상블 경로 재사용.
- `lotto/web/templates/recommend.html`: 전략 안내 범례에 배지 1개 추가.
- 기존 테스트 `test_recommender_strategies.py`: 전략 수 10→11 반영을 위해
  순환 검증 테스트를 동적(`len(STRATEGY_LABELS)`)으로 갱신(의도된 변경).
- API(`/api/recommendations`)는 전략명을 동적 처리하므로 변경 없음.
