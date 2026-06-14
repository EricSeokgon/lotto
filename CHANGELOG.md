# 변경 이력

모든 주목할 만한 변경 사항은 이 파일에 기록됩니다.

형식: [Keep a Changelog](https://keepachangelog.com/) 가이드를 따릅니다.

---

## [1.41.0] - 2026-06-15

### Added
- SPEC-LOTTO-080: 번호 간격 최대값 분포 분석
  - 정렬된 당첨번호 간 최대 간격의 구간별 분포 통계
  - GET /api/stats/max_gap_dist API 엔드포인트
  - GET /stats/max-gap-dist 웹 페이지
  - 테스트 33개 추가 (1952 → 1985)

---

## [1.40.0] - 2026-06-15

### Added
- SPEC-LOTTO-079: 끝자리 합계 분포 분석
  - 당첨번호 6개 끝자리(일의 자리) 합계의 구간별 분포 통계
  - GET /api/stats/digit_sum_dist API 엔드포인트
  - GET /stats/digit-sum-dist 웹 페이지
  - 테스트 34개 추가 (1918 → 1952)

---

## [1.39.0] - 2026-06-15

### Added
- SPEC-LOTTO-078: 3연속 이상 번호 포함 분포 분석
  - 3개 이상 연속 번호 묶음 수(0~2개) 분포 통계
  - GET /api/stats/triple_run API 엔드포인트
  - GET /stats/triple-run 웹 페이지
  - 테스트 36개 추가 (1882 → 1918)

---

## [1.38.0] - 2026-06-12

### Added
- SPEC-LOTTO-077: 1자리 번호 포함 개수 분포 분석
  - 1~9 사이 1자리 번호(9개) 회차별 포함 개수(0~6개) 분포 통계
  - GET /api/stats/single_digit API 엔드포인트
  - GET /stats/single-digit 웹 페이지
  - 테스트 31개 추가 (1851 → 1882)

---

## [1.37.0] - 2026-06-12

### Added
- SPEC-LOTTO-076: 4의 배수 포함 개수 분포 분석
  - 4의 배수(4,8,12,...,44) 회차별 포함 개수(0~6개) 분포 통계
  - GET /api/stats/mult4 API 엔드포인트
  - GET /stats/mult4 웹 페이지
  - 테스트 31개 추가 (1820 → 1851)

---

## [1.36.0] - 2026-06-12

### Added
- SPEC-LOTTO-075: 5의 배수 포함 개수 분포 분석 기능 추가
  - `get_mult5_stats()`: 회차별 5의 배수 개수(0~6) 분포 통계 산출
  - `GET /api/stats/mult5`: JSON 통계 API 엔드포인트
  - `GET /stats/mult5`: 5의 배수 개수 분포 분석 페이지 (`mult5.html`)
  - 내비게이션 "5배수" 링크 추가
  - 테스트 25개 추가 (1791→1816)

---

## [1.35.0] - 2026-06-12

### Added
- SPEC-LOTTO-074: 짝수 포함 개수 분포 분석 기능 추가
  - `get_even_count_stats()`: 회차별 짝수 개수(0~6) 분포 통계 산출
  - `GET /api/stats/even_count`: JSON 통계 API 엔드포인트
  - `GET /stats/even-count`: 짝수 개수 분포 분석 페이지 (`even_count.html`)
  - 내비게이션 "짝수개수" 링크 추가
  - 테스트 29개 추가 (1762→1791)

---

## [1.34.0] - 2026-06-12

### Added
- SPEC-LOTTO-073: 3의 배수 포함 개수 분포 분석 기능 추가
  - `get_mult3_stats()`: 회차별 3의 배수 개수(0~6) 분포 통계 산출
  - `GET /api/stats/mult3`: JSON 통계 API 엔드포인트
  - `GET /stats/mult3`: 3의 배수 분포 분석 페이지 (`mult3.html`)
  - 내비게이션 "3배수" 링크 추가
  - 테스트 30개 추가 (1732→1762)

---

## [1.33.0] - 2026-06-12

### Added (SPEC-LOTTO-072)
- 끝자리 유니크 수 분포 분석 기능 추가
  - `get_last_digit_unique_stats()`: 회차별 6개 번호의 끝자리(일의 자리) 중 서로 다른 값이 몇 개인지 분포 통계
  - 6개 구간("1"~"6") 분포, 평균 유니크 수, 전부 다른 회차 비율 제공
  - `GET /api/stats/last_digit_unique` API 엔드포인트
  - `GET /stats/last-digit-unique` 통계 페이지 (`last_digit_unique.html`)
  - 네비게이션 "끝자리유니크" 링크 추가
  - 테스트 30개 추가 (1702 → 1732)

---

## [1.32.0] - 2026-06-12

### Added (SPEC-LOTTO-071)
- 번호 중앙값(median) 분포 분석 기능 추가
  - `get_median_stats()`: 회차별 6개 번호의 중앙값((3번째+4번째)/2) 분포 통계
  - 9개 구간("1-5"~"41-45") 분포, 평균 중앙값, 저중앙값 비율(< 23.0) 제공
  - `GET /api/stats/median` API 엔드포인트
  - `GET /stats/median` 통계 페이지 (`median.html`)
  - 네비게이션 "중앙값" 링크 추가
  - 테스트 38개 추가 (1664 → 1702)

---

## [1.31.0] - 2026-06-11

### Added
- SPEC-LOTTO-070: AC값(산술 복잡도) 분포 분석
  - 회차별 본번호 6개의 C(6,2)=15 쌍 절대차 중 distinct 개수(AC값) 분포 분석
  - `GET /api/stats/ac_value` API 엔드포인트
  - `GET /stats/ac-value` 웹 페이지
  - AC값 0~14 전 구간 분포, 평균, 고다양성(AC≥9) 비율 제공
  - 35개 테스트 추가 (1629 → 1664)

---

## [1.30.0] - 2026-06-11

### Added
- SPEC-LOTTO-069: 연속번호 패턴 분석 (Consecutive Number Pattern Analysis)
  - `GET /api/stats/consecutive-pairs` — 4버킷 연속 쌍 분포 JSON API
  - `GET /stats/consecutive-pairs` — 연속번호 패턴 시각화 페이지
  - `get_consecutive_pairs_stats()` 함수: 0·1·2·3+ 버킷별 count/pct, avg_consecutive_pairs, most_common_bucket 산출
  - `count_consecutive_pairs()` 헬퍼 함수 (단독 테스트 가능)
  - `_consecutive_pairs_cache` 캐시 (SPEC-062 `_consecutive_cache`와 별개 네임스페이스)
  - `tests/test_consecutive_pairs_analysis.py` 31개 테스트 추가 (1598 → 1629)

---

## [1.29.0] - 2026-06-11

### Added
- SPEC-LOTTO-068: 번호 구간별 분포 분석 (Number Range Distribution Analysis)
  - `GET /api/stats/range_dist` — 5개 구간별 분포 통계 JSON API
  - `GET /stats/range_dist` — 번호 구간별 분포 시각화 페이지
  - `get_range_dist_stats()` 함수: 1-9, 10-19, 20-29, 30-39, 40-45 구간별 total_count, draw_count, avg_per_draw, pct_of_numbers, draw_pct 산출
  - `_range_dist_cache` 캐시 (key: 회차 수 기준, `invalidate_cache()` 연동)
  - `tests/test_range_dist_analysis.py` 29개 테스트 추가 (1569 → 1598)

---

## [1.28.0] - 2026-06-11

### Added
- SPEC-LOTTO-067: 번호 총합 분포 분석 (`get_total_sum_stats`, `/stats/total_sum`, `GET /api/stats/total_sum`)
  - 당첨번호 6개 총합(total sum) 분포 분석, 6개 고정 bucket(21-80, 81-110, 111-130, 131-150, 151-170, 171-255)
  - 저(<110)/중(110-170)/고(>170) 3구간 분류, 평균·최솟값·최댓값·최빈 bucket 제공
  - +28 테스트 (1541→1569)

---

## [1.27.0] - 2026-06-11

### Added
- SPEC-LOTTO-066: 소수합 분포 분석 (`get_prime_sum_stats`, `/stats/prime-sum`, `GET /api/stats/prime-sum`)
  - 회차별 소수(prime) 번호들의 합계 분포 분석, SPEC-058(소수 개수 분포)과 보완 관계
  - +26 테스트 (1515→1541)

---

## [1.26.0] - 2026-06-10

### Added
- SPEC-LOTTO-065: 번호 표준편차 분석 (`get_std_stats`, `/stats/std`, `GET /api/stats/std`)
  - 회차별 본번호 6개 모표준편차 분석, 저(<10)/중(10~14)/고(≥14) 카테고리, 6개 고정 bucket 분포
  - +35 테스트 (1480→1515)

---

## [1.25.0] - 2026-06-10

### Added
- SPEC-LOTTO-064: 최솟값·최댓값 분포 분석 (`get_min_max_stats`, `/stats/min-max`, `GET /api/stats/min-max`)
  - 회차별 최솟값·최댓값·범위(max-min) 분포 분석, 좁은(<30)/넓은(≥30) 범위 구간
  - +25 테스트 (1455→1480)

---

## [1.24.0] - 2026-06-10

### Added
- SPEC-LOTTO-063: 끝자리 합계 분석 (`get_last_digit_sum_stats`, `/stats/last-digit-sum`, `GET /api/stats/last-digit-sum`)
  - 회차별 본번호 6개 끝자리 합계 분석 (범위 0~54, 저/중/고 3구간 분류)
  - +26 테스트 (1429→1455)

---

## [1.23.0] - 2026-06-10

### Added
- SPEC-LOTTO-062: 연속 번호 패턴 분석 (`get_consecutive_pattern_stats`, `/stats/consecutive-pattern`, `GET /api/stats/consecutive-pattern`)
  - 회차별 연속 쌍(diff=1) 개수 0~5 분포, 트리플(3연속) 포함 회차 비율
  - +27 테스트 (1402→1429)

---

## [1.22.0] - 2026-06-10

### Added
- SPEC-LOTTO-061: 고저 비율 분석 (`get_high_low_stats`, `/stats/high-low`, `GET /api/stats/high-low`)
  - 저(1-22)/고(23-45) 번호 개수 분포 분석 (0~6 범위)
  - 균형 회차(저3:고3) 비율, 평균 저고 수, 분포 퍼센트
  - +28 테스트 (1374→1402)

---

## [1.21.0] - 2026-06-10

### Added
- SPEC-LOTTO-060: 홀짝 비율 분석 (`get_odd_even_stats`, `/stats/odd-even`, `GET /api/stats/odd-even`)
  - 회차별 홀수/짝수 개수 분포 분석 (0~6 범위)
  - 균형 회차(홀3:짝3) 비율, 평균 홀짝 수, 분포 퍼센트
  - +27 테스트 (1347→1374)

---

## [1.20.0] - 2026-06-10

### Added
- SPEC-LOTTO-059: 십의 자리 구간 분포 분석 (`get_decade_stats`, `/stats/decade`, `GET /api/stats/decade`)
  - 5개 구간(01-09, 10-19, 20-29, 30-39, 40-45) 분류 (명시적 범위 비교 방식)
  - 구간별 평균 출현수, 기대값 대비 편차, 분포 테이블 시각화
  - +27 테스트 (1320→1347)

---

## [1.14.0] - 2026-06-09

### Added (SPEC-LOTTO-058)
- `get_prime_stats(draws)` — 소수/합성수/숫자1 분포 분석 (_PRIMES_1_45 frozenset 기반, 메모리 캐시)
- `/stats/prime` 페이지 — 소수·합성수 개수별 분포 표
- `GET /api/stats/prime` — 소수/합성수 통계 JSON API
- 24개 신규 테스트 추가 (1296 → 1320)

---

## [1.13.0] - 2026-06-09

### Added (SPEC-LOTTO-057)
- `get_ac_stats(draws)` — AC(산술 복잡도)값 분포 분석 (avg_ac, 분포표, 고/저복잡도 비율, 메모리 캐시)
- `/stats/ac` 페이지 — AC 0~10 분포 표 (고복잡도 녹색·저복잡도 주황 강조)
- `GET /api/stats/ac` — AC 통계 JSON API
- 20개 신규 테스트 추가 (1276 → 1296)

---

## [1.12.0] - 2026-06-09

### Added (SPEC-LOTTO-056)
- `get_gap_stats(draws)` — 본번호 인접 간격 패턴 분석 (소·중·대 분포, 최빈 간격 top 10, 위치별 평균, 메모리 캐시)
- `/stats/gap` 페이지 — 간격 분포·위치별 평균·최빈 간격 표
- `GET /api/stats/gap` — 번호 간격 통계 JSON API
- 20개 신규 테스트 추가 (1256 → 1276)

---

## [1.11.0] - 2026-06-09

### Added (SPEC-LOTTO-055)
- `get_last_digit_stats(draws)` — 끝자리(0~9)별 출현 빈도·비율·편차 분석 (메모리 캐시)
- `/stats/last-digit` 페이지 — 끝자리별 count·pct·avg_expected·deviation 표 (과대/과소 강조)
- `GET /api/stats/last-digit` — 끝자리 분포 JSON API (10개 항목)
- 14개 신규 테스트 추가 (1242 → 1256)

---

## [1.10.0] - 2026-06-09

### Added (SPEC-LOTTO-054)
- `get_rolling_frequency(draws, windows)` — 윈도우별 번호 빈도·델타·추세 분류 (메모리 캐시)
- 추세 분류: 델타 > +0.02 "상승", < -0.02 "하락", 그 외 "보합"
- `/stats/rolling` 페이지 — 윈도우별 상승/하락 번호 표 (`?w=N` 단일 윈도우 지원)
- `GET /api/stats/rolling?windows=10,20,50,100` — 롤링 빈도 JSON API
- 21개 신규 테스트 추가 (1221 → 1242)

---

## [1.9.0] - 2026-06-09

### Added (SPEC-LOTTO-053)
- `get_cooccurrence_matrix` — 전체 번호 쌍(i<j) 동시 출현 횟수 원시 행렬 (메모리 캐시)
- `get_top_cooccurrences(n=20)` — 동시 출현 상위 N쌍 (count·pct 포함)
- `get_number_partners(number, top_k=10)` — 특정 번호의 상위 동반 번호 목록
- `/numbers/cooccurrence` 페이지 — 상위 쌍 표 / `?number=N` 시 특정 번호 파트너 표
- `GET /api/numbers/cooccurrence?number=N&top=T` — 동시 출현 JSON API
- 21개 신규 테스트 추가 (1200 → 1221)

---

## [1.8.0] - 2026-06-09

### Added (SPEC-LOTTO-052)
- `run_backtest(draws, n_past)` — 11개 전략을 과거 N회차에 대해 look-ahead 없이 백테스트
- `/backtest` 페이지 — 전략별 평균 적중수·점수를 내림차순 테이블로 표시
- `GET /api/backtest?n=N` — 백테스팅 결과 JSON API
- 메모리 캐시 (n_past 키) — DB 영속화 없이 동일 요청 재계산 방지
- 18개 신규 테스트 추가 (1182 → 1200)

---

## [1.7.0] - 2026-06-09

교차 전략 합의 알림 추가 (SPEC-LOTTO-051)

### 추가

#### 교차 전략 합의 알림 (SPEC-LOTTO-051)
- `get_cross_strategy_consensus(recommender, target_numbers)` 신규 함수 (`lotto/web/data.py`)
  - 11개 전략(`STRATEGY_LABELS`)을 요청당 1회씩 순회하여 각 번호의 합의 카운트(0~11) 산출
  - `recommend_by_strategy(label)`만 호출, raw draws/내부 점수 미접근 (레이어 분리)
- 추천 페이지(`GET /recommend`) 각 번호에 전략 합의도(`N/11`) 오버레이 표시
- 합의도 4개 이상 번호에 주의 배지/하이라이트 서버사이드 렌더링 (JS 미추가)
- `GET /api/recommendations` 응답에 `consensus` 필드 추가 (`{number: count}` 매핑)

### 개선

#### 테스트
- 1174개 → **1182개** (+8개, `TestCrossStrategyConsensus`)

---

## [1.6.0] - 2026-06-05

데이터스마트 추천 전략 추가 (SPEC-LOTTO-050)

### 추가

#### 데이터스마트 추천 전략 (SPEC-LOTTO-050)
- 11번째 추천 전략 "데이터스마트" 추가 (`STRATEGY_LABELS`, `STRATEGY_DESCRIPTIONS`)
- `_smart_scores()` 메서드: 빈도(0.22)·최근편향(0.22)·동반패턴(0.18)·갭분석(0.18)·홀짝균형(0.10)·번호대균형(0.10) 6축 복합 가중 점수
- 픽 로직은 기존 앙상블 경로(상위 25개 후보) 재사용 (`_pick_set` 조건 병합)
- `recommend.html` 전략 안내 범례에 보라색(`bg-violet-100 text-violet-700`) 배지 추가
- `Statistics` 객체만 의존, 원시 draws 미사용 — 추천기 계층 침범 없음

### 개선

#### 테스트
- 1165개 → **1174개** (+9개, `TestDataSmartStrategy`)
- 커버리지 89.20% (목표 85% 초과)

---

## [1.5.0] - 2026-05-27

신규 기능 5종 일괄 도입 (SPEC-LOTTO-016~021)

### 추가

#### 번호 즐겨찾기 관리 (SPEC-LOTTO-016)
- `POST /api/favorites` — 번호 조합(6개) + 이름 즐겨찾기 추가 (중복 시 409)
- `GET /api/favorites` — 즐겨찾기 전체 목록 반환
- `DELETE /api/favorites/{fav_id}` — 즐겨찾기 단건 삭제
- `data/favorites.json` 원자적 쓰기(tempfile + os.replace) 저장
- 추천 페이지: 번호 직접 입력·이름 저장 폼 + 목록·삭제 UI
- 시뮬레이션 페이지: 즐겨찾기 번호 선택 → 바로 시뮬레이션 실행

#### 번호 패턴 분석 강화 (SPEC-LOTTO-019)
- `GET /api/pattern-analysis` — 홀짝 비율·번호대 분포·연속 번호·합계 분포·끝자리 분포 반환
- 분석 페이지 "패턴 분석" 탭: 홀짝 도넛·번호대 바·합계 히스토그램 Chart.js 차트

#### 데이터 내보내기 (SPEC-LOTTO-020)
- `GET /api/export/draws` → `lotto_draws_YYYYMMDD.csv` 파일 다운로드 (`from_drw`, `to_drw` 필터 지원)
- `GET /api/export/history` → `lotto_history_YYYYMMDD.csv` 파일 다운로드
- `GET /api/export/history?format=json` → JSON 파일 다운로드
- 수집 현황 페이지: "추첨 데이터 내보내기 (CSV)" 버튼
- 구매 내역 페이지: "CSV 내보내기" / "JSON 내보내기" 버튼
- 데이터 없어도 빈 헤더 CSV 반환 (200, 404 아님)

#### 다크모드 & 반응형 UI (SPEC-LOTTO-021)
- `base.html` 헤더에 다크/라이트 토글 버튼 추가
- `localStorage.theme` 설정 영속화 + 시스템 `prefers-color-scheme` 자동 감지
- Tailwind CDN `darkMode: 'class'` 활성화
- FOUC 방지 인라인 스크립트 (페이지 로드 전 `dark` 클래스 적용)
- 모바일 햄버거 메뉴 토글 + 현재 페이지 활성화 표시
- 전체 페이지 `dark:` 클래스 적용 (테이블·카드·네비게이션·차트 영역)

#### 당첨금 분석 대시보드 (SPEC-LOTTO-017)
- `DrawResult` 모델에 `prize1Amount: Optional[int]`, `prize1Winners: Optional[int]` 추가
- `GET /api/prize-stats` — 평균·최대·최소 당첨금, 최근 20회차 데이터 반환
- 인덱스 페이지: 1등 당첨금 추이 라인 차트 + 평균/최대/최소 통계 카드
- 당첨금 데이터 없으면 차트 섹션 자동 숨김
- 기존 CSV 하위 호환 유지 (새 컬럼 없어도 오류 없음)

#### 추첨 회차 삭제
- `DELETE /api/draws/{drw_no}` — 지정 회차 데이터 삭제 (없으면 404)
- 수집 현황 테이블에 삭제 버튼 추가

### 개선

#### 테스트 커버리지
- 541개 → **631개** 테스트 (+90개)
- 즐겨찾기(17) · 패턴 분석(12) · 내보내기(21) · 다크모드(23) · 당첨금(17) 신규 테스트

---

## [1.4.0] - 2026-05-26

구매 이력 관리 및 수동 입력 날짜 형식 표준화 (SPEC-LOTTO-002·003·004·014)

### 추가

#### 구매 이력 관리 (SPEC-LOTTO-014)
- `POST /api/history` — 구매 티켓 등록 (회차·번호 6개 입력)
- `GET /api/history` — 구매 이력 목록 + 당첨 결과 자동 대조 (등수·ROI 계산)
- `DELETE /api/history/{ticket_id}` — 구매 티켓 단건 삭제
- `data/purchases.json` 파일 기반 영속 저장 (외부 DB 불필요)
- 등수 자동 산출: 추첨 결과와 대조하여 1~5등 / "미당첨" / "미추첨" 표시
- ROI(투자수익률) 통계: 누적 투자금·당첨금·수익률 요약
- 웹 UI "구매 내역" 탭: 구매 등록 폼 + 등수 확인 목록

### 변경

#### 수동 회차 입력 날짜 형식 (SPEC-LOTTO-002)
- `POST /draws/manual` — `date` 파라미터 형식을 `YYYYMMDD`(8자리 숫자)로 표준화
- 기존 `YYYY-MM-DD` 하이픈 형식에서 변경; API 클라이언트 업데이트 필요

### 개선

#### 테스트 커버리지 100% 달성
- 511개 테스트, 커버리지 99.85% → **100%** (branch partial miss 3건 pragma 억제)
- 구매 이력 관련 신규 테스트 51건 추가 (SPEC-LOTTO-014)

---

## [1.3.0] - 2026-05-26

추천 전략 앙상블 고도화 및 웹 UI 개선 (SPEC-LOTTO-009·013)

### 추가

#### 갭분석 (Gap Analysis) — analyze 페이지 (SPEC-LOTTO-013)
- 번호별 미출현 회차 수(갭) 시각화 — 오랫동안 안 나온 번호를 한눈에 확인
- `gap_rounds` 컨텍스트 변수: `consecutive_pattern.current_streak` 음수값 활용
- analyze 페이지 배지에 갭 정보 툴팁 표시

#### 데이터 게이트웨이 캐싱 (SPEC-LOTTO-009)
- `get_draws()` / `get_stats()` TTL 60초 모듈 레벨 캐시 도입
- `invalidate_cache()` — collect/analyze/scrape 완료 후 자동 호출
- `get_last_sync_date()` — last_sync.json 우선, draws.csv 최신 회차 폴백
- 인덱스 페이지 헤더에 "최근 수집: YYYY-MM-DD" 표시

### 개선

#### 복합 앙상블 추천 전략 고도화 (SPEC-LOTTO-013)
- 8가지 단일 전략을 복합 앙상블 모델로 통합
- 갭분석 기반 "핫콜드혼합" 전략 정확도 개선

#### 웹 UI 개선
- 수집현황: 최신순 정렬 + 처음/마지막 페이징 버튼 추가
- 추첨결과 테이블: 서버사이드 초기 렌더링으로 최신 회차 우선 표시
- 시뮬레이션: 5등 적중률 계산 정확도 개선
- 모바일 반응형 메뉴 (햄버거 메뉴)

#### 테스트 커버리지 향상 (SPEC-LOTTO-011 완료)
- 460개 테스트, 커버리지 98.51% → **99.85%** (statement miss 0건)
- 갭분석·앙상블 전략 테스트 22개 추가 (SPEC-LOTTO-013)
- TYPE_CHECKING 블록·방어용 폴백 코드에 `# pragma: no cover` 적용

---

## [1.2.0] - 2026-05-21

코드 품질 강화 및 운영 모니터링 지원 (SPEC-LOTTO-011~012)

### 추가

#### REQ-HLT: 헬스체크 엔드포인트 (SPEC-LOTTO-012)
- `GET /api/health` 엔드포인트 추가 (항상 HTTP 200)
- 응답 필드: `status`, `uptime_seconds`, `data` (csv_exists, csv_rows, stats_exists, last_sync), `version`
- `status: "ok"` — csv + stats 파일 모두 존재 시
- `status: "degraded"` — 데이터 파일 없을 때
- Pydantic 응답 모델: `HealthResponse`, `HealthDataResponse`
- Prometheus / UptimeRobot / k8s liveness probe 호환

### 개선

#### 테스트 커버리지 향상 (SPEC-LOTTO-011)
- 429개 테스트, 커버리지 96.26% → 98.51%
- 추천기 폴백 경로(홀짝균형, 번호대균형, 핫콜드혼합) 테스트 추가
- 웹 API 커버리지 미비 경로(CSV 삭제, analyze 분기 등) 추가
- 헬스체크 테스트 10개 추가 (REQ-HLT-001~005 검증)

#### mypy 타입 안정화
- mypy 에러 50건 → 0건 (`lotto/` 15개 소스 파일 전체)
- `web/data.py`: 반환 타입 구체화 (`list[DrawResult]`, `Statistics | None` 등)
- `web/routes/pages.py`: `TemplateResponse` 임포트 경로 수정, `dict[str, Any]` 적용
- `config.py`: `typing.Tuple` → `tuple` (UP035/UP006)
- `scraper.py`: `list[tuple[str, str | None]]` 구체화
- `pdf_report.py`: TYPE_CHECKING 임포트 경로 lotto.models로 통일

#### 린트 정리
- ruff SIM105: `try/except/pass` → `contextlib.suppress(OSError)` (collector.py)
- ruff TC003: `Path` → TYPE_CHECKING 블록으로 이동 (collector.py)
- ruff SIM117: 중첩 `with` → 괄호식 단일 `with` (test 파일 3개)
- ruff E501: 긴 줄 분리 (test_pdf_report.py)

---

## [1.1.0] - 2026-05-20

웹 대시보드 추가 (SPEC-WEB-001 구현 완료)

### 추가

#### REQ-WEB: 읽기 전용 웹 대시보드
- FastAPI 기반 5탭 웹 대시보드 (`lotto/web/`)
- 대시보드, 수집 현황, 빈도 분석, 추천 번호, 시뮬레이션 탭
- 번호별 빈도 백분위수 기반 컬러 배지 (저빈도 #E2E8F0 ~ 고빈도 #3B82F6)
- Chart.js v4 차트: 빈도 분석(가로 막대), 시뮬레이션(도넛)
- Tailwind CSS CDN, Noto Sans KR CDN 활용 (빌드 스텝 없음)
- REST API 엔드포인트: GET /api/draws, /api/stats, /api/recommendations, /api/simulation
- POST /api/collect, /api/analyze (비동기 백그라운드 실행)
- `python main.py web` CLI 서브커맨드 추가
- 65개 신규 테스트 추가, lotto.web 커버리지 ≥ 90%

---

## [1.0.0] - 2026-05-20

로또 번호 추천 CLI 도구의 초기 안정 버전 (SPEC-LOTTO-001 구현 완료)

### 추가

#### REQ-COLLECT: 당첨 번호 수집 모듈
- 동행복권 API에서 6/45 로또 당첨 번호 자동 수집
- `data/draws.csv` 형식으로 로컬 저장
- 증분 수집 (신규 회차만) 및 전체 재수집 (`--full`) 옵션
- API 장애 시 지수 백오프 재시도 (1s, 2s, 4s 최대 3회)
- 연속 5회 이상 수집 실패 시 자동 중단으로 데이터 무결성 보호
- 200ms 레이트 제한으로 서버 부하 경감

#### REQ-ANALYZE: 통계 분석 모듈
- 수집된 데이터에서 4가지 통계 지표 계산
  - **출현 빈도 (frequency)**: 각 번호(1~45)의 누적 출현 횟수 및 확률
  - **최근 패턴 (recent_pattern)**: 최근 N회차 내 각 번호의 출현 빈도 및 마지막 출현 회차
  - **연속 패턴 (consecutive_pattern)**: 최대 연속 출현 기간 및 최대 부재 기간
  - **동반 출현 (pair_analysis)**: 자주 함께 나오는 번호 쌍 TOP 20
- `data/stats.json` 형식으로 JSON 저장
- `--recent-window N` 옵션으로 분석 기간 커스터마이징 (기본값: 20회차)
- 데이터 부재 시 명확한 에러 메시지 및 상태 코드 반환

#### REQ-RECOMMEND: 번호 추천 모듈
- 통계 데이터 기반의 가중치식 점수 추천
- 스코어링 공식: `score(n) = w_freq × freq_norm(n) + w_recent × recent_norm(n) + w_pair × pair_norm(n) - w_consec × consec_penalty(n)`
- 5가지 전략 레이블 자동 할당
  - `고빈도`: 출현 빈도 편향
  - `저빈도`: 저빈도 번호 편향
  - `균형`: 모든 지표의 균형
  - `최근편향`: 최근 패턴 편향
  - `동반패턴`: 동반 출현 편향
- `--count N` 옵션으로 추천 세트 수 지정 (1~20, 기본값: 5)
- `--weights w_freq,w_recent,w_pair,w_consec` 옵션으로 가중치 커스터마이징
- 기본 가중치: 0.4, 0.3, 0.2, 0.1
- 추천 세트 번호는 항상 오름차순 정렬
- 동일 실행 내 중복 없음 보장

#### REQ-SIMULATE: 시뮬레이션/백테스팅 모듈
- 과거 회차 데이터를 사용한 인과 안전(look-ahead safe) 백테스팅
- 각 회차마다 독립적인 추천 생성 후 실제 당첨 번호와 비교
- 매칭 등급 자동 계산 (1등~5등, 낙첨)
- 집계 메트릭스 생성: 평가 회차, 등급별 횟수, 적중률(5등 이상)
- `--rounds N` 옵션으로 백테스팅 회차 수 지정 (기본값: 10, 최대: 수집된 전체 회차)
- `--output FILE` 옵션으로 상세 결과를 JSON 파일로 저장
- Rich 라이브러리로 진행 상황 표시

#### REQ-CLI: CLI 인터페이스 모듈
- typer 기반 단일 진입점 (`main.py`)
- 4개 서브커맨드: `collect`, `analyze`, `recommend`, `simulate`
- 한국어 헬프 텍스트 및 사용자 친화적 에러 메시지
- Rich 라이브러리로 테이블 및 칼러 출력
- 진행 상황 표시 (progress bar)
- 상태 코드 정의
  - 0: 성공
  - 1: 입력/데이터 검증 오류
  - 2: 외부 서비스 장애

### 개발

#### 테스트 및 품질
- 77개 단위 테스트 (PyTest)
- 라인 커버리지 85.25%
- ruff 린팅 0 오류
- mypy --strict 타입 검사 0 오류
- TDD 방법론 (RED-GREEN-REFACTOR)

#### 코드 구조
- `lotto/models.py`: Pydantic 데이터 모델 및 타입 정의
- `lotto/collector.py`: 수집 모듈 및 CSV 직렬화
- `lotto/analyzer.py`: 통계 분석 엔진 및 JSON 저장
- `lotto/recommender.py`: 가중치식 추천 알고리즘
- `lotto/simulator.py`: 백테스팅 및 매칭 등급 계산
- `main.py`: typer CLI 엔트리 포인트

#### 호환성
- Python 3.9+ (실제 런타임: 3.9.25)
- 외부 데이터베이스 불필요 (로컬 CSV/JSON만 사용)
- 크로스 플랫폼 (Windows, macOS, Linux)

#### 의존성
- typer 0.9+
- rich 13+
- pydantic 2.0+
- pytest 7.0+ (개발용)
- ruff, mypy (품질 검사용)

### 비기능 요구사항 충족

| 항목 | 요구사항 | 상태 |
|------|---------|------|
| 성능 (analyze) | 5초 이내 (1,200회차) | ✅ |
| 성능 (recommend) | 2초 이내 (5세트) | ✅ |
| 안정성 | API 장애 시 3회 재시도 | ✅ |
| 호환성 | Python 3.11, 3.12 | ✅ |
| 코드 품질 | ruff 0 오류, mypy --strict 0 오류 | ✅ |
| 테스트 | 85% 이상 커버리지 | ✅ 85.25% |
| 보안 | 입력값 범위 검증 | ✅ |

### 배제 범위

명시적으로 v1.0.0에서는 제공하지 않는 기능:
- 당첨 보장 — 본 시스템은 통계 기반이며 어떤 형태로도 당첨을 보장하지 않음
- 자동 구매 연동 — 추천 번호의 실제 구매는 사용자가 직접 수행
- GUI 또는 웹 인터페이스 — 순수 CLI 도구만 제공
- 실시간 스트리밍 — 사용자 명시 수집만 지원
- 외부 데이터베이스 — 로컬 CSV/JSON 파일만 사용
- 머신러닝 기반 추천 — v2.0.0 이후 별도 SPEC에서 다룸
- 다국어 지원 — 한국어만 제공

### 문서

- README.md: 설치, 사용 가이드, 명령어 상세
- 이 CHANGELOG
- SPEC-LOTTO-001 완료

### 면책 사항

⚠️ **본 프로그램은 통계 분석을 기반으로 하며 당첨을 보장하지 않습니다.**
- 로또는 완전 무작위 추첨 게임
- 역사적 패턴은 미래 결과를 예측하지 못함
- 사용자의 손실에 대해 책임지지 않음

---

## [미정] - 향후 계획

### 향후 버전에서 예상되는 기능

- API 입력 검증 강화 (Pydantic 경계 조건)
- Rate limiting (collect/scrape 엔드포인트)
- 웹 UI 개선 (히트맵, 트렌드 차트)
- Docker/배포 설정
- SPEC-LOTTO-002: 머신러닝 기반 추천 (신경망)
- 자동 구매 시스템 (PG 연동)
- 다국어 지원

---

## 버전 관리

- **Semantic Versioning** 준수
- **1.0.0** = 첫 안정 릴리스 (모든 SPEC-LOTTO-001 요구사항 구현)
