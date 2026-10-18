import unittest
import core

class StagingCounts(unittest.TestCase):
    def test_analysis_excludes_staging_and_handles_moves_and_renames(self):
        leader=core.make_entry('Leader',1,'Commander')
        leader['group']='Swap Out'  # Commander remains pinned and counted.
        normal=core.make_entry('Normal',1,'Draw')
        staged=core.make_entry('Incoming',3,'Swap In')
        staged['roles']=['Draw']
        outgoing=core.make_entry('Forest',4,'Swap Out')
        outgoing['group']='Swap Out'
        deck={'cards':[leader,normal,staged,outgoing]}
        self.assertEqual(core.analysis(deck)['total'],2)
        self.assertEqual(core.analysis(deck)['lands'],0)
        staged['group']='Draw'
        self.assertEqual(core.analysis(deck)['total'],5)
        deck['swap_categories']={'in':'Candidates','out':'Cuts'}
        staged['group']='Candidates'
        outgoing['group']='Cuts'
        self.assertEqual(core.analysis(deck)['total'],2)
        self.assertEqual(core.analysis(deck)['roles'],{})
