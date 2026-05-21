# SPEC-LOTTO-007 인수 기준 (Acceptance Criteria)

## REQ-SYNC-001: 원자적 CSV 저장

### AC-SYNC-001-1: 정상 저장
- **Given**: `tmp_data_dir`와 3건의 `DrawResult` 목록
- **When**: `collector.save_csv(draws)` 호출
- **Then**: `data_dir/draws.csv`가 존재하고, 다시 `load_existing()`으로 불러왔을 때 원본과 동일한 회차 목록이 반환된다.

### AC-SYNC-001-2: 부분 쓰기 방지
- **Given**: 기존 CSV가 존재하고, `os.replace`가 예외를 던지도록 모킹된 환경
- **When**: `collector.save_csv(new_draws)` 호출 시 예외 전파
- **Then**: 원본 CSV는 변경되지 않으며, 임시 `.tmp` 파일이 디렉토리에 남지 않는다.

### AC-SYNC-001-3: 디렉토리 자동 생성
- **Given**: `data_dir` 하위의 존재하지 않는 중첩 경로(`tmp_path/nested/data`)를 사용
- **When**: `collector.save_csv(draws)` 호출
- **Then**: 중첩 디렉토리가 자동 생성되고 CSV 파일이 저장된다.

## REQ-SYNC-002: Append 모드 신규 회차 추가

### AC-SYNC-002-1: append_draws 기본 동작
- **Given**: 10개 회차가 저장된 CSV
- **When**: `collector.append_draws([draw_11, draw_12])` 호출
- **Then**: CSV에는 12개 회차가 존재하며, `save_csv` 전체 재작성 호출이 발생하지 않는다.

### AC-SYNC-002-2: 파일 미존재 시 신규 생성
- **Given**: CSV가 없는 빈 `data_dir`
- **When**: `collector.append_draws([draw_1])` 호출
- **Then**: 헤더 포함하여 새 CSV가 생성되고, `load_existing()`이 1건을 반환한다.

### AC-SYNC-002-3: 중복 회차 제거
- **Given**: 회차 1,2,3이 저장된 CSV
- **When**: `collector.append_draws([draw_3, draw_4])` 호출 (drwNo=3 중복)
- **Then**: 회차 3은 추가되지 않고, CSV에는 회차 1,2,3,4가 존재한다.

### AC-SYNC-002-4: 빈 입력 노옵
- **Given**: 기존 CSV 존재
- **When**: `collector.append_draws([])` 호출
- **Then**: 파일이 전혀 수정되지 않는다(mtime 변화 없음).

## REQ-SYNC-003: last_sync.json 메타데이터

### AC-SYNC-003-1: 정상 수집 후 메타 기록
- **Given**: API가 2개 회차를 정상 반환하도록 모킹된 환경
- **When**: `collector.collect_new(latest_drw_no=2)` 호출
- **Then**: `data_dir/last_sync.json`이 존재하고 `last_round`, `synced_at`, `total_rounds` 필드가 모두 들어 있다.

### AC-SYNC-003-2: 메타데이터 구조 검증
- **When**: `last_sync.json` 파일을 JSON 파싱
- **Then**: `last_round`는 정수, `synced_at`은 ISO 8601 문자열, `total_rounds`는 정수이며, `last_round == max(drwNo)`를 만족한다.

### AC-SYNC-003-3: 후속 수집 시 갱신
- **Given**: 1회 수집 완료(`last_round=2`)
- **When**: 추가로 회차 3을 수집
- **Then**: `last_sync.json`의 `last_round`가 3으로 갱신된다.

## REQ-SYNC-004: 데이터 갭 감지

### AC-SYNC-004-1: 갭 없음
- **Given**: 회차 1,2,3,4,5
- **When**: `collector.detect_gaps(draws)` 호출
- **Then**: `[]` 반환

### AC-SYNC-004-2: 단일 갭
- **Given**: 회차 1,2,4,5 (3 누락)
- **When**: `collector.detect_gaps(draws)` 호출
- **Then**: `[3]` 반환

### AC-SYNC-004-3: 다중 갭
- **Given**: 회차 1,3,5 (2, 4 누락)
- **When**: `collector.detect_gaps(draws)` 호출
- **Then**: `[2, 4]` 반환 (오름차순)

### AC-SYNC-004-4: 빈 입력
- **Given**: 빈 회차 목록
- **When**: `collector.detect_gaps(draws=[])` 호출
- **Then**: `[]` 반환

### AC-SYNC-004-5: 단일 회차
- **Given**: 회차 1개만 존재
- **When**: `collector.detect_gaps(draws)` 호출
- **Then**: `[]` 반환

## 검증 절차

```bash
cd /home/sklee/moai/lotto
python3.9 -m pytest tests/test_collector_atomic.py tests/test_collector_append.py tests/test_collector_sync_meta.py tests/test_collector_gaps.py -v
python3.9 -m pytest tests/ -q --tb=no
```

### 합격 기준
- 신규 테스트 12개 이상 모두 통과
- 기존 360개 테스트 모두 통과
- 전체 커버리지 ≥ 95%
- `collect_new()` 시그니처 및 반환 타입 변경 없음
