import copy,json,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import advisor,server
from core import make_entry
from fixtures import fixture_state

def answer(data):return {'choices':[{'message':{'content':json.dumps(data)}}]}
class CutIntentTests(unittest.TestCase):
    def setUp(self):
        self.state=fixture_state();self.deck=self.state['decks'][0];self.state['settings']['model']='test'
        self.deck['cards']=[dict(make_entry('Main Cut '+str(i),1),mv=i,oracle_text='Synthetic fixture rules.',type_line='Creature') for i in range(6)]
        self.deck['cards'] += [dict(make_entry('Considering Only',1,'Considering'),mv=1),dict(make_entry('Locked Main',1),protected=True),dict(make_entry('Fixture Commander',1),zone='commander')]
        self.deck['chat']=[];self.question='help me find 5 cards to cut to add in more draw spells'
        self.good={'reply':'REMOVE CANDIDATES','cuts':[{'name':'Main Cut '+str(i),'reason':'Low contribution; cutting it loses its body.'} for i in range(5)]}
    def test_exact_requests_select_removal_not_addition(self):
        for text in [self.question,'Give me five cuts for more draw.','Which cards should I remove?','What should I cut for Deadly Dispute?','please give me 5 cards you would recommend swapping out for card draw','Recommend 5 cards to remove from my deck']:
            with self.subTest(text=text):self.assertIsNotNone(advisor.cut_request(text));self.assertFalse(advisor.wants_draw_advice(text))
        self.assertEqual(advisor.cut_request(self.question)['count'],5)
        self.assertEqual(advisor.cut_request('Give me five cuts for more draw.')['count'],5)
    def test_addition_requests_keep_their_scope(self):
        for text in ['Help me find reliable card draw','Give me 5 draw cards from my collection','What can I add without cutting removal?','Recommend 5 swaps with additions and cuts']:
            self.assertIsNone(advisor.cut_request(text),text)
        self.assertTrue(advisor.wants_draw_advice('help me find some efficient reliable card draw'))
    def test_mainboard_cuts_need_no_collection_manifest(self):
        before=copy.deepcopy(self.state)
        with patch.object(server,'collection_search',side_effect=AssertionError('No addition search')),patch.object(server,'request_json',return_value=answer(self.good)) as model:
            result=server.ai_chat(self.state,self.deck,self.question)
        self.assertEqual(model.call_count,1);self.assertEqual(result['recommendations'],[]);self.assertEqual(self.state,before)
        self.assertEqual(len(result['cuts']),5);self.assertIn('Main Cut 4',result['reply']);self.assertNotIn('Considering Only',result['reply'])
        sent=model.call_args.args[1]['messages'];workspace=json.loads(sent[0]['content'].split('\nWORKSPACE DATA:\n')[1]);self.assertEqual(workspace['request_task']['task'],'cuts');self.assertFalse(any(c['zone']=='maybe' for c in workspace['cards']))
    def test_wrong_addition_answer_is_repaired_into_cuts(self):
        wrong={'reply':'Add unrelated draw cards.','recommendations':[{'name':'Collection Draw'}]}
        with patch.object(server,'request_json',side_effect=[answer(wrong),answer(self.good)]) as model:result=server.ai_chat(self.state,self.deck,self.question)
        self.assertEqual(model.call_count,2);self.assertIn('Candidates to remove',result['reply']);self.assertNotIn('Collection Draw',result['reply'])
    def test_numbered_markdown_is_accepted_without_schema_retry(self):
        text='Five removal candidates:\n\n'+'\n'.join(str(i+1)+'. **Main Cut '+str(i)+'** — Low contribution; lose its creature body.' for i in range(5))
        with patch.object(server,'request_json',return_value={'choices':[{'message':{'content':text}}]}) as model:result=server.ai_chat(self.state,self.deck,'recommend me 5 cards to cut please')
        self.assertEqual(model.call_count,1);self.assertEqual(len(result['cuts']),5);self.assertEqual(result['_context_trace']['cut_response_format'],'readable list')
        self.assertIn('Low contribution',result['reply'])
    def test_aliases_and_table_cut_responses(self):
        formats=[{'cut_candidates':[{'card_name':c['name'],'why':c['reason']} for c in self.good['cuts']]},
                 {'reply':'| Card | MV | Reason |\n|---|---|---|\n'+'\n'.join('| '+c['name']+' | 2 | '+c['reason']+' |' for c in self.good['cuts'])}]
        for data in formats:
            with patch.object(server,'request_json',return_value=answer(data)) as model:result=server.ai_chat(self.state,self.deck,self.question)
            self.assertEqual(model.call_count,1);self.assertEqual(len(result['cuts']),5)
    def test_incidental_or_keep_mentions_are_not_cut_recommendations(self):
        for text in ['I would keep Main Cut 0. Main Cut 1 is good too.','1. **Main Cut 0** — Keep this engine.','1. Keep **Main Cut 0**.']:
            normalized,_=advisor.normalize_cut_response(self.deck,{'reply':text});self.assertFalse(normalized.get('cuts'))
    def test_recovered_lists_still_check_protected_and_wrong_board(self):
        text='1. **Locked Main** — Remove as low contribution.\n2. **Considering Only** — Remove as low contribution.'
        normalized,_=advisor.normalize_cut_response(self.deck,{'reply':text});issues=advisor.check_cuts(self.deck,normalized,advisor.cut_request('Give me 2 cuts'))
        self.assertTrue(any('protected' in i for i in issues));self.assertTrue(any('not in the current mainboard' in i for i in issues))
    def test_failure_has_actual_response_diagnostics_and_focused_prompt(self):
        raw='I could not complete this review.'
        with patch.object(server,'request_json',return_value={'choices':[{'message':{'content':raw}}]}) as model:result=server.ai_chat(self.state,self.deck,self.question)
        self.assertEqual(result['_context_trace']['model_response_diagnostic']['text'],raw)
        system=model.call_args.args[1]['messages'][0]['content'].split('\nWORKSPACE DATA:\n')[0]
        self.assertNotIn('category_changes',system);self.assertIn('removal candidates',system)
    def test_wrong_answer_does_not_fallback_to_collection(self):
        with patch.object(server,'request_json',return_value=answer({'reply':'Add new cards instead.'})):result=server.ai_chat(self.state,self.deck,self.question)
        self.assertIn('verifiable mainboard cut list',result['reply']);self.assertEqual(result['recommendations'],[]);self.assertNotIn('_collection_matches',result)
    def test_cut_validation_rejects_wrong_board_locked_duplicate_and_count(self):
        task=advisor.cut_request(self.question)
        for name in ['Considering Only','Locked Main','Fixture Commander','Not owned']:
            bad=copy.deepcopy(self.good);bad['cuts'][0]['name']=name;self.assertTrue(advisor.check_cuts(self.deck,bad,task))
        bad=copy.deepcopy(self.good);bad['cuts'][0]['name']='Main Cut 1';self.assertTrue(advisor.check_cuts(self.deck,bad,task))
        bad=copy.deepcopy(self.good);bad['cuts'].pop();self.assertTrue(advisor.check_cuts(self.deck,bad,task))
        bad['cut_limitations']='Only four candidates have enough known metadata.';self.assertFalse(advisor.check_cuts(self.deck,bad,task))
    def test_exact_deck_lookup_stays_in_cut_task(self):
        with patch.object(server,'request_json',side_effect=[answer({'collection_search':{'query':'Main Cut 0'}}),answer(self.good)]),patch.object(server,'collection_search',side_effect=AssertionError('Not an addition search')):
            result=server.ai_chat(self.state,self.deck,self.question)
        self.assertEqual(len(result['cuts']),5);self.assertEqual(result['_context_trace']['request_task']['task'],'cuts')
    def test_repeated_addition_search_does_not_display_matches(self):
        with patch.object(server,'request_json',return_value=answer({'collection_search':{'query':'draw'}})),patch.object(server,'collection_search',side_effect=AssertionError('Wrong scope')):
            result=server.ai_chat(self.state,self.deck,self.question)
        self.assertNotIn('_collection_matches',result);self.assertEqual(result['recommendations'],[])
if __name__=='__main__':unittest.main()
