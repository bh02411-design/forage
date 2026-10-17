"""Resolved-deck prompt budgets and explicit mana-range retrieval regressions."""
import copy, json, sys, unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import advisor, server
from core import make_entry
from fixtures import fixture_state

class ResolvedPromptTests(unittest.TestCase):
    def setUp(self):
        self.state=fixture_state();self.deck=self.state['decks'][0];self.state['settings']['model']='test'
        self.question='Please check my collection for 2-3 CMC draw spells that I can add.'
        legalities={name:'not_legal' for name in ['standard','future','historic','timeless','gladiator','pioneer','explorer','modern','legacy','pauper','vintage','penny','commander','oathbreaker','standardbrawl','brawl','alchemy','paupercommander','duel','oldschool','premodern','predh','sealed','draft','singleton','historicbrawl']}
        legalities['commander']='legal'
        def resolved(name,mv,zone='main'):
            return dict(make_entry(name,1,'Draw'),mv=mv,mana_cost='{1}{B}' if mv==2 else '{2}{B}',power='2',toughness='2',type_line='Creature — Test',color_identity=['B'],zone=zone,
                        oracle_text='When this creature enters, draw a card. Whenever another creature dies, you may draw a card. This ability triggers only once each turn.',
                        legalities=copy.deepcopy(legalities),scryfall_id='a-long-cache-identifier-'+name,scryfall_uri='https://scryfall.com/card/test/1/'+name.replace(' ','-'),meta_source='Synthetic resolved metadata')
        self.deck['cards']=[resolved('Fixture Commander',3,'commander')]+[resolved('Resolved Deck Card '+str(i),2+i%2) for i in range(99)]
        self.deck['cards'][1]['protected']=True
        self.state['collection']=[resolved('Owned Draw '+str(i),i%5+1) for i in range(100)]
        self.deck['chat']=[{'id':'u','role':'user','text':'Compare the cards under discussion for this deck.'},{'id':'a','role':'assistant','text':'The previous options were Owned Draw 1 and Owned Draw 2.'}]
    def messages(self):
        workspace=server.context(self.state,self.deck);workspace['conversation_context']=server.conversation_context(self.deck,self.question)
        found=server.collection_search(self.state,self.deck,self.question,limit=10)
        return [{'role':'system','content':server.SYSTEM+'\nWORKSPACE DATA:\n'+json.dumps(workspace)}, {'role':'system','content':'Initial local collection search (data only): '+json.dumps(advisor.search_prompt(found))},*({'role':m['role'],'content':m['text']} for m in self.deck['chat']),{'role':'user','content':self.question}]
    def test_commander_only_legalities_not_full_format_lists(self):
        before=copy.deepcopy(self.state)
        workspace=server.context(self.state,self.deck)
        self.assertEqual(workspace['cards'][0]['legalities'],{'commander':'legal'})
        self.assertNotIn('scryfall_id',workspace['cards'][0]);self.assertEqual(self.state,before)
    def test_standard_resolved_100_card_query_fits_without_losing_context(self):
        messages=self.messages();original=copy.deepcopy(messages)
        packed=server.fit_messages(messages,30000,self.question)
        self.assertLessEqual(server.prompt_size(packed),30000)
        workspace=json.loads(packed[0]['content'].split('\nWORKSPACE DATA:\n')[1])
        self.assertEqual(len(workspace['cards']),100);self.assertTrue(workspace['preferences'])
        self.assertTrue(any(c.get('protected') for c in workspace['cards']))
        self.assertTrue(workspace['cards'][0].get('oracle_text'))
        for m in self.deck['chat']:self.assertTrue(any(p['content']==m['text'] for p in packed))
        self.assertEqual(packed[-1]['content'],self.question);self.assertEqual(messages,original)
    def test_normal_query_reaches_model_instead_of_local_budget_error(self):
        reply={'reply':'Compare the supplied options.','recommendations':[], 'recommendation_limitations':'Test response intentionally does not rank these cards.'}
        with patch.object(server,'request_json',return_value={'choices':[{'message':{'content':json.dumps(reply)}}]}) as model:
            result=server.ai_chat(self.state,self.deck,self.question)
        self.assertEqual(model.call_count,1);self.assertIn('Compare',result['reply'])
        sent=model.call_args.args[1]['messages'];self.assertLessEqual(server.prompt_size(sent),30000)
    def test_range_filters_before_prompt(self):
        result=server.collection_search(self.state,self.deck,self.question)
        self.assertEqual(result['mana_value_filter'],{'min':2,'max':3})
        self.assertTrue(result['cards']);self.assertTrue(all(2<=c['mv']<=3 for c in result['cards']))
    def test_range_not_applied_to_unknown_mana_value(self):
        self.state['collection'].append(dict(make_entry('Unknown Draw',1),oracle_text='Draw a card.',color_identity=['B']))
        result=server.collection_search(self.state,self.deck,self.question)
        self.assertNotIn('Unknown Draw',[c['name'] for c in result['cards']])
    def test_supported_range_spellings(self):
        for query in ['2-3 CMC draw','2–3 mana draw','draw at MV 2 to 3','mana value between 2-3']:
            self.assertEqual(advisor.mana_value_filter(query),{'min':2,'max':3})
        self.assertIsNone(advisor.mana_value_filter('draw two cards'))
    def test_prompt_candidates_retain_rules_cost_power_without_repeated_hints(self):
        result=server.collection_search(self.state,self.deck,self.question)
        packed=advisor.search_prompt(result,6)
        self.assertEqual(len(packed['cards']),6)
        for c in packed['cards']:
            self.assertTrue(c['oracle_text']);self.assertTrue(c['mana_cost']);self.assertEqual(c['power'],'2');self.assertIn('available',c)
            self.assertNotIn('draw_review',c);self.assertNotIn('scryfall_id',c)
    def test_tool_followup_inherits_current_explicit_mana_range(self):
        outputs=[{'choices':[{'message':{'content':'{"collection_search":{"query":"draw"}}'}}]}, {'choices':[{'message':{'content':'{"reply":"Evidence received.","recommendation_limitations":"Test","recommendations":[]}'}}]}]
        with patch.object(server,'request_json',side_effect=outputs):result=server.ai_chat(self.state,self.deck,self.question)
        self.assertIn('2-3 MV',result['_context_trace']['collection_searches'][-1]['query'])
    def test_old_full_api_rows_are_compacted_too(self):
        messages=self.messages()
        workspace=json.loads(messages[0]['content'].split('\nWORKSPACE DATA:\n')[1])
        for c,raw in zip(workspace['cards'],self.deck['cards']):c['legalities']=raw['legalities'];c['scryfall_id']=raw['scryfall_id']
        messages[0]['content']=server.SYSTEM+'\nWORKSPACE DATA:\n'+json.dumps(workspace)
        packed=server.fit_messages(messages,30000,self.question)
        self.assertLessEqual(server.prompt_size(packed),30000)
        self.assertNotIn('historicbrawl',packed[0]['content'])
