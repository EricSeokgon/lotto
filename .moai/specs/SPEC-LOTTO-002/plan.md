---
id: SPEC-LOTTO-002
document: plan
version: "0.1.0"
created: "2026-05-21"
updated: "2026-05-21"
---

# SPEC-LOTTO-002 구현 계획 (plan.md)

> 본 문서는 SPEC-LOTTO-002의 구현 접근 방식, 우선순위, 마일스톤, 리스크를 정의한다. 시간 추정은 사용하지 않으며 우선순위(High/Medium/Low)와 단계 순서로 기술한다.

---

## 1. 전체 접근 방식

### 설계 원칙

1. **단일 소스 모듈 (Single Source of Truth)**: 모든 설정은 `lotto/config.py`에서만 읽고, 다른 모듈은 그 결과를 임포트하여 사용한다. 이 모듈은 부수 효과가 최소화되어야 하며 임포트 시점에 환경을 한 번 평가한다.
2. **선택적 의존성 (Optional Dependency)**: `python-dotenv`는 `try/except ImportError` 패턴으로 감싼다. 미설치 환경에서는 `.env` 로딩 단계가 단순 스킵된다.
3. **하위 호환성 보장**: 환경 변수가 전혀 설정되지 않은 환경에서도 기본값이 기존 하드코딩 값과 정확히 일치해야 한다. 기존 사용자/CI에 어떤 변경도 강제하지 않는다.
4. **로깅의 일관성**: 모든 모듈은 모듈 최상단에서 `logger = logging.getLogger(__name__)`을 한 번만 선언하고 이를 통해 출력한다. `print()`나 ad-hoc 로깅 함수는 사용하지 않는다.
5. **검증과 실행의 분리**: `POST /draws/manual`의 검증 로직은 가능하면 Pydantic 모델의 `field_validator`로 표현하여 라우트 함수 본문에서 분리한다.

### 변경 대상 파일 요약

| 파일 | 변경 유형 | 우선순위 |
|------|-----------|----------|
| `lotto/config.py` | **신규** 생성 | High |
| `.env.example` | **신규** 생성 (루트) | High |
| `.gitignore` | `.env` 라인 추가(이미 있다면 확인만) | High |
| `pyproject.toml` | `python-dotenv` optional 그룹 추가 | High |
| `lotto/collector.py` | API URL 외부화 | High |
| `main.py` | 데이터 디렉터리 외부화 | High |
| `lotto/recommender.py` | 가중치 튜플 외부화 | Medium |
| `lotto/scraper.py` | 스크래퍼 URL 외부화 | Medium |
| `lotto/web/routes/api.py` | 체크포인트 주기 외부화 + 무음 예외 로깅 + 입력 검증 | High |
| `lotto/web/data.py` | 무음 예외 로깅 | Medium |
| `lotto/simulator.py` | 무음 폴백 로깅 | Medium |
| `tests/test_config.py` | **신규** 테스트 모듈 | High |
| `tests/test_web_manual_validation.py` (또는 기존 라우트 테스트 확장) | 수동 입력 검증 테스트 | High |

---

## 2. 마일스톤 (우선순위 기반 단계)

### Milestone M1 — 설정 모듈 골조 (Priority: High)

**목표**: 다른 어떤 변경도 시작하기 전에 `lotto/config.py`라는 단일 진입점을 먼저 만든다. 이 단계에서는 아무도 이 모듈을 사용하지 않으므로 기존 동작에는 영향이 없다.

작업 단위:
1. `lotto/config.py` 생성 — 6개 설정 키 상수와 타입 변환 헬퍼 정의
2. `python-dotenv` 선택적 로딩 로직 작성 (try/except ImportError + try `load_dotenv()`)
3. `LOTTO_RECOMMENDER_WEIGHTS`(콤마 구분 문자열 → `tuple[float, ...]`) 와 `LOTTO_CHECKPOINT_INTERVAL`(str → int) 파싱 헬퍼 작성. 잘못된 형식은 `ValueError`로 전파 (REQ-CFG-005)
4. `pyproject.toml`에 optional 의존성 그룹(예: `[project.optional-dependencies] dotenv = ["python-dotenv>=1.0"]`) 추가
5. `.env.example` 생성 — 6개 키를 모두 기본값과 함께 주석으로 설명
6. `.gitignore`에 `.env` 포함 확인 (이미 있다면 생략)
7. `tests/test_config.py` 신규 작성 — 환경 변수 우선순위, 기본값 폴백, 타입 변환 실패 케이스, `python-dotenv` 미설치 시뮬레이션(`monkeypatch`로 ImportError 강제) 등을 검증

**완료 조건**: `tests/test_config.py`가 통과하고, 다른 모듈은 아직 `config.py`를 참조하지 않으므로 기존 144개 테스트도 그대로 통과해야 한다.

---

### Milestone M2 — 핵심 경로 외부화 적용 (Priority: High)

**목표**: 가장 자주 변경/배포될 가능성이 높은 두 지점(API URL, 데이터 디렉터리)을 먼저 `config.py`로 라우팅한다.

작업 단위:
1. `lotto/collector.py:15` — 하드코딩 `https://www.dhlottery.co.kr/...`를 `from lotto.config import LOTTO_API_URL`로 치환
2. `main.py` — `Path("data")`로 하드코딩된 데이터 디렉터리 경로를 `from lotto.config import LOTTO_DATA_DIR`로 치환. `LOTTO_DATA_DIR`은 `Path`로 래핑되어 노출되거나, `main.py`에서 `Path(LOTTO_DATA_DIR)`로 변환
3. 기존 144개 테스트를 모두 실행하여 회귀가 없음을 확인. 필요 시 테스트 픽스처에서 `monkeypatch.setenv("LOTTO_DATA_DIR", str(tmp_path))` 패턴으로 격리

**완료 조건**: `pytest`가 통과하며, `LOTTO_API_URL`/`LOTTO_DATA_DIR`을 환경 변수로 덮어쓰는 단위 테스트가 새로 추가되어 통과한다.

---

### Milestone M3 — 나머지 외부화 + 무음 예외 로깅 (Priority: Medium)

**목표**: 변경 빈도는 낮지만 외부화 가치가 있는 추천 가중치/스크래퍼 URL/체크포인트 주기를 마무리하고, 동시에 식별된 무음 예외 3개 지점을 로깅으로 전환한다.

작업 단위:
1. `lotto/recommender.py` — `(0.4, 0.3, 0.2, 0.1)` 튜플을 `from lotto.config import LOTTO_RECOMMENDER_WEIGHTS`로 치환
2. `lotto/scraper.py:21-24` — 스크래퍼 URL 두 개를 `LOTTO_SCRAPER_BASE_URL`, `LOTTO_SCRAPER_WIN_URL`로 치환
3. `lotto/web/routes/api.py` — `_CHECKPOINT_INTERVAL = 20`을 `from lotto.config import LOTTO_CHECKPOINT_INTERVAL`로 치환
4. `lotto/web/data.py:80` 근방 — `except Exception: pass`를 `logger.warning("Failed to load cached data: %s", exc)` 형태로 교체 (REQ-ERR-002)
5. `lotto/web/routes/api.py:180` 근방 — 체크포인트 저장 실패 시 `logger.warning("Checkpoint save failed at round %d: %s", round_no, exc)`로 전환 (REQ-ERR-003)
6. `lotto/simulator.py:130` 근방 — 무작위 폴백 분기에 `logger.warning("Analysis unavailable for %d draws, falling back to random sampling", draw_count)` 추가 (REQ-ERR-004)
7. 모듈 최상단 `logger = logging.getLogger(__name__)` 선언 누락 확인 및 보강

**완료 조건**: `grep -RIn "except Exception: pass" lotto/`가 더 이상 매칭되지 않으며, 변경된 3개 지점에 대한 로그 캡처 테스트(`caplog` fixture 사용)가 새로 추가되어 통과한다.

---

### Milestone M4 — 수동 회차 입력 검증 (Priority: High)

**목표**: `POST /draws/manual` 엔드포인트에 명시적 검증을 추가하여 잘못된 데이터의 진입을 봉쇄한다.

작업 단위:
1. `lotto/web/routes/api.py`의 수동 등록 요청 모델(예: `ManualDrawRequest`)을 Pydantic으로 정의 또는 보강
2. `date` 필드: `field_validator`로 `len(value)==8 and datetime.strptime(value, "%Y%m%d")` 검증
3. `numbers` 필드: `Annotated[List[int], Len(6, 6)]` 또는 `field_validator`로 길이 6, 각 원소 `1<=x<=45`, 중복 없음 검증
4. `bonus` 필드: `1<=bonus<=45` 및 `bonus not in numbers` 검증
5. 검증 실패는 FastAPI 표준 422 응답으로 전파. 라우트 핸들러 본문은 잘못된 입력에 도달조차 하지 않도록 한다
6. `tests/test_web_manual_validation.py` 작성 — 정상/날짜형식오류/범위오류/중복/보너스중복/길이오류 6개 시나리오 각각에 대해 status code와 `data/draws.csv` 비변경을 확인

**완료 조건**: 새로 추가된 6개 검증 시나리오가 모두 통과하며, 정상 경로의 수동 등록은 여전히 200/201 응답으로 동작한다.

---

### Milestone M5 — 품질 게이트 (Priority: High)

**목표**: 변경 후 코드베이스 전체가 기존 품질 기준을 유지함을 검증한다.

작업 단위:
1. `pytest --cov=lotto --cov-report=term-missing` 실행 — 변경된 파일들의 커버리지가 85% 이상인지 확인
2. `ruff check .` 실행 — 경고 0개 확인
3. `mypy lotto/` 실행 — 신규/변경 모듈 기준 에러 0개 확인
4. 기존 144개 테스트가 모두 PASS임을 재확인
5. `.env.example`이 실제로 `python -c "from lotto.config import *; print(LOTTO_API_URL)"`로 기본값을 확인 가능한지 수동 검증

**완료 조건**: 모든 자동 도구가 통과하고 `acceptance.md`의 모든 항목이 체크된다.

---

## 3. 기술 접근 상세

### 3.1 `lotto/config.py` 구조 스케치

본 SPEC은 코드를 작성하지 않으나, plan 단계에서 다음 책임을 명시한다:

- 모듈 임포트 시 `try: from dotenv import load_dotenv; load_dotenv()` 시도, 실패는 `try/except ImportError`로 조용히 무시
- 환경 변수 조회는 표준 라이브러리 `os.environ.get(KEY, DEFAULT)`만 사용
- 타입 변환 헬퍼는 `_parse_weights(value: str) -> tuple[float, ...]`, `_parse_int(value: str, key: str) -> int` 형태로 분리. 잘못된 형식은 변환 함수 내부에서 `ValueError`를 raise하며, 메시지는 `LOTTO_RECOMMENDER_WEIGHTS expects 4 comma-separated floats, got: 'xxx'`처럼 무엇이 잘못됐는지 명확히 기술
- 모듈 레벨 상수로 6개 키를 한 번만 평가하여 export. 재평가나 동적 리로드는 본 SPEC 범위 밖

### 3.2 무음 예외 → 로깅 전환 패턴

각 변경 지점은 동일한 패턴을 따른다:

- 모듈 최상단에 `import logging` 및 `logger = logging.getLogger(__name__)` 보장
- `except Exception as exc:` 형태로 예외 객체 캡처
- 1줄 `logger.warning("<지점 식별 메시지>: %s", exc)` 호출 후, 기존 폴백 동작(빈 캐시 반환, 작업 계속 진행, 무작위 추천) 그대로 유지
- 로그 메시지는 운영자가 검색하기 좋은 안정적 prefix를 가지도록 한다 (예: "Checkpoint save failed at round %d")
- 로깅 추가가 기존 동작을 바꾸지 않는지 회귀 테스트로 확인

### 3.3 입력 검증 패턴

- FastAPI + Pydantic v2 기준 `field_validator`(`@field_validator("numbers")` 등) 또는 `model_validator(mode="after")`로 다중 필드 교차 검증(bonus가 numbers에 포함되지 않음 등)을 구현
- 라우트 핸들러는 Pydantic 모델 인스턴스만 받으므로, 검증 실패는 FastAPI가 자동으로 422를 반환
- 응답 본문 형식은 FastAPI 기본 `{"detail": [...]}`을 따른다. 별도 응답 포맷터를 도입하지 않는다 (Enforce Simplicity)

---

## 4. 리스크 및 완화

| 리스크 | 영향 | 완화 |
|--------|------|------|
| `python-dotenv` 미설치 환경에서 `.env`를 사용해 테스트하다가 누락 발견 | 중 | CI에서 `python-dotenv` 미설치 매트릭스를 한 가지 추가하거나, `monkeypatch`로 ImportError를 강제하는 테스트로 대신함 |
| 기존 테스트가 `data/draws.csv` 경로를 절대값으로 의존 | 중 | conftest에서 `monkeypatch.setenv("LOTTO_DATA_DIR", str(tmp_path))` 패턴으로 격리. 직접 `Path("data")`를 참조하는 테스트는 변환 |
| 잘못된 환경 변수(`LOTTO_RECOMMENDER_WEIGHTS="abc"`) 입력 시 임포트 시점 크래시 | 낮음 | 의도된 동작. REQ-CFG-005가 명시한다. 에러 메시지가 친화적인지 단위 테스트로 보장 |
| `POST /draws/manual` 응답 포맷 변경으로 기존 프런트엔드 호출 깨짐 | 낮음 | 본 SPEC은 잘못된 입력에 대해서만 422를 추가한다. 정상 경로 응답은 변경하지 않음. 프런트엔드 회귀 가능성은 잘못된 입력을 보내고 있던 클라이언트에 한정됨 |
| 추천 가중치 환경 변수가 잘못 설정된 운영 환경에서 추천 결과가 미세하게 달라짐 | 중 | 기본값을 기존 하드코딩 값(`0.4,0.3,0.2,0.1`)과 비트 단위로 일치시킴. 변경하려는 사용자만 영향을 받음 |
| Python 3.9 호환성 위반 (예: `tuple[float, ...]`을 표현식으로 사용) | 중 | 변수/매개변수 타입 힌트는 `Tuple[float, ...]` (typing 모듈)로 작성하거나 `from __future__ import annotations` 사용. 메모리 [[feedback_python39]] 참조 |
| 무음 예외 로깅 추가로 인해 기존 테스트가 stderr 출력 변화로 깨짐 | 낮음 | pytest는 기본적으로 caplog로 격리. stderr 캡처 의존 테스트가 있다면 그 테스트만 수정 |

---

## 5. 완료 게이트 체크리스트

본 단계가 완료된 것으로 간주하려면 다음이 모두 참이어야 한다:

- [ ] `lotto/config.py` 모듈이 존재하고 6개 키를 export한다
- [ ] `.env.example`이 프로젝트 루트에 존재한다
- [ ] `.gitignore`에 `.env` 라인이 존재한다 (이미 있는 경우 변경 없음)
- [ ] `pyproject.toml`에 `python-dotenv` optional 의존성 그룹이 정의되어 있다
- [ ] `grep -RIn "except Exception: pass" lotto/`가 매치 0개를 반환한다
- [ ] `data.py:80`, `api.py:180`, `simulator.py:130`에 `logger.warning` 호출이 존재한다
- [ ] `POST /draws/manual`의 6개 검증 시나리오 테스트가 모두 통과한다
- [ ] `pytest`가 144 + 신규 테스트를 모두 통과한다
- [ ] `pytest --cov=lotto`가 변경 모듈 기준 85% 이상이다
- [ ] `ruff check .`이 경고 0개를 반환한다
- [ ] `mypy lotto/`가 신규/변경 모듈 기준 에러 0개를 반환한다
- [ ] `python-dotenv` 미설치 환경에서 `python -c "from lotto.config import LOTTO_API_URL"`이 성공한다

---

## 6. 작업 순서 요약

1. **High Priority**: M1 (설정 모듈 골조) → M2 (핵심 경로 외부화)
2. **High Priority 병행 가능**: M4 (입력 검증) — M1 완료 후 독립적으로 진행 가능
3. **Medium Priority**: M3 (나머지 외부화 + 로깅) — M2 이후
4. **High Priority 마지막**: M5 (품질 게이트) — 모든 변경 완료 후 일괄 검증

병렬화 힌트: M4(입력 검증)는 `lotto/config.py`에 의존하지 않으므로 M1 직후 M2와 병렬 진행 가능하다. 다만 동일한 `lotto/web/routes/api.py`를 M3와 M4가 모두 수정하므로, 둘 사이는 순차 실행이 안전하다.
