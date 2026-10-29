from __future__ import annotations

import unittest

from stock_automation.config import StrategyConfig
from stock_automation.learning import champion_matches_code, config_from_champion


class ChampionConfigTests(unittest.TestCase):
    def payload(self):
        return {
            "mode": "PAPER_ONLY",
            "rule_version": "closing-v0.2-learned",
            "base_rule_version": "closing-v0.4",
            "session": "KRX_1520",
            "parameters": {
                "minimum_score": 62.0,
                "minimum_close_strength": 0.66,
                "minimum_volume_ratio": 1.2,
                "maximum_day_gain_pct": 12.0,
                "maximum_ma5_distance_pct": 6.0,
            },
        }

    def test_loads_validated_paper_champion(self):
        config = config_from_champion(StrategyConfig(), self.payload())
        self.assertEqual("closing-v0.2-learned", config.rule_version)
        self.assertEqual(0.66, config.minimum_close_strength)

    def test_rejects_live_mode_or_unsafe_range(self):
        live = self.payload()
        live["mode"] = "LIVE"
        with self.assertRaisesRegex(ValueError, "paper mode"):
            config_from_champion(StrategyConfig(), live)
        unsafe = self.payload()
        unsafe["parameters"]["minimum_score"] = 10
        with self.assertRaisesRegex(ValueError, "safety envelope"):
            config_from_champion(StrategyConfig(), unsafe)

    def test_rejects_champion_tuned_on_other_engine_logic(self):
        legacy = self.payload()
        del legacy["base_rule_version"]  # written before closing-v0.4
        older = self.payload()
        older["base_rule_version"] = "closing-v0.3"
        for payload in (legacy, older):
            self.assertFalse(champion_matches_code(StrategyConfig(), payload))
            with self.assertRaisesRegex(ValueError, "base version"):
                config_from_champion(StrategyConfig(), payload)
        self.assertTrue(champion_matches_code(StrategyConfig(), self.payload()))


if __name__ == "__main__":
    unittest.main()
