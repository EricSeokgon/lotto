# SPEC-LOTTO-001: 인수 기준 (Acceptance Criteria)

본 문서는 `SPEC-LOTTO-001`의 완료를 판단하기 위한 Given-When-Then 시나리오, 엣지 케이스, 품질 게이트, Definition of Done을 정의한다. 본 SPEC의 모든 기능 요구사항(REQ-*)은 아래 시나리오 중 최소 하나로 검증된다.

---

## 1. Given-When-Then 시나리오 (정상 동작)

### Scenario 1: 전체 히스토리 데이터 수집 (REQ-COLLECT-02, REQ-COLLECT-03)

**Given** 사용자가 처음으로 시스템을 사용하며 `data/draws.csv` 파일이 존재하지 않는 상태이다.
**And** 동행복권 API가 정상적으로 동작하며 최신 회차가 1,200회차이다.
**When** 사용자가 터미널에서 `python main.py collect --full`을 실행한다.
**Then** 시스템은 회차 1부터 1,200까지의 모든 당첨 번호를 순차적으로 수집한다.
**And** `data/draws.csv` 파일이 생성되고 1,200개의 레코드를 포함한다.
**And** 각 레코드는 `drwNo, date, n1, n2, n3, n4, n5, n6, bonus` 9개 필드를 가진다.
**And** 진행률 바가 표시되며 종료 코드는 0이다.
**And** 인접 요청 간 최소 200ms 간격이 유지된다.

---

### Scenario 2: API 일시 오류 시 자동 재시도 (REQ-COLLECT-04, REQ-COLLECT-05)

**Given** `data/draws.csv`에 회차 1~500이 저장되어 있다.
**And** 동행복권 API의 회차 503 응답이 일시적으로 HTTP 500을 반환한다.
**When** 사용자가 `python main.py collect`를 실행한다.
**Then** 시스템은 회차 501, 502는 정상 수집한다.
**And** 회차 503에 대해 1초 → 2초 → 4초 간격으로 3회 재시도한다.
**And** 3회 재시도 모두 실패하면 회차 503을 스킵하고 경고 로그를 출력한다.
**And** 연속 실패가 5회 미만이므로 후속 회차 수집을 계속 진행한다.
**And** 모든 수집이 끝난 후 실패한 회차 목록을 콘솔에 요약 출력한다.

---

### Scenario 3: 출현 빈도 통계 산출 정확성 (REQ-ANALYZE-02, REQ-ANALYZE-05)

**Given** `data/draws.csv`에 다음 3개 회차 mini-dataset이 존재한다:
- 회차 1: `[1, 2, 3, 4, 5, 6]` bonus=`7`
- 회차 2: `[1, 2, 10, 20, 30, 40]` bonus=`8`
- 회차 3: `[1, 5, 10, 15, 20, 25]` bonus=`9`

**When** 사용자가 `python main.py analyze`를 실행한다.
**Then** `data/stats.json`이 생성된다.
**And** `frequency`에서 번호 `1`의 출현 횟수는 정확히 `3`, 번호 `10`은 `2`, 번호 `7`은 `0` (보너스는 본번호 빈도에 포함되지 않음)이다.
**And** `frequency`의 모든 번호(1~45)에 대해 출현 횟수와 상대 빈도(`count / total_draws`)가 기록된다.
**And** `pair_analysis`에서 상위 20개 동반 출현 쌍이 출현 빈도 내림차순으로 정렬되어 기록된다.
**And** 종료 코드는 0이다.

---

### Scenario 4: 추천 조합 생성 — 형식과 무결성 (REQ-RECOMMEND-01, REQ-RECOMMEND-02, REQ-RECOMMEND-05)

**Given** `data/stats.json`이 정상 생성되어 있다.
**When** 사용자가 `python main.py recommend`를 실행한다.
**Then** 시스템은 정확히 5개의 추천 조합을 출력한다.
**And** 각 조합은 정확히 6개의 정수로 구성된다.
**And** 각 조합의 모든 번호는 1 이상 45 이하의 정수이다.
**And** 한 조합 내 중복 번호는 없다.
**And** 5개 조합 중 완전히 동일한 두 조합은 존재하지 않는다.
**And** 각 조합은 오름차순으로 표시된다.
**And** 각 조합에 5가지 전략 라벨(`고빈도`, `저빈도`, `균형`, `최근편향`, `동반패턴`) 중 하나가 부여된다.
**And** 출력 마지막에 면책 문구 `본 추천은 통계적 참고용이며 당첨을 보장하지 않습니다.`가 표시된다.

---

### Scenario 5: `--count` 옵션으로 추천 개수 제어 (REQ-RECOMMEND-03, REQ-CLI-04)

**Given** `data/stats.json`이 정상 생성되어 있다.
**When** 사용자가 `python main.py recommend --count 10`을 실행한다.
**Then** 정확히 10개의 추천 조합이 출력된다.
**And** 종료 코드는 0이다.

**When** 사용자가 `python main.py recommend --count 0`을 실행한다.
**Then** 시스템은 `--count는 1 이상 20 이하의 정수여야 합니다.` 메시지를 출력한다.
**And** 추천 조합은 생성되지 않는다.
**And** 종료 코드는 2이다.

**When** 사용자가 `python main.py recommend --count 100`을 실행한다.
**Then** 시스템은 동일한 범위 오류 메시지를 출력하고 종료 코드 2로 종료한다.

---

### Scenario 6: 시뮬레이션의 매칭 등급 보고 (REQ-SIMULATE-01, REQ-SIMULATE-02, REQ-SIMULATE-04)

**Given** `data/draws.csv`에 1,000회차 데이터가 저장되어 있다.
**And** `data/stats.json`이 존재한다.
**When** 사용자가 `python main.py simulate --rounds 10`을 실행한다.
**Then** 시스템은 최근 10개 회차(991~1,000) 각각에 대해 다음을 수행한다:
- 회차 R에 대해 회차 1 ~ R-1 데이터만 사용해 5개 추천을 생성한다.
- 회차 R의 실제 당첨 번호와 5개 추천 각각을 비교한다.

**And** 시뮬레이션 종료 후 다음 항목을 포함한 요약표가 콘솔에 출력된다:
- 평가된 회차 수: 10
- 5등(3개 일치) 카운트
- 4등(4개 일치) 카운트
- 3등(5개 일치) 카운트
- 2등(5개 + 보너스 일치) 카운트
- 1등(6개 일치) 카운트
- 전체 hit rate (5등 이상 1회 이상 발생한 회차 비율)

**And** 종료 코드는 0이다.

---

## 2. 추가 시나리오 (엣지 케이스)

### Scenario 7: 데이터 부재 시 명확한 안내 (REQ-ANALYZE-06, REQ-RECOMMEND-06)

**Given** `data/draws.csv` 파일이 존재하지 않는다.
**When** 사용자가 `python main.py analyze`를 실행한다.
**Then** 시스템은 한국어 메시지 `당첨 데이터가 없습니다. 먼저 'collect' 명령을 실행하세요.`를 출력한다.
**And** `data/stats.json`은 생성되지 않는다.
**And** 종료 코드는 1이다.

**Given** `data/stats.json` 파일이 존재하지 않거나 손상되어 있다.
**When** 사용자가 `python main.py recommend`를 실행한다.
**Then** 시스템은 한국어 메시지 `통계 데이터가 없습니다. 먼저 'analyze' 명령을 실행하세요.`를 출력한다.
**And** 종료 코드는 1이다.

---

### Scenario 8: API 전체 장애 상황 처리 (REQ-COLLECT-05, REQ-CLI-05)

**Given** 동행복권 API 서버가 완전히 다운되어 모든 요청이 HTTP 500을 반환한다.
**And** `data/draws.csv`에 회차 1~500이 저장되어 있다.
**When** 사용자가 `python main.py collect`를 실행한다.
**Then** 시스템은 회차 501부터 시작해 각 회차당 3회 재시도를 수행한다.
**And** 회차 501~505 모두(5회 연속)가 재시도 후에도 실패한다.
**And** 시스템은 수집을 중단하고 한국어 에러 메시지 `5회 연속 수집 실패 — 동행복권 API 상태를 확인하세요.`를 출력한다.
**And** `data/draws.csv`의 기존 데이터(회차 1~500)는 손상되지 않고 유지된다.
**And** 종료 코드는 2이다.

---

### Scenario 9: `--recent-window`가 전체 회차 수보다 큰 경우 (REQ-ANALYZE-07)

**Given** `data/draws.csv`에 회차 1~10 (총 10개)만 저장되어 있다.
**When** 사용자가 `python main.py analyze --recent-window 50`을 실행한다.
**Then** 시스템은 경고 메시지 `최근 회차 윈도우(50)가 전체 회차 수(10)보다 큽니다. 전체 회차를 사용합니다.`를 출력한다.
**And** `recent_pattern`은 전체 10개 회차를 대상으로 계산된다.
**And** 시스템은 정상 종료한다 (종료 코드 0).

---

### Scenario 10: 시뮬레이션의 look-ahead bias 방지 (REQ-SIMULATE-05)

**Given** `data/draws.csv`에 1,000회차 데이터가 저장되어 있다.
**When** 단위 테스트가 `LottoSimulator.evaluate_round(500)`을 호출한다.
**Then** `Analyzer`가 회차 500의 데이터를 입력으로 받지 않음이 검증된다.
**And** `Recommender`가 사용하는 `stats`는 회차 1~499 데이터만 기반으로 한다.
**And** 만약 회차 500의 데이터가 추천 생성에 누설되면 테스트는 명시적으로 실패한다.

---

### Scenario 11: 커스텀 가중치 옵션 (REQ-RECOMMEND-04)

**Given** `data/stats.json`이 존재한다.
**When** 사용자가 `python main.py recommend --weights 0.5,0.3,0.2,0.0`을 실행한다.
**Then** 시스템은 제공된 가중치(w_freq=0.5, w_recent=0.3, w_pair=0.2, w_consec=0.0)를 사용해 추천을 생성한다.
**And** 5개 추천 조합이 정상 출력된다.

**When** 사용자가 `python main.py recommend --weights -0.1,0.5,0.3,0.3`을 실행한다.
**Then** 시스템은 `가중치는 모두 0 이상이어야 합니다.` 에러를 출력한다.
**And** 종료 코드는 2이다.

**When** 사용자가 `python main.py recommend --weights 0,0,0,0`을 실행한다.
**Then** 시스템은 `가중치 합이 0보다 커야 합니다.` 에러를 출력한다.
**And** 종료 코드는 2이다.

---

### Scenario 12: 한국어 도움말 출력 (REQ-CLI-02)

**Given** 시스템이 정상 설치되어 있다.
**When** 사용자가 `python main.py --help`를 실행한다.
**Then** 4개 서브커맨드(`collect`, `analyze`, `recommend`, `simulate`)와 한국어 설명이 표시된다.

**When** 사용자가 `python main.py recommend --help`를 실행한다.
**Then** `--count`, `--weights` 등 옵션 설명이 한국어로 표시된다.
**And** 사용 예시가 포함된다.

---

## 3. 품질 게이트 (Quality Gates)

`/moai run SPEC-LOTTO-001` 실행 시 다음 항목이 모두 통과해야 SPEC을 완료로 간주한다.

### 3.1 자동화 검증

- [ ] `pytest tests/ -v` — 전체 테스트 100% 통과
- [ ] `pytest --cov=lotto --cov=main --cov-report=term-missing` — 커버리지 ≥ 85%
- [ ] `ruff check .` — 0 오류
- [ ] `ruff format --check .` — 0 변경 필요
- [ ] `mypy --strict lotto/ main.py` — 0 오류
- [ ] 성능 벤치마크: 1,200회차 `analyze` 5초 이내, 5세트 `recommend` 2초 이내

### 3.2 TRUST 5 검증

| 차원 | 기준 |
|------|------|
| Tested | 커버리지 85%+, 모든 EARS 요구사항이 최소 하나의 자동 테스트로 검증됨 |
| Readable | 모든 공개 함수에 한국어/영어 docstring, 명명 규칙 일관성, ruff/mypy 통과 |
| Unified | 코드 스타일 통일(`ruff format`), 데이터 형식 일관성(CSV/JSON 스키마 명세 준수) |
| Secured | 사용자 입력 범위 검증, API 응답 검증(`returnValue == "success"`), 비밀정보 없음 |
| Trackable | 모든 커밋이 Conventional Commits 준수, SPEC ID 참조(`SPEC-LOTTO-001`), HISTORY 갱신 |

### 3.3 수동 검증

- [ ] 모든 추천 출력 하단에 면책 문구 표시 확인
- [ ] 한국어 메시지의 자연스러움 및 오타 검토
- [ ] `data/` 디렉토리가 `.gitignore`에 등록되어 사용자 데이터가 커밋되지 않음
- [ ] `README.md`에 4개 명령의 사용 예시 포함

---

## 4. Definition of Done

본 SPEC은 다음 조건을 **모두** 만족할 때 완료로 간주한다.

1. [ ] `spec.md`의 모든 REQ-* 요구사항이 구현되었다.
2. [ ] 본 `acceptance.md`의 Scenario 1~12 모두가 자동 또는 수동 테스트로 통과되었다.
3. [ ] `plan.md`의 Phase 1~6 모든 산출물이 생성되었으며 각 Phase 품질 게이트를 통과했다.
4. [ ] 4개 CLI 명령 (`collect`, `analyze`, `recommend`, `simulate`) 모두 종단 간 동작이 확인되었다.
5. [ ] 제외 범위(Exclusions) 항목이 구현에 포함되지 않았음을 코드 리뷰로 확인했다 (특히 자동 구매, GUI, 외부 DB 부재).
6. [ ] `README.md`에 설치 방법, 사용법, 면책 사항이 한국어로 명시되었다.
7. [ ] Git 작업 트리가 깨끗하며, 모든 변경이 `feat:` / `test:` / `docs:` 커밋으로 분리되어 푸시되었다.
8. [ ] 사용자(`ircp`)가 인수 시연을 수락했다.

---

## References

- 상세 요구사항: `spec.md`
- 구현 계획: `plan.md`
- 압축 SPEC (run 단계용): `spec-compact.md`
