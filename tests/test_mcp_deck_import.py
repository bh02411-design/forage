import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import server
from core import make_entry

def card(name, qty, colors, typ):
    c=make_entry(name,qty)
    c.update(color_identity=colors,type_line=typ,oracle_text='',legalities={'commander':'legal'})
    return c

class DeckImportTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        p=patch.object(server,'DATA',Path(tmp.name))
        p.start()
        self.addCleanup(p.stop)
        self.state=server.read_state()
        self.state['collection']=[card('Leader',1,['W'],'Legendary Creature — Human'),
                                  card('Plains',99,['W'],'Basic Land — Plains'),
                                  card('Mountain',99,['R'],'Basic Land — Mountain')]
        self.deck=self.state['decks'][0]
        self.deck['cards']=[]
        server.write_state(self.state)
        self.text='Commander\n1 Leader\nMainboard\n99 Plains'
    def request(self,action,**kwargs):
        return server.mcp_deck_import(server.read_state(),
            {'action':action,'deck':self.deck['id'],'text':self.text,**kwargs})
    def test_preview_and_apply(self):
        before=server.read_state()
        p=self.request('preview')
        self.assertFalse(p['saved'])
        self.assertEqual(before,server.read_state())
        self.assertTrue(self.request('apply',confirm=True,
            expected_workspace_sha=p['workspace_sha'],expected_import_sha=p['import_sha'])['verified'])
        self.assertEqual(sum(c['qty'] for c in server.read_state()['decks'][0]['cards']),100)
        self.assertEqual(len(list((server.DATA/'mcp-backups').glob('*.sqlite3'))),1)
    def test_reject_bad_identity_and_stale_hash(self):
        with self.assertRaises(ValueError):
            self.request('preview',text=self.text.replace('Plains','Mountain'))
        p=self.request('preview')
        with self.assertRaises(ValueError):
            self.request('apply',confirm=True,expected_workspace_sha='0'*64,
                         expected_import_sha=p['import_sha'])
        self.assertEqual(server.read_state()['decks'][0]['cards'],[])
    def test_create(self):
        with self.assertRaises(ValueError):
            self.request('create',name='New',commander='Leader')
        r=self.request('create',name='New',commander='Leader',confirm=True)
        self.assertTrue(r['saved'])
        self.assertEqual(len(server.deck_of(server.read_state(),r['deck_id'])['cards']),1)
