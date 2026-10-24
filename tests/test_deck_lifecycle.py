"""Deck deletion is recoverable, persistent, and independent of collection ownership."""
import copy
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

import core
import server
from fixtures import fixture_state


class DeckLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.old=server.DATA;server.DATA=Path(cls.temp.name)
        cls.http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        cls.thread=threading.Thread(target=cls.http.serve_forever,daemon=True);cls.thread.start()
        cls.base='http://127.0.0.1:'+str(cls.http.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown();cls.http.server_close();server.DATA=cls.old;cls.temp.cleanup()

    def setUp(self):
        self.state=fixture_state();self.deck=self.state['decks'][0]
        self.deck.update(chat=[{'role':'user','text':'Keep this conversation'}],categories=['Draw'],view_settings={'card_mode':'grid'})
        self.deck['cards'][0]['needs_sleeving']=True
        self.deck['history']=[{'before':copy.deepcopy(self.deck['cards']),'summary':'Earlier edit'}]
        self.state['collection']=[core.make_entry('Greater Good',1)]
        server.write_state(self.state)

    def post(self,path,payload,token=True):
        headers={'Content-Type':'application/json'}
        if token:headers['X-Forage-Token']=server.TOKEN
        request=urllib.request.Request(self.base+'/api/'+path,data=json.dumps(payload).encode(),headers=headers)
        with urllib.request.urlopen(request,timeout=5) as response:return json.load(response)

    def delete(self,deck=None):
        d=deck or self.deck
        return self.post('delete-deck',{'id':d['id'],'confirmed_name':d['name']})

    def test_complete_deck_survives_delete_and_restore(self):
        self.delete();deleted=server.read_state()
        self.assertNotIn(self.deck['id'],[d['id'] for d in deleted['decks']])
        self.assertEqual(deleted['deleted_decks'][0]['deck'],self.deck)
        self.assertTrue(deleted['deleted_decks'][0]['deleted_at'])
        for field in ['collection','memories','rules','settings']:self.assertEqual(deleted[field],self.state[field])
        self.post('restore-deck',{'id':self.deck['id']});restored=server.read_state()
        self.assertEqual(restored['active'],self.deck['id'])
        self.assertEqual(server.deck_of(restored,self.deck['id']),self.deck)
        self.assertEqual(restored['deleted_decks'],[])

    def test_last_deck_replaced_with_usable_empty_deck(self):
        self.delete();state=server.read_state();server.validate_backup(state)
        self.assertEqual(len(state['decks']),1);self.assertEqual(state['active'],state['decks'][0]['id'])
        self.assertNotEqual(state['active'],self.deck['id']);self.assertEqual(state['decks'][0]['cards'],[])
        self.post('new-deck',{'name':'Another deck'});self.assertEqual(len(server.read_state()['decks']),2)

    def test_collection_assignments_release_and_return(self):
        self.assertEqual(core.availability(self.state,'Greater Good')['available'],0)
        self.delete();self.assertEqual(core.availability(server.read_state(),'Greater Good')['available'],1)
        self.post('restore-deck',{'id':self.deck['id']})
        self.assertEqual(core.availability(server.read_state(),'Greater Good')['available'],0)

    def test_multiple_decks_active_selection_and_original_position(self):
        self.post('new-deck',{'name':'Second'});second=server.read_state()['active']
        self.delete();self.assertEqual(server.read_state()['active'],second)
        self.post('restore-deck',{'id':self.deck['id']})
        self.assertEqual([d['id'] for d in server.read_state()['decks']],[self.deck['id'],second])
        self.delete();self.assertEqual(server.read_state()['active'],second)

    def test_stale_confirmation_and_unknown_id_leave_state_unchanged(self):
        before=server.read_state()
        for payload in [{'id':self.deck['id']},{'id':self.deck['id'],'confirmed_name':'Old name'},{'id':'missing','confirmed_name':'No'}]:
            with self.assertRaises(urllib.error.HTTPError) as error:self.post('delete-deck',payload)
            self.assertEqual(error.exception.code,400);self.assertEqual(server.read_state(),before)

    def test_repeat_delete_and_restore_do_not_duplicate_decks(self):
        self.delete();before=server.read_state()
        with self.assertRaises(urllib.error.HTTPError):self.delete()
        self.assertEqual(server.read_state(),before)
        self.post('restore-deck',{'id':self.deck['id']});before=server.read_state()
        with self.assertRaises(urllib.error.HTTPError):self.post('restore-deck',{'id':self.deck['id']})
        self.assertEqual(server.read_state(),before)

    def test_backup_round_trip_includes_deleted_decks(self):
        self.delete()
        with urllib.request.urlopen(self.base+'/api/backup') as response:backup=json.load(response)
        server.validate_backup(backup)
        self.post('restore',{'state':backup});self.post('restore-deck',{'id':self.deck['id']})
        self.assertEqual(server.deck_of(server.read_state(),self.deck['id']),self.deck)
        server.validate_backup(self.state)  # Existing backups do not need a deleted_decks key.

    def test_invalid_deleted_deck_backups_rejected(self):
        self.delete();backup=server.read_state()
        cases=[None,[{}],[{'deck':{},'position':0,'deleted_at':'now'}]]
        for value in cases:
            bad=copy.deepcopy(backup);bad['deleted_decks']=value
            with self.assertRaises(ValueError):server.validate_backup(bad)
        bad=copy.deepcopy(backup);bad['deleted_decks'][0]['deck']['cards'][0]['qty']=0
        with self.assertRaises(ValueError):server.validate_backup(bad)
        bad=copy.deepcopy(backup);bad['decks'].append(copy.deepcopy(self.deck))
        with self.assertRaises(ValueError):server.validate_backup(bad)

    def test_delete_and_restore_require_csrf_token(self):
        for path,payload in [('delete-deck',{'id':self.deck['id'],'confirmed_name':self.deck['name']}),('restore-deck',{'id':self.deck['id']})]:
            with self.assertRaises(urllib.error.HTTPError) as error:self.post(path,payload,token=False)
            self.assertEqual(error.exception.code,403)
        self.assertEqual(server.read_state()['decks'],self.state['decks'])
