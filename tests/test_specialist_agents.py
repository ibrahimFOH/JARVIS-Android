import sys
import unittest
from pathlib import Path

HOST = Path(__file__).resolve().parents[1] / "JARVIS_HOST"
sys.path.insert(0, str(HOST))

from core.specialist_agents import (
    get_agent,
    list_agents,
    prepare_expert_task,
    route_agent,
)


class SpecialistAgentTests(unittest.TestCase):
    def test_all_menu_specialists_have_runtime_profiles(self):
        agents = list_agents()
        self.assertGreaterEqual(len(agents), 12)
        for agent in agents:
            self.assertTrue(get_agent(agent["id"]), agent["id"])
            self.assertTrue(agent["mission"])

    def test_domain_router_prefers_specific_tools(self):
        self.assertEqual(route_agent("Dante Controller clock master ve subscription sorunu"),
                         "dante_network_engineer")
        self.assertEqual(route_agent("SPL hesabı ref_db=100 ref_m=1 target_m=10"),
                         "spl_calculator")
        self.assertEqual(route_agent("Rider içindeki monitör ve input list maddeleri"),
                         "rider_analyst")
        self.assertIsNone(route_agent("Merhaba, saat kaç?"))

    def test_spl_distance_tool_returns_transparent_free_field_estimate(self):
        _, result = prepare_expert_task(
            "spl_calculator",
            "ref_db=100 ref_m=1 target_m=10 power_ratio=1 sources=1",
        )
        self.assertIn("80.00 dB", result)
        self.assertIn("serbest alan tahmini", result.lower())
        self.assertIn("Yansıma", result)

    def test_delay_tool_computes_ms_and_assumption(self):
        _, result = prepare_expert_task("system_tech", "delay_distance_m=10")
        self.assertIn("29.15 ms", result)
        self.assertIn("343 m/s", result)

    def test_invalid_spl_distance_is_rejected(self):
        _, result = prepare_expert_task(
            "spl_calculator", "ref_db=100 ref_m=0 target_m=10"
        )
        self.assertIn("HESAPLAMA HATASI", result)

    def test_unknown_agent_does_not_create_fake_expert(self):
        self.assertIsNone(get_agent("worlds_best_agent"))

    def test_expert_instructions_are_domain_specific(self):
        system, _ = prepare_expert_task("rf_engineer", "Dört kablosuz mikrofon planla")
        self.assertIn("RF", system)
        self.assertIn("scan verisi", system)
        self.assertIn("Fiziksel ölçüm", system)


if __name__ == "__main__":
    unittest.main()
