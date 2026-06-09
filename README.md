# 로또 번호 추천 프로그램

[![Python 3.9+](https://img.shields.io/badge/Python-3.9+-blue)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/Tests-1200-green)](./tests/)
[![Coverage](https://img.shields.io/badge/Coverage-100%25-brightgreen)](#)

통계 분석 기반의 로또 번호 추천 CLI 도구 및 웹 대시보드입니다. 동행복권 공식 데이터를 수집하여 다각적인 통계 분석을 수행하고, 가중치 기반 알고리즘으로 추천 번호를 생성합니다. 또한 과거 데이터에 대한 백테스팅으로 알고리즘의 유효성을 검증합니다.

## 개요

### 주요 기능

- **당첨 번호 수집**: 동행복권 API에서 회차별 당첨 번호 자동 수집 (원자적 저장, 증분 갭 감지)
- **블로그 크롤링**: API 차단 환경 대비 블로그 기반 대체 데이터 수집
- **통계 분석**: 5가지 분석 지표로 번호 패턴 파악
  - 출현 빈도: 각 번호의 누적 출현 횟수
  - 최근 패턴: 최근 N회차 내 출현 경향
  - 연속 패턴: 연속 출현/부재 계수
  - 동반 출현: 자주 함께 나오는 번호 쌍
  - 보너스 번호 빈도: 보너스 번호별 출현 횟수
- **번호 패턴 분석**: 홀짝 비율·번호대 분포·연속 번호·합계 분포·끝자리 분포
- **8가지 전략 추천**: 사용자 정의 가중치 및 전략 레이블로 유연한 추천
- **교차 전략 합의 알림**: 추천 번호별 11개 전략 합의도(N/11) 표시, 합의 4개 이상 번호 주의 배지
- **번호 즐겨찾기**: 자주 쓰는 번호 조합 저장·관리·시뮬레이션 연동
- **인과 안전 백테스팅**: 과거 데이터로 알고리즘 효용성 검증
- **전략 백테스팅 분석기**: 11개 전략의 과거 N회차 성능을 look-ahead 없이 비교, `/backtest` 페이지 및 JSON API 제공
- **웹 대시보드**: 브라우저 기반 대시보드 (FastAPI + Jinja2, 다크모드 지원)
- **데이터 내보내기**: 추첨 데이터·구매 이력 CSV/JSON 다운로드
- **당첨금 분석**: 1등 당첨금 추이 차트 및 평균/최대/최소 통계
- **PDF 리포트**: 통계·추천·시뮬레이션 결과를 단일 PDF로 다운로드
- **헬스체크 API**: `GET /api/health` — uptime, CSV 행 수, 데이터 상태 응답
- **설정 외부화**: 환경 변수(LOTTO_*)로 모든 핵심 파라미터 오버라이드

### 특징

- 외부 데이터베이스 불필요 — 로컬 CSV/JSON 파일 기반
- 원자적 파일 저장 — 쓰기 중 충돌 방지
- 타입 안전성 — Python 3.9+ 호환
- 높은 커버리지 — 1200개 테스트, 96%+ 라인 커버리지
- 다크모드 지원 — 시스템 테마 감지 + 수동 토글 (Tailwind CSS)

## 설치

### 전제 조건

- Python 3.9 이상
- pip 또는 uv

### 설치 방법

```bash
# 프로젝트 디렉토리로 이동
cd lotto

# 개발용 의존성 포함하여 설치
pip install -e ".[dev]"
# 또는 uv 사용 시:
# uv pip install -e ".[dev]"
```

### 의존성

- **typer**: CLI 프레임워크
- **rich**: 터미널 출력 스타일링
- **fastapi**: 웹 API 프레임워크
- **uvicorn**: ASGI 서버
- **jinja2**: 웹 템플릿 엔진
- **reportlab**: PDF 생성
- **pydantic**: 데이터 검증
- **pytest**: 테스트 프레임워크 (개발용)

## 웹 대시보드

브라우저에서 통계를 시각화하는 5탭 웹 대시보드입니다.

```bash
python main.py web
# 또는
python main.py web --port 8080 --reload
```

http://localhost:8000 에서 확인 가능합니다.

**탭 구성:**
- 대시보드: 데이터 상태·당첨금 추이 차트 및 기능 개요
- 수집 현황: 수집된 당첨 번호 목록 (삭제 버튼·CSV 내보내기 포함)
- 빈도 분석: 번호별 컬러 배지·차트·패턴 분석 탭 (홀짝·번호대·합계 분포)
- 추천 번호: 통계 기반 번호 추천 + 즐겨찾기 관리 (저장·삭제)
- 시뮬레이션: 도넛 차트·등수별 분포·즐겨찾기 번호로 시뮬레이션
- 구매 내역: 구매 티켓 등록·당첨 결과 확인·CSV/JSON 내보내기

**API 문서:**
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

> 차트 렌더링에는 인터넷 연결이 필요합니다 (Tailwind CSS, Chart.js, Noto Sans KR CDN 사용).

## REST API 엔드포인트

| 메서드 | 경로 | 설명 | 주요 파라미터 |
|--------|------|------|--------------|
| `GET` | `/api/draws` | 추첨 결과 목록 | `limit`, `offset`, `from_round`, `to_round` |
| `GET` | `/api/stats` | 통계 분석 결과 (보너스 빈도 포함) | — |
| `GET` | `/api/recommendations` | 번호 추천 목록 | `count`, `strategy` |
| `GET` | `/api/simulation` | 시뮬레이션 결과 | `rounds` |
| `GET` | `/api/report/pdf` | PDF 리포트 다운로드 | — |
| `POST` | `/api/collect` | 백그라운드 데이터 수집 시작 | `full`, `count` |
| `GET` | `/api/collect/status` | 수집 진행 상태 조회 | — |
| `POST` | `/api/draws/manual` | 회차 데이터 수동 추가 | `drwNo`, `date`(YYYYMMDD), `numbers`, `bonus` |
| `POST` | `/api/scrape` | 블로그 크롤링 시작 | — |
| `POST` | `/api/history` | 구매 티켓 추가 | `drwNo`, `numbers`, `bought_at` |
| `GET` | `/api/history` | 구매 히스토리 + 당첨 결과 조회 | — |
| `DELETE` | `/api/history/{ticket_id}` | 구매 티켓 삭제 | `ticket_id` |
| `DELETE` | `/api/draws/{drw_no}` | 추첨 회차 삭제 | `drw_no` |
| `POST` | `/api/favorites` | 즐겨찾기 번호 추가 | `numbers`, `name` |
| `GET` | `/api/favorites` | 즐겨찾기 목록 조회 | — |
| `DELETE` | `/api/favorites/{fav_id}` | 즐겨찾기 삭제 | `fav_id` |
| `GET` | `/api/pattern-analysis` | 번호 패턴 통계 조회 | — |
| `GET` | `/api/export/draws` | 추첨 데이터 CSV 다운로드 | `from_drw`, `to_drw` |
| `GET` | `/api/export/history` | 구매 이력 내보내기 | `format` (csv/json) |
| `GET` | `/api/prize-stats` | 1등 당첨금 통계 조회 | — |
| `POST` | `/api/analyze` | 통계 분석 백그라운드 시작 | — |
| `GET` | `/api/health` | 서버 상태 및 데이터 파일 존재 여부 | — |

### `/api/health` 응답 구조

항상 HTTP 200을 반환하며, 모니터링 도구(Prometheus, UptimeRobot, k8s liveness probe)에서 사용합니다.

```json
{
  "status": "ok",
  "uptime_seconds": 123.45,
  "data": {
    "csv_exists": true,
    "csv_rows": 1150,
    "stats_exists": true,
    "last_sync": "2024-01-15"
  },
  "version": "1.5.0"
}
```

- `status`: `"ok"` (csv + stats 모두 존재) / `"degraded"` (파일 없음)
- `uptime_seconds`: 앱 시작 이후 경과 시간(초)
- `data.csv_rows`: `data/draws.csv` 행 수 (파일 없으면 0)
- `data.last_sync`: `last_sync.json`의 날짜 (없으면 `null`)

## 환경 변수 (설정 외부화)

모든 설정은 환경 변수, `.env` 파일, 기본값 순으로 우선순위가 적용됩니다.

| 환경 변수 | 기본값 | 설명 |
|-----------|--------|------|
| `LOTTO_API_URL` | `https://www.dhlottery.co.kr/common.do?method=getLottoNumber&drwNo={drw_no}` | 동행복권 API URL 템플릿 |
| `LOTTO_DATA_DIR` | `data` | 데이터 파일 저장 디렉토리 |
| `LOTTO_WEB_HOST` | `127.0.0.1` | 웹 서버 바인딩 호스트 |
| `LOTTO_WEB_PORT` | `8000` | 웹 서버 포트 |
| `LOTTO_RECOMMENDER_WEIGHTS` | `0.4,0.3,0.2,0.1` | 추천 가중치 (w_freq,w_recent,w_pair,w_consec) |
| `LOTTO_CHECKPOINT_INTERVAL` | `20` | 수집 중 중간 저장 간격 (회차 수) |
| `LOTTO_SCRAPER_URL_1` | (블로그 URL 1) | 블로그 크롤링 대상 URL 1 |
| `LOTTO_SCRAPER_URL_2` | (블로그 URL 2) | 블로그 크롤링 대상 URL 2 |
| `LOTTO_MAX_RETRIES` | `3` | API 요청 최대 재시도 횟수 |
| `LOTTO_RETRY_DELAY` | `1` | 재시도 기본 대기 시간 (초, 지수 백오프 적용) |
| `LOTTO_BONUS_AVOIDANCE_WEIGHT` | `0.0` | 보너스 번호 회피 가중치 (0.0 = 비활성) |

**사용 예시:**

```bash
# 환경 변수로 포트 변경
LOTTO_WEB_PORT=9000 python main.py web

# .env 파일 사용
echo "LOTTO_WEB_PORT=9000" > .env
python main.py web
```

## 사용 가이드

### 기본 워크플로우

```bash
# 1. 당첨 번호 수집
python main.py collect

# 2. 통계 분석
python main.py analyze

# 3. 번호 추천
python main.py recommend

# 4. 알고리즘 백테스팅 (선택)
python main.py simulate

# 5. 웹 대시보드 실행
python main.py web
```

### 명령어 상세

#### `collect` — 당첨 번호 수집

동행복권 API에서 회차별 당첨 번호를 수집하여 `data/draws.csv`에 저장합니다.

```bash
python main.py collect [OPTIONS]
```

**옵션**

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--full` | (없음) | 전체 히스토리 재수집 (기존 데이터 덮어쓰기) |

**동작**

- 증분 수집 (기본): 마지막 저장된 회차 다음부터 최신 회차까지 수집
- 전체 수집 (`--full`): 1회차부터 최신까지 모든 데이터 재수집
- 재시도: API 실패 시 지수 백오프(1s, 2s, 4s)로 최대 3회 재시도
- 레이트 제한: 연속 요청 간 200ms 딜레이
- 원자적 저장: 쓰기 완료 전 부분 파일 노출 방지
- 갭 감지: 누락 회차 자동 감지 및 보고

**예시**

```bash
# 신규 데이터 증분 수집
python main.py collect

# 전체 데이터 재수집 (기존 데이터 덮어쓰기)
python main.py collect --full
```

**출력 파일**

- `data/draws.csv`: 회차별 당첨 번호
  ```
  drwNo,date,n1,n2,n3,n4,n5,n6,bonus
  1,2002-12-07,10,22,05,33,20,31,16
  ...
  ```

---

#### `analyze` — 통계 분석

수집된 데이터에서 통계 지표를 계산하여 `data/stats.json`에 저장합니다.

```bash
python main.py analyze [OPTIONS]
```

**옵션**

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--recent-window` | 20 | 최근 패턴 분석 대상 회차 수 |

**분석 지표**

1. **출현 빈도 (frequency)**
   - 각 번호(1~45)의 누적 출현 횟수 및 상대 확률
   
2. **최근 패턴 (recent_pattern)**
   - 최근 N회차 내 각 번호의 출현 횟수
   - 가장 최근 출현 회차

3. **연속 패턴 (consecutive_pattern)**
   - 각 번호의 최대 연속 출현 기간
   - 각 번호의 최대 연속 부재 기간

4. **동반 출현 (pair_analysis)**
   - 자주 함께 나오는 번호 쌍 TOP 20

5. **보너스 빈도 (bonus_frequency)**
   - 보너스 번호(1~45) 각각의 누적 출현 횟수

**예시**

```bash
# 기본 설정 (최근 20회차)
python main.py analyze

# 최근 50회차 기준 분석
python main.py analyze --recent-window 50
```

**출력 파일**

- `data/stats.json`: JSON 형식의 5가지 통계 지표

---

#### `recommend` — 번호 추천

통계 데이터를 기반으로 추천 번호 조합을 생성합니다.

```bash
python main.py recommend [OPTIONS]
```

**옵션**

| 옵션 | 기본값 | 범위 | 설명 |
|------|--------|------|------|
| `--count` | 5 | 1~20 | 추천 세트 수 |
| `--weights` | (기본값) | (실수) | 4개 가중치: w_freq,w_recent,w_pair,w_consec |

**가중치 설명**

기본 가중치: `0.4, 0.3, 0.2, 0.1` (LOTTO_RECOMMENDER_WEIGHTS로 오버라이드 가능)

- **w_freq**: 출현 빈도 가중치 (0.4) — 높을수록 자주 나오는 번호를 선호
- **w_recent**: 최근 패턴 가중치 (0.3) — 높을수록 최근에 자주 나온 번호를 선호
- **w_pair**: 동반 출현 가중치 (0.2) — 높을수록 함께 자주 나오는 쌍을 선호
- **w_consec**: 연속성 페널티 (0.1) — 높을수록 최근 연속으로 나온 번호를 회피

**추천 전략 (8가지)**

각 추천 세트에는 다음 8가지 전략 중 하나가 부여됩니다:

| 전략 | 설명 |
|------|------|
| **고빈도** | 역대 가장 자주 나온 번호를 중심으로 선택 |
| **저빈도** | 상대적으로 덜 나온 번호로 역발상 조합 구성 |
| **균형** | 전체 번호 범위에서 고르게 선택 |
| **최근편향** | 최근 20회 출현이 많은 번호를 우선 |
| **동반패턴** | 함께 자주 나온 번호 쌍을 반영 |
| **홀짝균형** | 홀수 3개, 짝수 3개로 균형 잡힌 조합 |
| **번호대균형** | 1~45 구간을 5개 영역으로 나눠 고르게 선택 |
| **핫콜드혼합** | 자주 나온 번호 3개와 오랫동안 안 나온 번호 3개를 혼합 |

**예시**

```bash
# 기본 설정 (5개 세트, 기본 가중치)
python main.py recommend

# 10개 세트 생성
python main.py recommend --count 10

# 커스텀 가중치 적용 (최근 패턴에 더 가중치)
python main.py recommend --count 5 --weights 0.2,0.5,0.2,0.1
```

---

#### `simulate` — 시뮬레이션 (백테스팅)

추천 알고리즘을 과거 데이터에 적용하여 효용성을 검증합니다.

```bash
python main.py simulate [OPTIONS]
```

**옵션**

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--rounds` | 10 | 백테스팅 대상 회차 수 |
| `--output` | (없음) | 결과를 저장할 JSON 파일 경로 |

**특징**

- **인과 안전 (Look-Ahead Safe)**: 특정 회차 추천 시, 그 회차 이후 데이터는 사용하지 않음
- 각 회차마다 독립적으로 추천을 생성하고 실제 당첨 번호와 비교

**예시**

```bash
# 기본 설정 (최근 10회차)
python main.py simulate

# 최근 50회차 백테스팅
python main.py simulate --rounds 50

# 결과를 JSON 파일로 저장
python main.py simulate --rounds 20 --output results.json
```

---

## 데이터 파일

### `data/draws.csv`

동행복권 API에서 수집한 회차별 당첨 번호.

**스키마**

```
drwNo    : 회차 번호 (1부터 순차)
date     : 당첨 날짜 (YYYY-MM-DD)
n1~n6    : 본 번호 6개 (1~45, 오름차순)
bonus    : 보너스 번호 (1~45)
```

### `data/stats.json`

`analyze` 명령으로 생성되는 통계 분석 결과 (5가지 지표).

### `data/last_sync.json`

마지막 수집 동기화 메타데이터.

**구조**

```json
{
  "last_round": 1150,
  "collected_at": "2025-01-15T10:30:00",
  "total_rounds": 1150,
  "gaps": []
}
```

- `last_round`: 마지막으로 수집된 회차 번호
- `collected_at`: 수집 완료 시각 (ISO 8601)
- `total_rounds`: 저장된 총 회차 수
- `gaps`: 감지된 누락 회차 목록

---

## 개발

### 테스트 실행

```bash
# 전체 테스트 실행
pytest

# 커버리지 리포트 포함
pytest --cov=lotto --cov-report=html

# 특정 테스트 실행
pytest tests/test_collector.py -v
```

### 품질 검사

```bash
# Ruff 린팅
ruff check .

# 타입 검사
python3.9 -m mypy lotto/ --ignore-missing-imports

# 형식 검사
ruff format --check .
```

### 디렉토리 구조

```
lotto/
├── main.py              # CLI 진입점 (typer)
├── lotto/
│   ├── __init__.py
│   ├── config.py        # 설정 외부화 (LOTTO_* 환경 변수)
│   ├── models.py        # Pydantic 모델 및 타입
│   ├── collector.py     # 데이터 수집 모듈 (원자적 저장, 갭 감지)
│   ├── analyzer.py      # 통계 분석 모듈 (보너스 빈도 포함)
│   ├── recommender.py   # 번호 추천 모듈 (8가지 전략)
│   ├── simulator.py     # 백테스팅 모듈
│   ├── scraper.py       # 블로그 크롤링 모듈
│   ├── pdf_report.py    # PDF 리포트 생성 모듈
│   └── web/
│       ├── app.py       # FastAPI 앱 초기화
│       ├── data.py      # 데이터 접근 레이어
│       └── routes/
│           ├── api.py   # REST API 라우터
│           └── pages.py # 페이지 라우터 (Jinja2)
├── tests/
│   ├── test_collector.py
│   ├── test_analyzer.py
│   ├── test_recommender.py
│   ├── test_simulator.py
│   ├── test_config.py
│   ├── test_scraper.py
│   ├── test_pdf_report.py
│   └── test_web/        # 웹 API 통합 테스트
├── data/                # 런타임 데이터 디렉토리
│   ├── draws.csv        # 당첨 번호 (자동 생성)
│   ├── stats.json       # 통계 분석 결과 (자동 생성)
│   └── last_sync.json   # 마지막 수집 메타데이터 (자동 생성)
├── pyproject.toml       # 프로젝트 설정
└── README.md            # 이 파일
```

---

## 면책 사항

**본 프로그램은 통계 분석을 기반으로 하며 당첨을 보장하지 않습니다.**

- 로또는 완전 무작위 추첨 게임입니다.
- 역사적 패턴은 미래 결과를 예측하지 못합니다.
- 본 프로그램의 추천은 참고용일 뿐이며, 실제 당첨 확률에 영향을 주지 않습니다.
- 본 프로그램 사용으로 인한 손실에 대해 책임지지 않습니다.

---

## 라이선스

MIT License

## 기여

이슈 및 풀 리퀘스트는 환영합니다.

## 참조

- 동행복권 공식 사이트: https://www.dhlottery.co.kr/lt645/result
- 당첨 통계: https://www.dhlottery.co.kr/lt645/stats
