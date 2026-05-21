"""CLI 진입점 — typer 기반 collect/analyze/recommend/simulate 서브커맨드."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.table import Table

from lotto.config import settings

console = Console()
app = typer.Typer(
    name="lotto",
    help="로또 번호 추천 프로그램 (통계 기반)",
    add_completion=False,
)

# SPEC-LOTTO-002: 데이터 디렉토리 외부화 — LOTTO_DATA_DIR 환경 변수로 오버라이드 가능
DATA_DIR = settings.data_dir
DISCLAIMER = "이 추천은 통계 기반이며 당첨을 보장하지 않습니다."


def _get_data_dir() -> Path:
    """현재 데이터 디렉토리 경로를 반환합니다."""
    return DATA_DIR


@app.command()
def collect(
    full: Annotated[bool, typer.Option("--full", help="전체 히스토리 재수집")] = False,
) -> None:
    """동행복권 API에서 당첨 번호를 수집합니다."""
    from lotto.collector import CollectAbortError, LottoCollector

    data_dir = _get_data_dir()
    collector = LottoCollector(data_dir=data_dir)

    try:
        if full:
            console.print("[bold]전체 히스토리 재수집을 시작합니다...[/bold]")
            draws = collector.collect_full()
        else:
            existing = collector.load_existing()
            if existing:
                latest = max(d.drwNo for d in existing)
                console.print(f"[bold]기존 {latest}회차 이후 신규 데이터를 수집합니다...[/bold]")
            else:
                latest = 0
                console.print("[bold]신규 데이터를 수집합니다...[/bold]")
            draws = collector.collect_new(latest_drw_no=latest + 50)
        console.print(f"[green]수집 완료: 총 {len(draws)}회차[/green]")
    except CollectAbortError as e:
        console.print(f"[red]수집 중단: {e}[/red]")
        raise typer.Exit(2) from e


@app.command()
def analyze(
    recent_window: Annotated[
        int, typer.Option("--recent-window", help="최근 N 회차 패턴 분석")
    ] = 20,
) -> None:
    """수집된 데이터로 통계를 분석합니다."""
    from lotto.analyzer import LottoAnalyzer
    from lotto.collector import LottoCollector

    data_dir = _get_data_dir()
    csv_path = data_dir / "draws.csv"

    if not csv_path.exists():
        console.print("[red]draws.csv 없습니다. collect 명령을 먼저 실행하세요.[/red]")
        raise typer.Exit(1)

    collector = LottoCollector(data_dir=data_dir)
    draws = collector.load_existing()

    if not draws:
        console.print("[red]수집된 데이터가 없습니다. collect 명령을 먼저 실행하세요.[/red]")
        raise typer.Exit(1)

    import warnings
    with warnings.catch_warnings(record=True) as w_list:
        warnings.simplefilter("always")
        analyzer = LottoAnalyzer(recent_window=recent_window)
        stats = analyzer.analyze(draws)

    if w_list:
        for w in w_list:
            console.print(f"[yellow]경고: {w.message}[/yellow]")

    stats_path = data_dir / "stats.json"
    analyzer.save_stats(stats, stats_path)
    console.print(f"[green]분석 완료: {len(draws)}회차 데이터 분석 → {stats_path}[/green]")


@app.command()
def recommend(
    count: Annotated[
        int, typer.Option("--count", min=1, max=20, help="추천 세트 수 (1~20)")
    ] = 5,
    weights: Annotated[
        Optional[str],  # noqa: UP045
        typer.Option(
            "--weights",
            help="가중치 w_freq,w_recent,w_pair,w_consec (기본: 0.4,0.3,0.2,0.1)",
        ),
    ] = None,
) -> None:
    """통계를 바탕으로 번호 세트를 추천합니다."""
    from lotto.analyzer import LottoAnalyzer
    from lotto.recommender import LottoRecommender, Weights

    data_dir = _get_data_dir()
    stats_path = data_dir / "stats.json"

    if not stats_path.exists():
        console.print("[red]stats.json 없습니다. analyze 명령을 먼저 실행하세요.[/red]")
        raise typer.Exit(1)

    stats = LottoAnalyzer.load_stats(stats_path)

    parsed_weights: Optional[Weights] = None  # noqa: UP045
    if weights is not None:
        try:
            parts = [float(x) for x in weights.split(",")]
            if len(parts) != 4:  # noqa: PLR2004
                console.print("[red]가중치 4개 필요: w_freq,w_recent,w_pair,w_consec[/red]")
                raise typer.Exit(2)
            parsed_weights = Weights(*parts)
        except ValueError as e:
            console.print(f"[red]가중치 파싱 오류: {e}[/red]")
            raise typer.Exit(2) from e

    recommender = LottoRecommender(stats, weights=parsed_weights)
    results = recommender.recommend(count=count)

    table = Table(title="로또 번호 추천")
    table.add_column("세트", style="cyan")
    table.add_column("번호", style="green")
    table.add_column("전략", style="yellow")

    for i, rec in enumerate(results, 1):
        nums_str = ", ".join(f"{n:2d}" for n in rec.numbers)
        table.add_row(str(i), nums_str, rec.strategy_label)

    console.print(table)
    console.print(f"[yellow]{DISCLAIMER}[/yellow]")


@app.command()
def simulate(
    rounds: Annotated[int, typer.Option("--rounds", help="백테스팅 회차 수")] = 10,
    output: Annotated[
        Optional[Path],  # noqa: UP045
        typer.Option("--output", help="결과를 저장할 JSON 파일 경로"),
    ] = None,
) -> None:
    """역대 데이터로 백테스팅 시뮬레이션을 실행합니다."""
    from lotto.collector import LottoCollector
    from lotto.simulator import LottoSimulator

    data_dir = _get_data_dir()
    csv_path = data_dir / "draws.csv"

    if not csv_path.exists():
        console.print("[red]draws.csv 없습니다. collect 명령을 먼저 실행하세요.[/red]")
        raise typer.Exit(1)

    collector = LottoCollector(data_dir=data_dir)
    draws = collector.load_existing()

    if not draws:
        console.print("[red]수집된 데이터가 없습니다. collect 명령을 먼저 실행하세요.[/red]")
        raise typer.Exit(1)

    console.print(f"[bold]{rounds}회차 시뮬레이션을 시작합니다...[/bold]")
    sim = LottoSimulator(draws)
    result = sim.simulate(rounds=rounds)

    # 결과 테이블 출력
    table = Table(title="시뮬레이션 결과")
    table.add_column("등수", style="cyan")
    table.add_column("횟수", style="green")

    for prize, cnt in result.prize_counts.items():
        table.add_row(prize, str(cnt))

    console.print(table)
    console.print(f"적중률 (5등 이상): [bold]{result.hit_rate:.2%}[/bold]")
    console.print(f"총 시뮬레이션 회차: {result.total_rounds}")

    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(result.model_dump(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        console.print(f"[green]결과 저장 완료: {output}[/green]")


@app.command()
def web(
    host: Annotated[str, typer.Option("--host", help="바인딩 호스트")] = settings.web_host,
    port: Annotated[int, typer.Option("--port", help="포트 번호")] = settings.web_port,
    reload: Annotated[bool, typer.Option("--reload", help="자동 재시작 (개발 모드)")] = False,
) -> None:
    """웹 대시보드를 시작합니다.

    SPEC-LOTTO-002: --host/--port 미지정 시 LOTTO_WEB_HOST / LOTTO_WEB_PORT 환경 변수를 사용.
    """
    import uvicorn

    uvicorn.run("lotto.web.app:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    app()
