"""Regression tests for the private, read-only ChatGPT connector."""
import io
import json
import os
import unittest
from unittest.mock import MagicMock, call, patch
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


class WorkspaceReadTests(unittest.TestCase):
    def setUp(self):
        connection_patch = patch.object(bridge.http.client, "HTTPConnection")
        self.connection_factory = connection_patch.start()
        self.addCleanup(connection_patch.stop)
        self.connection = self.connection_factory.return_value
        env_patch = patch.dict(os.environ, {"FORAGE_PORT": "8765", "FORAGE_MCP_MAX_MIB": ""})
        env_patch.start()
        self.addCleanup(env_patch.stop)

    def response(self, body, *, status=200, length=None):
        response = MagicMock(status=status, length=length)
        response.__enter__.return_value = response
        response.read.side_effect = io.BytesIO(body).read
        return response

    def respond(self, body, *, status=200, length=None):
        response = self.response(body, status=status, length=length)
        self.connection.getresponse.return_value = response
        return response

    def test_large_workspace_through_mcp_tools(self):
        state = {
            "active": "deck-1",
            "decks": [{"id": "deck-1", "name": "Example", "cards": [
                {"name": "Island", "zone": "main", "qty": 2},
            ]}],
            "collection": [{"name": "Island", "qty": 3}],
            "settings": {"private_setting": "hidden-setting"},
            "chat": "x" * (12 * bridge.MIB),
        }
        body = json.dumps({"state": state, "token": "hidden-token"}).encode()

        for name, arguments in (
            ("list_decks", {}),
            ("search_collection", {"query": "island", "limit": 1}),
        ):
            with self.subTest(name=name):
                missing = self.response(b"", status=404)
                response = self.response(body)
                self.connection.getresponse.side_effect = [missing, response]
                self.connection.request.reset_mock()
                request = {"id": 1, "method": "tools/call",
                           "params": {"name": name, "arguments": arguments}}
                output = io.StringIO()
                bridge.serve([json.dumps(request)], output)
                wire = output.getvalue()
                self.assertNotIn("hidden-token", wire)
                self.assertNotIn("hidden-setting", wire)
                result = json.loads(json.loads(wire)["result"]["content"][0]["text"])
                if name == "list_decks":
                    self.assertEqual(result["decks"][0]["mainboard_count"], 2)
                else:
                    self.assertEqual(result["cards"][0]["availability"]["available"], 1)
                response.read.assert_called_once_with(64 * bridge.MIB + 1)
                self.connection_factory.assert_called_with("127.0.0.1", 8765, timeout=8)
                self.assertEqual(self.connection.request.call_args_list, [
                    call("GET", "/api/mcp-state", headers={"Accept": "application/json"}),
                    call("GET", "/api/state", headers={"Accept": "application/json"}),
                ])
                missing.read.assert_not_called()

    def test_returns_only_tool_state_fields(self):
        self.respond(b'{"token":"secret","state":{"active":null,"decks":[],"collection":[],"settings":{}}}')
        self.assertEqual(bridge.read_workspace(), {"active": None, "decks": [], "collection": []})
        self.connection.request.assert_called_once_with(
            "GET", "/api/mcp-state", headers={"Accept": "application/json"})

    def test_rejects_declared_oversize_before_read(self):
        response = self.respond(b"", length=64 * bridge.MIB + 1)
        with self.assertRaisesRegex(ValueError, r"exceeds bridge size limit \(64 MiB\)"):
            bridge.read_workspace()
        response.read.assert_not_called()
        self.connection.close.assert_called_once()

    def test_checks_actual_size_and_clamps_override(self):
        with patch.dict(os.environ, {"FORAGE_MCP_MAX_MIB": "999"}), patch.object(bridge, "MIB", 1):
            body = b'{"state":{}}'.ljust(128, b" ")
            response = self.respond(body)
            self.assertEqual(bridge.read_workspace(), {})
            response.read.assert_called_once_with(129)
            response = self.respond(body + b" ")
            with self.assertRaisesRegex(ValueError, r"exceeds bridge size limit \(128 MiB\)"):
                bridge.read_workspace()
            response.read.assert_called_once_with(129)

    def test_redirect_is_rejected_without_another_request(self):
        response = self.respond(b"", status=302)
        with self.assertRaisesRegex(ValueError, "Forage workspace request failed"):
            bridge.read_workspace()
        self.connection.request.assert_called_once()
        response.read.assert_not_called()
        self.connection.close.assert_called_once()

    def test_invalid_response_does_not_include_payload_in_error(self):
        for body in (b'{"token":"secret",', b"[]", b'{"state":"secret"}', b"\xff"):
            with self.subTest(body=body):
                self.respond(body)
                with self.assertRaisesRegex(ValueError, "^Invalid Forage workspace response$"):
                    bridge.read_workspace()


if __name__ == "__main__":
    unittest.main()
