"""Synthetic test workspace, not a user's deck, collection or preferences."""
from core import make_entry,uid
from seed import initial_state

def fixture_state():
    state=initial_state();deck=state['decks'][0]
    commander=dict(make_entry('Fixture Commander',1,'Commander'),mv=5,color_identity=['B','G'])
    good=dict(make_entry('Greater Good',1,'Draw'),mv=4,roles=['Draw','Sacrifice: creature / free / repeatable'])
    protected=dict(make_entry('Fixture Protected Creature',1,'Ramp'),mv=2,protected=True)
    modal=dict(make_entry('Fixture MDFC',1,'Removal'),mv=3,mdfc=True)
    drain=dict(make_entry('Fixture Drain',1,'Drain'),mv=3)
    draw=dict(make_entry('Fixture Draw',1,'Draw'),mv=2)
    forest=make_entry('Forest',36,'Land')
    land=dict(make_entry('Fixture Land',1,'Land'),land=True,mv=0)
    fillers=[dict(make_entry('Fixture Creature '+str(i),1,'Creatures'),mv=2) for i in range(57)]
    deck['cards']=[commander,good,protected,modal,drain,draw,forest,land]+fillers
    deck['proposals']=[{'id':uid(),'add':name,'cut':'Fixture Land','reason':'Synthetic test swap.','status':'pending'} for name in ['Fixture Addition A','Fixture Addition B','Orcish Bowmasters']]
    state['memories']=[{'id':uid(),'scope':'deck','deck':deck['id'],'text':'Keep Fixture Protected Creature for this test.'}]
    return state
