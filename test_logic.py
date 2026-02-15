from datetime import datetime
from logic import get_arrival_in_minutes_from_now, filter_arrivals, format_arrival_triple


class TestGetArrivalInMinutesFromNow:
    def test_basic(self):
        now = datetime(2024, 1, 1, 12, 0, 0)
        assert get_arrival_in_minutes_from_now(now, "2024-01-01T12:10:00") == 10

    def test_with_timezone_suffix(self):
        now = datetime(2024, 1, 1, 12, 0, 0)
        assert get_arrival_in_minutes_from_now(now, "2024-01-01T12:15:00-05:00") == 15

    def test_rounds(self):
        now = datetime(2024, 1, 1, 12, 0, 0)
        assert get_arrival_in_minutes_from_now(now, "2024-01-01T12:00:30") == 0
        assert get_arrival_in_minutes_from_now(now, "2024-01-01T12:01:30") == 2

    def test_negative_time(self):
        now = datetime(2024, 1, 1, 12, 10, 0)
        assert get_arrival_in_minutes_from_now(now, "2024-01-01T12:00:00") == -10

    def test_zero(self):
        now = datetime(2024, 1, 1, 12, 0, 0)
        assert get_arrival_in_minutes_from_now(now, "2024-01-01T12:00:00") == 0


class TestFilterArrivals:
    def test_filters_negative(self):
        now = datetime(2024, 1, 1, 12, 0, 0)
        times = [
            "2024-01-01T11:55:00",  # -5 min - filtered
            "2024-01-01T12:03:00",  # 3 min - kept
            "2024-01-01T12:20:00",  # 20 min - kept
        ]
        assert filter_arrivals(now, times) == [3, 20]

    def test_empty_list(self):
        now = datetime(2024, 1, 1, 12, 0, 0)
        assert filter_arrivals(now, []) == []

    def test_all_negative_filtered(self):
        now = datetime(2024, 1, 1, 12, 10, 0)
        times = ["2024-01-01T12:00:00", "2024-01-01T12:05:00"]
        assert filter_arrivals(now, times) == []

    def test_zero_kept(self):
        now = datetime(2024, 1, 1, 12, 0, 0)
        times = ["2024-01-01T12:00:00"]
        assert filter_arrivals(now, times) == [0]

    def test_keeps_small_positive(self):
        now = datetime(2024, 1, 1, 12, 0, 0)
        times = ["2024-01-01T12:01:00", "2024-01-01T12:02:00"]
        assert filter_arrivals(now, times) == [1, 2]


class TestFormatArrivalTriple:
    def test_three_values(self):
        assert format_arrival_triple([10, 20, 30]) == ('10', '20', '30')

    def test_two_values(self):
        assert format_arrival_triple([10, 20]) == ('10', '20', '-')

    def test_one_value(self):
        assert format_arrival_triple([10]) == ('10', '-', '-')

    def test_empty(self):
        assert format_arrival_triple([]) == ('-', '-', '-')

    def test_more_than_three(self):
        assert format_arrival_triple([10, 20, 30, 40]) == ('10', '20', '30')
