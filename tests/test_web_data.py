"""데이터 레이어 함수 테스트 — interpolate_color, percentiles, get_data_status 등."""

from __future__ import annotations

# ──────────────────────────────────────────────
# T-003: interpolate_color
# ──────────────────────────────────────────────

def test_interpolate_color_at_zero():
    """t=0 일 때 저빈도 색상 반환."""
    from lotto.web.data import interpolate_color

    assert interpolate_color(0.0) == "#E2E8F0"


def test_interpolate_color_at_one():
    """t=1 일 때 고빈도 색상 반환."""
    from lotto.web.data import interpolate_color

    assert interpolate_color(1.0) == "#3B82F6"


def test_interpolate_color_clamps_negative():
    """음수 입력을 0으로 클램핑해 저빈도 색상 반환."""
    from lotto.web.data import interpolate_color

    assert interpolate_color(-0.5) == "#E2E8F0"


def test_interpolate_color_clamps_over_one():
    """1 초과 입력을 1로 클램핑해 고빈도 색상 반환."""
    from lotto.web.data import interpolate_color

    assert interpolate_color(1.5) == "#3B82F6"


def test_interpolate_color_at_half_is_between():
    """t=0.5 일 때 두 색상 사이 R채널 반환."""
    from lotto.web.data import interpolate_color

    result = interpolate_color(0.5)
    assert result.startswith("#")
    assert len(result) == 7
    # R 채널은 0x3B(59)~0xE2(226) 사이
    r = int(result[1:3], 16)
    assert 59 <= r <= 226


# ──────────────────────────────────────────────
# T-004: compute_frequency_percentiles
# ──────────────────────────────────────────────

def test_percentile_highest_frequency_is_one():
    """최고 빈도 번호의 백분위수가 1.0인지 확인."""
    from lotto.web.data import compute_frequency_percentiles

    freqs = {i: i * 5 for i in range(1, 46)}
    result = compute_frequency_percentiles(freqs)
    assert result[45] == 1.0


def test_percentile_lowest_frequency_is_zero():
    """최저 빈도 번호의 백분위수가 0.0인지 확인."""
    from lotto.web.data import compute_frequency_percentiles

    freqs = {i: i * 5 for i in range(1, 46)}
    result = compute_frequency_percentiles(freqs)
    assert result[1] == 0.0


def test_percentile_monotonic_with_distinct_frequencies():
    """빈도가 단조증가할 때 백분위수도 단조증가."""
    from lotto.web.data import compute_frequency_percentiles

    freqs = {i: i * 5 for i in range(1, 46)}
    result = compute_frequency_percentiles(freqs)
    for i in range(1, 45):
        assert result[i] <= result[i + 1]


def test_percentile_tie_break_by_number():
    """동일 빈도 시 번호가 작은 쪽이 더 낮은 백분위수."""
    from lotto.web.data import compute_frequency_percentiles

    freqs = {1: 10, 2: 10, 3: 20}
    result = compute_frequency_percentiles(freqs)
    assert result[1] < result[2]


# ──────────────────────────────────────────────
# T-005: get_data_status, get_draws, get_stats
# ──────────────────────────────────────────────

def test_get_data_status_returns_dataclass():
    """get_data_status 가 DataStatus 인스턴스를 반환하는지 확인."""
    from lotto.web.data import get_data_status

    status = get_data_status()
    assert hasattr(status, "draws_available")
    assert hasattr(status, "stats_available")
    assert isinstance(status.draws_available, bool)
    assert isinstance(status.stats_available, bool)


def test_get_data_status_no_data_both_false(tmp_path, monkeypatch):
    """데이터 파일 없을 때 둘 다 False."""
    from lotto.web.data import get_data_status

    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    status = get_data_status()
    assert status.draws_available is False
    assert status.stats_available is False


def test_get_draws_returns_none_without_csv(tmp_path, monkeypatch):
    """CSV 없을 때 get_draws 가 None 반환."""
    from lotto.web.data import get_draws

    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    result = get_draws()
    assert result is None


def test_get_stats_returns_none_without_json(tmp_path, monkeypatch):
    """stats.json 없을 때 get_stats 가 None 반환."""
    from lotto.web.data import get_stats

    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    result = get_stats()
    assert result is None


# ──────────────────────────────────────────────
# T-006: get_recommendations, get_simulation
# ──────────────────────────────────────────────

def test_get_recommendations_returns_none_without_data(tmp_path, monkeypatch):
    """stats.json 없을 때 get_recommendations 가 None 반환."""
    from lotto.web.data import get_recommendations

    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    result = get_recommendations(count=5)
    assert result is None


def test_get_simulation_returns_none_without_data(tmp_path, monkeypatch):
    """draws.csv 없을 때 get_simulation 이 None 반환."""
    from lotto.web.data import get_simulation

    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    result = get_simulation(rounds=10)
    assert result is None


# ──────────────────────────────────────────────
# 추가 커버리지 향상 테스트
# ──────────────────────────────────────────────

def test_percentile_single_item():
    """항목이 1개일 때 백분위수가 0.0."""
    from lotto.web.data import compute_frequency_percentiles

    result = compute_frequency_percentiles({7: 42})
    assert result[7] == 0.0


def test_get_draws_returns_none_on_exception(tmp_path, monkeypatch):
    """CSV 파싱 실패 시 None 반환."""
    from lotto.web.data import get_draws

    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    # 빈 CSV 파일 생성 (EmptyDataError 유발)
    (tmp_path / "data" / "draws.csv").write_text("")
    result = get_draws()
    assert result is None


def test_get_data_status_csv_exists(tmp_path, monkeypatch):
    """CSV 파일만 있을 때 draws_available=True, stats_available=False."""
    from lotto.web.data import get_data_status

    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "draws.csv").write_text("dummy")
    status = get_data_status()
    assert status.draws_available is True
    assert status.stats_available is False


def test_get_stats_with_mock():
    """get_stats 가 실제 파일 있을 때 LottoAnalyzer.load_stats 를 호출하는지 확인."""
    from unittest.mock import MagicMock, patch

    from lotto.web.data import get_stats

    mock_stats = MagicMock()
    with patch("lotto.web.data.STATS_PATH") as mock_path:
        mock_path.exists.return_value = True
        with patch("lotto.analyzer.LottoAnalyzer.load_stats", return_value=mock_stats):
            result = get_stats()
    assert result == mock_stats


def test_get_recommendations_with_mock():
    """get_recommendations 가 실제 파일 있을 때 추천 결과 반환."""
    from unittest.mock import MagicMock, patch

    from lotto.web.data import get_recommendations

    mock_recs = [MagicMock()]
    with patch("lotto.web.data.STATS_PATH") as mock_path:
        mock_path.exists.return_value = True
        with patch("lotto.web.data.get_stats") as mock_gs:
            mock_gs.return_value = MagicMock()
            with patch("lotto.recommender.LottoRecommender") as mock_rec_cls:
                mock_rec_cls.return_value.recommend.return_value = mock_recs
                result = get_recommendations(count=3)
    assert result == mock_recs


def test_get_simulation_draws_none():
    """get_draws 가 None 반환할 때 get_simulation 도 None 반환."""
    from unittest.mock import patch

    from lotto.web.data import get_simulation

    with patch("lotto.web.data.DRAWS_PATH") as mock_path:
        mock_path.exists.return_value = True
        with patch("lotto.web.data.get_draws", return_value=None):
            result = get_simulation(rounds=10)
    assert result is None


# ──────────────────────────────────────────────
# get_history / save_history 테스트
# ──────────────────────────────────────────────

def test_get_history_returns_empty_when_file_missing(tmp_path, monkeypatch):
    """history.json 없을 때 빈 리스트 반환."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    from lotto.web.data import get_history
    result = get_history()
    assert result == []


def test_get_history_returns_data_from_file(tmp_path, monkeypatch):
    """history.json 있을 때 파싱된 데이터 반환."""
    import json
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    tickets = [{"id": "abc", "drwNo": 1100, "numbers": [1, 2, 3, 4, 5, 6],
                "bought_at": "2024-01-15"}]
    (tmp_path / "data" / "history.json").write_text(json.dumps(tickets), encoding="utf-8")
    from lotto.web.data import get_history
    result = get_history()
    assert result == tickets


def test_get_history_returns_empty_on_invalid_json(tmp_path, monkeypatch):
    """history.json 파싱 실패 시 빈 리스트 반환."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "history.json").write_text("not-json", encoding="utf-8")
    from lotto.web.data import get_history
    result = get_history()
    assert result == []


def test_save_history_creates_file(tmp_path, monkeypatch):
    """save_history 가 history.json 파일을 생성한다."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    from lotto.web.data import save_history
    tickets = [{"id": "abc", "drwNo": 1100, "numbers": [1, 2, 3, 4, 5, 6]}]
    save_history(tickets)
    assert (tmp_path / "data" / "history.json").exists()


def test_save_history_roundtrip(tmp_path, monkeypatch):
    """save_history 후 get_history 로 동일 데이터 읽힌다."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    from lotto.web.data import get_history, save_history
    tickets = [{"id": "xyz", "drwNo": 1050, "numbers": [10, 20, 30, 40, 41, 42]}]
    save_history(tickets)
    result = get_history()
    assert result == tickets


def test_save_history_creates_data_dir_if_missing(tmp_path, monkeypatch):
    """data 디렉토리가 없어도 save_history 가 생성한다."""
    monkeypatch.chdir(tmp_path)
    from lotto.web.data import save_history
    save_history([])
    assert (tmp_path / "data" / "history.json").exists()


# ──────────────────────────────────────────────
# _calc_prize 테스트
# ──────────────────────────────────────────────

def test_calc_prize_1st():
    """6개 일치 → 1등."""
    from lotto.web.data import _calc_prize
    assert _calc_prize(6, False) == "1등"


def test_calc_prize_2nd():
    """5개 + 보너스 → 2등."""
    from lotto.web.data import _calc_prize
    assert _calc_prize(5, True) == "2등"


def test_calc_prize_3rd():
    """5개 (보너스 없음) → 3등."""
    from lotto.web.data import _calc_prize
    assert _calc_prize(5, False) == "3등"


def test_calc_prize_4th():
    """4개 일치 → 4등."""
    from lotto.web.data import _calc_prize
    assert _calc_prize(4, False) == "4등"


def test_calc_prize_5th():
    """3개 일치 → 5등."""
    from lotto.web.data import _calc_prize
    assert _calc_prize(3, False) == "5등"


def test_calc_prize_no_win():
    """2개 이하 → 낙첨."""
    from lotto.web.data import _calc_prize
    assert _calc_prize(2, False) == "낙첨"
    assert _calc_prize(0, False) == "낙첨"


# ──────────────────────────────────────────────
# compute_ticket_results 테스트
# ──────────────────────────────────────────────

def test_compute_ticket_results_empty_history(tmp_path, monkeypatch):
    """히스토리 없을 때 빈 리스트 반환."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    from lotto.web.data import compute_ticket_results
    result = compute_ticket_results()
    assert result == []


def test_compute_ticket_results_no_draw_match(tmp_path, monkeypatch):
    """추첨 데이터 없을 때 미추첨 상태 반환."""
    import json
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    tickets = [{"id": "abc", "drwNo": 9999, "numbers": [1, 2, 3, 4, 5, 6],
                "bought_at": "2024-01-01"}]
    (tmp_path / "data" / "history.json").write_text(json.dumps(tickets), encoding="utf-8")

    from unittest.mock import patch

    from lotto.web.data import compute_ticket_results

    with patch("lotto.web.data.get_draws", return_value=None):
        result = compute_ticket_results()

    assert len(result) == 1
    assert result[0]["prize"] == "미추첨"
    assert result[0]["matched"] == 0


def test_compute_ticket_results_with_draw_match(tmp_path, monkeypatch):
    """추첨 데이터와 매칭되면 등수가 계산된다."""
    import json
    from unittest.mock import MagicMock, patch

    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()

    # 1~6 모두 일치 → 1등
    tickets = [{"id": "abc", "drwNo": 1100, "numbers": [1, 2, 3, 4, 5, 6],
                "bought_at": "2024-01-15"}]
    (tmp_path / "data" / "history.json").write_text(json.dumps(tickets), encoding="utf-8")

    mock_draw = MagicMock()
    mock_draw.drwNo = 1100
    mock_draw.numbers.return_value = [1, 2, 3, 4, 5, 6]
    mock_draw.bonus = 7
    mock_draw.date = "2024-01-15"

    from lotto.web.data import compute_ticket_results

    with patch("lotto.web.data.get_draws", return_value=[mock_draw]):
        result = compute_ticket_results()

    assert len(result) == 1
    assert result[0]["prize"] == "1등"
    assert result[0]["matched"] == 6


def test_compute_ticket_results_sorted_by_drw_no_desc(tmp_path, monkeypatch):
    """결과가 drwNo 내림차순으로 정렬된다."""
    import json
    from unittest.mock import patch

    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()

    tickets = [
        {"id": "a", "drwNo": 1100, "numbers": [1, 2, 3, 4, 5, 6], "bought_at": "2024-01-15"},
        {"id": "b", "drwNo": 1200, "numbers": [7, 8, 9, 10, 11, 12], "bought_at": "2024-06-01"},
    ]
    (tmp_path / "data" / "history.json").write_text(json.dumps(tickets), encoding="utf-8")

    from lotto.web.data import compute_ticket_results

    with patch("lotto.web.data.get_draws", return_value=None):
        result = compute_ticket_results()

    assert result[0]["ticket"]["drwNo"] == 1200
    assert result[1]["ticket"]["drwNo"] == 1100


def test_compute_ticket_results_5th_prize(tmp_path, monkeypatch):
    """3개 일치 → 5등 계산."""
    import json
    from unittest.mock import MagicMock, patch

    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()

    tickets = [{"id": "abc", "drwNo": 1100, "numbers": [1, 2, 3, 40, 41, 42],
                "bought_at": "2024-01-15"}]
    (tmp_path / "data" / "history.json").write_text(json.dumps(tickets), encoding="utf-8")

    mock_draw = MagicMock()
    mock_draw.drwNo = 1100
    mock_draw.numbers.return_value = [1, 2, 3, 4, 5, 6]
    mock_draw.bonus = 7
    mock_draw.date = "2024-01-15"

    from lotto.web.data import compute_ticket_results

    with patch("lotto.web.data.get_draws", return_value=[mock_draw]):
        result = compute_ticket_results()

    assert result[0]["prize"] == "5등"
    assert result[0]["matched"] == 3


# ──────────────────────────────────────────────
# get_strategy_comparison 가드 테스트
# ──────────────────────────────────────────────

def test_get_strategy_comparison_no_files_returns_none(tmp_path, monkeypatch):
    """draws.csv 또는 stats.json 없을 때 None 반환 확인."""
    from lotto.web import data as wd

    monkeypatch.setattr(wd, "DRAWS_PATH", tmp_path / "draws.csv")
    monkeypatch.setattr(wd, "STATS_PATH", tmp_path / "stats.json")

    result = wd.get_strategy_comparison()
    assert result is None


def test_get_strategy_comparison_empty_draws_returns_none(tmp_path, monkeypatch):
    """draws.csv 존재하지만 get_draws가 None일 때 None 반환 확인."""
    from unittest.mock import patch

    from lotto.web import data as wd

    draws_path = tmp_path / "draws.csv"
    stats_path = tmp_path / "stats.json"
    draws_path.write_text("dummy")
    stats_path.write_text("{}")

    monkeypatch.setattr(wd, "DRAWS_PATH", draws_path)
    monkeypatch.setattr(wd, "STATS_PATH", stats_path)

    with patch.object(wd, "get_draws", return_value=None), \
         patch.object(wd, "get_stats", return_value=None):
        result = wd.get_strategy_comparison()

    assert result is None


def test_get_recommendations_stats_none_returns_none(tmp_path, monkeypatch):
    """STATS_PATH 존재하지만 get_stats()가 None일 때 None 반환 확인."""
    from unittest.mock import patch

    from lotto.web import data as wd

    stats_path = tmp_path / "stats.json"
    stats_path.write_text("{}")

    monkeypatch.setattr(wd, "STATS_PATH", stats_path)

    with patch.object(wd, "get_stats", return_value=None):
        result = wd.get_recommendations()

    assert result is None
