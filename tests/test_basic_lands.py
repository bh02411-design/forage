import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import core

def basic(name,qty,protected=False,zone='main'):
    c=core.make_entry(name,qty);c.update(protected=protected,zone=zone);return c

def spell(name,cost,mv=3,qty=1):
    c=core.make_entry(name,qty);c.update(mana_cost=cost,mv=mv,type_line='Creature',oracle_text='Synthetic fixture text.');return c

class BasicLandTests(unittest.TestCase):
    def fixture(self):
        commander=spell('Fixture Commander','{B}{G}',2);commander.update(zone='commander',color_identity=['B','G'])
        deck={'id':'land-test','name':'Land Test','cards':[commander,basic('Swamp',2),basic('Forest',18),spell('Black Demand','{B}{B}{B}',3,10),spell('Green Demand','{G}',1,3)],'history':[],'chat':[],'proposals':[]}
        state={'decks':[deck],'collection':[basic(n,100) for n in core.BASIC_LANDS.values()],'settings':{'collection_only':True}}
        return state,deck
    def rows(self,plan):return {r['color']:r for r in plan['rows']}
    def test_preview_balances_demand_without_mutating_state(self):
        state,deck=self.fixture();before=copy.deepcopy(state);plan=core.basic_land_plan(state,deck);rows=self.rows(plan)
        self.assertEqual(state,before);self.assertTrue(plan['can_apply']);self.assertEqual(sum(r['suggested'] for r in plan['rows']),20);self.assertGreater(rows['B']['suggested'],rows['G']['suggested']);self.assertEqual(rows['W']['suggested'],0)
    def test_apply_keeps_counts_other_cards_and_collection_then_matches(self):
        state,deck=self.fixture();others=[basic('Forest',3,zone='maybe'),basic('Snow-Covered Forest',2),basic('Wastes',1),dict(basic('Forest',2),protected=True)]
        deck['cards']+=others;before=copy.deepcopy(deck['cards']);collection=copy.deepcopy(state['collection']);count=sum(c['qty'] for c in before)
        plan=core.basic_land_plan(state,deck);core.apply_basic_land_plan(state,deck,plan['fingerprint'])
        self.assertEqual(sum(c['qty'] for c in deck['cards']),count);self.assertEqual(state['collection'],collection)
        for c in others:self.assertIn(c,deck['cards'])
        self.assertEqual(len(deck['history']),1);self.assertEqual(deck['history'][0]['before'],before)
        self.assertFalse(core.basic_land_plan(state,deck)['changed'])
    def test_existing_nonbasics_shift_needed_basics(self):
        state,deck=self.fixture();deck['cards']=[spell('White','{W}',3,5),spell('Black','{B}',3,5),basic('Plains',5),basic('Swamp',5),dict(basic('White Sources',10),type_line='Land',oracle_text='{T}: Add {W}.')]
        plan=core.basic_land_plan(state,deck,False);rows=self.rows(plan)
        self.assertEqual(rows['W']['fixed_sources'],10);self.assertEqual(rows['W']['suggested'],0);self.assertEqual(rows['B']['suggested'],10)
    def test_early_spells_have_more_weight_than_late_spells(self):
        state,deck=self.fixture();deck['cards']=[basic('Plains',10),basic('Swamp',10),spell('Early','{W}',1,5),spell('Late','{B}',7,5)]
        weighted=self.rows(core.basic_land_plan(state,deck,True));flat=self.rows(core.basic_land_plan(state,deck,False))
        self.assertGreater(weighted['W']['suggested'],flat['W']['suggested']);self.assertEqual(flat['W']['suggested'],flat['B']['suggested'])
    def test_hybrid_and_generic_do_not_invent_extra_colored_pips(self):
        state,deck=self.fixture();deck['cards']=[basic('Swamp',5),basic('Forest',5),spell('Hybrid','{7}{B/G}{B/G}{X}',9)]
        rows=self.rows(core.basic_land_plan(state,deck));self.assertEqual(rows['B']['colored_pips'],1);self.assertEqual(rows['G']['colored_pips'],1)
    def test_conditional_fetch_and_mdfc_limits_are_visible(self):
        state,deck=self.fixture();deck['cards']+=[dict(basic('Conditional Source',1),type_line='Land',oracle_text='{T}: Add one mana of any color a land an opponent controls could produce.'),dict(basic('Fetch Source',1),type_line='Land',oracle_text='{T}, Sacrifice this land: Search your library for a basic land card.'),dict(spell('Spell Land','{G}',2),mdfc=True)]
        plan=core.basic_land_plan(state,deck);text=' '.join(plan['warnings']);self.assertIn('Conditional Source',text);self.assertIn('Fetch Source',text);self.assertIn('Spell Land',text)
    def test_unknown_costs_and_commander_identity_block_apply(self):
        state,deck=self.fixture();deck['cards'].append(core.make_entry('Unknown Cost',1));plan=core.basic_land_plan(state,deck);self.assertFalse(plan['can_apply']);self.assertIn('Unknown Cost',plan['unknown_costs'])
        state,deck=self.fixture();deck['cards'][0].pop('color_identity');self.assertFalse(core.basic_land_plan(state,deck)['can_apply'])
    def test_missing_nonbasic_rules_are_flagged_as_unknown(self):
        state,deck=self.fixture();deck['cards'].append(dict(basic('Unknown Utility Land',1),type_line='Land'))
        plan=core.basic_land_plan(state,deck);self.assertIn('Unknown Utility Land',plan['unknown_lands']);self.assertFalse(plan['can_apply'])
    def test_collection_only_counts_other_deck_assignments(self):
        state,deck=self.fixture();state['collection']=[basic('Swamp',10),basic('Forest',100)];state['decks'].append({'id':'other','cards':[basic('Swamp',10)]})
        plan=core.basic_land_plan(state,deck);self.assertFalse(plan['can_apply']);self.assertTrue(any('Swamp:' in x for x in plan['blocking']))
    def test_stale_review_and_blocked_review_are_atomic(self):
        state,deck=self.fixture();plan=core.basic_land_plan(state,deck);deck['cards'][1]['qty']+=1;before=copy.deepcopy(deck)
        with self.assertRaisesRegex(ValueError,'changed'):core.apply_basic_land_plan(state,deck,plan['fingerprint'])
        self.assertEqual(deck,before)
    def test_locked_basics_cannot_be_replaced(self):
        state,deck=self.fixture();deck['cards'][2]['protected']=True;plan=core.basic_land_plan(state,deck)
        self.assertGreaterEqual(self.rows(plan)['G']['suggested'],18)
    def test_suggestion_deterministic_and_source_types_can_be_inferred(self):
        state,deck=self.fixture();deck['cards'].append(dict(basic('Typed Dual',1),type_line='Land — Swamp Forest'))
        a=core.basic_land_plan(state,deck);b=core.basic_land_plan(state,deck);self.assertEqual(a,b);self.assertEqual(self.rows(a)['B']['fixed_sources'],1);self.assertEqual(self.rows(a)['G']['fixed_sources'],1)
    def test_increasing_a_color_keeps_existing_printing_rows(self):
        state,deck=self.fixture();extra=basic('Swamp',1);extra.update(group='Special printing',scryfall_id='printing-b');deck['cards'].append(extra);before=copy.deepcopy(extra)
        plan=core.basic_land_plan(state,deck);core.apply_basic_land_plan(state,deck,plan['fingerprint'])
        self.assertIn(before,deck['cards'])
    def test_no_basic_slots_and_colorless_decks_do_not_manufacture_lands(self):
        state,deck=self.fixture();deck['cards']=[spell('Colorless','{3}',3),basic('Wastes',20)]
        plan=core.basic_land_plan(state,deck);self.assertFalse(plan['can_apply']);self.assertEqual(plan['basic_count'],0)

if __name__=='__main__':unittest.main()
