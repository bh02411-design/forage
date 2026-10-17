"""Regression cases from the Terra draw failure; model calls are mocked."""
import copy, json, sys, unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server, advisor
from core import make_entry

def card(name,cost,mv,text,ci,typ='Sorcery',power=None):
    return dict(make_entry(name,1),mana_cost=cost,mv=mv,oracle_text=text,color_identity=ci,type_line=typ,power=power,legalities={'commander':'legal'},meta_source='Test fixture',scryfall_id='fixture-'+name)

def answer(data):return {'choices':[{'message':{'content':json.dumps(data)}}]}

class TerraDrawTests(unittest.TestCase):
    def setUp(self):
        self.terra=card('Terra, Herald of Hope','{3}{R}{W}{B}',6,'Whenever Terra deals combat damage to a player, you may pay {2}. When you do, return target creature card with power 3 or less from your graveyard to the battlefield tapped.',['W','B','R'],'Legendary Creature',4)
        self.terra['zone']='commander'
        self.reunion=card('Cathartic Reunion','{1}{R}',2,'As an additional cost to cast this spell, discard two cards. Draw three cards.',['R'])
        self.whisper=card("Night's Whisper",'{1}{B}',2,'You draw two cards and lose 2 life.',['B'])
        self.wall=card('Wall of Omens','{1}{W}',2,'Defender\nWhen this creature enters, draw a card.',['W'],'Creature — Wall','0')
        self.mutt=card('Scrapwork Mutt','{2}',2,'When this creature enters, you may discard a card. If you do, draw a card.\nUnearth {1}{R}',['R'],'Artifact Creature — Dog','2')
        self.bridge=card('Crashing Drawbridge','{2}',2,'Defender\n{T}: Creatures you control gain haste until end of turn.',[],'Artifact Creature — Wall','0')
        self.deck={'id':'terra','name':'Terra','cards':[self.terra,self.reunion],'chat':[],'proposals':[]}
        self.state={'decks':[self.deck],'collection':[self.whisper,self.wall,self.mutt,self.bridge,copy.deepcopy(self.reunion)],'memories':[{'scope':'deck','deck':'terra','text':'Prefer minimal setup in this synthetic test.'}],'rules':[],'settings':{'model':'test','lm_url':'http://localhost:1234/v1','collection_only':True}}
    def rec(self,c):return {'name':c['name'],'mana_cost':c['mana_cost'],'mv':c['mv'],'reason':'Matches the requested role.'}
    def test_drawbridge_not_draw(self):
        found=server.collection_search(self.state,self.deck,'help me find some efficient reliable card draw')
        self.assertEqual({c['name'] for c in found['cards']},{"Night's Whisper",'Wall of Omens','Scrapwork Mutt'})
    def test_exact_ownership_still_finds_drawbridge(self):
        self.assertEqual(server.collection_search(self.state,self.deck,'Crashing Drawbridge')['cards'][0]['name'],'Crashing Drawbridge')
    def test_roles_not_proof_of_draw(self):
        self.bridge['roles']=['Draw']
        self.assertNotIn('Crashing Drawbridge',[c['name'] for c in server.collection_search(self.state,self.deck,'draw')['cards']])
    def test_best_duplicate_metadata(self):
        self.state['collection'].insert(0,make_entry('Wall of Omens',1))
        found=server.collection_search(self.state,self.deck,'draw')
        self.assertEqual(next(c for c in found['cards'] if c['name']=='Wall of Omens')['power'],'0')
    def test_unknown_metadata_disclosed(self):
        self.state['collection'].append(make_entry('Unknown',1))
        found=server.collection_search(self.state,self.deck,'draw');self.assertEqual(found['unresolved_names'],1)
    def test_unknown_identity_is_not_claimed_legal(self):
        self.whisper.pop('color_identity')
        found=server.collection_search(self.state,self.deck,'draw')
        self.assertEqual(next(c for c in found['cards'] if c['name']=="Night's Whisper")['color_check'],'unknown')
    def test_power_cost_and_preferences_in_context(self):
        ctx=server.context(self.state,self.deck)
        self.assertEqual(ctx['cards'][0]['power'],4);self.assertEqual(ctx['cards'][1]['mana_cost'],'{1}{R}');self.assertTrue(ctx['preferences'])
    def test_discard_and_creature_review_not_blind_advantage(self):
        self.assertIn('draw/discard',str(advisor.draw_profile(self.reunion)))
        self.assertIn('casting draw may only replace itself',str(advisor.draw_profile(self.wall)))
        self.assertIn('flashback',str(advisor.draw_profile(card('Test','{2}{R}',3,'Discard a card. Draw two cards. Flashback {3}{R}.',['R']))))
    def test_reject_wrong_mana_cost(self):
        rec=self.rec(self.whisper);rec['mana_cost']='{2}{B}'
        self.assertTrue(advisor.check_recommendations(self.state,self.deck,{'recommendations':[rec]}))
    def test_reject_wrong_mana_value(self):
        rec=self.rec(self.whisper);rec['mv']=3
        self.assertTrue(advisor.check_recommendations(self.state,self.deck,{'recommendations':[rec]}))
    def test_reject_in_deck(self):
        self.assertTrue(advisor.check_recommendations(self.state,self.deck,{'recommendations':[self.rec(self.reunion)]}))
    def test_reject_unowned(self):
        self.assertTrue(advisor.check_recommendations(self.state,self.deck,{'recommendations':[{'name':'Invented'}]}))
    def test_reject_assigned_elsewhere(self):
        self.state['decks'].append({'id':'ygra','cards':[self.whisper]})
        self.assertTrue(advisor.check_recommendations(self.state,self.deck,{'recommendations':[self.rec(self.whisper)]}))
    def test_reject_off_color_and_banned(self):
        self.whisper['color_identity']=['G']
        self.assertTrue(advisor.check_recommendations(self.state,self.deck,{'recommendations':[self.rec(self.whisper)]}))
        self.whisper['color_identity']=['B'];self.whisper['legalities']['commander']='banned'
        self.assertTrue(advisor.check_recommendations(self.state,self.deck,{'recommendations':[self.rec(self.whisper)]}))
    def test_protected_cut_rejected(self):
        self.reunion['protected']=True
        self.assertTrue(advisor.check_recommendations(self.state,self.deck,{'proposals':[{'add':"Night's Whisper",'cut':'Cathartic Reunion','reason':'More hand advantage'}]}))
    def test_valid_alternative_passes(self):
        self.assertFalse(advisor.check_recommendations(self.state,self.deck,{'recommendations':[self.rec(self.whisper)]}))
    def test_button_style_fenced_swap_gets_checked_visual_card(self):
        proposal={'add':self.whisper['name'],'cut':self.reunion['name'],'reason':'Compare immediate hand advantage with filtering.'}
        text='This proposal respects your preferences.\n\n```json\n'+json.dumps({'reply':'A readable swap explanation.','recommendations':[],'proposals':[proposal]})+'\n```'
        fake={'choices':[{'message':{'content':text}}]}
        with patch.object(server,'request_json',return_value=fake) as model:
            result=server.ai_chat(self.state,self.deck,"Find one concrete swap to add Night's Whisper. Explain the tradeoff and propose the swap.")
        self.assertEqual(model.call_count,1);self.assertEqual(result['proposals'],[proposal])
        self.assertEqual(result['reply'],'A readable swap explanation.')
        self.assertEqual(result['_context_trace']['recommendation_checks']['status'],'passed')
        cards=server.visual_recommendations(self.state,self.deck,result)
        self.assertEqual(cards[0]['card']['name'],self.whisper['name'])
    def test_invalid_answer_gets_one_repair(self):
        bad={'reply':'Add Cathartic Reunion.','recommendations':[self.rec(self.reunion)]}
        good={'reply':"Add Night's Whisper for immediate hand advantage.",'recommendations':[self.rec(self.whisper)]}
        with patch.object(server,'request_json',side_effect=[answer(bad),answer(good)]) as model:
            result=server.ai_chat(self.state,self.deck,'help me find efficient reliable card draw')
        self.assertEqual(model.call_count,2);self.assertIn("Night's Whisper",result['reply']);self.assertEqual(result['_context_trace']['recommendation_checks']['status'],'passed')
    def test_missing_manifest_repaired(self):
        with patch.object(server,'request_json',side_effect=[answer({'reply':'Try a card.'}),answer({'reply':'Use Wall of Omens.','recommendations':[self.rec(self.wall)]})]) as model:
            server.ai_chat(self.state,self.deck,'help find reliable draw')
        self.assertEqual(model.call_count,2)
    def test_repeated_invalid_answer_withheld(self):
        bad=answer({'reply':'BAD RECOMMENDATION','recommendations':[self.rec(self.reunion)]})
        with patch.object(server,'request_json',return_value=bad) as model:
            result=server.ai_chat(self.state,self.deck,'help find efficient draw')
        self.assertEqual(model.call_count,2);self.assertNotIn('BAD RECOMMENDATION',result['reply']);self.assertIn('withheld',result['reply']);self.assertFalse(result['proposals'])
    def test_explicit_preference_keeps_user_words(self):
        text="I prefer cards with few setup requirements."
        with patch.object(server,'request_json',return_value=answer({'reply':'Understood.'})):
            result=server.ai_chat(self.state,self.deck,text)
        self.assertEqual(result['memory_suggestions'][0]['text'],text)
        self.assertIsNone(advisor.preference_suggestion('yes'))
    def test_lookup_preserves_power(self):
        c=server.card_data({'id':'123','name':'Test','cmc':2,'power':'0','toughness':'4','mana_cost':'{1}{W}','type_line':'Creature','color_identity':['W'],'oracle_text':'Draw a card.'})
        self.assertEqual(c['power'],'0');self.assertEqual(c['mana_cost'],'{1}{W}')
