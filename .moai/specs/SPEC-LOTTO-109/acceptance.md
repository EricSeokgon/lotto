# SPEC-LOTTO-109 수용 기준 (Acceptance Criteria)

## 공통 픽스처

`drwNo` 오름차순 5개 회차(본번호만 표기, 보너스는 임의):

| 회차(drwNo) | 본번호 |
|------|--------|
| 1 | [1, 2, 3, 4, 5, 6] |
| 5 | [1, 7, 8, 9, 10, 11] |
| 10 | [2, 12, 13, 14, 15, 16] |
| 12 | [1, 17, 18, 19, 20, 21] |
| 20 | [2, 22, 23, 24, 25, 26] |

### 손계산

- **번호 1**: 출현 drwNo = [1, 5, 12] → gaps = [5-1=4, 12-5=7]
  - count=2, min_gap=4, max_gap=7, avg_gap=5.5, median_gap=5.5
  - std_gap = round(stdev([4,7]),2) = 2.12
  - gap_histogram = {"1-10": 2, 나머지 0}, appearance_count=3
- **번호 2**: 출현 drwNo = [1, 10, 20] → gaps = [10-1=9, 20-10=10]
  - count=2, min_gap=9, max_gap=10, avg_gap=9.5, median_gap=9.5
  - std_gap = round(stdev([9,10]),2) = 0.71
  - gap_histogram = {"1-10": 2, 나머지 0}, appearance_count=3
- **번호 7**: 출현 drwNo = [5] (1회) → count=0, 모든 통계 None
  - gap_histogram 전부 0, appearance_count=1
- **번호 45**: 미출현 → count=0, appearance_count=0, 모든 통계 None, 히스토그램 0
- **overall_summary**: all_gaps = [4, 7, 9, 10]
  - avg_gap_all = round(mean([4,7,9,10]),2) = round(7.5,2) = 7.5
  - max_gap_ever = 10, max_gap_number = 2
  - min_gap_ever = 4, min_gap_number = 1

---

## 수용 항목

- **AC-01 (REQ-GAP-001)**: 픽스처로 호출 시 번호 1의 gaps가 정확히 [4, 7]이다
  (drwNo 차이 기반).
- **AC-02 (REQ-GAP-002)**: 번호 1의 count=2, min_gap=4, max_gap=7, avg_gap=5.5,
  median_gap=5.5 이다.
- **AC-03 (REQ-GAP-002)**: 번호 1의 std_gap == 2.12 이다.
- **AC-04 (REQ-GAP-002)**: 번호 1의 appearance_count == 3 이다.
- **AC-05 (REQ-GAP-001/002)**: 번호 2의 gaps가 [9, 10], min_gap=9, max_gap=10,
  avg_gap=9.5, median_gap=9.5, std_gap=0.71 이다.
- **AC-06 (REQ-GAP-003)**: 번호 1의 gap_histogram == {"1-10":2, "11-20":0,
  "21-30":0, "31-40":0, "41-50":0, "51+":0} 이다.
- **AC-07 (REQ-GAP-003)**: 번호 2의 gap_histogram도 {"1-10":2, 나머지 0} 이다
  (9,10 모두 1~10 버킷).
- **AC-08 (REQ-GAP-006)**: 번호 7은 count=0, avg_gap/median_gap/min_gap/max_gap/
  std_gap 모두 None, appearance_count=1 이다.
- **AC-09 (REQ-GAP-006)**: 번호 7의 gap_histogram 모든 버킷이 0 이다.
- **AC-10 (REQ-GAP-006)**: 번호 45는 count=0, appearance_count=0, 모든 통계 None
  이다.
- **AC-11 (REQ-GAP-004)**: overall_summary.avg_gap_all == 7.5 이다.
- **AC-12 (REQ-GAP-004)**: overall_summary.max_gap_ever == 10,
  max_gap_number == 2 이다.
- **AC-13 (REQ-GAP-004)**: overall_summary.min_gap_ever == 4,
  min_gap_number == 1 이다.
- **AC-14 (REQ-GAP-002)**: 결과 numbers 길이가 45이며 index 0의 number==1,
  index 44의 number==45 이다.
- **AC-15 (REQ-GAP-005)**: draws=None 호출 시 total_draws=0, overall_summary의
  모든 값이 None, numbers 45개 모두 count=0·통계 None·히스토그램 0 이다.
- **AC-16 (REQ-GAP-005)**: draws=[] (빈 리스트) 호출 시에도 AC-15와 동일한
  0 채움 구조를 반환한다.
- **AC-17 (REQ-GAP-003)**: 큰 간격 버킷 경계 검증 — gap이 51 이상이면 "51+"
  버킷, 정확히 50이면 "41-50" 버킷, 정확히 51이면 "51+" 버킷에 들어간다
  (별도 픽스처로 확인).
- **AC-18 (REQ-GAP-009)**: 결과에 disclaimer(비어 있지 않은 str)가 포함되며
  "예측"하지 않는다는 회고적 분석 취지가 담긴다.

## API / 페이지 수용 (통합 테스트)

- **AC-API-01 (REQ-GAP-007)**: `GET /api/stats/gap-distribution`이 200을 반환하고
  JSON에 total_draws, overall_summary, numbers(45개), disclaimer 키가 있다.
- **AC-PAGE-01 (REQ-GAP-008)**: `GET /stats/gap-distribution`이 200을 반환하고
  HTML에 "간격" 관련 제목이 렌더링된다(active_tab="gap_dist").
