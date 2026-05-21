# SPEC-LOTTO-005: PDF 리포트 내보내기

## 개요

웹 대시보드에서 추천 번호, 통계 분석, 시뮬레이션 결과를 단일 PDF 파일로 다운로드할 수 있는 기능을 제공한다. 사용자는 분석 결과를 오프라인에서 보관하거나 인쇄하여 활용할 수 있다.

## 배경

기존 웹 대시보드(SPEC-WEB-001)는 화면에서 데이터를 표시하지만, 보관·공유·인쇄에 최적화된 출력 포맷이 없다. PDF 리포트를 통해 분석 결과의 영구 보관 및 오프라인 활용을 가능하게 한다.

## 요구사항 (EARS 형식)

### Ubiquitous (시스템 전역)

- **REQ-PDF-001**: 시스템은 `GET /api/report/pdf` 엔드포인트를 제공해야 한다. 응답은 `application/pdf` Content-Type을 가져야 하며, `Content-Disposition: attachment; filename=lotto_report.pdf` 헤더를 포함해야 한다.

### Event-driven (이벤트 기반)

- **REQ-PDF-002**: PDF가 생성될 때, 시스템은 추천 번호 섹션을 포함해야 한다. 섹션은 각 추천 세트의 6개 번호 목록과 전략명(strategy_label)을 표시해야 한다.
- **REQ-PDF-003**: PDF가 생성될 때, 시스템은 통계 요약 섹션을 포함해야 한다. 섹션은 상위 10개 빈출 번호(빈도 내림차순)와 상위 5개 보너스 빈출 번호를 표시해야 한다.
- **REQ-PDF-004**: PDF가 생성될 때, 시스템은 시뮬레이션 결과 섹션을 포함해야 한다. 섹션은 등수별(1등~5등, 낙첨) 당첨 횟수를 표시해야 한다.

### State-driven (상태 기반)

- **REQ-PDF-005**: 웹 UI의 추천(`/recommend`), 통계(`/analyze`), 시뮬레이션(`/simulate`) 페이지가 렌더링될 때, 각 페이지에는 PDF 다운로드 버튼이 노출되어야 한다. 버튼은 `/api/report/pdf` 링크로 동작해야 한다.

### Unwanted (회피)

- **REQ-PDF-006**: 시스템은 데이터(통계/추천/시뮬레이션)가 부재한 경우에도 예외를 발생시키지 말아야 한다. 부재한 섹션은 "No data available" 메시지로 대체하여 정상적인 PDF를 생성해야 한다.

## 비기능 요구사항 (NFR)

- **NFR-PDF-001**: PDF 생성 함수는 부분/전체 데이터 부재 시 빈 섹션을 표시하고 예외를 발생시키지 않아야 한다.
- **NFR-PDF-002**: PDF는 fpdf2 라이브러리의 내장 Helvetica 폰트를 사용하여 외부 폰트 파일에 의존하지 않아야 한다.
- **NFR-PDF-003**: 한글 인코딩 이슈를 피하기 위해 PDF의 섹션 라벨과 고정 텍스트는 영문으로 작성되어야 한다. 데이터 값(전략명 등)은 안전한 매핑을 거치거나 ASCII로 변환되어야 한다.

## 범위

### In Scope
- `lotto/pdf_report.py` 모듈 신설 (`generate_report` 함수)
- `lotto/web/routes/api.py`에 `GET /api/report/pdf` 엔드포인트 추가
- `lotto/web/templates/recommend.html`, `analyze.html`, `simulate.html`에 다운로드 버튼 추가
- `pyproject.toml`에 fpdf2 의존성 추가

### Out of Scope
- 한글 폰트 렌더링 (별도 TTF 임베딩 필요 — 향후 SPEC에서 처리)
- 차트/그래프 이미지 포함 (텍스트 기반 리포트만 제공)
- PDF 페이지 분할/페이지네이션 최적화
- PDF 보안(암호화/서명)

## 의존성

- 신규 라이브러리: `fpdf2` (이미 설치 확인됨)
- 기존 모듈: `lotto.web.data` (get_stats, get_recommendations, get_simulation)
- 기존 모델: `lotto.analyzer.Statistics`, `lotto.recommender.Recommendation`, `lotto.simulator.SimulationResult`

## 참고

- SPEC-WEB-001: 웹 대시보드 기반 인프라
- SPEC-LOTTO-003: 보너스 번호 빈도 통계
