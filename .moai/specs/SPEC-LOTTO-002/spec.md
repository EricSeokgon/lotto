---
id: SPEC-LOTTO-002
version: "0.1.0"
status: draft
created: "2026-05-21"
updated: "2026-05-21"
author: ircp
priority: medium
issue_number: 0
---

# SPEC-LOTTO-002: 설정 외부화 및 에러 처리 강화

## HISTORY

| 버전 | 일자 | 작성자 | 변경 내용 |
|------|------|--------|-----------|
| 0.1.0 | 2026-05-21 | ircp | 초기 SPEC 작성 — 하드코딩 상수 외부화, 무음 예외 처리 강화, 수동 입력 검증 추가 |

---

## Overview (개요)

### What (무엇을 만드는가)

SPEC-LOTTO-001(CLI)과 SPEC-WEB-001(웹 대시보드)이 완료된 현재 코드베이스를 대상으로, **운영 안정성과 배포 유연성을 강화**하는 비기능 개선을 정의한다. 본 SPEC은 새로운 사용자 기능을 추가하지 않으며, 다음 세 가지 비기능 품질을 끌어올린다.

1. **설정 외부화**: 코드 곳곳에 흩어진 하드코딩 상수(API URL, 데이터 디렉터리, 추천 가중치, 스크래퍼 URL, 체크포인트 주기)를 단일 설정 모듈로 모으고 환경 변수 / `.env` 파일로 주입 가능하게 한다.
2. **에러 처리 강화**: 현재 `except Exception: pass` 등 무음으로 삼켜지는 예외 지점을 식별하여 구조화된 로깅으로 전환한다. 운영 중 문제가 발생해도 흔적이 남도록 한다.
3. **입력 검증**: 웹 대시보드의 수동 회차 입력 엔드포인트(`POST /draws/manual`)에 명시적 유효성 검증을 추가하여 잘못된 데이터가 데이터 저장소까지 흘러가지 않도록 차단한다.

### Why (왜 만드는가)

- **배포 유연성**: 개발/스테이징/운영 환경마다 API 엔드포인트, 데이터 저장 경로, 추천 가중치를 다르게 운용해야 하지만, 현재는 소스 코드 수정 없이 변경할 수 없다. 이는 12-Factor App 원칙(Config Separation)에 위배되며 배포 자동화의 가장 큰 장애물이다.
- **운영 가시성**: 무음 예외는 디버깅 시 가장 비싼 비용을 만든다. 사용자가 "수동 입력이 안 됐다"고 신고했을 때, 로그가 없으면 원인 파악이 불가능하다. 구조화된 `logging.warning` 호출로 전환하여 추후 ELK/Loki 같은 로그 수집기에 자연스럽게 통합 가능하게 한다.
- **데이터 무결성**: 현재 `POST /draws/manual` 엔드포인트는 잘못된 날짜 형식이나 1~45 범위를 벗어난 번호, 중복 번호도 받아 들이고 저장 단계에서 무음으로 누락된다. 데이터가 일단 잘못 들어가면 분석/추천/시뮬레이션 모든 하위 시스템이 오염된다. 422 응답으로 명확히 거부해 데이터 오염을 입구에서 차단한다.

### Scope (적용 범위)

- **포함**: `lotto/collector.py`, `lotto/recommender.py`, `lotto/scraper.py`, `lotto/simulator.py`, `lotto/web/data.py`, `lotto/web/routes/api.py`, `main.py`의 하드코딩 상수 외부화. 새 모듈 `lotto/config.py`(설정 로더) 추가. 식별된 무음 예외 지점 로깅. 수동 회차 등록 API 입력 검증.
- **제외**: 사용자 인증, 권한 관리, 로그 외부 수집기 연동(ELK/Loki), 설정 동적 리로드(SIGHUP 등), 추가 분석/추천 로직 변경, CLI 인터페이스 변경, 웹 UI 변경.
- **제약**: Python 3.9 호환 유지. 기존 144개 테스트 케이스가 모두 통과해야 함. `python-dotenv`는 선택적 의존성으로만 추가하며, 미설치 환경에서도 시스템은 정상 동작해야 함.

---

## Glossary (용어 정의)

| 용어 | 정의 |
|------|------|
| 설정 외부화(Config Externalization) | 코드 내부에 박혀 있던 상수를 환경 변수, `.env` 파일, 또는 기본값을 통해 런타임에 결정하도록 분리하는 작업 |
| `.env` 파일 | 프로젝트 루트에 위치하는 KEY=VALUE 형식의 텍스트 파일. `python-dotenv`로 로드되며 Git에 커밋되지 않음 |
| 폴백(Fallback) | 환경 변수도 `.env` 파일도 값을 제공하지 않을 때 사용되는 안전한 기본값 |
| 무음 예외(Silent Exception) | `except Exception: pass` 같은 패턴으로 로그 없이 삼켜지는 예외. 디버깅을 어렵게 만드는 안티 패턴 |
| 구조화 로깅(Structured Logging) | `logging` 표준 라이브러리를 사용하여 레벨, 로거 이름, 컨텍스트를 명시적으로 남기는 로그 작성 방식 |
| 체크포인트(Checkpoint) | 장시간 수집/스크래핑 작업 중 진행 상황을 주기적으로 저장하여 중단 시 재개 가능하게 하는 스냅숏 |
| 422 Unprocessable Entity | HTTP 응답 코드. 요청 형식은 올바르지만 의미 수준에서 처리 불가능한 입력이 들어왔음을 의미 |

---

## Functional Requirements (기능 요구사항 — EARS 형식)

### REQ-CFG: 설정 외부화 (Configuration Externalization)

#### REQ-CFG-001 (Ubiquitous)
시스템은 모든 외부 설정 값을 단일 모듈 `lotto/config.py`에서 노출(export)하는 모듈 레벨 상수로 제공해야 한다. 다른 모듈은 하드코딩 상수를 직접 정의하는 대신 `from lotto.config import ...` 형태로 참조해야 한다.

#### REQ-CFG-002 (Event-driven)
WHEN `lotto/config.py`가 처음 임포트될 때, THE 시스템은 다음 순서로 설정 값을 결정해야 한다: (1) 환경 변수가 정의되어 있으면 환경 변수 값을 사용, (2) 환경 변수가 없고 프로젝트 루트에 `.env` 파일이 존재하며 `python-dotenv`가 설치되어 있으면 `.env` 값을 사용, (3) 그 외에는 모듈에 정의된 기본값을 사용해야 한다.

#### REQ-CFG-003 (Optional)
WHERE 패키지 `python-dotenv`가 설치되어 있는 환경에서, THE 시스템은 `lotto/config.py` 초기화 시 프로젝트 루트의 `.env` 파일을 자동으로 로드해야 한다. WHERE `python-dotenv`가 설치되어 있지 않은 환경에서는, 시스템은 `.env` 파일을 무시하고 환경 변수와 기본값만 사용해야 하며 임포트 자체는 실패하지 않아야 한다.

#### REQ-CFG-004 (Ubiquitous)
THE 시스템은 다음 설정 키를 환경 변수로 노출해야 한다:

| 환경 변수 | 기본값 | 대상 위치 | 의미 |
|-----------|--------|-----------|------|
| `LOTTO_API_URL` | `https://www.dhlottery.co.kr/common.do?method=getLottoNumber` | `collector.py:15` | 동행복권 회차 조회 API 베이스 URL |
| `LOTTO_DATA_DIR` | `data` | `main.py` 전반 | 데이터 저장 루트 디렉터리 (상대 경로 또는 절대 경로) |
| `LOTTO_RECOMMENDER_WEIGHTS` | `0.4,0.3,0.2,0.1` | `recommender.py` | 추천 가중치 4-튜플 (콤마 구분 문자열) |
| `LOTTO_SCRAPER_BASE_URL` | `https://dhlottery.co.kr` | `scraper.py:21-24` | 스크래퍼 베이스 URL |
| `LOTTO_SCRAPER_WIN_URL` | `https://www.dhlottery.co.kr/gameResult.do?method=byWin` | `scraper.py:21-24` | 회차별 당첨 결과 페이지 URL |
| `LOTTO_CHECKPOINT_INTERVAL` | `20` | `web/routes/api.py` | 체크포인트 저장 주기 (회차 단위) |

#### REQ-CFG-005 (Unwanted behavior)
IF 환경 변수 또는 `.env` 값이 타입 변환(예: `LOTTO_RECOMMENDER_WEIGHTS`를 `tuple[float, ...]`로, `LOTTO_CHECKPOINT_INTERVAL`을 `int`로 변환)에 실패하면, THEN 시스템은 `ValueError`를 발생시키고 어떤 환경 변수가 어떤 형식을 기대하는지 명시한 에러 메시지를 출력해야 하며, 잘못된 값을 무음으로 기본값으로 폴백해서는 안 된다.

---

### REQ-ERR: 에러 처리 강화 (Error Handling Hardening)

#### REQ-ERR-001 (Ubiquitous)
THE 시스템은 코드베이스 내에서 `except Exception: pass` 형태의 무음 예외 처리를 사용해서는 안 된다. 모든 예외 처리 블록은 최소 `logger.warning(...)` 이상의 로그 호출을 포함해야 한다.

#### REQ-ERR-002 (Event-driven)
WHEN `lotto/web/data.py` 라인 80 근방의 캐시 로드/파일 읽기 예외가 발생할 때, THE 시스템은 `logger.warning("Failed to load cached data: %s", exc)` 형태의 경고 로그를 남기고, 빈 캐시(또는 폴백 데이터)를 반환하여 동작을 계속해야 한다.

#### REQ-ERR-003 (Event-driven)
WHEN `lotto/web/routes/api.py` 라인 180 근방의 체크포인트 저장 단계에서 예외가 발생할 때, THE 시스템은 `logger.warning("Checkpoint save failed at round %d: %s", round_no, exc)` 형태의 경고 로그를 남기고, 수집 작업 자체는 중단하지 않아야 한다.

#### REQ-ERR-004 (Event-driven)
WHEN `lotto/simulator.py` 라인 130 근방에서 분석 결과를 사용할 수 없어 무작위 추천으로 폴백할 때, THE 시스템은 `logger.warning("Analysis unavailable for %d draws, falling back to random sampling", draw_count)` 형태의 경고 로그를 남겨야 한다.

---

### REQ-VAL: 입력 검증 (Input Validation)

#### REQ-VAL-001 (Event-driven + Unwanted behavior)
WHEN 사용자가 웹 대시보드의 `POST /draws/manual` 엔드포인트로 수동 회차 데이터를 제출할 때, THE 시스템은 요청 본문에 대해 다음 검증을 수행해야 한다:

| 필드 | 검증 규칙 |
|------|-----------|
| `date` | 정확히 8자리 숫자 문자열이며 `datetime.strptime(value, "%Y%m%d")`로 파싱 가능해야 함 |
| `numbers` | 길이가 정확히 6인 정수 리스트 |
| `numbers[i]` | 각 원소는 1 이상 45 이하 정수 |
| `numbers` 중복 | 6개 원소 사이에 중복이 없어야 함 |
| `bonus` | 1 이상 45 이하 정수 |
| `bonus`와 `numbers` 중복 | `bonus`는 `numbers` 6개 중 어느 것과도 같지 않아야 함 |

IF 위 검증 중 어느 하나라도 실패하면, THEN 시스템은 HTTP 422 Unprocessable Entity 응답을 반환하고 응답 본문에 `{"detail": "<사람이 읽을 수 있는 오류 메시지>"}` 형태로 어떤 필드가 어떤 규칙을 위반했는지 명시해야 하며, 잘못된 입력을 데이터 저장소(`data/draws.csv`)에 기록해서는 안 된다.

---

## Non-Functional Requirements (비기능 요구사항)

| ID | 항목 | 요구 수준 |
|----|------|-----------|
| NFR-COMPAT-01 | Python 호환 | Python 3.9에서 동작해야 함. `zip(strict=True)` 등 3.10+ 문법 금지 (사유: 프로젝트 메모리 등록된 [[feedback_python39]] 규칙) |
| NFR-COMPAT-02 | 기존 테스트 호환 | 변경 후에도 기존 144개 테스트가 모두 통과해야 함 |
| NFR-COMPAT-03 | 선택적 의존성 | `python-dotenv`는 `pyproject.toml`의 optional 그룹에만 추가. 코어 설치(`pip install .`)는 `python-dotenv` 없이도 성공해야 함 |
| NFR-LOG-01 | 로깅 표준 | 모든 로그는 `logging.getLogger(__name__)`로 얻은 로거를 통해 출력. `print()` 사용 금지 |
| NFR-LOG-02 | 로그 레벨 | 폴백/회복 가능 상황은 `WARNING`, 단순 정보는 `INFO`, 디버그용은 `DEBUG` 사용 |
| NFR-QUAL-01 | 테스트 커버리지 | 새로 추가/변경된 파일의 커버리지가 85% 이상 유지되어야 함 |
| NFR-QUAL-02 | Lint | `ruff check .`이 경고 0개로 통과 |
| NFR-QUAL-03 | 타입 체크 | `mypy lotto/`가 신규/변경된 모듈에서 에러 0개로 통과 |
| NFR-SEC-01 | 비밀 관리 | `.env` 파일은 `.gitignore`에 반드시 포함. `.env.example` 템플릿 파일은 커밋. 실제 비밀(토큰/키)이 노출되지 않아야 함 |

---

## Out of Scope (명시적 제외 사항)

본 SPEC은 다음을 다루지 않는다. 향후 SPEC으로 분리하거나 의도적으로 보류한다.

- **사용자 인증 / 권한 관리**: 현재 웹 대시보드는 단일 사용자 전제이므로 인증 도입은 별도 SPEC에서 다룬다.
- **로그 외부 수집기 연동**: ELK, Loki, Sentry, CloudWatch 등 외부 로그 시스템 통합은 본 SPEC의 범위를 벗어난다. 본 SPEC은 표준 `logging` 호출까지만 보장한다.
- **설정 동적 리로드**: 프로세스 실행 중 `.env` 변경을 감지하여 재로드하는 기능(SIGHUP 등)은 다루지 않는다. 변경 적용은 프로세스 재시작이 전제다.
- **새로운 분석/추천 알고리즘**: 추천 가중치를 외부화하지만, 가중치의 의미나 기본값 자체를 변경하지 않는다. 알고리즘 변경은 별도 SPEC에서 다룬다.
- **CLI 명령 인터페이스 변경**: `python main.py collect/analyze/recommend/simulate/web`의 시그니처와 동작은 변경하지 않는다. 환경 변수로 동작을 제어할 수 있게만 한다.
- **웹 UI 변경**: 사용자에게 보이는 페이지/스타일은 본 SPEC에서 다루지 않는다. 변경은 백엔드 검증 로직과 422 응답까지로 한정된다.
- **수동 회차 등록 외 다른 엔드포인트의 검증 강화**: 본 SPEC은 `POST /draws/manual`에만 집중한다. 다른 엔드포인트 검증은 필요 시 별도 SPEC에서 다룬다.
- **CSV/JSON 파일 외 데이터 백엔드 도입**: SQLite, PostgreSQL 등 RDBMS 도입은 다루지 않는다.

---

## Dependencies (의존성)

| 항목 | 종류 | 비고 |
|------|------|------|
| SPEC-LOTTO-001 | 선행 | CLI 파이프라인(`main.py`, `lotto/collector.py`, `recommender.py`, `simulator.py`)이 본 SPEC 변경 대상의 일부 |
| SPEC-WEB-001 | 선행 | 웹 대시보드(`lotto/web/`)와 `POST /draws/manual` 엔드포인트가 본 SPEC 변경 대상의 일부 |
| `python-dotenv` | 외부 (선택) | optional 의존성. 미설치 환경에서도 시스템 정상 동작 보장 (REQ-CFG-003) |
| `python>=3.9` | 외부 (필수) | 기존 프로젝트 제약. 3.10+ 전용 문법 금지 |

---

## Acceptance Criteria 요약 (상세는 `acceptance.md`)

본 SPEC이 "완료(completed)" 상태로 전환되려면 다음 조건이 모두 충족되어야 한다:

1. `lotto/config.py` 모듈이 존재하며 6개 설정 키를 모두 노출한다.
2. 6개 소스 위치(collector.py:15, main.py, recommender.py 가중치, scraper.py:21-24, api.py 체크포인트, 데이터 디렉터리)에 더 이상 하드코딩 상수가 남아 있지 않다.
3. 식별된 3개 무음 예외 지점(data.py:80, api.py:180, simulator.py:130)에서 모두 `logger.warning` 호출이 확인된다.
4. `POST /draws/manual`에 잘못된 입력을 보내면 422 응답이 반환되며, `data/draws.csv`에 데이터가 추가되지 않는다.
5. `pytest`로 기존 144개 테스트 + 신규 테스트가 모두 통과한다.
6. `ruff check .`이 경고 0개, `mypy lotto/`이 변경 모듈 기준 에러 0개를 보고한다.
7. `.env.example` 템플릿 파일이 프로젝트 루트에 존재하고 `.env`는 `.gitignore`에 포함된다.

---

## References

- 본 프로젝트 `CLAUDE.md` Section 9 "Configuration Reference"
- 12-Factor App, "III. Config — Store config in the environment" (https://12factor.net/config)
- Python `logging` 표준 라이브러리 (https://docs.python.org/3.9/library/logging.html)
- FastAPI 응답 코드 가이드 — HTTP 422 Unprocessable Entity
- 프로젝트 메모리: [[feedback_python39]] — Python 3.9 호환성 규칙
