"""Regression tests for the private, read-only ChatGPT connector."""
import io
import json
import unittest
from unittest.mock import patch
import mcp_bridge as bridge


def fixture():
    return {
        "active": "frog",
        "collection": [
            {"name": "Dour Port-Mage", "qty": 1, "color_identity": ["B"]},
            {"name": "Ponder", "qty": 1, "color_identity": ["U"], "legalities": {"commander": "legal"}},
            {"name": "Forest", "qty": 3, "color_identity": []},
            {"name": "Dark Ritual", "qty": 1, "color_identity": ["B"], "legalities": {"commander": "legal"}},
        ],
        "decks": [
            {"id": "frog", "name": "Frogs", "cards": [
                {"name": "Clement, the Worrywort", "zone": "commander", "qty": 1, "color_identity": ["G", "U"]},
                {"name": "Dour Port-Mage", "zone": "main", "qty": 1},
                {"name": "Island", "zone": "main", "qty": 2},
                {"name": "Unwanted", "zone": "main", "group": "Swap Out", "qty": 1},
                {"name": "Ponder", "zone": "maybe", "qty": 1},
            ]},
            {"id": "ygra", "name": "Ygra", "cards": [
                {"name": "Dour Port Mage", "zone": "main", "qty": 1},
            ]},
        ],
        "settings": {"lm_url": "http://127.0.0.1:1234/v1"},
        "token": "never-expose-this",
    }


class BridgeTests(unittest.TestCase):
    def test_inventory_and_mainboard(self):
        state = fixture()
        decks = bridge.list_decks({}, state)
        self.assertEqual(decks["decks"][0]["mainboard_count"], 4)
        result = bridge.get_deck({"deck_id": "frog"}, state)
        self.assertEqual(result["count"], 4)
        self.assertNotIn("Unwanted", [c["name"] for c in result["cards"]])
        self.assertNotIn("Ponder", [c["name"] for c in result["cards"]])
        self.assertNotIn("token", json.dumps(result))

    def test_collection_search_and_overallocation(self):
        state = fixture()
        result = bridge.search_collection({"query": "port"}, state)
        self.assertEqual(result["total_matching_names"], 1)
        self.assertEqual(result["cards"][0]["availability"]["owned"], 1)
        self.assertEqual(result["cards"][0]["availability"]["assigned_elsewhere"], 2)
        self.assertEqual(result["cards"][0]["availability"]["available"], 0)
        self.assertEqual(bridge.card_availability({"name": "Dour Port-Mage", "exclude_deck_id": "frog"}, state)["assigned_elsewhere"], 1)

    def test_swap_preview_never_changes_state(self):
        state = fixture()
        before = json.dumps(state, sort_keys=True)
        result = bridge.propose_swap({"deck_id": "frog", "add": "Ponder", "cut": "Dour Port-Mage"}, state)
        self.assertEqual(result["status"], "review_only")
        self.assertFalse(result["saved"])
        self.assertTrue(result["ready_to_consider"])
        self.assertEqual(json.dumps(state, sort_keys=True), before)
        with self.assertRaisesRegex(ValueError, "already on the mainboard"):
            bridge.propose_swap({"add": "Dour Port-Mage", "cut": "Island"}, state)
        bad = bridge.propose_swap({"add": "Dark Ritual", "cut": "Island"}, state)
        self.assertIn("Addition is outside commander color identity", bad["warnings"])
        missing = bridge.propose_swap({"add": "Missing Card", "cut": "Island"}, state)
        self.assertIn("Card not found in imported collection", missing["warnings"])

    def test_stdio_protocol(self):
        requests = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "list_decks", "arguments": {}}},
        ]
        source = io.StringIO("\n".join(json.dumps(r) for r in requests) + "\n")
        output = io.StringIO()
        with patch.object(bridge, "read_workspace", return_value=fixture()):
            bridge.serve(source, output)
        messages = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual([x["id"] for x in messages], [1, 2, 3])
        self.assertEqual(messages[0]["result"]["serverInfo"]["name"], "forage-private")
        self.assertEqual(len(messages[1]["result"]["tools"]), 5)
        self.assertTrue(all(tool["annotations"]["readOnlyHint"] for tool in messages[1]["result"]["tools"]))
        self.assertNotIn("never-expose-this", output.getvalue())

    def test_no_credential_or_arbitrary_url_arguments(self):
        for tool in bridge.TOOLS:
            self.assertNotIn("url", tool["inputSchema"]["properties"])
            self.assertNotIn("token", tool["inputSchema"]["properties"])
        self.assertEqual(bridge.normalize("Dour Port-Mage"), bridge.normalize("Dour Port Mage"))


if __name__ == "__main__":
    unittest.main()
