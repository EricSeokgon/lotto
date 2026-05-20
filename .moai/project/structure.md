# 로또 번호 추천 시스템 - 프로젝트 구조

## 디렉토리 트리

```
lotto/
├── main.py                        # CLI 진입점 - 4개 서브커맨드 라우팅
├── requirements.txt               # 프로젝트 의존성 정의
├── README.md                      # 프로젝트 설명서
├── .gitignore                     # Git 추적 제외 파일 정의
│
├── lotto/                         # 메인 패키지 (비즈니스 로직)
│   ├── __init__.py                # 패키지 초기화
│   ├── models.py                  # Pydantic v2 모델 (DrawResult)
│   ├── collector.py               # 데이터 수집 (API 호출, CSV 저장)
│   ├── analyzer.py                # 통계 분석 (빈도, 최근, 연속, 페어)
│   ├── recommender.py             # 번호 추천 엔진 (점수 계산)
│   └── simulator.py               # 백테스팅/시뮬레이션 (HistoricalView)
│
├── data/                          # 데이터 저장소 (CSV/JSON)
│   ├── draws.csv                  # 수집된 당첨 번호 히스토리
│   └── stats.json                 # 계산된 통계 정보
│
├── tests/                         # 자동화 테스트 (77개 케이스, 85.25% 커버리지)
│   ├── __init__.py
│   ├── test_models.py             # 데이터 모델 테스트
│   ├── test_collector.py          # 수집 모듈 테스트 (지수 백오프 포함)
│   ├── test_analyzer.py           # 분석 모듈 테스트
│   ├── test_recommender.py        # 추천 엔진 테스트
│   └── test_simulator.py          # 시뮬레이션 테스트 (인과관계 안전성)
│
└── docs/                          # 추가 문서 (선택사항)
    ├── API.md                     # API 스펙
    └── DEVELOPMENT.md             # 개발 가이드
```

---

## 각 디렉토리 및 파일의 목적

## 각 디렉토리 및 파일의 목적

### 루트 레벨 파일

| 파일명 | 목적 | 설명 |
|--------|------|------|
| **main.py** | CLI 진입점 | 사용자 입력을 처리하고 각 기능을 조율하는 메인 스크립트 |
| **requirements.txt** | 의존성 관리 | pip로 설치할 모든 외부 라이브러리와 버전 정보 |
| **README.md** | 프로젝트 소개 | 설치 방법, 사용 예시, 기본 설명 |
| **.gitignore** | Git 제외 | 버전 관리에서 제외할 파일 및 디렉토리 (data/, __pycache__/ 등) |

### lotto/ 패키지

**목적**: 로또 시스템의 모든 비즈니스 로직을 포함하는 Python 패키지

#### 모듈별 설명

| 모듈명 | 책임 | 주요 기능 |
|--------|------|----------|
| **collector.py** | 데이터 수집 | dhlottery.co.kr API 호출, JSON 파싱, CSV 저장 |
| **analyzer.py** | 통계 분석 | 빈도 분석, 패턴 인식, 점수 계산 |
| **recommender.py** | 번호 생성 | 추천 알고리즘 구현, 조합 생성 |
| **simulator.py** | 검증 | 백테스트 실행, 성과 계산, 리포트 생성 |
| **models.py** | 데이터 정의 | 데이터클래스 및 타입 정의 |

### data/ 디렉토리

**목적**: 수집된 데이터와 계산된 통계 저장

- **history.csv**: 
  - 내용: 회차(drwNo), 당첨 번호 6개, 보너스 번호, 당첨일
  - 형식: CSV (쉼표로 구분)
  - 크기: 일반적으로 100-200KB
  - 접근: collector.py가 갱신, analyzer.py가 읽음

- **stats.json**:
  - 내용: 빈도 데이터, 평균, 표준편차, 패턴 분석 결과
  - 형식: JSON
  - 크기: 일반적으로 50KB 이하
  - 접근: analyzer.py가 생성, recommender.py가 사용

### output/ 디렉토리

**목적**: 실행 결과 저장 (사용자 생성 파일)

- **recommendations/**:
  - 파일명: recommendation_YYYYMMDD_HHMMSS.json
  - 내용: 추천된 번호 6개 조합, 각각의 신뢰도 점수
  - 사용: 사용자가 구매 결정 시 참고

- **reports/**:
  - 파일명: simulation_YYYYMMDD_HHMMSS.json
  - 내용: 백테스트 결과, 성공률, 기대 수익률

### tests/ 디렉토리

**목적**: 자동화된 테스트 코드

- 각 모듈에 대응하는 테스트 파일
- pytest 프레임워크 사용
- 최소 85% 코드 커버리지 목표

## 주요 파일 위치

### CLI 진입점
```
main.py
```
사용자가 터미널에서 실행하는 파일. 모든 명령어의 라우팅 담당.

```bash
python main.py collect      # 데이터 수집
python main.py analyze      # 통계 분석
python main.py recommend    # 번호 추천
python main.py simulate     # 시뮬레이션
```

### 데이터 저장 경로
```
data/history.csv           # 당첨 번호 히스토리 (읽기/쓰기)
data/stats.json            # 계산된 통계 (읽기/쓰기)
```

### 결과 출력 경로
```
output/recommendations/recommendation_*.json   # 추천 결과
output/reports/simulation_*.json               # 시뮬레이션 결과
```

## 모듈 간 데이터 흐름

### 데이터 파이프라인

```
┌─────────────────────────────────────────────────────────────┐
│                      1. 수집 (Collection)                    │
│  main.py → collector.py → dhlottery.co.kr API               │
│                          ↓                                   │
│                   data/history.csv 저장                      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                      2. 분석 (Analysis)                      │
│  main.py → analyzer.py → 읽기: data/history.csv             │
│                          ↓                                   │
│                  data/stats.json 저장                        │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    3. 추천 (Recommendation)                  │
│  main.py → recommender.py → 읽기: data/stats.json           │
│                             ↓                                │
│              output/recommendations/*.json 저장             │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    4. 검증 (Simulation)                      │
│  main.py → simulator.py → 읽기: data/history.csv + 추천번호  │
│                          ↓                                   │
│               output/reports/simulation_*.json 저장          │
└─────────────────────────────────────────────────────────────┘
```

## 5개 핵심 모듈 상세 설명

### 1. models.py - 데이터 모델 (Pydantic v2)

**책임**: 입출력 데이터 스키마 정의 및 검증

**핵심 모델**:

```python
DrawResult:
  - draw_no: int                # 회차 번호
  - date: datetime              # 당첨일
  - numbers: list[int]          # 당첨 번호 6개
  - bonus: int                  # 보너스 번호
```

**주요 특징**:
- Pydantic v2 기반 자동 검증
- 타입 안정성 보장
- JSON 직렬화/역직렬화 지원

---

### 2. collector.py - 데이터 수집 모듈

**책임**: API에서 당첨 번호 수집 및 CSV 저장

**주요 기능**:

| 기능 | 설명 |
|------|------|
| `collect(full=False)` | API 호출하여 데이터 수집 |
| 지수 백오프 (@MX:WARN) | 네트워크 실패 시 자동 재시도 |
| CSV 저장 | `data/draws.csv`에 저장 |

**API 엔드포인트**:
- 주소: `dhapi.co.kr/wplotData/getLottoNumber`
- 응답: JSON 형식의 당첨 번호 데이터

**데이터 흐름**:
```
동행복권 API → JSON 파싱 → DrawResult 모델 변환 → CSV 저장
```

---

### 3. analyzer.py - 통계 분석 모듈 (@MX:ANCHOR)

**책임**: 수집된 데이터를 기반으로 4가지 통계 지표 계산

**분석 함수** `analyze()` (fan_in ≥ 3):

| 지표 | 계산 방식 | 출력 |
|------|----------|------|
| **Frequency** | 1~45번 각 번호의 절대/상대 빈도 | 빈도 배열 |
| **Recent** | 최근 N회차(기본 10) 내 번호 빈도 | 최근 빈도 배열 |
| **Consecutive** | 연속 출현/부재 추적 | 연속성 스코어 |
| **Pairs** | NumPy 행렬로 상위 20 조합 도출 | 페어 리스트 |

**결과 저장**: `data/stats.json`

**알고리즘 복잡도**:
- Frequency: O(n) 선형
- Pairs: O(n²) 행렬 연산 (NumPy 최적화)

---

### 4. recommender.py - 번호 추천 엔진 (@MX:ANCHOR)

**책임**: 가중 점수를 기반으로 추천 번호 세트 생성

**추천 함수** `recommend()` (fan_in ≥ 3):

**점수 계산 공식**:
```
최종 점수 = (빈도×0.4) + (최근×0.3) + (페어×0.2) + (연속×0.1)
```

**기능**:

| 기능 | 설명 |
|------|------|
| 기본 추천 | 기본 가중치로 5개 세트 생성 |
| 커스텀 가중치 | `--weights` 옵션으로 조정 |
| 5가지 전략 | 빈도 중심, 최근 중심, 균형형 등 라벨링 |
| 신뢰도 점수 | 0~1.0 범위의 신뢰도 스코어 |

**출력**: 추천 번호 + 전략 라벨 + 신뢰도 점수

---

### 5. simulator.py - 백테스팅 모듈 (@MX:ANCHOR)

**책임**: 과거 데이터 대비 추천 알고리즘의 성능 검증

**핵심 클래스** `HistoricalView` (인과관계 안전성):

**설계 원칙**:
- 미래 데이터 사용 방지 (look-ahead bias 차단)
- 각 회차에서 그 당시의 데이터만으로 분석
- 인과관계 위반 없는 현실적인 백테스트

**성능 평가 항목**:

| 항목 | 설명 |
|------|------|
| 맞춘 번호 개수 | 0~6개 분포 |
| 당첨 등급 | 1등~5등, 낙첨 |
| 기대 수익률 | 예상 ROI 계산 |
| 통계 요약 | 평균, 표준편차 |

**결과 출력**: CSV 형식 및 CLI 표

## 모듈 간 의존성 그래프

```
┌─────────────────────────────────────────────────────────────┐
│                        main.py (CLI)                        │
│              (4개 서브커맨드 라우팅 담당)                     │
└──────────────────────────────────────────────────────────────┘
        │           │            │             │
        ↓           ↓            ↓             ↓
   collector.py analyzer.py recommender.py simulator.py
        │           │            │             │
        └───────────┴────────────┴─────────────┘
                    │
                    ↓
              models.py
        (Pydantic v2 DrawResult)
```

---

## 파일 간 읽기/쓰기 관계

| 모듈 | 의존성 라이브러리 | 읽기 | 쓰기 |
|------|-----------------|------|------|
| **main.py** | Typer, Rich | - | CLI 출력 |
| **models.py** | Pydantic v2 | - | 타입 정의 |
| **collector.py** | Requests | - | data/draws.csv |
| **analyzer.py** | Pandas, NumPy | data/draws.csv | data/stats.json |
| **recommender.py** | NumPy | data/stats.json | 추천 결과 (stdout) |
| **simulator.py** | Pandas | data/draws.csv + 추천번호 | 시뮬레이션 결과 |

---

## 계층 구조 (Layered CLI Architecture)

```
┌─────────────────────────────────────┐
│        CLI Layer (main.py)          │  ← 사용자 입력 처리
└─────────────────────────────────────┘
           ↓
┌─────────────────────────────────────┐
│    Business Logic Layer             │  ← 4개 핵심 모듈
│  (collector, analyzer, recommender) │
│  (simulator, models)                │
└─────────────────────────────────────┘
           ↓
┌─────────────────────────────────────┐
│    Data Access Layer                │  ← 파일 I/O
│  (CSV, JSON 읽기/쓰기)              │
└─────────────────────────────────────┘
           ↓
┌─────────────────────────────────────┐
│    External Layer                   │  ← API, 외부 서비스
│  (동행복권 API)                     │
└─────────────────────────────────────┘
```

---

## 테스트 커버리지 (85.25%)

**총 77개 테스트 케이스**:

| 모듈 | 테스트 개수 | 주요 항목 |
|------|-----------|---------|
| **models** | 8개 | 데이터 검증, 직렬화 |
| **collector** | 18개 | API 호출, 재시도 로직, CSV 저장 |
| **analyzer** | 20개 | 4가지 통계 지표 계산 검증 |
| **recommender** | 18개 | 점수 계산, 가중치 조정, 전략 라벨링 |
| **simulator** | 13개 | 백테스트, 인과관계 검증, 성과 계산 |

---

## 아키텍처 패턴

### 1. 데이터 흐름 (파이프라인)

```
수집 → 분석 → 추천 → 검증

[API] → [CSV] → [JSON] → [추천] → [결과]
```

각 단계는 독립적으로 실행 가능하며, 이전 단계의 결과에 의존합니다.

### 2. 책임 분리 (Single Responsibility)

- **collector**: 데이터 수집만 담당
- **analyzer**: 통계 계산만 담당
- **recommender**: 추천 생성만 담당
- **simulator**: 검증만 담당
- **models**: 데이터 스키마만 정의

### 3. 의존성 역전 원칙 (DIP)

- 각 모듈은 models.py에 정의된 추상 데이터 타입에 의존
- 구체적인 구현에 의존하지 않음

---

## 확장 계획

### v1.0.0 (현재 - 완성)
- 기본 4가지 기능 구현
- CSV/JSON 파일 기반 데이터 관리
- 77개 테스트, 85.25% 커버리지

### v1.1.0 (단기)
- 웹 대시보드 인터페이스
- 실시간 알림 기능
- 사용자 설정 저장

### v2.0.0 (중기)
- 머신러닝 기반 고급 분석
- 데이터베이스 지원 (선택사항)
- API 서버 제공

### v3.0.0 (장기)
- 다국가 로또 지원
- 사용자 커뮤니티 기능

---

**버전**: 1.0.0 완성  
**마지막 업데이트**: 2026-05-20  
**테스트 커버리지**: 85.25% (77/86 케이스)
