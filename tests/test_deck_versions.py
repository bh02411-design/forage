"""Regression tests for named deck snapshots and backup round-trips."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import server


class SavedVersionsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.data_patch=patch.object(server,'DATA',Path(self.temp.name))
        self.data_patch.start()
        self.addCleanup(self.data_patch.stop)
        self.state=server.read_state()
        self.deck=self.state['decks'][0]
        self.deck['cards']=[{'id':'one','name':'Sol Ring','qty':1,'zone':'main','group':'Ramp'}]
        self.deck['categories']=['Ramp']
        server.write_state(self.state)

    def test_snapshots_are_not_in_normal_workspace(self):
        saved=server.save_deck_version(self.deck,'Original')
        self.assertEqual(len(server.list_deck_versions(self.deck['id'])),1)
        self.assertEqual(server.list_deck_versions(self.deck['id'])[0]['card_count'],1)
        normal=server.read_state()
        self.assertNotIn('saved_versions',normal['decks'][0])
        self.assertNotIn(saved['id'],json.dumps(normal))

    def test_restore_is_reversible_and_keeps_version(self):
        saved=server.save_deck_version(self.deck,'Baseline')
        self.deck['cards']=[{'id':'two','name':'Arcane Signet','qty':1,'zone':'main'}]
        self.deck['categories']=['Mana']
        server.restore_deck_version(self.deck,saved['id'])
        self.assertEqual(self.deck['cards'][0]['name'],'Sol Ring')
        self.assertEqual(self.deck['categories'],['Ramp'])
        self.assertEqual(len(server.list_deck_versions(self.deck['id'])),1)
        undo=self.deck['history'].pop()
        self.deck['cards']=undo['before']
        self.deck['categories']=undo['before_categories']
        self.assertEqual(self.deck['cards'][0]['name'],'Arcane Signet')
        self.assertEqual(self.deck['categories'],['Mana'])

    def test_backup_round_trip_and_isolation(self):
        first=server.save_deck_version(self.deck,'Old')
        exported=server.workspace_backup(server.read_state())
        self.assertEqual(exported['decks'][0]['saved_versions'][0]['id'],first['id'])
        server.delete_deck_version(self.deck,first['id'])
        self.assertFalse(server.list_deck_versions(self.deck['id']))
        server.validate_backup(exported)
        server.restore_workspace_backup(exported)
        self.assertEqual(server.list_deck_versions(self.deck['id'])[0]['name'],'Old')
        self.assertNotIn('saved_versions',server.read_state()['decks'][0])

    def test_legacy_embedded_versions_are_migrated(self):
        legacy=copy.deepcopy(self.state)
        saved={'id':'legacy-id','name':'Early snapshot',
               'created_at':'2026-11-09T23:31:00+00:00',
               'snapshot':{'cards':copy.deepcopy(self.deck['cards'])}}
        legacy['decks'][0]['saved_versions']=[saved]
        with server.db() as conn:
            conn.execute('UPDATE workspace SET payload=? WHERE id=1',(json.dumps(legacy),))
        migrated=server.read_state()
        self.assertNotIn('saved_versions',migrated['decks'][0])
        self.assertEqual(server.list_deck_versions(self.deck['id'])[0]['id'],'legacy-id')

    def test_hundred_versions_do_not_expand_workspace_payload(self):
        baseline=len(json.dumps(server.read_state()))
        for number in range(100):
            server.save_deck_version(self.deck,'Version '+str(number))
        self.assertEqual(len(server.list_deck_versions(self.deck['id'])),100)
        self.assertEqual(len(json.dumps(server.read_state())),baseline)
        with self.assertRaises(ValueError):
            server.save_deck_version(self.deck,'Version 101')

    def test_http_state_and_snapshot_listing(self):
        import threading
        import urllib.request
        from http.server import ThreadingHTTPServer
        server.save_deck_version(self.deck,'Original')
        app=ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        thread=threading.Thread(target=app.serve_forever,daemon=True)
        thread.start()
        self.addCleanup(thread.join,2)
        self.addCleanup(app.server_close)
        self.addCleanup(app.shutdown)
        base='http://127.0.0.1:'+str(app.server_address[1])
        with urllib.request.urlopen(base+'/api/state',timeout=5) as response:
            state=json.load(response)['state']
        self.assertNotIn('saved_versions',state['decks'][0])
        with urllib.request.urlopen(base+'/api/deck-versions?deck='+self.deck['id'],timeout=5) as response:
            versions=json.load(response)['versions']
        self.assertEqual(versions[0]['name'],'Original')
        self.assertNotIn('snapshot',versions[0])
        with urllib.request.urlopen(base+'/api/backup',timeout=5) as response:
            backup=json.load(response)
        self.assertEqual(backup['decks'][0]['saved_versions'][0]['name'],'Original')

    def test_deleted_deck_versions_are_in_backup(self):
        server.save_deck_version(self.deck,'Equipment test')
        server.delete_deck(self.state,self.deck['id'],self.deck['name'])
        backup=server.workspace_backup(self.state)
        self.assertEqual(backup['deleted_decks'][0]['deck']['saved_versions'][0]['name'],'Equipment test')


if __name__=='__main__':
    unittest.main()
