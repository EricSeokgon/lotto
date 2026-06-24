import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from lotto.web.app import app
from lotto.web.data import get_median_analysis
from lotto.models import DrawResult

client = TestClient(app)

def make_draws(nums_list):
    import datetime
    draws = []
    for i, nums in enumerate(nums_list, start=1):
        d = DrawResult(
            drwNo=i,
            date=datetime.date(2020, 1, i),
            n1=nums[0], n2=nums[1], n3=nums[2],
            n4=nums[3], n5=nums[4], n6=nums[5],
            bonus=7,
        )
        draws.append(d)
    return draws

SAMPLE = [
    [1, 5, 10, 20, 30, 40],
    [3, 8, 15, 25, 35, 42],
    [2, 6, 12, 22, 32, 44],
    [4, 9, 18, 28, 38, 45],
    [7, 11, 16, 24, 34, 43],
]

def test_returns_none_when_empty():
    with patch('lotto.web.data.get_draws', return_value=[]):
        assert get_median_analysis() is None

def test_returns_dict():
    draws = make_draws(SAMPLE)
    with patch('lotto.web.data.get_draws', return_value=draws):
        result = get_median_analysis()
    assert isinstance(result, dict)

def test_required_keys():
    draws = make_draws(SAMPLE)
    with patch('lotto.web.data.get_draws', return_value=draws):
        result = get_median_analysis()
    for key in ['total','avg_median','min_median','max_median','min_draw','max_draw',
                'best_bucket_label','bucket_list','below_center','above_center','at_center','recent']:
        assert key in result

def test_avg_median_in_range():
    draws = make_draws(SAMPLE)
    with patch('lotto.web.data.get_draws', return_value=draws):
        result = get_median_analysis()
    assert 1.5 <= result['avg_median'] <= 44.5

def test_min_le_avg_le_max():
    draws = make_draws(SAMPLE)
    with patch('lotto.web.data.get_draws', return_value=draws):
        result = get_median_analysis()
    assert result['min_median'] <= result['avg_median'] <= result['max_median']

def test_bucket_list_length_is_7():
    draws = make_draws(SAMPLE)
    with patch('lotto.web.data.get_draws', return_value=draws):
        result = get_median_analysis()
    assert len(result['bucket_list']) == 7

def test_bucket_list_sum_equals_total():
    draws = make_draws(SAMPLE)
    with patch('lotto.web.data.get_draws', return_value=draws):
        result = get_median_analysis()
    assert sum(b['count'] for b in result['bucket_list']) == result['total']

def test_center_split_sums_to_total():
    draws = make_draws(SAMPLE)
    with patch('lotto.web.data.get_draws', return_value=draws):
        result = get_median_analysis()
    assert result['below_center'] + result['above_center'] + result['at_center'] == result['total']

def test_recent_length_lte_20():
    draws = make_draws(SAMPLE)
    with patch('lotto.web.data.get_draws', return_value=draws):
        result = get_median_analysis()
    assert len(result['recent']) <= 20

def test_median_page_200():
    response = client.get('/stats/median')
    assert response.status_code == 200
