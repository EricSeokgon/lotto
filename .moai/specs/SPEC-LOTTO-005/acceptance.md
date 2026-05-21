# SPEC-LOTTO-005 Acceptance Criteria

## AC-1: PDF 생성 모듈 (REQ-PDF-001, REQ-PDF-006)

**Given** `lotto.pdf_report` 모듈이 존재할 때
**When** `generate_report(stats=None, recommendations=None, simulation=None)`를 호출하면
**Then** 함수는 `bytes` 타입의 비어있지 않은 값을 반환하고, 예외를 발생시키지 않는다.

검증:
- `isinstance(result, (bytes, bytearray))` is True
- `len(result) > 0`
- PDF 매직 바이트 `%PDF`로 시작

## AC-2: 추천 번호 섹션 (REQ-PDF-002)

**Given** Recommendation 객체 리스트가 주어졌을 때
**When** `generate_report(recommendations=recs)`를 호출하면
**Then** PDF는 추천 섹션을 포함하고, 각 추천의 번호 6개와 전략명이 텍스트로 포함된다.

검증:
- PDF 생성이 성공한다 (bytes 반환, 길이 > 0)

## AC-3: 통계 요약 섹션 (REQ-PDF-003)

**Given** Statistics 객체가 주어졌을 때 (frequency.absolute, bonus_frequency.absolute 포함)
**When** `generate_report(stats=stats)`를 호출하면
**Then** PDF는 상위 10개 빈출 번호와 상위 5개 보너스 빈출 번호 섹션을 포함한다.

검증:
- PDF 생성이 성공한다

## AC-4: 시뮬레이션 결과 섹션 (REQ-PDF-004)

**Given** SimulationResult 객체가 주어졌을 때 (prize_counts 포함)
**When** `generate_report(simulation=sim)`를 호출하면
**Then** PDF는 등수별 당첨 횟수 섹션을 포함한다.

검증:
- PDF 생성이 성공한다

## AC-5: API 엔드포인트 (REQ-PDF-001)

**Given** FastAPI 애플리케이션이 실행 중일 때
**When** 클라이언트가 `GET /api/report/pdf`를 요청하면
**Then** 응답은 HTTP 200이며, Content-Type은 `application/pdf`이고 Content-Disposition 헤더에 `attachment`와 `filename=lotto_report.pdf`를 포함한다.

검증:
- `response.status_code == 200`
- `"application/pdf" in response.headers["content-type"]`
- `"attachment" in response.headers["content-disposition"]`
- `"lotto_report.pdf" in response.headers["content-disposition"]`

## AC-6: 데이터 부재 처리 (REQ-PDF-006, NFR-PDF-001)

**Given** 데이터 파일이 부재하여 get_stats(), get_recommendations(), get_simulation()이 모두 None을 반환할 때
**When** 클라이언트가 `GET /api/report/pdf`를 요청하면
**Then** 응답은 HTTP 200이고, PDF는 빈 섹션 메시지("No data available")를 포함하여 정상 생성된다.

검증:
- `response.status_code == 200` (500 아님)
- 응답 body가 PDF 바이트로 시작

## AC-7: 웹 UI 다운로드 버튼 (REQ-PDF-005)

**Given** 사용자가 `/recommend`, `/analyze`, `/simulate` 페이지에 접근할 때
**When** 페이지가 렌더링되면
**Then** 각 페이지에는 `/api/report/pdf`를 가리키는 다운로드 링크/버튼이 존재한다.

검증 (수동):
- 3개 템플릿에 `href="/api/report/pdf"` 또는 동등한 다운로드 트리거 존재
