from __future__ import annotations

import unittest

from stock_automation.indicators import Bar, compute_features


class IndicatorTests(unittest.TestCase):
    def test_detects_rising_intraday_structure_and_breakout_hold(self):
        daily = []
        for index in range(130):
            close = 10_000 + index * 8 + (20 if index % 3 else -10)
            daily.append(Bar(str(index), close - 20, close + 80, close - 80, close, 100_000 + index))

        minutes = []
        for index in range(30):
            close = 10_800 + index * 8
            high = close + 10
            low = close - 10
            volume = 1_000 if index < 27 else 2_500
            minutes.append(Bar(f"{index:02d}", close - 5, high, low, close, volume))
        # Force the last three bars to hold above the earlier 20-bar high.
        prior_high = max(bar.high for bar in minutes[-23:-3])
        for index in range(27, 30):
            close = prior_high + 5 + (index - 27) * 4
            minutes[index] = Bar(f"{index:02d}", close - 2, close + 4, prior_high + 1, close, 3_000)

        features = compute_features(daily, minutes)
        self.assertGreater(features.five_min_ma20_slope, 0)
        self.assertGreater(features.five_min_volume_ratio, 1)
        self.assertTrue(features.higher_lows)
        self.assertTrue(features.breakout_holds)
        self.assertGreater(features.vwap, 0)


if __name__ == "__main__":
    unittest.main()
