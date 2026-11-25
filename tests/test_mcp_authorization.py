"""Exercise MCP authorization without touching a live workspace."""
import io
import json
import unittest
from unittest.mock import MagicMock, call, patch

import mcp_bridge as bridge
import server


class LocalAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.handler = object.__new__(server.Handler)
        self.handler.client_address = ("127.0.0.1", 54321)
        self.handler.path = "/api/mcp-auth"
        self.handler.headers = {"Host": "127.0.0.1:8765", "X-Forage-MCP": "1"}
        self.handler.send_json = MagicMock()

    def test_token_is_scoped_and_does_not_read_workspace(self):
        with patch.object(server, "read_state", side_effect=AssertionError("workspace read")):
            self.handler.do_GET()
        self.handler.send_json.assert_called_once_with({"token": server.MCP_TOKEN})
        self.assertNotEqual(server.MCP_TOKEN, server.TOKEN)

        self.handler.headers["X-Forage-MCP-Token"] = server.MCP_TOKEN
        for path in ("/api/restore", "/api/desktop"):
            with self.subTest(path=path):
                self.handler.path = path
                self.handler.handle_post()
                self.assertEqual(self.handler.send_json.call_args.args[1], 403)

    def test_only_non_browser_loopback_clients_can_fetch_token(self):
        for host, peer, marker, extra in (
            ("example.com", "127.0.0.1", "1", {}),
            ("localhost", "192.0.2.1", "1", {}),
            ("localhost", "127.0.0.1", "", {}),
            ("localhost", "127.0.0.1", "1", {"Origin": "https://example.com"}),
            ("localhost", "127.0.0.1", "1", {"Sec-Fetch-Site": "same-origin"}),
        ):
            with self.subTest(host=host, peer=peer, marker=marker, extra=extra):
                self.handler.client_address = (peer, 54321)
                self.handler.headers = {"Host": host, "X-Forage-MCP": marker, **extra}
                self.handler.do_GET()
                self.assertEqual(self.handler.send_json.call_args.args[1], 403)

    def test_scoped_token_authorizes_update_status_only_on_valid_request(self):
        self.handler.path = "/api/mcp-updates"
        body = b'{"action":"status"}'
        self.handler.headers.update({"X-Forage-MCP-Token": server.MCP_TOKEN,
                                     "Content-Length": str(len(body))})
        self.handler.rfile = io.BytesIO(body)
        with patch.object(server.updater, "status", return_value={"current_version": "0.2.48"}):
            self.handler.handle_post()
        self.handler.send_json.assert_called_once_with({"ok": True, "current_version": "0.2.48"})
        self.handler.headers.update({"X-Forage-MCP-Token": "invalid"})
        self.handler.handle_post()
        self.assertEqual(self.handler.send_json.call_args.args[1], 403)


class BridgeAuthorizationTests(unittest.TestCase):
    def test_update_status_never_downloads_workspace(self):
        with patch.object(bridge.http.client, "HTTPConnection") as connect, \
                patch.object(bridge, "read_workspace", side_effect=AssertionError("workspace read")):
            connection = connect.return_value
            auth = MagicMock(status=200)
            auth.__enter__.return_value = auth
            auth.read.return_value = b'{"token":"test-only-secret"}'
            status = MagicMock(status=200)
            status.__enter__.return_value = status
            status.read.return_value = b'{"ok":true,"current_version":"0.2.48"}'
            connection.getresponse.side_effect = [auth, status]

            result = bridge.dispatch({"method": "tools/call", "params": {"name": "update_status"}})
            self.assertEqual(json.loads(result["content"][0]["text"]),
                             {"ok": True, "current_version": "0.2.48"})
            auth.read.assert_called_once_with(bridge.AUTH_MAX_BYTES + 1)
            self.assertEqual(connection.request.call_args_list, [
                call("GET", "/api/mcp-auth", headers=bridge.MCP_HEADERS),
                call("POST", "/api/mcp-updates", body=b'{"action": "status"}',
                     headers={**bridge.MCP_HEADERS, "Content-Type": "application/json",
                              "X-Forage-MCP-Token": "test-only-secret"}),
            ])

    def test_old_server_fails_closed_without_full_state_fallback(self):
        with patch.object(bridge.http.client, "HTTPConnection") as connect:
            connection = connect.return_value
            connection.getresponse.return_value.__enter__.return_value.status = 404
            with self.assertRaisesRegex(ValueError, "v0.2.48"):
                bridge.local_mutation("/api/mcp-updates", {"action": "status"})
            connection.request.assert_called_once_with("GET", "/api/mcp-auth",
                                                       headers=bridge.MCP_HEADERS)

    def test_discovery_lists_tools_while_forage_is_offline(self):
        with patch.object(bridge.http.client, "HTTPConnection", side_effect=AssertionError("HTTP request")):
            tools = bridge.dispatch({"method": "tools/list"})["tools"]
        self.assertEqual(len(tools), 19)
        self.assertEqual({tool["name"] for tool in tools}, {
            "list_decks", "get_deck", "search_collection", "card_availability", "propose_swap",
            "preview_collection_import", "apply_collection_import", "create_deck_version",
            "preview_deck_swap", "apply_deck_swap", "check_updates", "update_status",
            "install_update", "restart_forage",
            "create_deck", "preview_deck_import", "apply_deck_import",
            "preview_collection_change", "apply_collection_change",
        })
