---
id: SPEC-LOTTO-048
version: 0.1.0
status: Planned
created: 2026-06-02
updated: 2026-06-02
author: ircp
priority: medium
---

# SPEC-LOTTO-048 구현 계획

## 접근 방식

기존 즐겨찾기/예약 영속화 패턴을 그대로 차용하여 신규 저장소를 추가한다.
TDD(RED → GREEN → REFACTOR) 사이클로 진행한다.

## 변경 파일

1. **lotto/web/data.py** (영속화 레이어)
   - `_SIM_HISTORY_PATH = settings.data_dir / "sim_history.json"`, `_SIM_HISTORY_MAX = 50`
   - `list_simulation_results()` — 최신순 반환 (저장은 추가 순서, 반환은 reversed)
   - `_write_sim_history()` — tempfile + os.replace 원자적 쓰기
   - `save_simulation_result(entry)` — id(8자리 hex)/created_at(UTC ISO) 부여, 50건 상한
   - `get_simulation_result(result_id)` — 단건 조회 (없으면 None)
   - `delete_simulation_result(result_id)` — 삭제 (성공 True / 없음 False)

2. **lotto/web/routes/api.py** (API)
   - `SimHistoryRequest` Pydantic 모델 (label 검증: trim 후 비어 있으면 422, 최대 50자)
   - `POST /api/simulation-history` → 200 + 저장 엔트리
   - `GET /api/simulation-history` → 200 + 최신순 배열
   - `DELETE /api/simulation-history/{result_id}` → 200 {deleted} / 404

3. **lotto/web/routes/pages.py** (페이지)
   - `GET /simulation-history` → `sim_history.html`, `active_tab="sim_history"`

4. **lotto/web/templates/sim_history.html** (신규 템플릿)
   - 최신순 카드(라벨/전략/번호/등수 분포/ROI), 삭제(JS fetch DELETE), 비교(2건 이상 선택), 빈 상태

5. **lotto/web/templates/base.html** (네비)
   - "시뮬 기록" → `/simulation-history` 3곳(데스크톱 목록, 모바일 활성 라벨, 모바일 목록)

6. **mypy.ini** — 테스트 모듈 3건 추가

## 테스트 (17건)

- `tests/test_sim_history.py` (8): save/list newest-first/empty/delete true·false/get·missing/round-trip
- `tests/test_api_sim_history.py` (5): POST 200/POST empty 422/GET list/DELETE 200/DELETE 404
- `tests/test_sim_history_page.py` (4): 페이지 200/저장 표시/빈 상태/인덱스 네비 링크

## 품질 게이트

- Python 3.9 호환: Pydantic 위치에 `Optional[X]`/`List[X]`/`Dict[X, Y]` (typing)
- mypy strict 0 오류 유지, ruff clean, 신규 외부 의존성 없음
- 테스트 저장 경로 격리(monkeypatch `_SIM_HISTORY_PATH`)
