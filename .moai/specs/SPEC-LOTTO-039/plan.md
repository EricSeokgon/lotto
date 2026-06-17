# SPEC-LOTTO-039 구현 계획 (plan.md)

## 1. 기술 접근 (Technical Approach)

기존 집계 함수(`weekly_report`, `hot_cold_analysis`, `number_stats`)와 동일한
설계 패턴을 따른다:

- `_UNSET` 센티넬로 "인자 생략(자동 로드)" vs "명시적 None(데이터 없음)" 구분
- `from __future__ import annotations`로 Python 3.9 호환 유지
- 순수 파이썬 단일 패스 집계 (numpy 미사용 — 신규 의존성 0)
- 결정적(deterministic) 스코어링 — 난수 미사용
- API/페이지는 `wd.` 동적 디스패치로 테스트 patch 호환

### 1.1 스코어링 모델

각 번호 n(1~45)에 대해 표본(최근 recent_n 회차)에서:

1. **frequency score** = (n의 출현 횟수) / (표본 내 최대 출현 횟수)
   - 최대 출현 횟수가 0이면 모두 0.0
2. **interval score** = (n의 마지막 출현 이후 경과 회차 gap) / (표본 최대 gap)
   - gap이 클수록(오래 미출현) 높음. 표본 내 한 번도 안 나온 번호는 gap=표본크기
3. **odd/even balance score**: 후보 선정 단계에서 홀짝 균형을 유지하기 위한
   기여도. 번호 단위 점수에서는 홀짝 그룹의 상대 희소도를 반영
   (적게 나온 그룹의 번호에 가산).
4. **range distribution score**: 5개 번호대 중 표본에서 상대적으로 적게 나온
   번호대에 속한 번호에 가산 (분포 균형 유도).

**composite score** = `W_FREQ·freq + W_INTERVAL·interval +
W_ODDEVEN·oddeven + W_RANGE·range`

가중치 상수(합=1.0, 예시):
- `_W_FREQUENCY = 0.40`
- `_W_INTERVAL = 0.30`
- `_W_ODD_EVEN = 0.15`
- `_W_RANGE = 0.15`

### 1.2 추천 조합 생성 (결정적)

- top_candidates(상위 10개)에서 6개씩 추출하여 3세트 구성.
- 세트1: 상위 1~6위
- 세트2: 상위 1~5위 + 7위 (또는 오프셋 회전)
- 세트3: 상위 1~4위 + 7,8,9위 등 — 세 세트가 서로 다르도록 인덱스 회전
- 각 세트는 6개 서로 다른 번호를 오름차순 정렬.
- 후보가 6개 미만이면 가능한 만큼만 조합 생성(빈 표본 방어).

---

## 2. 마일스톤 (우선순위 기반, 시간 추정 없음)

### M1 (Priority High): 집계 함수 구현 — `prediction_report`
- `lotto/web/data.py`에 가중치 상수 + `prediction_report` 추가
- 부분 점수 4종 계산, composite 정규화, top_candidates, recommended_combinations
- 빈/None 데이터 방어 (REQ-PRED-009)
- @MX:NOTE + @MX:SPEC 태그 추가 (code_comments=ko)

### M2 (Priority High): API 엔드포인트
- `lotto/web/routes/api.py`에 `GET /api/prediction/report` 추가
- `recent_n` Query(default=50, ge=1, le=200) 검증
- `wd.prediction_report(recent_n, wd.get_draws())` 동적 호출
- 데이터 부재 시 200 빈 응답

### M3 (Priority Medium): 페이지 + 템플릿
- `lotto/web/routes/pages.py`에 `GET /prediction` 추가
- `lotto/web/templates/prediction.html` 신규 (analyze/recommend 패턴 참고)
- 후보 표(번호·종합점수·점수분해 바) + 추천 조합 3세트 카드
- 빈 상태 안내 메시지

### M4 (Priority High): 테스트 (최소 12개)
- 집계 함수 단위 테스트 (스코어링/정규화/빈 데이터/recent_n 클램프/결정성)
- API 테스트 (정상/검증 실패 422/데이터 부재 200)
- 페이지 테스트 (200 렌더/빈 상태)

### M5 (Priority Medium): 품질 게이트
- ruff 통과, 신규 코드 커버리지 85%+
- 전체 테스트 회귀 없음 (961 → 973+)

---

## 3. 테스트 명령

```
PYTHONPATH=/home/sklee/moai/lotto /home/sklee/.local/bin/pytest --tb=short -q
```

---

## 4. 리스크 및 완화 (Risks)

| 리스크 | 영향 | 완화 |
|--------|------|------|
| 가중치 임의성 — "왜 이 가중치?"라는 비판 | 신뢰성 | 가중치를 명명 상수로 분리, breakdown으로 근거 노출, 합=1.0 검증 테스트 |
| 정규화 분모 0 (빈/단일 표본) | ZeroDivision | 분모 0이면 해당 부분 점수 0.0 처리, 테스트로 검증 |
| 조합 세트 중복 | UX 저하 | 인덱스 회전 로직 + 세 세트 비동일 단언 테스트 |
| Python 3.9 호환 위반 (`X|Y`, `zip(strict=)`) | 런타임 오류 | `from __future__ import annotations`, Optional/Union, noqa 패턴 준수 |
| 신규 의존성 유입 | 빌드 실패 | 순수 파이썬만 사용, import 검토 |

---

## 5. @MX 태그 대상

- `prediction_report`: fan_in 2 예상(API, 페이지) → @MX:NOTE + @MX:SPEC
  (fan_in 3 미만이므로 ANCHOR 대신 NOTE)
- 가중치 상수: 매직 상수 설명 @MX:NOTE
