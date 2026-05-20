"""web 서브커맨드 CLI 테스트."""

from __future__ import annotations

from typer.testing import CliRunner

runner = CliRunner()


def _get_app():
    """main.py 에서 Typer 앱을 가져옵니다."""
    import sys

    # main 모듈 강제 재로드
    if "main" in sys.modules:
        del sys.modules["main"]
    import main  # noqa: F401

    return main.app


def test_web_subcommand_exists():
    """web 서브커맨드가 존재하는지 확인."""
    app = _get_app()
    result = runner.invoke(app, ["web", "--help"])
    assert result.exit_code == 0, result.output
    assert "--host" in result.output or "host" in result.output


def test_web_subcommand_in_help():
    """전체 도움말에 web 서브커맨드가 표시되는지 확인."""
    app = _get_app()
    result = runner.invoke(app, ["--help"])
    assert "web" in result.output


def test_web_default_host_option():
    """--host 옵션 기본값이 도움말에 표시되는지 확인."""
    app = _get_app()
    result = runner.invoke(app, ["web", "--help"])
    assert "127.0.0.1" in result.output or "host" in result.output.lower()


def test_web_port_option():
    """--port 옵션이 도움말에 표시되는지 확인."""
    app = _get_app()
    result = runner.invoke(app, ["web", "--help"])
    assert "port" in result.output.lower() or "8000" in result.output
