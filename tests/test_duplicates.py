import unittest
import core

class DuplicateRules(unittest.TestCase):
    def card(self,name,qty=1,zone='main',**fields):
        return {**core.make_entry(name,qty), 'zone':zone, **fields}
    def check(self,cards,**fields):
        return core.duplicate_violations({'cards':cards,**fields})
    def test_printings_and_commander_are_counted_by_english_name(self):
        a=self.card('Sol Ring',set='one',foil=True)
        b=self.card('Sol Ring',zone='commander',set='two',language='fr')
        result=self.check([a,b])
        self.assertEqual(result[0]['quantity'],2)
        self.assertEqual(set(result[0]['ids']),{a['id'],b['id']})
        self.assertEqual(len(self.check([self.card('Sol Ring',2)])),1)
    def test_basic_lands_and_ordinary_lands(self):
        self.assertEqual(self.check([self.card('Forest',99),self.card('Snow-Covered Island',9),self.card('Wastes',9)]),[])
        self.assertEqual(len(self.check([self.card('Command Tower',2,land=True)])),1)
        self.assertEqual(self.check([self.card('Resolved Basic',5,type_line='Basic Snow Land — Forest')]),[])
    def test_any_number_and_self_reference(self):
        rat=self.card('Rat Colony',40,oracle_text='A deck can have any number of cards named Rat Colony.')
        self.assertEqual(self.check([rat]),[])
        rat['oracle_text']='A deck can have any number of cards named Relentless Rats.'
        self.assertEqual(len(self.check([rat])),1)
    def test_finite_exceptions(self):
        for name,word,limit in [('Seven Dwarves','seven',7),('Nazgûl','nine',9),('Templar Knight','thirty',30)]:
            c=self.card(name,limit,oracle_text=f'A deck can have up to {word} cards named {name}.')
            self.assertEqual(self.check([c]),[])
            c['qty']+=1
            self.assertEqual(self.check([c])[0]['limit'],limit)
    def test_considering_and_renamed_staging_are_excluded(self):
        cards=[self.card('Sol Ring'),self.card('Sol Ring',3,zone='maybe'),self.card('Sol Ring',2,group='Candidates')]
        self.assertEqual(self.check(cards,swap_categories={'in':'Candidates','out':'Cuts'}),[])
        cards[2]['group']='Ramp'
        self.assertEqual(self.check(cards,swap_categories={'in':'Candidates','out':'Cuts'})[0]['quantity'],3)
    def test_exact_english_identity_and_resolved_language_variants(self):
        cards=[self.card('Anneau solaire',oracle_id='same',english_name='Sol Ring'),self.card('Sol Ring',oracle_id='same')]
        self.assertEqual(self.check(cards)[0]['quantity'],2)
        self.assertEqual(self.check([self.card('A-B'),self.card('AB')]),[])
        self.assertEqual(self.check([self.card('Nazgûl'),self.card('Nazgu\u0302l')])[0]['quantity'],2)
    def test_resolved_peer_supplies_exception_and_unknown_is_explicit(self):
        a=self.card('Rat Colony',oracle_text='A deck can have any number of cards named Rat Colony.')
        self.assertEqual(self.check([a,self.card('Rat Colony')]),[])
        self.assertTrue(self.check([self.card('Unknown',2)])[0]['unresolved'])
        self.assertFalse(self.check([self.card('Known',2,oracle_text='')])[0]['unresolved'])
    def test_deck_size_remains_exactly_100_including_commander(self):
        cards=[self.card('Leader',zone='commander'),self.card('Forest',99)]
        self.assertEqual(core.analysis({'cards':cards})['total'],100)
        self.assertFalse(any('expected 100' in w for w in core.analysis({'cards':cards})['warnings']))
