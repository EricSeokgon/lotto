# 로또 번호 추천 시스템 - 기술 스택 및 개발 가이드

## 프로젝트 개요

**프로젝트명**: 로또 번호 추천 시스템  
**타입**: Python CLI 애플리케이션  
**버전**: 1.0.0 완성  
**주요 언어**: Python 3.11+  
**테스트**: 77개 케이스, 85.25% 커버리지

---

## 개발 환경 요구사항

### 시스템 사양

| 항목 | 최소 | 권장 |
|------|------|------|
| **Python 버전** | 3.11 | 3.12+ |
| **메모리** | 512MB | 2GB+ |
| **디스크** | 100MB | 500MB+ |
| **인터넷** | 수집 시 필수 | 항상 권장 |

### 지원 운영체제

- Windows 10/11 (x86_64)
- macOS 10.14+ (Intel/Apple Silicon)
- Linux (Ubuntu 18.04+, CentOS 7+)

---

## 핵심 의존성

### 필수 라이브러리

#### requests (HTTP 통신)
```
목적: dhlottery.co.kr API로부터 당첨 번호 데이터 조회
버전: >= 2.28.0
기능: 
  - JSON API 호출
  - HTTP 요청/응답 처리
  - 에러 핸들링
용법:
  import requests
  response = requests.get('https://www.dhlottery.co.kr/lt645/result')
  data = response.json()
```

#### pandas (데이터 조작 및 분석)
```
목적: 히스토리 데이터 처리, 통계 계산, 분석
버전: >= 2.0.0
기능:
  - CSV 파일 읽기/쓰기
  - DataFrame 형태의 데이터 조작
  - 빈도 분석 (value_counts)
  - 통계 함수 (mean, std, quantile)
용법:
  import pandas as pd
  df = pd.read_csv('data/history.csv')
  frequencies = df['number'].value_counts()
```

#### numpy (수치 계산 및 선형대수)
```
목적: 통계 계산, 행렬 연산, 알고리즘 최적화
버전: >= 1.23.0
기능:
  - 고속 배열 연산
  - 통계 함수 (mean, std, percentile)
  - 난수 생성
  - 가중치 기반 선택
용법:
  import numpy as np
  scores = np.array([0.8, 0.7, 0.9, 0.6])
  weighted_numbers = np.random.choice(range(1,46), 6, p=weights)
```

#### rich (CLI 출력 포맷팅)
```
목적: 터미널에서 가독성 높은 출력 표현
버전: >= 13.0.0
기능:
  - 색상 지원 (컬러 출력)
  - 테이블 포맷팅
  - 진행 표시줄
  - 박스/구분선 그리기
용법:
  from rich.table import Table
  table = Table(title="추천 번호")
  table.add_column("조합", style="cyan")
  table.add_row("1, 5, 12, 23, 34, 43")
  console.print(table)
```

#### typer (CLI 인자 파싱)
```
목적: 명령행 인터페이스 구현, 사용자 입력 처리
버전: >= 0.9.0
기능:
  - 서브 명령어 정의
  - 인자 타입 검증
  - 도움말 자동 생성
  - 옵션 관리
용법:
  import typer
  app = typer.Typer()
  
  @app.command()
  def collect(limit: int = 5):
      '''당첨 번호 수집'''
      ...
  
  if __name__ == "__main__":
      app()
```

### 개발 및 테스트 도구

#### pytest (단위 테스트)
```
목적: 자동화된 테스트 실행 및 관리
버전: >= 7.0.0
사용:
  pytest tests/              # 모든 테스트 실행
  pytest --cov              # 코드 커버리지 측정
  pytest -v                 # 상세 출력
목표: 85% 이상 코드 커버리지
```

#### ruff (코드 린터)
```
목적: 코드 스타일 검사 및 오류 발견
버전: >= 0.1.0
사용:
  ruff check lotto/         # 린트 검사
  ruff check --fix          # 자동 수정
주요 규칙:
  - PEP 8 코드 스타일
  - 사용하지 않는 임포트 감지
  - 변수명 규칙
```

#### mypy (정적 타입 검사)
```
목적: Python 코드의 타입 안정성 검증
버전: >= 1.0.0
사용:
  mypy lotto/               # 타입 검사 실행
장점:
  - 타입 오류 조기 발견
  - IDE 자동완성 개선
  - 코드 문서화 효과
```

#### black (코드 포매터)
```
목적: 일관된 코드 스타일 유지
버전: >= 23.0.0
사용:
  black lotto/              # 코드 자동 포매팅
특징:
  - 결정론적 포매팅
  - 라인 길이: 88자 (설정 가능)
  - 주석 보존
```

## 의존성 설정 (requirements.txt)

```
# 핵심 라이브러리
requests>=2.28.0
pandas>=2.0.0
numpy>=1.23.0
rich>=13.0.0
typer[all]>=0.9.0

# 개발 및 테스트
pytest>=7.0.0
pytest-cov>=4.0.0
ruff>=0.1.0
mypy>=1.0.0
black>=23.0.0
```

## 아키텍처 패턴

### 파이프라인 아키텍처 (Pipeline Architecture)

로또 시스템은 선형 파이프라인으로 구성되며, 각 단계는 이전 단계의 결과를 입력으로 받습니다.

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Collect    │───→│   Analyze    │───→│ Recommend    │───→│  Simulate    │
│   (수집)     │    │   (분석)     │    │  (추천)      │    │  (검증)      │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
     ↓                   ↓                    ↓                   ↓
  API 호출         CSV 데이터          통계 데이터         추천 번호
  ↓               ↓                    ↓                   ↓
history.csv    stats.json         recommendations/    reports/
```

### 계층 구조

```
┌────────────────────────────────────────┐
│           CLI Layer (main.py)          │
│      (사용자 입력 처리 및 라우팅)       │
└────────────────────────────────────────┘
            ↓ ↓ ↓ ↓
┌────────────────────────────────────────┐
│      Business Logic Layer (lotto/)     │
│  - collector.py (데이터 수집)          │
│  - analyzer.py (통계 분석)             │
│  - recommender.py (추천 알고리즘)      │
│  - simulator.py (백테스트)             │
└────────────────────────────────────────┘
            ↓
┌────────────────────────────────────────┐
│       Data Model Layer (models.py)     │
│    (데이터 타입 및 구조 정의)          │
└────────────────────────────────────────┘
            ↓
┌────────────────────────────────────────┐
│      Persistence Layer                 │
│  - CSV 파일 (data/)                   │
│  - JSON 파일 (output/)                │
└────────────────────────────────────────┘
```

## 데이터 흐름

### 1단계: 수집 (Collection)

```
입력: 없음 (또는 회차 범위)
처리:
  1. API 연결 확인
  2. JSON 응답 파싱
  3. 데이터 검증
출력: data/history.csv
  - 회차 번호
  - 당첨 번호 6개
  - 보너스 번호
  - 당첨일
```

### 2단계: 분석 (Analysis)

```
입력: data/history.csv
처리:
  1. 데이터 로드
  2. 각 번호의 출현 빈도 계산
  3. 최근 n회 패턴 분석
  4. 연속 번호 조합 분석
  5. 기본 통계 계산 (평균, 표준편차)
출력: data/stats.json
  - 빈도 데이터
  - 패턴 지표
  - 점수 기준
```

### 3단계: 추천 (Recommendation)

```
입력: data/stats.json
처리:
  1. 가중치 기반 점수 계산
     - 빈도 점수 (40%)
     - 최근성 점수 (30%)
     - 다양성 점수 (30%)
  2. 상위 점수 번호 선택
  3. 번호 조합 생성
  4. 신뢰도 점수 계산
출력: output/recommendations/recommendation_*.json
  - 추천 조합 (최대 10개)
  - 각 조합의 신뢰도 점수
  - 생성 시각
  - 알고리즘 버전
```

### 4단계: 검증 (Simulation)

```
입력: 
  - data/history.csv (과거 데이터)
  - 추천 번호 조합
처리:
  1. 각 추천 조합을 과거 데이터와 비교
  2. 맞춘 번호 개수 집계
  3. 성공률, 기대 수익률 계산
  4. 성과 리포트 생성
출력: output/reports/simulation_*.json
  - 적중 분포 (0~6개)
  - 당첨 확률 추정
  - 기대 수익률
  - 추천 신뢰도 평가
```

## 빌드 및 실행 가이드

### 초기 설정 (3단계)

#### 1단계: 파이썬 환경 준비

```bash
# Python 버전 확인 (3.11 이상 필수)
python --version

# 프로젝트 디렉토리 이동
cd lotto/

# 가상환경 생성 (권장)
python -m venv venv

# 가상환경 활성화
# ▶ Windows
venv\Scripts\activate

# ▶ macOS/Linux
source venv/bin/activate
```

#### 2단계: 의존성 설치

```bash
# 모든 필수 라이브러리 설치
pip install -r requirements.txt

# 설치 확인
pip list | grep -E "requests|pandas|numpy|rich|typer"

# 또는 uv를 사용하는 경우 (더 빠름)
uv pip install -r requirements.txt
```

#### 3단계: 디렉토리 구조 초기화

```bash
# 필수 디렉토리 생성
mkdir -p data
```

---

### 명령어 실행

#### 수집 (Collect)

```bash
# 증분 수집 (새로운 데이터만)
python main.py collect

# 전체 데이터 재수집
python main.py collect --full
```

**결과**: `data/draws.csv` 생성/갱신

#### 분석 (Analyze)

```bash
# 기본 분석 (최근 10회차 기준)
python main.py analyze

# 커스텀 윈도우로 분석
python main.py analyze --recent-window 20
```

**결과**: `data/stats.json` 생성

#### 추천 (Recommend)

```bash
# 기본 설정: 5개 세트, 기본 가중치
python main.py recommend

# 커스텀 개수
python main.py recommend --count 10

# 커스텀 가중치 (빈도, 최근, 페어, 연속)
python main.py recommend --weights 0.5,0.3,0.1,0.1
```

**결과**: 터미널 출력

#### 시뮬레이션 (Simulate)

```bash
# 모든 과거 회차 시뮬레이션
python main.py simulate

# 최근 N회차만 시뮬레이션
python main.py simulate --rounds 100

# 결과를 CSV로 저장
python main.py simulate --output results.csv
```

**결과**: 터미널 표 + 선택적으로 CSV 파일

#### 도움말

```bash
python main.py --help
python main.py collect --help
python main.py analyze --help
python main.py recommend --help
python main.py simulate --help
```

---

### 테스트 실행 및 품질 검사

#### pytest - 단위 테스트

```bash
# 모든 테스트 실행
pytest tests/

# 커버리지 리포트 포함
pytest --cov=lotto --cov-report=html tests/

# HTML 리포트 보기
open htmlcov/index.html  # macOS
start htmlcov/index.html # Windows
xdg-open htmlcov/index.html # Linux

# 특정 모듈만 테스트
pytest tests/test_analyzer.py -v

# 상세 출력
pytest -v tests/
```

**목표**: 85% 이상 커버리지

#### ruff - 코드 린팅

```bash
# 코드 스타일 검사
ruff check lotto/

# 자동 수정 (안전한 이슈만)
ruff check --fix lotto/

# 정렬 및 임포트 최적화
ruff check --select=I,F lotto/ --fix
```

#### mypy - 정적 타입 검사

```bash
# 전체 타입 검사 (strict 모드)
mypy lotto/ --strict

# 기본 타입 검사
mypy lotto/
```

#### black - 코드 포매팅

```bash
# 코드 포매팅 확인
black --check lotto/

# 자동 포매팅
black lotto/

# 라인 길이 지정 (기본 88)
black lotto/ --line-length=100
```

#### 통합 품질 체크

```bash
# 모든 검사를 순차 실행
ruff check lotto/ && \
mypy lotto/ && \
pytest --cov=lotto tests/ && \
black --check lotto/
```

---

## 성능 특성 및 최적화

### 메모리 프로필

| 작업 | 메모리 사용 | 비고 |
|------|-----------|------|
| 기본 상태 | ~30MB | 프로세스 기본 |
| 히스토리 로드 | 50-100MB | 1000회 이상 데이터 |
| 통계 분석 | 추가 30-50MB | NumPy 배열 |
| 추천 생성 | 추가 20MB | 점수 계산 |
| **최대 피크** | ~150MB | 모든 작업 동시 진행 |

### 실행 시간

| 작업 | 소요 시간 | 변수 |
|------|----------|------|
| **collect** | 1-5초 | 네트워크 속도, API 응답 |
| **analyze** | 1-2초 | 데이터 크기 (회차 수) |
| **recommend** | <500ms | 추천 개수 |
| **simulate** | 2-10초 | 히스토리 크기 |

### 확장성 제한

- **최대 히스토리**: 메모리 허용 범위 내 무제한
- **추천 개수**: 1-100개 지원
- **병렬 처리**: 미지원 (순차 처리)
- **네트워크 병목**: API 응답 시간 의존

## 보안 고려사항

### API 통신

| 항목 | 상태 | 설명 |
|------|------|------|
| **HTTPS** | 지원 | dhlottery.co.kr은 HTTPS 사용 |
| **인증** | 불필요 | 공개 API (토큰/키 불필요) |
| **데이터 검증** | 구현 | Pydantic 자동 검증 |
| **타임아웃** | 구현 | 연결 타임아웃 5초 설정 |

### 로컬 저장소

- **암호화**: 미제공 (평문 저장)
- **접근 제어**: OS 파일 권한에 의존
- **백업**: 사용자 책임
- **권장사항**: 백업 스크립트 사용

### 사용자 입력 검증

```python
# 예: 회차 번호 범위 검증
if draw_no < 1 or draw_no > 1145:
    raise ValueError("Invalid draw number")

# 예: 번호 범위 검증 (1-45)
if not (1 <= number <= 45):
    raise ValueError("Number must be 1-45")

# 예: 가중치 합계 검증
if abs(sum(weights) - 1.0) > 0.01:
    raise ValueError("Weights must sum to 1.0")
```

---

## 주요 설계 결정사항

### 1. 파일 기반 저장소 선택

**의사결정**: CSV/JSON 파일 기반 (데이터베이스 미사용)

**근거**:
- 간단한 설치 (외부 DB 서버 불필요)
- 높은 접근성 (스프레드시트 소프트웨어로 열기 가능)
- 데이터 이동 용이 (파일 복사로 백업 가능)
- 쿼리 성능이 중요하지 않은 분석 용도

**트레이드오프**: 대규모 데이터 쿼리 시 성능 저하 (현재 규모 1000회차 내 문제없음)

### 2. 지수 백오프 재시도 메커니즘 (@MX:WARN)

**의사결정**: Requests 라이브러리에 재시도 로직 추가

**알고리즘**:
```python
# 지수 백오프: 1초 → 2초 → 4초 → 8초
wait_time = 2^(attempt - 1)  # 최대 4회 시도
```

**목적**: 일시적인 네트워크 오류 자동 복구

### 3. 가중치 기반 점수 시스템

**계산식**:
```
최종 점수 = (빈도×0.4) + (최근×0.3) + (페어×0.2) + (연속×0.1)
```

**설계 원칙**:
- 각 지표를 0~1.0 범위로 정규화
- 사용자가 `--weights` 옵션으로 커스터마이징 가능
- 가중치 합계가 1.0 검증

### 4. HistoricalView 클래스 (인과관계 안전성)

**목적**: 백테스트에서 미래 데이터 사용 방지 (look-ahead bias)

**구현**:
```python
class HistoricalView:
    """각 회차에서 그 당시 데이터만으로 분석"""
    def get_stats_at(self, draw_index):
        # draw_index 이전 데이터만 사용
        historical_data = draws[:draw_index]
        return analyze(historical_data)
```

**중요성**: 현실적인 백테스트 결과 보장

---

## 외부 서비스 의존성

### 동행복권 API

| 항목 | 상세 |
|------|------|
| **서비스** | 로또 당첨 번호 조회 |
| **엔드포인트** | dhapi.co.kr/wplotData/getLottoNumber |
| **제공자** | 동행복권 (한국) |
| **가용성** | 매주 토요일 이후 업데이트 |
| **비용** | 무료 |
| **인증** | 불필요 |
| **형식** | JSON |
| **속도** | ~1-2초 (회차당) |

**대체 방안**: 웹 스크래핑 (마지막 수단)

---

## 의존성 라이센스

| 라이브러리 | 라이센스 | 용도 |
|-----------|---------|------|
| requests | Apache 2.0 | HTTP 통신 |
| pandas | BSD 3-Clause | CSV 처리 |
| numpy | BSD 3-Clause | 수치 계산 |
| rich | MIT | 터미널 출력 |
| typer | MIT | CLI 프레임워크 |
| Pydantic | MIT | 데이터 검증 |
| **테스트** | | |
| pytest | MIT | 단위 테스트 |
| pytest-cov | MIT | 커버리지 |
| ruff | MIT | 린팅 |
| mypy | MIT | 타입 검사 |
| black | MIT | 포매팅 |

**모두 오픈소스 호환 라이센스** (상업 용도 가능)

---

## 향후 개선 계획

### v1.1.0 (단기 - 1~2개월)

- 웹 대시보드 (Flask/FastAPI)
- 실시간 알림 (pushover/이메일)
- 설정 파일 저장 (YAML/JSON)

### v2.0.0 (중기 - 3~6개월)

- 머신러닝 알고리즘 (scikit-learn, TensorFlow)
- 데이터베이스 지원 (PostgreSQL, SQLite)
- REST API 서버 제공

### v3.0.0 (장기 - 6개월+)

- 다국가 로또 지원 (미국, 유럽 등)
- 사용자 커뮤니티 기능
- 고급 시각화 (matplotlib, plotly)

---

**버전**: 1.0.0 완성  
**마지막 업데이트**: 2026-05-20  
**테스트 커버리지**: 85.25%
