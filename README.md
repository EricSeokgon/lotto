# 로또 번호 추천 프로그램

[![Python 3.9+](https://img.shields.io/badge/Python-3.9+-blue)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/Tests-77-green)](./tests/)
[![Coverage](https://img.shields.io/badge/Coverage-85.25%-green)](#)

통계 분석 기반의 로또 번호 추천 CLI 도구입니다. 동행복권 공식 데이터를 수집하여 다각적인 통계 분석을 수행하고, 가중치 기반 알고리즘으로 추천 번호를 생성합니다. 또한 과거 데이터에 대한 백테스팅으로 알고리즘의 유효성을 검증합니다.

## 개요

### 주요 기능

- **당첨 번호 수집**: 동행복권 API에서 회차별 당첨 번호 자동 수집
- **통계 분석**: 4가지 분석 지표로 번호 패턴 파악
  - 출현 빈도: 각 번호의 누적 출현 횟수
  - 최근 패턴: 최근 N회차 내 출현 경향
  - 연속 패턴: 연속 출현/부재 계수
  - 동반 출현: 자주 함께 나오는 번호 쌍
- **다중 가중치 추천**: 사용자 정의 가중치로 유연한 추천
- **인과 안전 백테스팅**: 과거 데이터로 알고리즘 효용성 검증

### 특징

- 외부 데이터베이스 불필요 — 로컬 CSV/JSON 파일 기반
- 순수 CLI 도구 — 별도 인프라 필수 없음
- 타입 안전성 — Python 3.9+ 호환
- 높은 커버리지 — 77개 테스트, 85.25% 라인 커버리지

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
- **pydantic**: 데이터 검증
- **pytest**: 테스트 프레임워크 (개발용)

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

**예시**

```bash
# 기본 설정 (최근 20회차)
python main.py analyze

# 최근 50회차 기준 분석
python main.py analyze --recent-window 50
```

**출력 파일**

- `data/stats.json`: JSON 형식의 4가지 통계 지표

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

기본 가중치: `0.4, 0.3, 0.2, 0.1`

- **w_freq**: 출현 빈도 가중치 (0.4)
  - 높을수록 자주 나오는 번호를 선호
  
- **w_recent**: 최근 패턴 가중치 (0.3)
  - 높을수록 최근에 자주 나온 번호를 선호
  
- **w_pair**: 동반 출현 가중치 (0.2)
  - 높을수록 함께 자주 나오는 쌍을 선호
  
- **w_consec**: 연속성 페널티 (0.1)
  - 높을수록 최근 연속으로 나온 번호를 회피

**전략 레이블**

각 추천 세트에는 점수 분포 특성에 따라 5가지 전략 중 하나가 부여됩니다:

- **고빈도**: 출현 빈도가 높은 번호 위주
- **저빈도**: 출현 빈도가 낮은 번호 위주 (도박성)
- **균형**: 모든 지표가 균형잡힌 조합
- **최근편향**: 최근에 자주 나온 번호 위주
- **동반패턴**: 함께 자주 나오는 번호 쌍 위주

**예시**

```bash
# 기본 설정 (5개 세트, 기본 가중치)
python main.py recommend

# 10개 세트 생성
python main.py recommend --count 10

# 커스텀 가중치 적용 (최근 패턴에 더 가중치)
python main.py recommend --count 5 --weights 0.2,0.5,0.2,0.1

# 저빈도 전략 강조
python main.py recommend --weights 0.0,0.2,0.2,0.6
```

**출력 형식**

```
┏━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┓
┃ 세트 ┃ 번호                   ┃ 전략   ┃
┡━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━┩
│  1  │  7, 12, 23, 31, 38, 42 │ 균형   │
│  2  │  3,  9, 15, 27, 35, 44 │ 최근편향│
└─────┴────────────────────────┴────────┘

이 추천은 통계 기반이며 당첨을 보장하지 않습니다.
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

**매칭 등급**

| 일치 개수 | 등급 | 상금 (참고) |
|----------|------|-----------|
| 6개 | 1등 | 1등 당첨금 |
| 5개 + 보너스 | 2등 | 2등 당첨금 |
| 5개 | 3등 | 5만원 |
| 4개 | 4등 | 5천원 |
| 3개 | 5등 | 5백원 |
| < 3개 | 낙첨 | — |

**예시**

```bash
# 기본 설정 (최근 10회차)
python main.py simulate

# 최근 50회차 백테스팅
python main.py simulate --rounds 50

# 결과를 JSON 파일로 저장
python main.py simulate --rounds 20 --output results.json
```

**출력 형식**

```
┏━━━━┳━━━━┓
┃ 등수┃ 횟수┃
┡━━━━╇━━━━┩
│ 1등 │  0 │
│ 2등 │  0 │
│ 3등 │  1 │
│ 4등 │  3 │
│ 5등 │  8 │
└────┴────┘

적중률 (5등 이상): 40.00%
총 시뮬레이션 회차: 10
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

**예시**

```csv
drwNo,date,n1,n2,n3,n4,n5,n6,bonus
1,2002-12-07,10,22,05,33,20,31,16
2,2002-12-14,08,10,24,27,33,41,03
...
```

### `data/stats.json`

`analyze` 명령으로 생성되는 통계 분석 결과.

**구조**

```json
{
  "frequency": {
    "1": {"count": 150, "probability": 0.125},
    ...
  },
  "recent_pattern": {
    "1": {"count": 3, "latest_round": 1250},
    ...
  },
  "consecutive_pattern": {
    "1": {"max_consecutive": 5, "max_absent": 15},
    ...
  },
  "pair_analysis": [
    {"numbers": [7, 23], "count": 12},
    ...
  ]
}
```

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

# 타입 검사 (mypy --strict)
mypy --strict lotto main.py

# 형식 검사
ruff format --check .
```

### 디렉토리 구조

```
lotto/
├── main.py              # CLI 진입점 (typer)
├── lotto/
│   ├── __init__.py
│   ├── models.py        # Pydantic 모델 및 타입
│   ├── collector.py     # 데이터 수집 모듈
│   ├── analyzer.py      # 통계 분석 모듈
│   ├── recommender.py   # 번호 추천 모듈
│   └── simulator.py     # 백테스팅 모듈
├── tests/
│   ├── test_collector.py
│   ├── test_analyzer.py
│   ├── test_recommender.py
│   └── test_simulator.py
├── data/                # 런타임 데이터 디렉토리
│   ├── draws.csv        # 당첨 번호 (자동 생성)
│   └── stats.json       # 통계 분석 결과 (자동 생성)
├── pyproject.toml       # 프로젝트 설정
└── README.md            # 이 파일
```

---

## 면책 사항

⚠️ **본 프로그램은 통계 분석을 기반으로 하며 당첨을 보장하지 않습니다.**

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
