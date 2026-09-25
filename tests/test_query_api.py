from pathlib import Path
import unittest
from unittest.mock import patch

import main


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TWO_PLAN_MARKDOWN = PROJECT_ROOT / "output" / "AI_Trip_Planner_2026-09-25_07-30-38.md"
QUERY = "Plan a 4-day trip from Bengaluru to Jaipur for 2 people with ₹60,000 budget"


class QueryApiAlternativesTests(unittest.TestCase):
    def test_query_response_preserves_structured_alternatives(self):
        raw_markdown = TWO_PLAN_MARKDOWN.read_text(encoding="utf-8")
        ai_message = type("AIMessage", (), {"content": raw_markdown})()

        class FakeGraph:
            def invoke(self, _messages):
                return {"messages": [ai_message]}

        class FakeGraphBuilder:
            def __init__(self, model_provider):
                self.model_provider = model_provider

            def __call__(self):
                return FakeGraph()

        with (
            patch.object(main, "GraphBuilder", FakeGraphBuilder),
            patch.object(main, "save_document"),
            patch.object(main, "save_to_pdf", return_value=None),
        ):
            response = main.query_travel_agent(main.QueryRequest(question=QUERY))

        self.assertIn("answer", response)
        self.assertIn("structured_itinerary", response)
        self.assertIn("pdf_url", response)

        structured = response["structured_itinerary"]
        self.assertEqual(structured["selected_alternative_id"], "classic")
        self.assertEqual([a["id"] for a in structured["alternatives"]], ["classic", "off-beat"])
        self.assertEqual(len(structured["alternatives"]), 2)
        self.assertTrue(all(a["raw_markdown"] and a["itinerary"] for a in structured["alternatives"]))
        self.assertIn("destination", structured)
        self.assertIn("days", structured)
        self.assertEqual(len(structured["days"]), 4)


if __name__ == "__main__":
    unittest.main()
