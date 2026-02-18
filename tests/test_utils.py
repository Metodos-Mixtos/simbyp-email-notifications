import unittest
from datetime import datetime
from src import utils

class TestSchedulingUtils(unittest.TestCase):
    """Test scheduling utilities"""

    def test_is_first_friday_not_friday(self):
        """Test that non-Friday dates return False"""
        # February 10, 2026 is a Monday
        test_date = datetime(2026, 2, 10)
        self.assertFalse(utils.is_first_friday_of_month(test_date))

    def test_is_first_friday_first_week(self):
        """Test that first Friday of month (in first week) returns True"""
        # February 6, 2026 is a Friday and in first week
        test_date = datetime(2026, 2, 6)
        self.assertTrue(utils.is_first_friday_of_month(test_date))

    def test_is_first_friday_second_week(self):
        """Test that Friday in second week returns False"""
        # February 13, 2026 is a Friday but not in first week
        test_date = datetime(2026, 2, 13)
        self.assertFalse(utils.is_first_friday_of_month(test_date))

    def test_get_first_friday_of_month(self):
        """Test getting first Friday of month"""
        # February 2026's first Friday should be the 6th
        first_friday = utils.get_this_month_first_friday()
        # Note: This test depends on when it's run; we test the logic instead
        self.assertEqual(first_friday.weekday(), 4)  # 4 = Friday
        self.assertGreaterEqual(first_friday.day, 1)
        self.assertLessEqual(first_friday.day, 7)


if __name__ == '__main__':
    unittest.main()
