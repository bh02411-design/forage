import io
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import MagicMock, patch

import mcp_bridge
import server
from core import make_entry


class CollectionChangeTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        data = patch.object(server, 'DATA', Path(directory.name))
        data.start()
        self.addCleanup(data.stop)
        self.before = server.read_state()
        first = {**make_entry('Forest', 3), 'scryfall_id': 'printing-one'}
        second = {**make_entry('Forest', 2), 'scryfall_id': 'printing-two'}
        self.before['collection'] = [first, second, make_entry('Island', 4)]
        server.write_state(self.before)
        self.handler = object.__new__(server.Handler)
        self.handler.client_address = ('127.0.0.1', 12345)
        self.handler.send_json = MagicMock()

    def request(self, change, path='mcp-collection-change', auth='mcp'):
        self.handler.path = '/api/' + path
        body = json.dumps(change).encode()
        self.handler.headers = {'Host': 'localhost', 'Content-Length': str(len(body))}
        if auth == 'mcp':
            self.handler.headers.update({'X-Forage-MCP': '1', 'X-Forage-MCP-Token': server.MCP_TOKEN})
        if auth == 'browser':
            self.handler.headers['X-Forage-Token'] = server.TOKEN
        self.handler.rfile = io.BytesIO(body)
        self.handler.handle_post()
        return self.handler.send_json.call_args.args

    def apply_payload(self, change, preview):
        return {**change, 'action': 'apply', 'confirm': True,
                'expected_collection_sha': preview['collection_sha'],
                'expected_change_sha': preview['change_sha']}

    def test_append_preserves_existing_rows_and_backup_is_pre_edit(self):
        change = {'operation': 'append', 'text': '2 Forest\n1 Plains\n1 Forest [Considering]'}
        preview, = self.request({**change, 'action': 'preview'})
        self.assertEqual(preview['copies_after'], 13)
        self.assertEqual(server.read_state(), self.before)
        result, = self.request(self.apply_payload(change, preview))
        self.assertTrue(result['verified'])
        saved = server.read_state()
        previous = self.before['collection']
        self.assertEqual(saved['collection'][:3], [{**previous[0], 'qty': 6}, *previous[1:]])
        self.assertEqual(saved['collection'][3]['name'], 'Plains')
        self.assertEqual(saved['decks'], self.before['decks'])
        backup, = (server.DATA / 'mcp-backups').glob('*.sqlite3')
        with closing(sqlite3.connect(backup)) as conn:
            self.assertEqual(json.loads(conn.execute('SELECT payload FROM workspace').fetchone()[0]), self.before)

    def test_browser_add_decrease_and_remove(self):
        for operation, name, quantity, before, after in (
            ('add', 'Pollywog Prodigy', 1, 0, 1),
            ('decrease', 'Forest', 3, 5, 2),
            ('remove', 'Forest', None, 2, 0),
        ):
            change = {'operation': operation, 'name': name}
            if quantity is not None:
                change['quantity'] = quantity
            route = {'path': 'collection-change', 'auth': 'browser'}
            preview, = self.request({**change, 'action': 'preview'}, **route)
            self.assertEqual(preview['changes'], [{'name': name, 'before': before, 'after': after}])
            result, = self.request(self.apply_payload(change, preview), **route)
            self.assertTrue(result['saved'])
            if operation == 'decrease':
                self.assertEqual(server.read_state()['collection'][0],
                                 {**self.before['collection'][0], 'qty': 2})
        self.assertEqual([row['name'] for row in server.read_state()['collection']],
                         ['Island', 'Pollywog Prodigy'])

    def test_approval_hashes_authorization_and_replay(self):
        change = {'operation': 'add', 'name': 'Forest', 'quantity': 1}
        preview_payload = {**change, 'action': 'preview'}
        self.assertEqual(self.request(preview_payload, auth='browser')[1], 403)
        self.assertEqual(self.request(preview_payload, path='collection-change')[1], 403)
        self.assertEqual(self.request(preview_payload, auth=None)[1], 403)
        preview, = self.request(preview_payload)
        apply_payload = self.apply_payload(change, preview)
        for override in ({'confirm': False}, {'quantity': 2}, {'expected_change_sha': '0' * 64}):
            self.assertEqual(self.request({**apply_payload, **override})[1], 400)
        self.assertFalse((server.DATA / 'mcp-backups').exists())
        self.assertTrue(self.request(apply_payload)[0]['saved'])
        self.assertEqual(self.request(apply_payload)[1], 400)

    def test_invalid_quantity_and_backup_failure_save_nothing(self):
        for quantity in (True, 0, 6, 1.5):
            self.assertEqual(self.request({'action': 'preview', 'operation': 'decrease',
                                           'name': 'Forest', 'quantity': quantity})[1], 400)
        change = {'operation': 'remove', 'name': 'Forest'}
        preview, = self.request({**change, 'action': 'preview'})
        connect = sqlite3.connect
        def fail_backup(path, **kwargs):
            if Path(path).parent.name == 'mcp-backups':
                raise OSError('Backup unavailable')
            return connect(path, **kwargs)
        with patch.object(server.sqlite3, 'connect', side_effect=fail_backup):
            self.assertGreaterEqual(self.request(self.apply_payload(change, preview))[1], 400)
        self.assertEqual(server.read_state(), self.before)

    def test_bridge_apply_requires_approval_and_both_hashes(self):
        with patch.object(mcp_bridge, 'local_mutation') as send:
            for args in ({'confirm': False}, {'confirm': True, 'expected_change_sha': '0' * 64}):
                with self.assertRaises(ValueError):
                    mcp_bridge.apply_collection_change(args, None)
            send.assert_not_called()
            args = {'operation': 'remove', 'name': 'Forest', 'confirm': True,
                    'expected_collection_sha': '0' * 64, 'expected_change_sha': '1' * 64}
            mcp_bridge.apply_collection_change(args, None)
            send.assert_called_once_with('/api/mcp-collection-change', {**args, 'action': 'apply'})
