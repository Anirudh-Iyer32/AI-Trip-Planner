from pathlib import Path
import re
import unittest

from agent.itinerary_structurer import normalize_text, structure_and_validate_itinerary


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TWO_PLAN_MARKDOWN = PROJECT_ROOT / "output" / "AI_Trip_Planner_2026-09-25_07-30-38.md"
QUERY = "Plan a 4-day trip from Bengaluru to Jaipur for 2 people with ₹60,000 budget"


class MultiItineraryParserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = TWO_PLAN_MARKDOWN.read_text(encoding="utf-8")
        cls.structured = structure_and_validate_itinerary(cls.raw, QUERY)
        cls.alternatives = cls.structured["alternatives"]

    def test_detects_and_names_both_alternatives(self):
        self.assertEqual(len(self.alternatives), 2)
        self.assertEqual([a["id"] for a in self.alternatives], ["classic", "off-beat"])
        self.assertEqual([a["kind"] for a in self.alternatives], ["classic", "off_beat"])
        classic_name = re.sub(r"[^a-z0-9]+", "-", normalize_text(self.alternatives[0]["name"]).lower())
        off_beat_name = re.sub(r"[^a-z0-9]+", "-", normalize_text(self.alternatives[1]["name"]).lower())
        self.assertIn("classic-tourist-friendly-itinerary", classic_name)
        self.assertIn("off-beat-heritage-local-flavor-itinerary", off_beat_name)

    def test_each_alternative_has_its_own_four_day_plan(self):
        self.assertEqual(len(self.alternatives[0]["itinerary"]["days"]), 4)
        self.assertEqual(len(self.alternatives[1]["itinerary"]["days"]), 4)
        classic_main_counts = [
            sum(activity["time"] == "Flexible" for activity in day["activities"])
            for day in self.alternatives[0]["itinerary"]["days"]
        ]
        self.assertEqual(classic_main_counts, [3, 5, 5, 3])
        self.assertTrue(all(day["activities"] for day in self.alternatives[1]["itinerary"]["days"]))

    def test_raw_sections_do_not_bleed_into_each_other(self):
        classic_raw = self.alternatives[0]["raw_markdown"]
        off_beat_raw = self.alternatives[1]["raw_markdown"]
        self.assertIn("Amber Fort", classic_raw)
        self.assertNotIn("Panna Meena Ka Kund", classic_raw)
        self.assertIn("Panna Meena Ka Kund", off_beat_raw)
        self.assertNotIn("Amber Fort", off_beat_raw)
        self.assertNotIn("How the Plans Stay Within", off_beat_raw)

        classic_activities = " ".join(
            activity["description"]
            for day in self.alternatives[0]["itinerary"]["days"]
            for activity in day["activities"]
        )
        off_beat_activities = " ".join(
            activity["description"]
            for day in self.alternatives[1]["itinerary"]["days"]
            for activity in day["activities"]
        )
        self.assertNotIn("Panna Meena Ka Kund", classic_activities)
        self.assertNotIn("Amber Fort", off_beat_activities)

    def test_top_level_remains_the_first_selected_itinerary(self):
        self.assertEqual(self.structured["selected_alternative_id"], "classic")
        self.assertEqual(self.structured["days"], self.alternatives[0]["itinerary"]["days"])

    def test_single_itinerary_output_remains_unchanged(self):
        single_raw = """## Single City Itinerary

| Day | Main Activities | Suggested Hotel* | Meals & Restaurants | Transport | Entry-fees & Extras |
|-----|-----------------|------------------|----------------------|-----------|---------------------|
| **1 - Arrival** | • Check-in <br>• Museum visit | Hotel One | Dinner at Cafe | Metro | - |
"""
        structured = structure_and_validate_itinerary(single_raw, "Plan a 1-day trip to Test City")
        self.assertNotIn("alternatives", structured)
        self.assertNotIn("selected_alternative_id", structured)
        self.assertEqual(len(structured["days"]), 1)
        self.assertEqual(sum(a["time"] == "Flexible" for a in structured["days"][0]["activities"]), 2)


if __name__ == "__main__":
    unittest.main()
