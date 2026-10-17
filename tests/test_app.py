import copy, json, os, sys, tempfile, threading, unittest, urllib.request, urllib.error
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import core, seed, server
from fixtures import fixture_state

class CoreTests(unittest.TestCase):
    def setUp(self): self.state=fixture_state();self.deck=self.state['decks'][0]
    def test_considering_defaults_keep_roles_and_type_fallback(self):
        cases=[({'oracle_text':'Draw two cards. Sacrifice a creature.'},'Draw'),({'land':True},'Land'),({'type_line':'Creature — Squirrel'},'Creature'),({},'Uncategorized')]
        for facts,expected in cases:
            c=dict(core.make_entry('Candidate',1,'Considering'),**facts);roles=copy.deepcopy(c['roles'])
            core.auto_categorize_card({'cards':[c]},c);self.assertEqual(c['group'],expected);self.assertEqual(c['roles'],roles)
    def test_ai_board_change_uses_same_considering_default(self):
        c=dict(core.make_entry('Candidate',1),oracle_text='Draw two cards.')
        deck={'cards':[c],'name':'Test','history':[]}
        core.apply_workspace_plan(deck,[],[{'action':'set_card','card':'Candidate','fields':{'zone':'maybe'}}])
        self.assertEqual(deck['cards'][0]['group'],'Draw')
    def test_snapshot_counts(self):
        r=core.analysis(self.deck)
        self.assertEqual(r['total'],100);self.assertEqual(r['lands'],37);self.assertEqual(r['mdfc'],1);self.assertEqual(r['average'],2.11)
    def test_role_overlap(self):
        good=next(c for c in self.deck['cards'] if c['name']=='Greater Good')
        self.assertIn('Draw',good['roles']);self.assertTrue(any('free' in r for r in good['roles']))
    def test_archidekt(self):
        cards,w=core.parse_import('1 Ygra, Eater of All (BLB) 241 [Commander]\n11 Forest [Land]\n1 Brawn [Maybeboard]')
        self.assertFalse(w);self.assertEqual(cards[0]['zone'],'commander');self.assertEqual(cards[0]['name'],'Ygra, Eater of All');self.assertTrue(cards[1]['land']);self.assertEqual(cards[2]['zone'],'maybe')
    def test_csv_quotes(self):
        cards,w=core.parse_import('Quantity,Name,Category\n2,"Braids, Cabal Minion",Mainboard\n1,"Braids, Cabal Minion",Mainboard')
        self.assertEqual(len(cards),1);self.assertEqual(cards[0]['qty'],3)
    def test_tsv_bom(self):
        cards,_=core.parse_import('\ufeffName\tQuantity\nSwamp\t13')
        self.assertEqual(cards[0]['qty'],13)
    def test_invalid_import(self):
        for text in ['', 'garbage', '0 Forest', '-1 Forest']:
            with self.assertRaises(ValueError):core.parse_import(text)
    def test_available_excludes_other_decks(self):
        self.state['collection']=[{'name':'Reanimate','qty':1}]
        other={'id':'terra','cards':[{'name':'Reanimate','qty':1,'zone':'main'}]}
        self.state['decks'].append(other)
        self.assertEqual(core.availability(self.state,'Reanimate',self.deck['id'])['available'],0)
    def test_protected_cut_fails(self):
        p={'id':'p','cut':'Fixture Protected Creature','add':'Birds of Paradise','status':'pending'}
        with self.assertRaisesRegex(ValueError,'protected'):core.apply_swap(self.state,self.deck,p,core.make_entry('New card',1))
    def test_swap_preserves_size_and_undo(self):
        p=self.deck['proposals'][2];before=copy.deepcopy(self.deck['cards'])
        core.apply_swap(self.state,self.deck,p,core.make_entry('Orcish Bowmasters',1))
        self.assertEqual(core.analysis(self.deck)['total'],100);self.assertEqual(p['status'],'accepted');self.assertEqual(self.deck['history'][-1]['before'],before)
    def test_mana_sample_reproducible(self):
        a=core.mana_sample(self.deck,runs=1000);b=core.mana_sample(self.deck,runs=1000)
        self.assertEqual(a,b);self.assertGreater(a['land_drop'][2],a['land_drop'][5])
    def test_no_lands(self):
        d={'cards':[dict(core.make_entry('Test',99),land=False)]}
        self.assertEqual(core.mana_sample(d,runs=50)['land_drop'][2],0)
    def test_all_lands(self):
        d={'cards':[core.make_entry('Forest',99)]}
        self.assertEqual(core.mana_sample(d,runs=50)['land_drop'][6],100)
    def test_multiface(self):
        raw={'id':'abc','name':'Front // Back','cmc':3,'layout':'modal_dfc','color_identity':['G'],'card_faces':[{'type_line':'Sorcery','oracle_text':'Do a thing.','mana_cost':'{2}{G}'},{'type_line':'Land','oracle_text':'Add green.'}]}
        c=server.card_data(raw);self.assertTrue(c['mdfc']);self.assertFalse(c['land']);self.assertEqual(c['mv'],3)
    def test_drop_links(self):
        with patch.object(server,'lookup',return_value={'name':'Orcish Bowmasters'}) as mock:
            server.resolve_drop({'text':'https://edhrec.com/cards/orcish-bowmasters'})
            mock.assert_called_with('orcish bowmasters')
        with patch.object(server,'scry',return_value={'id':'abc','name':'Master','cmc':6}) as mock:
            server.resolve_drop({'text':'https://scryfall.com/card/kld/90/marionette-master'})
            mock.assert_called_with('/cards/kld/90')
    def test_drop_image_url(self):
        ident='a0c12345-1234-5678-abcd-123456789abc'
        with patch.object(server,'scry',return_value={'id':ident,'name':'Test','cmc':1}) as mock:
            server.resolve_drop({'text':'https://cards.scryfall.io/normal/front/a/0/'+ident+'.jpg?12345'})
            mock.assert_called_with('/cards/'+ident)
    def test_lm_url_restriction(self):
        for address in ['https://example.com/v1','http://169.254.169.254','http://localhost@evil.com','http://localhost/v1?redirect=evil']:
            self.state['settings']['lm_url']=address
            with self.assertRaises(ValueError):server.lm_config(self.state)
    def test_backup_validation(self):
        server.validate_backup(self.state)
        with self.assertRaises(ValueError):server.validate_backup({'version':99})
    def test_ai_context_and_structured_reply(self):
        self.state['settings']['model']='test-model'
        fake={'choices':[{'message':{'content':json.dumps({'reply':'Keep the fixture.','proposals':[],'memory_suggestions':[]})}}]}
        with patch.object(server,'request_json',return_value=fake) as mock:
            r=server.ai_chat(self.state,self.deck,'What next?')
            self.assertEqual(r['reply'],'Keep the fixture.')
            data=mock.call_args.args[1];self.assertIn('Fixture Protected Creature',data['messages'][0]['content']);self.assertEqual(data['model'],'test-model')
    def test_prose_before_fenced_swap_retains_controls(self):
        proposal={'add':'Candidate','cut':'Existing','reason':'Compare these options.'}
        text='This proposal respects your preferences.\n\n```json\n'+json.dumps({'reply':'**Readable** swap.','recommendations':[],'proposals':[proposal]})+'\n```'
        parsed=server.parse_model_output(text)
        self.assertEqual(parsed['reply'],'**Readable** swap.');self.assertEqual(parsed['proposals'],[proposal])
        self.assertEqual(server.readable_history(text),'**Readable** swap.')
    def test_nested_reply_envelope_is_unwrapped(self):
        inner={'reply':'Readable answer\n\nSecond paragraph','proposals':[{'add':'Candidate','cut':'Existing','reason':'Tradeoff'}]}
        parsed=server.parse_model_output(json.dumps({'reply':'Introduction\n```json\n'+json.dumps(inner)+'\n```'}))
        self.assertEqual(parsed['reply'],'Readable answer\n\nSecond paragraph');self.assertEqual(parsed['proposals'],inner['proposals'])
    def test_embedded_response_after_mana_braces(self):
        parsed=server.parse_model_output('At {1}{B}, consider this.\n'+json.dumps({'reply':'Readable answer','proposals':[]}))
        self.assertEqual(parsed['reply'],'Readable answer')
    def test_truncated_embedded_envelope_hides_internal_fields(self):
        parsed=server.parse_model_output('Intro\n```json\n{"reply":"Readable answer","proposals":[')
        self.assertEqual(parsed['reply'],'Readable answer');self.assertEqual(parsed['proposals'],[])
    def test_plain_ai_reply_supported(self):
        self.state['settings']['model']='test'
        with patch.object(server,'request_json',return_value={'choices':[{'message':{'content':'A plain answer'}}]}):
            self.assertEqual(server.ai_chat(self.state,self.deck,'Hi')['reply'],'A plain answer')

class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.old=server.DATA;server.DATA=Path(cls.temp.name)
        cls.http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        cls.thread=threading.Thread(target=cls.http.serve_forever,daemon=True);cls.thread.start();cls.base='http://127.0.0.1:'+str(cls.http.server_port)
    @classmethod
    def tearDownClass(cls):cls.http.shutdown();cls.http.server_close();server.DATA=cls.old;cls.temp.cleanup()
    def request(self,path,data=None,token=True):
        headers={'Content-Type':'application/json'}
        if token:headers['X-Forage-Token']=server.TOKEN
        req=urllib.request.Request(self.base+path,data=json.dumps(data).encode() if data is not None else None,headers=headers)
        return urllib.request.urlopen(req,timeout=5)
    def setUp(self):server.write_state(fixture_state())
    def test_static_and_state(self):
        with self.request('/') as r:self.assertEqual(r.status,200);self.assertIn(b'forage',r.read())
        with self.request('/api/state') as r:self.assertEqual(json.load(r)['state']['version'],1)
    def test_version_selection_requires_updated_launcher_before_download(self):
        with patch.dict(os.environ,{'FORAGE_VERSION_SWITCH':'','FORAGE_LAUNCHER':'1'}),patch.object(server.updater,'stage') as stage:
            with self.assertRaises(urllib.error.HTTPError) as response:self.request('/api/updates',{'action':'stage','version':'0.2.8'})
            self.assertEqual(response.exception.code,400);self.assertIn('reopen Start-Forage.bat',json.load(response.exception)['error']);stage.assert_not_called()
    def test_update_history_endpoint_returns_notes(self):
        with patch.object(server.updater,'fetch',side_effect=OSError('offline')):
            with self.request('/api/updates/history') as response:data=json.load(response)
        self.assertEqual(data['current_version'],server.updater.current_version(server.ROOT));self.assertTrue(any(row.get('changes') for row in data['releases']))
    def test_csrf_blocks_mutation(self):
        with self.assertRaises(urllib.error.HTTPError) as e:self.request('/api/settings',{'model':'oops'},token=False)
        self.assertEqual(e.exception.code,403)
    def test_dns_rebinding_block(self):
        req=urllib.request.Request(self.base+'/api/state',headers={'Host':'evil.example'})
        with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(req)
        self.assertEqual(e.exception.code,403)
    def test_memory_persists(self):
        with self.request('/api/memory',{'text':'Prefer a low curve','scope':'deck'}) as r:self.assertTrue(json.load(r)['ok'])
        self.assertTrue(any(m['text']=='Prefer a low curve' for m in server.read_state()['memories']))
    def test_import_and_undo(self):
        s=server.read_state();ident=s['active'];before=copy.deepcopy(s['decks'][0]['cards'])
        with self.request('/api/import',{'deck':ident,'text':'Commander\n1 Ygra, Eater of All\nMainboard\n35 Forest','target':'deck'}) as r:self.assertTrue(json.load(r)['ok'])
        self.assertEqual(core.analysis(server.read_state()['decks'][0])['total'],36)
        with self.request('/api/undo',{'deck':ident}) as r:self.assertTrue(json.load(r)['ok'])
        self.assertEqual(server.read_state()['decks'][0]['cards'],before)
    def test_add_card_undo(self):
        s=server.read_state();ident=s['active'];n=len(s['decks'][0]['cards'])
        with self.request('/api/card',{'deck':ident,'action':'add','card':core.make_entry('Test',1),'zone':'maybe'}) as r:self.assertTrue(json.load(r)['ok'])
        self.assertEqual(len(server.read_state()['decks'][0]['cards']),n+1)
        with self.request('/api/undo',{'deck':ident}) as r:json.load(r)
        self.assertEqual(len(server.read_state()['decks'][0]['cards']),n)
    def test_chat_saves_proposal_not_applies(self):
        s=server.read_state();ident=s['active'];before=copy.deepcopy(s['decks'][0]['cards'])
        fake={'reply':'Consider this.','proposals':[{'add':'Test Add','cut':'Forest','reason':'Testing'}],'memory_suggestions':[{'text':'Low curve','scope':'deck'}]}
        with patch.object(server,'ai_chat',return_value=fake):
            with self.request('/api/chat',{'deck':ident,'message':'What next?'}) as r:self.assertTrue(json.load(r)['ok'])
        after=server.read_state();d=core.deck_of(after,ident) if hasattr(core,'deck_of') else server.deck_of(after,ident)
        self.assertEqual(d['cards'],before);self.assertTrue(any(p['add']=='Test Add' for p in d['proposals']));self.assertFalse(any(m['text']=='Low curve' for m in after['memories']))
    def test_visual_recommendation_and_pass_preserve_board(self):
        state=server.read_state();d=server.deck_of(state,state['active']);before=copy.deepcopy(d['cards'])
        candidate=dict(core.make_entry('Visual Candidate',1),image='https://cards.scryfall.io/normal/front/a/test.jpg',mv=2)
        state['collection'].append(candidate);server.write_state(state)
        fake={'reply':'Consider Visual Candidate.','recommendations':[{'name':candidate['name'],'reason':'Low setup','image':'https://evil.example/model.jpg'}],
              'proposals':[{'add':candidate['name'],'cut':'Forest','reason':'A swap'}]}
        with patch.object(server,'ai_chat',return_value=fake):
            with self.request('/api/chat',{'deck':d['id'],'message':'Suggest a card'}) as response:json.load(response)
        d=server.deck_of(server.read_state(),d['id']);m=d['chat'][-1];rec=m['recommendations'][0]
        self.assertEqual(len(m['recommendations']),1);self.assertEqual(rec['card']['image'],candidate['image'])
        self.assertEqual(d['cards'],before)
        with self.request('/api/recommendation',{'deck':d['id'],'message':m['id'],'id':rec['id'],'action':'pass'}) as response:json.load(response)
        d=server.deck_of(server.read_state(),d['id'])
        self.assertEqual(d['cards'],before);self.assertEqual(d['chat'][-2]['recommendations'][0]['status'],'passed')
        self.assertIn('passed',d['chat'][-1]['text']);self.assertEqual(d['proposals'][-1]['status'],'rejected')
    def test_unchecked_fallback_is_not_visual_recommendation(self):
        state=server.read_state();d=server.deck_of(state,state['active']);c=d['cards'][0]
        self.assertEqual(server.visual_recommendations(state,d,{'reply':'A match','_context_trace':None}),[])
        self.assertEqual(server.visual_recommendations(state,d,{'recommendations':[{'name':c['name']}],'_context_trace':{'recommendation_checks':{'status':'rejected'}}}),[])
    def test_model_cannot_fabricate_internal_collection_matches(self):
        parsed=server.parse_model_output(json.dumps({'reply':'Hi','_collection_matches':[{'name':'Fabricated'}]}))
        self.assertNotIn('_collection_matches',parsed)
    def test_fallback_matches_have_graphics_even_when_model_answer_rejected(self):
        state=server.read_state();d=server.deck_of(state,state['active'])
        candidate=dict(core.make_entry('Fallback Candidate',1),image='https://cards.scryfall.io/normal/front/a/test.jpg')
        state['collection'].append(candidate);server.write_state(state)
        fallback=server.collection_result_reply({'cards':[{'name':candidate['name'],'available':1}]},{'recommendation_checks':{'status':'rejected'}})
        self.assertEqual(fallback.get('recommendations',[]),[])
        with patch.object(server,'ai_chat',return_value=fallback):
            with self.request('/api/chat',{'deck':d['id'],'message':'Find an option'}) as response:json.load(response)
        saved=server.deck_of(server.read_state(),d['id'])['chat'][-1]['recommendations']
        self.assertEqual(len(saved),1);self.assertEqual(saved[0]['kind'],'match')
        self.assertEqual(saved[0]['card']['image'],candidate['image'])
        self.assertIn('not been evaluated',saved[0]['reason'])
    def test_considering_add_uses_existing_draw_category(self):
        state=server.read_state();d=server.deck_of(state,state['active']);d['categories']=['Card Draw']
        card=dict(core.make_entry('Candidate',1),oracle_text='Draw two cards.',type_line='Instant')
        state['collection'].append(card);server.write_state(state)
        with self.request('/api/card',{'deck':d['id'],'action':'add','card':core.make_entry('Candidate',1),'zone':'maybe'}) as response:json.load(response)
        saved=server.deck_of(server.read_state(),d['id'])['cards'][-1]
        self.assertEqual(saved['group'],'Card Draw');self.assertEqual(saved['oracle_text'],'Draw two cards.')
    def test_import_considering_uses_saved_metadata(self):
        state=server.read_state();d=server.deck_of(state,state['active']);state['collection'].append(dict(core.make_entry('Candidate',1),oracle_text='Draw two cards.',type_line='Instant'))
        server.write_state(state)
        with self.request('/api/import',{'deck':d['id'],'text':'Considering\n1 Candidate'}) as response:json.load(response)
        saved=server.deck_of(server.read_state(),d['id'])['cards'][0]
        self.assertEqual(saved['zone'],'maybe');self.assertEqual(saved['group'],'Draw')
    def test_drag_board_move_autocategorizes_but_explicit_group_wins(self):
        state=server.read_state();d=server.deck_of(state,state['active']);card=dict(core.make_entry('Candidate',1),oracle_text='Draw two cards.',type_line='Instant');d['cards'].append(card);server.write_state(state)
        with self.request('/api/card',{'deck':d['id'],'action':'edit','id':card['id'],'zone':'maybe'}) as response:json.load(response)
        self.assertEqual(server.deck_of(server.read_state(),d['id'])['cards'][-1]['group'],'Draw')
        with self.request('/api/card',{'deck':d['id'],'action':'edit','id':card['id'],'group':'Uncategorized'}) as response:json.load(response)
        with self.request('/api/auto-categorize',{'deck':d['id']}) as response:self.assertEqual(json.load(response)['categorized'],0)
        self.assertEqual(server.deck_of(server.read_state(),d['id'])['cards'][-1]['group'],'Uncategorized')
    def test_existing_considering_auto_button_undo_keeps_other_boards(self):
        state=server.read_state();d=server.deck_of(state,state['active'])
        d['cards'] += [dict(core.make_entry('Candidate',1,'Considering'),oracle_text='Draw two cards.',type_line='Instant'),dict(core.make_entry('Custom',1,'Considering'),group='My engine',oracle_text='Draw two cards.')]
        before=copy.deepcopy(d['cards']);server.write_state(state)
        with self.request('/api/auto-categorize',{'deck':d['id']}) as response:self.assertEqual(json.load(response)['categorized'],1)
        saved=server.deck_of(server.read_state(),d['id'])['cards'];self.assertEqual(saved[:-2],before[:-2]);self.assertEqual(saved[-1]['group'],'My engine');self.assertEqual(saved[-2]['group'],'Draw')
        with self.request('/api/undo',{'deck':d['id']}) as response:json.load(response)
        self.assertEqual(server.deck_of(server.read_state(),d['id'])['cards'],before)
    def test_mainboard_autocategorize_is_scoped_and_undoable(self):
        state=server.read_state();d=server.deck_of(state,state['active'])
        main=dict(core.make_entry('Main Candidate',1),oracle_text='Draw two cards.',type_line='Instant')
        maybe=dict(core.make_entry('Maybe Candidate',1,'Considering'),oracle_text='Draw two cards.')
        d['cards'] += [main,maybe];before=copy.deepcopy(d['cards']);server.write_state(state)
        with self.request('/api/auto-categorize',{'deck':d['id'],'zone':'main'}) as response:
            result=json.load(response);self.assertEqual(result['categorized'],1);self.assertTrue(result['undo_available'])
        saved=server.deck_of(server.read_state(),d['id'])['cards']
        self.assertEqual(saved[-2]['group'],'Draw');self.assertEqual(saved[-1],before[-1]);self.assertEqual(saved[0],before[0])
        with self.request('/api/undo',{'deck':d['id']}) as response:json.load(response)
        self.assertEqual(server.deck_of(server.read_state(),d['id'])['cards'],before)
    def test_mainboard_new_card_gets_default_category(self):
        state=server.read_state();d=server.deck_of(state,state['active'])
        candidate=dict(core.make_entry('Candidate',1),type_line='Instant',oracle_text='Draw two cards.')
        with self.request('/api/card',{'deck':d['id'],'action':'add','card':candidate,'zone':'main'}) as response:json.load(response)
        saved=server.deck_of(server.read_state(),d['id'])['cards'][-1]
        self.assertEqual(saved['group'],'Draw');self.assertEqual(saved['zone'],'main')
    def test_autocategorize_rejects_commander_board(self):
        state=server.read_state()
        with self.assertRaises(urllib.error.HTTPError) as response:self.request('/api/auto-categorize',{'deck':state['active'],'zone':'commander'})
        self.assertEqual(response.exception.code,400)
    def test_autocategorize_noop_does_not_create_false_undo(self):
        state=server.read_state();d=server.deck_of(state,state['active']);d['cards']=[];before=copy.deepcopy(d['history']);server.write_state(state)
        with self.request('/api/auto-categorize',{'deck':d['id'],'zone':'main'}) as response:self.assertFalse(json.load(response)['undo_available'])
        self.assertEqual(server.deck_of(server.read_state(),d['id'])['history'],before)
    def test_collection_only_blocks_unowned(self):
        s=server.read_state();d=server.deck_of(s,s['active']);p=d['proposals'][0]
        with patch.object(server,'lookup',return_value=core.make_entry(p['add'],1)):
            with self.assertRaises(urllib.error.HTTPError) as e:self.request('/api/proposal',{'deck':d['id'],'id':p['id'],'action':'accept'})
            self.assertEqual(e.exception.code,400);self.assertIn('available copy',json.load(e.exception)['error'])
    def test_local_ai_unavailable_clear_error(self):
        s=server.read_state();s['settings']['model']='';server.write_state(s)
        with self.assertRaises(urllib.error.HTTPError) as e:self.request('/api/chat',{'deck':s['active'],'message':'Hello'})
        self.assertIn('Choose a loaded model',json.load(e.exception)['error'])
    def test_malformed_backup_does_not_replace(self):
        before=server.read_state()['active']
        with self.assertRaises(urllib.error.HTTPError):self.request('/api/restore',{'state':{'version':99}})
        self.assertEqual(server.read_state()['active'],before)

if __name__=='__main__':unittest.main(verbosity=2)

class RetrievalTests(unittest.TestCase):
    def setUp(self):self.state=fixture_state();self.deck=self.state['decks'][0]
    def test_search_beyond_first_500(self):
        self.state['collection']=[{'name':'Card '+str(i),'qty':1} for i in range(700)]
        self.state['collection'].append({'name':'Useful Engine','qty':1,'oracle_text':'Whenever you sacrifice a Food, draw a card.','color_identity':['B']})
        r=server.collection_search(self.state,self.deck,'Food draw')
        self.assertEqual(r['cards'][0]['name'],'Useful Engine');self.assertEqual(r['matches'],1)
    def test_search_excludes_known_off_color(self):
        self.state['collection']=[{'name':'Red Draw','qty':1,'oracle_text':'Draw a card.','color_identity':['R']},{'name':'Black Draw','qty':1,'oracle_text':'Draw a card.','color_identity':['B']}]
        r=server.collection_search(self.state,self.deck,'draw');self.assertEqual(r['matches'],1)
    def test_model_requests_local_search(self):
        self.state['settings']['model']='test'
        self.state['collection']=[{'name':'Useful Engine','qty':1,'oracle_text':'Draw a card.'}]
        responses=[{'choices':[{'message':{'content':'{"collection_search":{"query":"draw"}}'}}]}, {'choices':[{'message':{'content':'{"reply":"Consider Useful Engine.","proposals":[],"memory_suggestions":[]}'}}]}]
        with patch.object(server,'request_json',side_effect=responses) as mock:
            result=server.ai_chat(self.state,self.deck,'What should I add?')
            self.assertEqual(mock.call_count,2);self.assertIn('Useful Engine',mock.call_args.args[1]['messages'][-1]['content']);self.assertIn('Useful Engine',result['reply'])

class ServiceErrorTests(unittest.TestCase):
    def check_error(self,url,body,expected):
        import io
        err=urllib.error.HTTPError(url,400,'Bad Request',{},io.BytesIO(body.encode()))
        with patch('urllib.request.OpenerDirector.open',side_effect=err):
            with self.assertRaisesRegex(ValueError,expected):server.request_json(url,{'test':True})
    def test_local_string_error(self):
        self.check_error('http://127.0.0.1:1234/v1/chat/completions','{"error":"Model not found"}','LM Studio HTTP 400: Model not found')
    def test_local_nested_error(self):
        self.check_error('http://localhost:1234/v1/chat/completions','{"error":{"message":"Context length exceeded"}}','exceeded the loaded model context')
    def test_card_details(self):
        self.check_error('https://api.scryfall.com/cards/named','{"details":"Card not found"}','Scryfall HTTP 400: Card not found')
    def test_plain_error(self):
        self.check_error('http://127.0.0.1:1234/v1/models','Unsupported model type','Unsupported model type')

class ModelOutputTests(unittest.TestCase):
    def test_reply_with_trailing_fields_outside_object(self):
        out=server.parse_model_output('{"reply":"Hello\\n\\n**World**"}, "proposals": []')
        self.assertEqual(out['reply'],'Hello\n\n**World**')
    def test_reply_in_truncated_object(self):
        out=server.parse_model_output('{"reply":"Readable answer", "proposals": [')
        self.assertEqual(out['reply'],'Readable answer')
    def test_plain_text_unchanged(self):
        self.assertEqual(server.parse_model_output('Normal answer')['reply'],'Normal answer')
    def test_malformed_object_hidden(self):
        out=server.parse_model_output('{broken_json')
        self.assertNotIn('broken_json',out['reply'])
    def test_collection_search_preserved(self):
        out=server.parse_model_output('{"collection_search":{"query":"mill"}}')
        self.assertEqual(out['collection_search']['query'],'mill')

class PromptBudgetTests(unittest.TestCase):
    def setUp(self):self.state=fixture_state();self.deck=self.state['decks'][0]
    def test_old_chat_compacted_not_deleted(self):
        messages=[{'role':'system','content':'Important constraints'},*({'role':'assistant','content':'old '*2000} for _ in range(8)),{'role':'user','content':'current question'}]
        original=copy.deepcopy(messages)
        packed=server.fit_messages(messages,3000,'current question')
        self.assertEqual(messages,original);self.assertLessEqual(server.prompt_size(packed),3000);self.assertEqual(packed[-1]['content'],'current question')
    def test_deck_and_preferences_preserved(self):
        for c in self.deck['cards']:c['oracle_text']='A very long rule description. '*100
        original=server.context(self.state,self.deck)
        m=[{'role':'system','content':server.SYSTEM+'\nWORKSPACE DATA:\n'+json.dumps(original)},{'role':'user','content':'Compare cheap draw.'}]
        packed=server.fit_messages(m,24000,'Compare cheap draw.')
        ctx=json.JSONDecoder().raw_decode(packed[0]['content'].split('\nWORKSPACE DATA:\n')[1])[0]
        self.assertEqual(len(ctx['cards']),len(original['cards']));self.assertTrue(any('Fixture Protected Creature' in x['text'] for x in ctx['preferences']));self.assertTrue(any(c['protected'] for c in ctx['cards']))
        self.assertLessEqual(server.prompt_size(packed),24000)
    def test_measured_overflow_retried(self):
        messages=[{'role':'system','content':'Rules'}, {'role':'assistant','content':'history '*2000},{'role':'user','content':'Question'}]
        overflow=ValueError('LM Studio HTTP 400: {"n_ctx":8192,"n_prompt_tokens":10000}')
        result={'choices':[{'message':{'content':'Works'}}]}
        with patch.object(server,'request_json',side_effect=[overflow,result]) as mock:
            actual=server.predict_with_budget('http://localhost:1234/v1','test',messages,'Question',{'bytes':30000})
            self.assertEqual(actual,result);self.assertEqual(mock.call_count,2)
            self.assertLess(server.prompt_size(mock.call_args_list[1].args[1]['messages']),server.prompt_size(mock.call_args_list[0].args[1]['messages']))
    def test_noncontext_error_not_retried(self):
        with patch.object(server,'request_json',side_effect=ValueError('Model not found')) as mock:
            with self.assertRaisesRegex(ValueError,'Model not found'):server.predict_with_budget('http://localhost:1234/v1','test',[{'role':'user','content':'Hi'}],'Hi',{'bytes':30000})
            self.assertEqual(mock.call_count,1)
    def test_essential_context_not_silently_dropped(self):
        with self.assertRaisesRegex(ValueError,'Nothing was deleted'):server.fit_messages([{'role':'system','content':'Rules'*1000},{'role':'user','content':'Keep my full question'}],100,'Keep my full question')

class CategoryTests(unittest.TestCase):
    def setUp(self):self.state=fixture_state();self.deck=self.state['decks'][0]
    def test_rename_preserves_all_cards_and_roles(self):
        before=copy.deepcopy(self.deck['cards']);core.apply_category_changes(self.deck,[{'action':'rename','from':'Draw','to':'Card advantage'}])
        self.assertEqual(len(before),len(self.deck['cards']));self.assertEqual(core.analysis(self.deck)['total'],100)
        for a,b in zip(before,self.deck['cards']):
            self.assertEqual(a['roles'],b['roles']);self.assertEqual(a['zone'],b['zone']);self.assertEqual(a['qty'],b['qty'])
        self.assertNotIn('Draw',core.category_names(self.deck));self.assertIn('Card advantage',core.category_names(self.deck))
    def test_create_empty_category(self):
        core.apply_category_changes(self.deck,[{'action':'create','to':'New engines'}]);self.assertIn('New engines',self.deck['categories'])
    def test_move_retains_draw_role(self):
        core.apply_category_changes(self.deck,[{'action':'move','cards':['Greater Good'],'to':'Free outlets'}])
        c=next(c for c in self.deck['cards'] if c['name']=='Greater Good');self.assertEqual(c['group'],'Free outlets');self.assertIn('Draw',c['roles'])
    def test_invalid_batch_atomic(self):
        before=copy.deepcopy(self.deck)
        with self.assertRaises(ValueError):core.apply_workspace_plan(self.deck,[{'action':'rename','from':'Draw','to':'Cards'}],[{'action':'set_card','card':'Nonexistent card','fields':{'protected':True}}])
        self.assertEqual(self.deck,before)
    def test_populated_category_not_deleted(self):
        with self.assertRaisesRegex(ValueError,'contains cards'):core.apply_category_changes(self.deck,[{'action':'delete','from':'Draw'}])
    def test_merge_existing(self):
        core.apply_category_changes(self.deck,[{'action':'merge','from':'Draw','to':'Drain'}]);self.assertNotIn('Draw',core.category_names(self.deck))
    def test_workspace_plan_changes_only_requested_fields(self):
        before=copy.deepcopy(self.deck);core.apply_workspace_plan(self.deck,[],[{'action':'rename_deck','name':'Food machine'},{'action':'set_card','card':'Greater Good','fields':{'protected':True}},{'action':'set_view','fields':{'card_mode':'grid','card_size':200}}],'plan1')
        self.assertEqual(self.deck['name'],'Food machine');self.assertEqual(self.deck['view_settings']['card_mode'],'grid');self.assertEqual(self.deck['history'][-1]['before_name'],before['name']);self.assertEqual(self.deck['history'][-1]['before'],before['cards'])
    def test_ai_cannot_change_oracle_text(self):
        with self.assertRaisesRegex(ValueError,'Unsupported card'):core.normalize_workspace_changes(self.deck,[{'action':'set_card','card':'Greater Good','fields':{'oracle_text':'Invented'}}])
    def test_invalid_view_rejected(self):
        with self.assertRaises(ValueError):core.normalize_workspace_changes(self.deck,[{'action':'set_view','fields':{'card_size':9999}}])

class WorkspaceHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.old=server.DATA;server.DATA=Path(cls.temp.name)
        cls.http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler);cls.thread=threading.Thread(target=cls.http.serve_forever,daemon=True);cls.thread.start();cls.base='http://127.0.0.1:'+str(cls.http.server_port)
    @classmethod
    def tearDownClass(cls):cls.http.shutdown();cls.http.server_close();server.DATA=cls.old;cls.temp.cleanup()
    def setUp(self):server.write_state(fixture_state())
    def post(self,path,data):
        req=urllib.request.Request(self.base+'/api/'+path,data=json.dumps(data).encode(),headers={'Content-Type':'application/json','X-Forage-Token':server.TOKEN})
        with urllib.request.urlopen(req,timeout=5) as r:return json.load(r)
    def test_category_endpoint_and_undo(self):
        ident=server.read_state()['active'];self.post('category',{'deck':ident,'changes':[{'action':'rename','from':'Draw','to':'Card access'}]})
        self.assertIn('Card access',core.category_names(server.read_state()['decks'][0]));self.post('undo',{'deck':ident});self.assertIn('Draw',core.category_names(server.read_state()['decks'][0]))
    def test_ai_proposes_then_user_applies_and_undoes(self):
        s=server.read_state();ident=s['active'];original=copy.deepcopy(s['decks'][0])
        fake={'reply':'Here are proposed changes.','category_changes':[{'action':'move','cards':['Greater Good'],'to':'Free outlets'}],'workspace_changes':[{'action':'rename_deck','name':'Test deck'},{'action':'set_view','fields':{'card_mode':'grid'}}]}
        with patch.object(server,'ai_chat',return_value=fake):self.post('chat',{'deck':ident,'message':'Move Greater Good, rename the deck, and use grid view.'})
        d=server.read_state()['decks'][0];self.assertEqual(d['cards'],original['cards']);self.assertEqual(d['name'],original['name']);plan=d['category_plans'][0]
        self.assertEqual(d['chat'][-1]['category_plan_id'],plan['id']);self.post('category',{'deck':ident,'plan_id':plan['id']})
        d=server.read_state()['decks'][0];self.assertEqual(d['name'],'Test deck');self.assertEqual(d['view_settings']['card_mode'],'grid');self.assertEqual(d['category_plans'][0]['status'],'accepted')
        self.post('undo',{'deck':ident});d=server.read_state()['decks'][0];self.assertEqual(d['cards'],original['cards']);self.assertEqual(d['name'],original['name']);self.assertNotIn('view_settings',d);self.assertEqual(d['category_plans'][0]['status'],'pending')
    def test_explicit_chat_apply_without_model(self):
        s=server.read_state();d=s['decks'][0];d['category_plans']=[{'id':'plan','changes':[{'action':'create','to':'Engines'}],'status':'pending'}];server.write_state(s)
        with patch.object(server,'ai_chat',side_effect=AssertionError('Model should not be called')):self.post('chat',{'deck':s['active'],'message':'apply category changes'})
        self.assertIn('Engines',server.read_state()['decks'][0]['categories'])
    def test_ai_invalid_plan_not_applied(self):
        s=server.read_state()
        with patch.object(server,'ai_chat',return_value={'reply':'Proposed.','category_changes':[{'action':'move','cards':['Missing'],'to':'Draw'}]}):self.post('chat',{'deck':s['active'],'message':'Change categories'})
        d=server.read_state()['decks'][0];self.assertFalse(d.get('category_plans'));self.assertIn('not created',d['chat'][-1]['text'])
    def test_skip_plan_preserves_deck(self):
        s=server.read_state();d=s['decks'][0];before=copy.deepcopy(d['cards']);d['category_plans']=[{'id':'plan','changes':[{'action':'create','to':'Engines'}],'status':'pending'}];server.write_state(s)
        self.post('category',{'deck':s['active'],'plan_id':'plan','action':'reject'});d=server.read_state()['decks'][0];self.assertEqual(d['cards'],before);self.assertEqual(d['category_plans'][0]['status'],'rejected')
    def test_view_endpoint(self):
        self.post('view',{'settings':{'card_mode':'list','group_by':'mana'}});self.assertEqual(server.read_state()['decks'][0]['view_settings']['group_by'],'mana')

class ContinuityTests(unittest.TestCase):
    def setUp(self):self.state=fixture_state();self.deck=self.state['decks'][0]
    def test_latest_pair_survives_large_deck_payload(self):
        self.deck['chat']=[{'id':'u1','role':'user','text':'Compare Mire Triton and Millikin for Terra.'},{'id':'a1','role':'assistant','text':'The two candidates are Mire Triton and Millikin. Mire Triton provides immediate mill.'}]
        for c in self.deck['cards']:c['oracle_text']='Repeated Oracle reference text. '*70
        workspace=server.context(self.state,self.deck);workspace['conversation_context']=server.conversation_context(self.deck,'Which of those two?')
        messages=[{'role':'system','content':server.SYSTEM+'\nWORKSPACE DATA:\n'+json.dumps(workspace)}]+[{'role':m['role'],'content':m['text']} for m in self.deck['chat']]+[{'role':'user','content':'Which of those two?'}]
        packed=server.fit_messages(messages,27000,'Which of those two?')
        self.assertTrue(any(m['content'].startswith('Compare Mire Triton') for m in packed));self.assertTrue(any('The two candidates' in m['content'] for m in packed));self.assertEqual(packed[-1]['content'],'Which of those two?')
        self.assertLessEqual(server.prompt_size(packed),27000)
    def test_prior_substantial_request_beyond_recent_window(self):
        original='Please check my collection for creature-based mill, draw that discards cards, and noncreature spells with flashback for Terra.'
        self.deck['chat']=[{'id':'task','role':'user','text':original}]+[{'id':str(i),'role':'assistant' if i%2 else 'user','text':'Short follow-up '+str(i)} for i in range(20)]
        ctx=server.conversation_context(self.deck,'What else?');self.assertIn(original,[m['text'] for m in ctx['earlier_user_requests']])
    def test_context_trace_is_actual_packed_history(self):
        m=[{'role':'system','content':'Rules'},{'role':'user','content':'First question'},{'role':'assistant','content':'First answer'},{'role':'user','content':'Follow-up'}]
        trace=server.prompt_trace(m,'Follow-up');self.assertEqual([m['text'] for m in trace['recent_messages']],['First question','First answer'])
    def test_ai_adapter_sends_history_and_trace(self):
        self.state['settings']['model']='test';self.deck['chat']=[{'role':'user','text':'I like Mire Triton.'},{'role':'assistant','text':'Mire Triton and Millikin are the current candidates.'}]
        with patch.object(server,'request_json',return_value={'choices':[{'message':{'content':'{"reply":"Mire Triton.","proposals":[]}'}}]}) as mock:
            result=server.ai_chat(self.state,self.deck,'Which of those is better?')
            packed=mock.call_args.args[1]['messages'];self.assertTrue(any(m.get('content')=='I like Mire Triton.' for m in packed));self.assertEqual(len(result['_context_trace']['recent_messages']),2)
    def test_saved_json_envelopes_are_cleaned_in_history(self):
        self.assertEqual(server.readable_history('{"reply":"Choose Mire Triton."}, "proposals": []'),'Choose Mire Triton.')
    def test_refuses_to_drop_latest_exchange_to_force_fit(self):
        m=[{'role':'system','content':'Rules'*3000},{'role':'user','content':'Earlier question'},{'role':'assistant','content':'Earlier answer'},{'role':'user','content':'Follow-up'}]
        with self.assertRaisesRegex(ValueError,'latest conversation exchange'):server.fit_messages(m,1000,'Follow-up')

class ToolCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.state=fixture_state();self.deck=self.state['decks'][0];self.state['settings']['model']='test'
        self.state['collection']=[{'name':'New Draw Engine','qty':1,'oracle_text':'Draw two cards, then discard a card.','mv':2,'color_identity':['B']},{'name':'Greater Good','qty':1,'oracle_text':'Draw cards.','mv':4,'color_identity':['G']}]
    def test_exact_reported_tool_format(self):
        text='<|tool_call>call:collection_search{query:<|"|>draw<|"|>}<tool_call|>'
        self.assertEqual(server.parse_model_output(text),{'collection_search':{'query':'draw'}})
    def test_native_tool_call(self):
        msg={'tool_calls':[{'id':'1','type':'function','function':{'name':'collection_search','arguments':'{"query":"discard"}'}}]}
        self.assertEqual(server.tool_request_from_message(msg)['collection_search']['query'],'discard')
    def test_unknown_tool_never_executed(self):
        self.assertIsNone(server.tool_request_from_text('<|tool_call>call:delete_everything{}<tool_call|>'))
        parsed=server.parse_model_output('<|tool_call>call:delete_everything{}<tool_call|>');self.assertNotIn('<|tool_call>',parsed['reply'])
    def test_text_tool_runs_search_and_returns_answer(self):
        responses=[{'choices':[{'message':{'content':'<|tool_call>call:collection_search{query:<|"|>draw<|"|>}<tool_call|>'}}]}, {'choices':[{'message':{'content':'{"reply":"New Draw Engine is an owned alternative.","proposals":[]}'}}]}]
        with patch.object(server,'request_json',side_effect=responses) as mock:
            out=server.ai_chat(self.state,self.deck,'Search my collection for draw.')
            sent=mock.call_args.args[1]['messages'];search_result=next(m['content'] for m in reversed(sent) if str(m['content']).startswith('LOCAL SEARCH RESULT'))
            self.assertIn('New Draw Engine',search_result);self.assertNotIn('"name": "Greater Good"',search_result);self.assertNotIn('<|tool_call>',out['reply']);self.assertTrue(out['_context_trace']['collection_searches'])
    def test_native_call_with_empty_content_executes(self):
        responses=[{'choices':[{'message':{'content':None,'tool_calls':[{'function':{'name':'collection_search','arguments':'{"query":"draw"}'}}]}}]}, {'choices':[{'message':{'content':'{"reply":"Found it."}'}}]}]
        with patch.object(server,'request_json',side_effect=responses):self.assertEqual(server.ai_chat(self.state,self.deck,'Draw?')['reply'],'Found it.')
    def test_repeated_tool_returns_real_results_without_loop(self):
        tool={'choices':[{'message':{'content':'<|tool_call>call:collection_search{query:<|"|>draw<|"|>}<tool_call|>'}}]}
        with patch.object(server,'request_json',return_value=tool) as mock:
            out=server.ai_chat(self.state,self.deck,'Search draw');self.assertEqual(mock.call_count,2);self.assertIn('New Draw Engine',out['reply']);self.assertNotIn('<|tool_call>',out['reply'])
    def test_search_excludes_deck_cards_by_default(self):
        found=server.collection_search(self.state,self.deck,'draw');self.assertEqual([c['name'] for c in found['cards']],['New Draw Engine'])
    def test_exact_ownership_query_can_include_existing_card(self):
        found=server.collection_search(self.state,self.deck,'Greater Good');self.assertEqual(found['cards'][0]['name'],'Greater Good');self.assertTrue(found['cards'][0]['already_in_deck'])
    def test_old_tool_text_not_reintroduced_as_history(self):
        self.assertIn('not executed',server.readable_history('<|tool_call>call:collection_search{}<tool_call|>'))
