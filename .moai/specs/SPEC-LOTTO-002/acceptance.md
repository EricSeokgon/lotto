---
id: SPEC-LOTTO-002
document: acceptance
version: "0.1.0"
created: "2026-05-21"
updated: "2026-05-21"
---

# SPEC-LOTTO-002 인수 기준 (acceptance.md)

> 본 문서는 SPEC-LOTTO-002가 "completed"로 전환되기 위해 충족해야 하는 인수 기준을 Given-When-Then 시나리오로 기술한다. 모든 시나리오는 자동화된 테스트 또는 명령으로 검증 가능해야 한다.

---

## 1. 설정 외부화 인수 시나리오 (REQ-CFG 계열)

### AC-CFG-001: 모듈 진입점 존재

**Given** SPEC-LOTTO-002 구현이 완료된 상태에서
**When** 사용자가 `python -c "import lotto.config as c; print(c.LOTTO_API_URL, c.LOTTO_DATA_DIR, c.LOTTO_RECOMMENDER_WEIGHTS, c.LOTTO_SCRAPER_BASE_URL, c.LOTTO_SCRAPER_WIN_URL, c.LOTTO_CHECKPOINT_INTERVAL)"`를 실행하면
**Then** 6개 모든 상수가 출력되며 어떠한 예외도 발생하지 않는다.

> 대응 요구사항: REQ-CFG-001, REQ-CFG-004

---

### AC-CFG-002: 환경 변수 우선순위

**Given** `LOTTO_API_URL=https://example.test/api`가 환경에 설정된 상태에서
**When** `lotto.config`를 임포트한 후 `lotto.config.LOTTO_API_URL`을 읽으면
**Then** 값은 `https://example.test/api`이며 기본값(`https://www.dhlottery.co.kr/...`)이 아니다.

> 대응 요구사항: REQ-CFG-002 (1순위: 환경 변수)

---

### AC-CFG-003: `.env` 파일 폴백

**Given** 환경 변수에 `LOTTO_DATA_DIR`이 설정되지 않았고, 프로젝트 루트에 `.env` 파일이 존재하며 `LOTTO_DATA_DIR=/tmp/lotto-test`가 적혀 있고, `python-dotenv`가 설치된 상태에서
**When** `lotto.config`를 임포트한 후 `lotto.config.LOTTO_DATA_DIR`을 읽으면
**Then** 값은 `/tmp/lotto-test`이다.

> 대응 요구사항: REQ-CFG-002 (2순위), REQ-CFG-003

---

### AC-CFG-004: 기본값 폴백

**Given** 환경 변수에 어떤 `LOTTO_*` 키도 설정되지 않았고, `.env` 파일도 존재하지 않는 상태에서
**When** `lotto.config`의 6개 상수를 모두 읽으면
**Then** 각 값은 다음 기본값과 정확히 일치한다:
- `LOTTO_API_URL` == `https://www.dhlottery.co.kr/common.do?method=getLottoNumber`
- `LOTTO_DATA_DIR` == `data` (또는 `Path("data")`)
- `LOTTO_RECOMMENDER_WEIGHTS` == `(0.4, 0.3, 0.2, 0.1)`
- `LOTTO_SCRAPER_BASE_URL` == `https://dhlottery.co.kr`
- `LOTTO_SCRAPER_WIN_URL` == `https://www.dhlottery.co.kr/gameResult.do?method=byWin`
- `LOTTO_CHECKPOINT_INTERVAL` == `20`

> 대응 요구사항: REQ-CFG-002 (3순위), REQ-CFG-004

---

### AC-CFG-005: `python-dotenv` 미설치 환경에서도 동작

**Given** `python-dotenv`가 설치되지 않은 가상환경에서 (또는 `monkeypatch`로 `ImportError`를 강제한 테스트 환경에서)
**When** `import lotto.config`를 실행하면
**Then** 임포트는 성공하며 환경 변수 + 기본값 기반으로 6개 상수가 정상적으로 평가된다. `ImportError`나 `ModuleNotFoundError`가 사용자에게 전파되지 않는다.

> 대응 요구사항: REQ-CFG-003 (Optional / Fallback)

---

### AC-CFG-006: 잘못된 형식의 환경 변수는 명시적 에러

**Given** `LOTTO_RECOMMENDER_WEIGHTS=abc,def,ghi,jkl`가 환경에 설정된 상태에서
**When** `lotto.config`를 임포트하면
**Then** `ValueError`가 발생하며 에러 메시지에 `LOTTO_RECOMMENDER_WEIGHTS`와 "expects 4 comma-separated floats" 같은 명시적 표현이 포함된다. 기본값으로 무음 폴백되지 않는다.

추가 케이스:
- `LOTTO_CHECKPOINT_INTERVAL=not-a-number` → `ValueError` (메시지에 `LOTTO_CHECKPOINT_INTERVAL` 포함)
- `LOTTO_RECOMMENDER_WEIGHTS=0.5,0.5` (4개가 아님) → `ValueError`

> 대응 요구사항: REQ-CFG-005

---

### AC-CFG-007: 하드코딩 잔존 부재

**Given** 구현이 완료된 코드베이스에서
**When** 사용자가 다음 명령을 실행하면

```
grep -RIn "https://www.dhlottery.co.kr/common.do?method=getLottoNumber" lotto/ main.py
grep -RIn "_CHECKPOINT_INTERVAL = 20" lotto/
grep -RIn "(0.4, 0.3, 0.2, 0.1)" lotto/
grep -RIn 'Path("data")' main.py
```

**Then** `lotto/config.py` 자체(기본값 정의)를 제외하면 어떤 매치도 나오지 않는다.

> 대응 요구사항: REQ-CFG-001 (단일 진입점 강제)

---

## 2. 에러 처리 강화 인수 시나리오 (REQ-ERR 계열)

### AC-ERR-001: 무음 예외 패턴 제거

**Given** 구현이 완료된 코드베이스에서
**When** 사용자가 `grep -RIn "except Exception: pass" lotto/`를 실행하면
**Then** 매치가 0개이다. 단순 `pass`가 아니더라도 로그 호출 없이 예외를 삼키는 패턴은 발견되지 않는다.

> 대응 요구사항: REQ-ERR-001

---

### AC-ERR-002: `web/data.py` 캐시 로드 실패 로깅

**Given** `lotto/web/data.py`의 캐시 로드 함수가 깨진 캐시 파일(또는 권한 오류 등)을 만나는 상황을 단위 테스트가 시뮬레이션한 상태에서
**When** 해당 함수를 호출하면
**Then** 함수는 폴백 동작(빈 캐시 / 기본값 반환)을 수행하며, `caplog`에 `lotto.web.data` 로거에서 `WARNING` 레벨로 "Failed to load cached data" 같은 식별 가능한 메시지가 기록되어 있다.

> 대응 요구사항: REQ-ERR-002

---

### AC-ERR-003: 체크포인트 저장 실패 로깅

**Given** `lotto/web/routes/api.py`의 체크포인트 저장 단계에서 디스크 IO 예외를 단위 테스트가 시뮬레이션한 상태에서
**When** 수집 흐름이 체크포인트 저장 라인을 통과하면
**Then** 수집 작업 자체는 중단되지 않으며, `caplog`에 `WARNING` 레벨로 "Checkpoint save failed at round" + 회차 번호를 포함하는 메시지가 기록된다.

> 대응 요구사항: REQ-ERR-003

---

### AC-ERR-004: 시뮬레이터 무작위 폴백 로깅

**Given** `lotto/simulator.py`가 분석 데이터가 비어 있어 무작위 추천으로 폴백해야 하는 상황 (예: `draws`가 빈 리스트)에서
**When** 시뮬레이션을 실행하면
**Then** 시뮬레이션은 무작위 추천으로 정상 종료되며, `caplog`에 `WARNING` 레벨로 "Analysis unavailable" + draw 개수를 포함하는 메시지가 기록된다.

> 대응 요구사항: REQ-ERR-004

---

## 3. 수동 입력 검증 인수 시나리오 (REQ-VAL-001)

다음 시나리오들은 FastAPI 테스트 클라이언트(`TestClient`) 기반으로 검증한다.

### AC-VAL-001: 정상 입력은 정상 응답

**Given** 시스템이 정상 동작 중이고 `data/draws.csv`에 회차 1100이 아직 존재하지 않는 상태에서
**When** 클라이언트가 `POST /draws/manual`로 다음 본문을 전송하면

```json
{
  "draw_no": 1100,
  "date": "20240101",
  "numbers": [1, 7, 14, 22, 33, 41],
  "bonus": 5
}
```

**Then** 응답 상태 코드는 200 또는 201이며, `data/draws.csv`에 회차 1100 레코드가 추가되어 있다.

(주: `draw_no` 필드 존재 여부와 정확한 응답 코드는 기존 라우트 시그니처에 따른다. 본 SPEC은 정상 경로 동작을 변경하지 않는다.)

> 대응 요구사항: REQ-VAL-001 (정상 경로 비회귀)

---

### AC-VAL-002: 잘못된 날짜 형식 거부

**Given** 시스템이 정상 동작 중인 상태에서
**When** 클라이언트가 `date` 필드를 `"2024-01-01"`(하이픈 포함) 또는 `"20240230"`(존재하지 않는 날짜) 또는 `"abc"` 등으로 보내면
**Then** 응답 상태 코드는 422이며, 응답 본문에 `date` 필드의 형식 오류가 명시되어 있다. `data/draws.csv`에 새 레코드가 추가되지 않는다.

> 대응 요구사항: REQ-VAL-001 (date 검증)

---

### AC-VAL-003: 번호 범위 초과 거부

**Given** 시스템이 정상 동작 중인 상태에서
**When** 클라이언트가 `numbers: [1, 7, 14, 22, 33, 46]` (46은 1-45 범위 초과) 또는 `numbers: [0, 7, 14, 22, 33, 41]` (0은 범위 미만)을 보내면
**Then** 응답 상태 코드는 422이며, 응답 본문에 어떤 번호가 범위를 벗어났는지 식별 가능한 메시지가 포함된다. CSV 변경 없음.

> 대응 요구사항: REQ-VAL-001 (numbers[i] 범위 검증)

---

### AC-VAL-004: 본 번호 개수 오류 거부

**Given** 시스템이 정상 동작 중인 상태에서
**When** 클라이언트가 `numbers: [1, 2, 3, 4, 5]` (5개) 또는 `numbers: [1, 2, 3, 4, 5, 6, 7]` (7개)를 보내면
**Then** 응답 상태 코드는 422이며, 응답 본문에 길이가 정확히 6이어야 함이 명시된다. CSV 변경 없음.

> 대응 요구사항: REQ-VAL-001 (numbers 길이 검증)

---

### AC-VAL-005: 본 번호 중복 거부

**Given** 시스템이 정상 동작 중인 상태에서
**When** 클라이언트가 `numbers: [1, 7, 7, 22, 33, 41]` (7이 중복)을 보내면
**Then** 응답 상태 코드는 422이며, 응답 본문에 중복이 발견되었음이 명시된다. CSV 변경 없음.

> 대응 요구사항: REQ-VAL-001 (numbers 중복 검증)

---

### AC-VAL-006: 보너스 번호 본 번호 중복 거부

**Given** 시스템이 정상 동작 중인 상태에서
**When** 클라이언트가 `numbers: [1, 7, 14, 22, 33, 41], bonus: 7`을 보내면
**Then** 응답 상태 코드는 422이며, 응답 본문에 보너스가 본 번호와 중복됨이 명시된다. CSV 변경 없음.

> 대응 요구사항: REQ-VAL-001 (bonus ↔ numbers 교차 검증)

---

### AC-VAL-007: 보너스 번호 범위 초과 거부

**Given** 시스템이 정상 동작 중인 상태에서
**When** 클라이언트가 `bonus: 0` 또는 `bonus: 46`을 보내면
**Then** 응답 상태 코드는 422이며, 응답 본문에 보너스 범위 오류가 명시된다. CSV 변경 없음.

> 대응 요구사항: REQ-VAL-001 (bonus 범위 검증)

---

## 4. 비기능 인수 시나리오 (NFR)

### AC-NFR-001: 기존 테스트 회귀 없음

**Given** SPEC-LOTTO-002 구현 완료 후의 코드베이스에서
**When** `pytest`를 실행하면
**Then** 기존 144개 테스트가 모두 PASS이며, 추가된 신규 테스트도 모두 PASS이다. 어떤 테스트도 SKIP 또는 XFAIL로 전환되지 않았다.

> 대응 요구사항: NFR-COMPAT-02

---

### AC-NFR-002: 커버리지 유지

**Given** 구현 완료 후의 코드베이스에서
**When** `pytest --cov=lotto --cov-report=term-missing`을 실행하면
**Then** 새로 추가된 모듈(`lotto/config.py`)과 변경된 모듈들의 커버리지가 각각 85% 이상이다. 전체 프로젝트 커버리지가 기존 85.65%보다 낮아지지 않는다.

> 대응 요구사항: NFR-QUAL-01

---

### AC-NFR-003: Lint 통과

**Given** 구현 완료 후의 코드베이스에서
**When** `ruff check .`을 실행하면
**Then** 0개의 경고와 0개의 에러로 종료한다. 신규 추가된 `# noqa` 주석이 있다면 모두 명시적 근거(예: `# noqa: B905  # Python 3.9 compat`)를 동반한다.

> 대응 요구사항: NFR-QUAL-02

---

### AC-NFR-004: 타입 체크 통과

**Given** 구현 완료 후의 코드베이스에서
**When** `mypy lotto/`를 실행하면
**Then** 신규 추가 모듈(`lotto/config.py`)과 변경된 모듈에서 에러 0개로 종료한다.

> 대응 요구사항: NFR-QUAL-03

---

### AC-NFR-005: Python 3.9 호환

**Given** Python 3.9.x 인터프리터로 만든 가상환경에서
**When** `pip install -e .` 후 `pytest`를 실행하면
**Then** 모든 테스트가 PASS이며, 어떤 `SyntaxError`도 발생하지 않는다. (특히 `zip(strict=True)`, `match/case`, `tuple[float, ...]` 표현식 사용 등 3.10+ 기능이 신규 코드에 포함되지 않았는지 확인)

> 대응 요구사항: NFR-COMPAT-01, 프로젝트 메모리 [[feedback_python39]]

---

### AC-NFR-006: 비밀 관리

**Given** 구현 완료 후 저장소 상태에서
**When** 사용자가 다음을 확인하면
- `.env.example`이 프로젝트 루트에 커밋되어 있고
- `.env`가 `.gitignore`에 포함되어 있으며
- `git ls-files | grep -E '^\.env$'`이 매치 0개를 반환

**Then** 위 3가지가 모두 참이다. 실제 비밀이 담길 수 있는 `.env`는 저장소에 포함되지 않는다.

> 대응 요구사항: NFR-SEC-01

---

## 5. 종합 Definition of Done

본 SPEC이 `status: completed`로 전환되려면 위 27개 인수 기준이 다음과 같이 모두 충족되어야 한다:

| 영역 | 인수 ID 수 | 상태 |
|------|-----------|------|
| 설정 외부화 (REQ-CFG) | 7 (AC-CFG-001~007) | All PASS |
| 에러 처리 (REQ-ERR) | 4 (AC-ERR-001~004) | All PASS |
| 입력 검증 (REQ-VAL) | 7 (AC-VAL-001~007) | All PASS |
| 비기능 (NFR) | 6 (AC-NFR-001~006) | All PASS |

추가로 다음 게이트가 통과되어야 한다:

- [ ] `acceptance.md`의 모든 시나리오에 대응하는 자동화된 pytest 케이스가 존재한다
- [ ] `plan.md`의 마일스톤 M1~M5가 모두 완료 체크되었다
- [ ] 사용자 회귀 점검: `python main.py collect --help`, `python main.py recommend`, `python main.py web` 명령이 환경 변수 미설정 환경에서 SPEC-LOTTO-001/SPEC-WEB-001 완료 시점과 동일하게 동작한다
- [ ] `git diff`로 검토 시 SPEC 범위를 벗어난 변경(예: UI 수정, 새 기능 추가)이 없음을 사람이 확인했다

---

## 6. 검증 명령 요약 (운영자가 실행 가능한 단일 시퀀스)

```
# 1. 기본값 임포트 동작 확인
python -c "from lotto import config; print(config.LOTTO_API_URL); print(config.LOTTO_RECOMMENDER_WEIGHTS)"

# 2. 잘못된 형식 거부 확인
LOTTO_RECOMMENDER_WEIGHTS="abc" python -c "from lotto import config" 2>&1 | grep -q "LOTTO_RECOMMENDER_WEIGHTS" && echo "OK: rejected"

# 3. 무음 예외 잔존 검사
test "$(grep -RIn 'except Exception: pass' lotto/ | wc -l)" = "0" && echo "OK: no silent except"

# 4. 하드코딩 잔존 검사 (config.py 자체는 제외)
grep -RIn '_CHECKPOINT_INTERVAL = 20' lotto/ | grep -v 'lotto/config.py' | wc -l   # → 0이어야 함

# 5. 품질 게이트
pytest --cov=lotto --cov-report=term-missing
ruff check .
mypy lotto/

# 6. .env 비밀 노출 검사
git ls-files | grep -E '^\.env$' | wc -l    # → 0이어야 함
test -f .env.example && echo "OK: example exists"
```

위 6개 단계가 모두 의도한 결과를 보이면 본 SPEC은 인수 완료로 간주된다.
