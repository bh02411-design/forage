"""Empty starter workspace. User decks and preferences are stored only locally."""
import uuid

def uid():return uuid.uuid4().hex

def initial_state():
    ident=uid()
    return {'version':1,'active':ident,'decks':[{'id':ident,'name':'My deck','source':'Import a deck to get started.','cards':[],'chat':[],'history':[],'proposals':[]}],
            'collection':[],'collection_source':'Not imported.','memories':[],'rules':[],
            'settings':{'lm_url':'http://127.0.0.1:1234/v1','model':'','collection_only':True}}
