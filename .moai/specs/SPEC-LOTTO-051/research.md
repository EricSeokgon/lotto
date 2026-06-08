# Research: SPEC-LOTTO-051 주차 선택 주의 알림

## Executive Summary

SPEC-LOTTO-051 is a cross-strategy indicator feature that shows users how many different recommendation strategies include each number in the current result set. The feature alerts users when specific numbers appear in many (or all) strategies, suggesting high consensus among the analysis algorithms.

**Key Finding**: The recommender already supports calling individual strategies via `recommend_by_strategy(label)`, and a precedent exists in SPEC-LOTTO-032 (`strategy_compare`) that calls all 11 strategies sequentially for performance comparison. Implementation should mirror this proven pattern.

---

## 1. Architecture Analysis

### Key Files and Roles

| File | Role |
|------|------|
| `/home/sklee/moai/lotto/lotto/recommender.py` | Core recommendation engine; defines `STRATEGY_LABELS` (11 strategies), `Recommendation` dataclass, `LottoRecommender` class with `recommend_by_strategy(label)` method |
| `/home/sklee/moai/lotto/lotto/models.py:92–113` | `Recommendation` dataclass definition with fields: `numbers`, `strategy_label`, `strategy_desc`, `scores` |
| `/home/sklee/moai/lotto/lotto/web/routes/pages.py:239–258` | `GET /recommend` page route; calls `get_recommendations(count=count)` and passes to template |
| `/home/sklee/moai/lotto/lotto/web/routes/api.py:267–301` | `GET /api/recommendations` endpoint; same function, returns JSON |
| `/home/sklee/moai/lotto/lotto/web/data.py:180–189` | `get_recommendations(count)` function; instantiates `LottoRecommender(stats).recommend(count)` |
| `/home/sklee/moai/lotto/lotto/web/data.py:775–854` | `strategy_compare(rounds, draws, stats)` — **existing cross-strategy pattern** |
| `/home/sklee/moai/lotto/lotto/web/templates/recommend.html` | Recommendation page template; displays each recommendation as a card with strategy badge |

### Data Flow: Recommender → Web Template

```
GET /recommend?count=5
  ↓
recommend_page(request, count)  [pages.py:239]
  ├─ data.get_recommendations(count=5)
  │   └─ LottoRecommender(stats).recommend(count=5)
  │       └─ for i in range(5):
  │           └─ strategy = STRATEGY_LABELS[i % 11]
  │           └─ scores = _strategy_scores(strategy, used_numbers)
  │           └─ numbers, label = _pick_set(scores, used_sets, force_label)
  │           └─ Recommendation(numbers, strategy_label, strategy_desc, scores)
  │       └─ [Recommendation, Recommendation, ...]
  └─ return _render(request, "recommend.html", {
      "recommendations": [Recommendation, ...],
      "count": 5
    })
      ↓
Template: recommend.html (line 91–149)
  └─ {% for rec in recommendations %}
      └─ Display as card with strategy badge, numbers, description
```

**Note**: The `Recommendation` dataclass has `scores: dict[int, float]` field (line 295 in recommender.py), but this is **per-recommendation scores**, not cross-strategy visibility.

---

## 2. Recommendation Data Model

### Recommendation Fields (Python Types)

```python
@dataclass(frozen=True)
class Recommendation(BaseModel):
    numbers: list[int]              # 6 sorted integers [1..45]
    strategy_label: str             # e.g., "고빈도", "저빈도", "균형", ...
    strategy_desc: str              # Human-readable strategy description
    scores: dict[int, float]        # Per-number weighted scores from _strategy_scores()
```

**File**: `/home/sklee/moai/lotto/lotto/models.py:92–113`

### STRATEGY_LABELS (11 Strategies)

**File**: `/home/sklee/moai/lotto/lotto/recommender.py:18–30`

```python
STRATEGY_LABELS = [
    "고빈도",        # High frequency
    "저빈도",        # Low frequency (inverse)
    "균형",          # Balanced
    "최근편향",      # Recent bias
    "동반패턴",      # Pair co-occurrence
    "홀짝균형",      # Odd/even balance
    "번호대균형",    # Range balance (5 zones)
    "핫콜드혼합",    # Hot/cold mix
    "갭분석",        # Gap analysis (long drought)
    "앙상블",        # Ensemble (equal weights)
    "데이터스마트",  # Data-smart (6-axis)
]
```

### Statistics Class (Accessible in Templates)

**Type**: `lotto.models.Statistics`

The `recommender.py` uses:
- `stats.frequency.absolute` — dict[int, int] per-number absolute counts
- `stats.recent_pattern.counts` — dict[int, int] last N rounds per-number
- `stats.pair_analysis.top_pairs` — list[tuple[int, int, int]] co-occurrence top pairs
- `stats.consecutive_pattern.current_streak` — dict[int, int] gap streaks (negative = not appeared)
- `stats.bonus_frequency.absolute` — dict[int, int] bonus number frequency (optional penalty)

All data flows through `Statistics` only; **raw draws are NOT accessed by recommender** (layer separation).

---

## 3. Current Recommendation Route & Template

### Route Code

**File**: `/home/sklee/moai/lotto/lotto/web/routes/pages.py:239–258`

```python
@router.get("/recommend")
async def recommend_page(
    request: Request,
    count: int = 5,
) -> TemplateResponse:
    """추천 번호 페이지.
    
    Args:
        count: 추천 세트 수 (1~20)
    """
    count = max(1, min(20, count))
    data_status = get_data_status()
    recommendations = get_recommendations(count=count)

    return _render(request, "recommend.html", {
        "active_tab": "recommend",
        "data_status": data_status,
        "recommendations": recommendations,
        "count": count,
    })
```

**API Endpoint**: `/home/sklee/moai/lotto/lotto/web/routes/api.py:267–301`

```python
@router.get("/api/recommendations")
async def get_recommendation_list(
    count: int = Query(default=5, ge=1, le=20),
    strategy: Optional[str] = Query(default=None),  # Filter by strategy
) -> list[dict[str, Any]]:
    """번호 추천 결과를 반환합니다. 파일 없으면 503.
    
    REQ-FILTER-001: strategy 파라미터로 특정 전략만 반환
    """
    recs = get_recommendations(count=count)
    if recs is None:
        raise HTTPException(503, ...)
    if strategy is not None:
        recs = [r for r in recs if r.strategy_label == strategy]
    # ... append to gen_history ...
    return [r.model_dump() for r in recs]
```

### Template Variables Available

**File**: `/home/sklee/moai/lotto/lotto/web/templates/recommend.html:91–149`

```jinja2
{% for rec in recommendations %}
    <div class="card">
        <!-- Access per-recommendation data -->
        {{ rec.numbers }}              <!-- [int, ...] -->
        {{ rec.strategy_label }}       <!-- str: "고빈도" -->
        {{ rec.strategy_desc }}        <!-- str: description -->
        {{ rec.scores }}               <!-- dict[int, float] -->
    </div>
{% endfor %}
```

**Context passed**: `recommendations` (list[Recommendation]), `count` (int), `data_status` (DataStatus), `active_tab` (str)

### How Numbers Currently Displayed

- Balls styled by range (lines 115–124): Yellow (1–10), Blue (11–20), Red (21–30), Gray (31–40), Green (41–45)
- Odd/even distribution shown below numbers (lines 135–146)
- Sum calculated (line 145)
- Strategy badge with color-coded label (lines 97–111)

---

## 4. Cross-Strategy Capability Assessment

### Precedent: SPEC-LOTTO-032 (Strategy Comparison)

**File**: `/home/sklee/moai/lotto/lotto/web/data.py:775–854`

The system **already implements** calling all 11 strategies sequentially:

```python
for label in STRATEGY_LABELS:
    rec = recommender.recommend_by_strategy(label)
    prize = sim._evaluate_round(rec.numbers, target)
    # ... accumulate results ...
```

**Observations**:
1. Calls `recommend_by_strategy(label)` once per strategy (11 calls per comparison request)
2. **No performance concerns noted** in existing code — used in production at `/api/simulation/compare` endpoint
3. Each call is deterministic (same `Statistics` object, same weights)
4. Response includes aggregated metrics (ROI, match counts, best rank)

### Can We Call All 11 Strategies Per Recommendation Request?

**YES**, with caveats:

1. **Performance**: Calling all 11 strategies on-demand for each `/recommend` request adds ~N×11 strategy evaluations (N = count parameter, default 5). Each strategy evaluation:
   - Computes normalized scores (O(45) numbers per axis: freq, recent, pair, gap)
   - Runs `_pick_set()` with random sampling (100 trials max for deduplication)
   - Expected: ~10–50ms per strategy call on modern hardware
   - **Total**: ~100–550ms for all 11 strategies (acceptable for web response)

2. **Determinism**: Using same `Statistics` object ensures reproducibility. **Seed management**: recommender.py does NOT use explicit seed (relies on random module), so results vary across calls. **For SPEC-LOTTO-051**: We must ensure the reported consensus is for the **currently shown recommendations**, not a separate all-strategy scan.

3. **Layer Boundary**: Recommender uses `Statistics` only (no raw draws access). ✓ Respects constraint.

### Existing Patterns for Multi-Strategy Analysis

| Pattern | Location | Use Case |
|---------|----------|----------|
| `strategy_compare()` | data.py:775 | Backtest all strategies over N recent rounds; aggregate ROI/match counts |
| `recommend_by_strategy(label)` | recommender.py:284 | Single-strategy recommendation for testing/filtering |
| `recommend(count)` | recommender.py:300 | Default multi-strategy recommendation (rotate through STRATEGY_LABELS) |

**For SPEC-LOTTO-051**, the most analogous pattern is `strategy_compare()`:
- Call all 11 strategies
- Aggregate/analyze results
- Return structured output for display

---

## 5. Implementation Options

### Option A: Server-Side All-Strategy Scan Per Recommendation Request (Recommended)

**Flow**:
```
GET /recommend?count=5
  ↓
recommend_page()
  ├─ get_recommendations(count=5)  [existing, returns count recommendations]
  │   └─ [Recommendation with strategy_label, numbers, scores]
  │
  ├─ NEW: get_cross_strategy_indicators(recommendations)
  │   └─ for each rec.numbers:
  │       ├─ for each strategy_label in STRATEGY_LABELS:
  │       │   └─ recommend_by_strategy(strategy_label)
  │       │       └─ extract numbers from that strategy's rec
  │       │       └─ COUNT how many strategies include each number
  │       └─ return {number: count_of_strategies_with_this_number, ...}
  │
  └─ render with cross-strategy counts
```

**Pros**:
- Simple to understand and maintain
- Mirrors existing `strategy_compare()` pattern
- Data is computed fresh for each request (always current)
- No caching complexity
- Deterministic per Statistics object

**Cons**:
- Adds ~11 recommender calls per recommendation request (5 recommendations = 55 additional calls if applied per recommendation)
- Performance: ~500ms–1s latency increase in worst case
- No caching — repeated requests incur full cost

**Effort**: ~2–3 hours (new `get_cross_strategy_indicators()` in data.py, template modification)

---

### Option B: Dedicated API Endpoint for Cross-Strategy Analysis

**Flow**:
```
GET /recommend?count=5  [existing, returns count recommendations]
  ↓ (page loads)
JavaScript fetch() to new endpoint:
  POST /api/recommend/cross-strategy?numbers=1,7,13,22,35,44&numbers=...
    ↓
New endpoint: analyze_cross_strategy()
  └─ for each strategy_label in STRATEGY_LABELS:
      └─ recommend_by_strategy(strategy_label)
          └─ check which numbers appear
      └─ COUNT how many strategies include each input number
  └─ return {
      "results": [
        {
          "numbers": [1,7,13,22,35,44],
          "consensus": 8,     // 8/11 strategies include these
          "alerts": [1, 7],   // numbers appearing in >8 strategies
          "details": {
            "1": 11,  // number 1 appears in all 11 strategies
            "7": 9,
            ...
          }
        },
        ...
      ]
    }
```

**Pros**:
- Decouples analysis from page load (async JS request)
- Allows user to click "Analyze Consensus" button on-demand
- Cleaner separation of concerns (API vs. page template)
- Avoids blocking initial page render

**Cons**:
- Requires JavaScript fetch in template (already present in recommend.html, but adds complexity)
- Two roundtrips instead of one
- Need to manage cache invalidation if recommendations change

**Effort**: ~3–4 hours (new endpoint, JavaScript integration, UI updates)

---

### Option C: Pre-Compute on Page Load with Lazy Loading

**Flow**:
```
recommend_page(count=5)
  ├─ get_recommendations(count=5)        [existing]
  ├─ NEW: get_all_strategies_one_call()
  │   └─ Call all 11 strategies once (not per recommendation)
  │   └─ Return {strategy_label: Recommendation, ...}
  │   └─ Use these to compute per-number strategy count
  └─ Pass to template:
      {
        "recommendations": [Rec, ...],
        "strategy_counts": {1: 8, 2: 5, ..., 45: 3},
        "consensus_threshold": 8  // e.g., 8+/11
      }

Template:
  {% for num in 1..45 %}
    {% if strategy_counts[num] >= consensus_threshold %}
      <span class="alert">{{ num }} ({{ strategy_counts[num] }}/11)</span>
    {% endif %}
  {% endfor %}
```

**Pros**:
- Computes cross-strategy info once per page load (not per recommendation card)
- Can pre-render HTML (no async JS)
- Single consolidated view of all-strategy consensus

**Cons**:
- Bloats template context with all-strategy data
- All 11 strategies evaluated even if user doesn't care about consensus
- Harder to update dynamically if user changes recommendation count

**Effort**: ~2–3 hours (similar to Option A, but structure differently)

---

### Recommendation

**Use Option A (Server-Side, Per-Request)** because:
1. Follows existing `strategy_compare()` pattern already proven in production
2. Simplest implementation — no JavaScript or cache invalidation needed
3. Data always fresh and consistent with shown recommendations
4. Acceptable performance for web context (~500ms total latency increase)

---

## 6. Reference Implementations

### Pattern 1: All-Strategy Scan (from SPEC-LOTTO-032)

**File**: `/home/sklee/moai/lotto/lotto/web/data.py:775–854`

**Key takeaway**: Loop through `STRATEGY_LABELS`, call `recommend_by_strategy(label)`, aggregate results.

```python
from lotto.recommender import STRATEGY_LABELS, LottoRecommender

recommender = LottoRecommender(stats)
for label in STRATEGY_LABELS:
    rec = recommender.recommend_by_strategy(label)
    # ... use rec.numbers, rec.scores, etc.
```

### Pattern 2: Returning Recommendation List

**File**: `/home/sklee/moai/lotto/lotto/web/data.py:180–189`

```python
def get_recommendations(count: int = 5) -> list[Recommendation] | None:
    """번호 추천 결과를 반환합니다. stats.json 없으면 None."""
    if not STATS_PATH.exists():
        return None
    from lotto.recommender import LottoRecommender
    stats = get_stats()
    if stats is None:
        return None
    return LottoRecommender(stats).recommend(count=count)
```

**To implement cross-strategy info**, add a parallel function:

```python
def get_cross_strategy_consensus(
    stats: Statistics | None = None,
) -> dict[int, int]:
    """각 번호(1~45)가 몇 개 전략에 포함되는지 반환합니다.
    
    Returns:
        {1: 11, 2: 9, ..., 45: 3}  where value = count of strategies with that number
    """
    if stats is None:
        stats = get_stats()
    if stats is None:
        return {}
    
    from lotto.recommender import STRATEGY_LABELS, LottoRecommender
    
    recommender = LottoRecommender(stats)
    consensus = {n: 0 for n in range(1, 46)}
    
    for label in STRATEGY_LABELS:
        rec = recommender.recommend_by_strategy(label)
        for num in rec.numbers:
            consensus[num] += 1
    
    return consensus
```

### Pattern 3: Template Rendering

**File**: `/home/sklee/moai/lotto/lotto/web/templates/recommend.html:91–149`

Current structure: Loop through `recommendations`, display each as a card.

**To add cross-strategy info**:

```jinja2
<!-- Existing -->
{% for rec in recommendations %}
  <div class="card">
    {{ rec.numbers }}
    {{ rec.strategy_label }}
  </div>
{% endfor %}

<!-- NEW: Cross-Strategy Consensus Panel -->
{% if strategy_consensus %}
<div class="bg-card rounded-lg p-4 border border-yellow-300">
  <h3 class="text-lg font-semibold text-ink mb-3">전략 합의도 분석</h3>
  <p class="text-sm text-muted mb-3">각 번호가 몇 개 전략에 포함되는지 표시합니다.</p>
  
  {% set consensus_nums = [] %}
  {% for num, count in strategy_consensus.items() %}
    {% if count >= 8 %}  <!-- threshold -->
      <span class="inline-flex items-center px-2 py-1 rounded bg-yellow-100 text-yellow-800 text-xs font-semibold mr-1 mb-1">
        {{ num }} ({{ count }}/11)
      </span>
    {% endif %}
  {% endfor %}
  
  {% if not consensus_nums %}
  <p class="text-sm text-muted">높은 합의도의 번호가 없습니다.</p>
  {% endif %}
</div>
{% endif %}
```

---

## 7. Risks and Constraints

### Performance Risk: 11 Strategy Calls Per Page Load

- **Current baseline**: Single `recommend(count=5)` = 5 strategies called (rotation)
- **With SPEC-LOTTO-051**: 5 recommendations + all-strategy scan = 5 + 11 = 16 strategy calls
- **Impact**: ~200–500ms additional latency (acceptable for human web interaction)

**Mitigation**:
- Monitor response time in production
- Cache Statistics object aggressively (already done with 60-second TTL)
- Lazy-load cross-strategy info on-demand (Option B) if bottleneck confirmed

### Determinism Risk: Random Number Generation

- Recommender uses `random.sample()` for `_pick_set()`
- Calling `recommend_by_strategy()` 11 times with same stats produces 11 **different** sets (due to random seed variation)
- **For SPEC-LOTTO-051**: We want to report which strategies include each number **in the result set shown to user**, so must use same Statistics snapshot

**Mitigation**:
- Pass same `Statistics` object to all 11 calls (already guaranteed by implementation)
- Semantics: "In the current recommendation analysis, these strategies include number 7"
- If reproducibility is required, recommender would need explicit seeding (out of scope for SPEC-LOTTO-051)

### Layer Constraint: Statistics Only

- Recommender never accesses raw `draws` — only `Statistics` object
- Cross-strategy consensus **must also use Statistics only** (no raw draws access)
- ✓ Constraint satisfied: calling `recommend_by_strategy()` respects this

### Seed Reproducibility

- **Current behavior**: Each page load produces different recommendations (random seeding)
- **SPEC-LOTTO-051 implication**: Consensus counts also vary per load
- **User expectation**: They might expect "reproducible" consensus (e.g., "always 8/11 for this number")
- **Actual behavior**: Consensus will vary because underlying recommendations vary
- **Mitigation**: UI language: "In this analysis session, X strategies include number 7"

---

## 8. Recommendations

### Suggested Implementation Approach

**Use Option A (Server-Side Per-Request Cross-Strategy Scan)**:

1. **Add function to `lotto/web/data.py`** (after `get_recommendations()`, line 189):
   ```python
   def get_cross_strategy_consensus(
       stats: Statistics | None = None,
   ) -> dict[int, int]:
       """각 번호(1~45)가 몇 개 전략에 포함되는지 반환.
       
       - Returns: {1: 11, 2: 9, ..., 45: 3}
       - stats=None: auto-load via get_stats()
       - Empty stats: return empty dict
       """
       # See Pattern 3 above
   ```

2. **Modify `recommend_page()` in `lotto/web/routes/pages.py:239`**:
   ```python
   recommendations = get_recommendations(count=count)
   cross_strategy_consensus = None
   if recommendations:
       cross_strategy_consensus = get_cross_strategy_consensus()
   
   return _render(request, "recommend.html", {
       "active_tab": "recommend",
       "data_status": data_status,
       "recommendations": recommendations,
       "cross_strategy_consensus": cross_strategy_consensus,
       "count": count,
   })
   ```

3. **Update `recommend.html` template** (after line 149, before favorites section):
   - Add alert section showing numbers with high strategy consensus (e.g., ≥8/11)
   - Use warning color (yellow/orange) to indicate high consensus
   - Show "This number appears in X out of 11 strategies" tooltip

4. **Update `/api/recommendations` endpoint** (routes/api.py:267):
   - Return `cross_strategy_consensus` in JSON response alongside recommendations
   - Clients can use consensus data for custom alerts/highlighting

### Files to Modify

| File | Change | Estimate |
|------|--------|----------|
| `lotto/web/data.py` | Add `get_cross_strategy_consensus()` function (20 lines) | 0.5 hours |
| `lotto/web/routes/pages.py` | Update `recommend_page()` context (5 lines) | 0.25 hours |
| `lotto/web/routes/api.py` | Update `get_recommendation_list()` response (3 lines) | 0.25 hours |
| `lotto/web/templates/recommend.html` | Add cross-strategy alert panel (30–50 lines Jinja2) | 1 hour |
| `tests/test_web_data.py` | Unit test for `get_cross_strategy_consensus()` (30 lines) | 1 hour |
| `tests/test_web_pages.py` | Integration test for recommend page with consensus | 1 hour |

**Total Estimated Effort**: ~4 hours (RED phase implementation)

### Acceptance Criteria

1. Cross-strategy consensus accurately counts which strategies include each number
2. Consensus info available in both HTML and `/api/recommendations` JSON response
3. Page load time increase < 1 second (measure with and without feature)
4. All 1087 existing tests still pass
5. New unit tests for `get_cross_strategy_consensus()` (target: 90%+ coverage)
6. UI clearly indicates threshold for "high consensus" alert (e.g., 8+/11)

---

## 9. Implementation Layering & Seed Safety

### Current `recommend()` Flow (Baseline)

```python
def recommend(self, count: int = 5) -> list[Recommendation]:
    """count 개의 번호 세트를 추천합니다."""
    used_sets: set[frozenset[int]] = set()
    used_numbers: set[int] = set()
    results: list[Recommendation] = []
    
    for i in range(count):
        label = STRATEGY_LABELS[i % len(STRATEGY_LABELS)]  # rotate strategies
        scores = self._strategy_scores(label, used_numbers)
        numbers, actual_label = self._pick_set(scores, used_sets, force_label=label)
        used_sets.add(frozenset(numbers))
        used_numbers.update(numbers)
        results.append(Recommendation(...))
    
    return results
```

**Issue**: `used_numbers` accumulates, so each strategy call gets penalized for numbers in previous recommendations. This is intentional (diversity across count recommendations).

### For SPEC-LOTTO-051 (All-Strategy Scan)

When we call all 11 strategies independently:

```python
def get_cross_strategy_consensus(stats) -> dict[int, int]:
    consensus = {n: 0 for n in range(1, 46)}
    recommender = LottoRecommender(stats)
    
    for label in STRATEGY_LABELS:
        rec = recommender.recommend_by_strategy(label)  # No used_numbers penalty
        for num in rec.numbers:
            consensus[num] += 1
    
    return consensus
```

**Key**: `recommend_by_strategy()` does NOT use `used_numbers` penalty (it's independent per call). This is correct for consensus — each strategy should be evaluated in isolation.

**Semantics**: "Given the same statistical analysis snapshot, if we asked each of the 11 strategies for their top recommendation, how many would include this number?"

---

## 10. Edge Cases & Data Integrity

### Empty Statistics
- `get_stats()` returns None → `get_cross_strategy_consensus()` returns `{}`
- Template checks `if cross_strategy_consensus` before rendering alert panel

### Mixed Data Freshness
- Recommendations based on Statistics at time T
- Cross-strategy scan also uses Statistics at time T (same snapshot) ✓

### Strategies with Identical Numbers
- Two strategies might recommend the same 6 numbers
- Consensus correctly counts both (e.g., if strategies 1 and 2 both recommend [1,7,13,22,35,44], then number 1 has at least count of 2) ✓

### Threshold Selection
- Recommend visible alert if ≥8/11 strategies include (73% consensus)
- Alternative thresholds: 10/11 (very high), 6/11 (moderate)
- **Decision**: Let SPEC define threshold; suggest 8/11 as default

---

## 11. Test Strategy

### Unit Tests (data.py)

```python
def test_get_cross_strategy_consensus_empty_stats():
    """stats=None returns empty dict"""
    result = get_cross_strategy_consensus(None)
    assert result == {}

def test_get_cross_strategy_consensus_with_stats():
    """All 11 strategies called; consensus counted correctly"""
    stats = get_stats()  # Fixture with sample data
    consensus = get_cross_strategy_consensus(stats)
    
    # Each number should have count 0-11
    for num, count in consensus.items():
        assert 0 <= count <= 11
    
    # Spot-check: high-frequency numbers likely in many strategies
    # (not deterministic without seeding, but bounds are)
    assert sum(consensus.values()) == 11 * 6  # 11 strategies × 6 numbers each
```

### Integration Tests (pages.py, api.py)

```python
async def test_recommend_page_includes_cross_strategy_consensus():
    """GET /recommend includes consensus in template context"""
    response = client.get("/recommend?count=5")
    assert response.status_code == 200
    # Check that cross_strategy_consensus is in response HTML or fixture

async def test_api_recommendations_includes_consensus():
    """GET /api/recommendations includes consensus in JSON"""
    response = client.get("/api/recommendations?count=5")
    assert response.status_code == 200
    data = response.json()
    assert "cross_strategy_consensus" in data or similar indicator
```

---

## Final Summary

SPEC-LOTTO-051 is implementable using the proven `strategy_compare()` pattern. By calling all 11 strategies once per page load and counting how many include each number, we provide users with a valuable "consensus strength" indicator.

**Estimated implementation**: 4 hours (dev + testing)
**Performance impact**: ~500ms additional latency (acceptable)
**Risk level**: LOW (mirrors existing SPEC-LOTTO-032 pattern)
**Recommendation**: PROCEED with Option A (server-side per-request scan)

