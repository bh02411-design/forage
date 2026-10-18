"""Import, analysis, and deterministic deck edits. No AI needed for these operations."""
import csv, io, re, math, copy, random, uuid

def uid(): return uuid.uuid4().hex

def key(name): return re.sub(r'[^a-z0-9]', '', name.lower().split(' // ')[0])

def parse_import(text):
    text=text.lstrip('\ufeff').strip()
    if not text: raise ValueError('Paste a deck list or collection export first.')
    lines=text.splitlines(); out=[]; warnings=[]
    header=lines[0].lower()
    if ('name' in header or 'card' in header) and (',' in header or '\t' in header or ';' in header):
        delimiter='\t' if '\t' in header else ';' if header.count(';')>header.count(',') else ','
        for row in csv.DictReader(io.StringIO(text), delimiter=delimiter):
            row={str(k).strip().lower():v for k,v in row.items() if k is not None}
            name=next((row[k] for k in ['name','card name','cardname','card'] if row.get(k)), '').strip()
            quantity=next((row[k] for k in ['quantity','qty','count','amount'] if row.get(k)), '1')
            zone=next((row[k] for k in ['category','categories','board','zone'] if row.get(k)), 'main')
            if not name: continue
            try: qty=int(quantity)
            except ValueError: raise ValueError('Invalid quantity for '+name)
            out.append(make_entry(name,qty,zone))
    else:
        zone='main'
        for i,line in enumerate(lines,1):
            line=line.strip()
            if not line or line.startswith('#'): continue
            if line.lower().rstrip(':') in ['commander','mainboard','main','maybeboard','sideboard','considering']:
                zone=line.lower().rstrip(':'); continue
            match=re.match(r'^(\d+)x?\s+(.+)$',line)
            if not match:
                warnings.append('Line %d skipped: expected quantity + card name.'%i); continue
            qty=int(match[1]); name=match[2]
            category=re.search(r'\[([^\]]+)\]',name)
            group=category[1] if category else zone
            name=re.sub(r'\s+\([A-Za-z0-9]+\).*$', '',name)
            name=re.sub(r'\s+\[[^\]]*\].*$', '',name)
            name=re.sub(r'\s+\*[^*]*\*.*$', '',name).strip()
            out.append(make_entry(name,qty,group))
    merged={}
    for c in out:
        if c['qty']<=0 or c['qty']>100000: raise ValueError('Quantity must be between 1 and 100000.')
        k=(key(c['name']),c['zone'])
        if k in merged: merged[k]['qty']+=c['qty']
        else: merged[k]=c
    if not merged: raise ValueError('No card rows found. Use plain text or CSV with Name and Quantity columns.')
    return list(merged.values()),warnings

def make_entry(name,qty,group='main'):
    g=group.lower()
    zone='commander' if 'commander' in g else 'maybe' if any(x in g for x in ['maybe','consider','sideboard']) else 'main'
    land=key(name) in [key(n) for n in ['Forest','Swamp','Plains','Island','Mountain','Wastes','Snow-Covered Forest','Snow-Covered Swamp','Snow-Covered Plains','Snow-Covered Island','Snow-Covered Mountain']]
    return {'id':uid(),'name':name,'qty':qty,'zone':zone,'group':'Land' if land else group if g not in ['main','mainboard'] else 'Uncategorized','roles':['Land'] if land else [],'land':land,'mv':0 if land else None,'mdfc':False,'protected':False,'meta_source':'Imported name; metadata not resolved'}

def analysis(deck):
    cards=[c for c in deck['cards'] if c['zone'] in ['main','commander']]
    total=sum(c['qty'] for c in cards); lands=sum(c['qty'] for c in cards if c.get('land'))
    mdfc=sum(c['qty'] for c in cards if c.get('mdfc') and not c.get('land'))
    nonland=[c for c in cards if not c.get('land')]
    known=[c for c in nonland if c.get('mv') is not None]
    n=sum(c['qty'] for c in known); unknown=sum(c['qty'] for c in nonland if c.get('mv') is None)
    hist=[sum(c['qty'] for c in known if min(int(c['mv']),7)==i) for i in range(8)]
    roles={}
    for c in cards:
        for role in set(c.get('roles',[])): roles[role]=roles.get(role,0)+c['qty']
    warnings=[]
    if total!=100: warnings.append('Commander mainboard + commander contains %d cards; expected 100.'%total)
    if not any(c['zone']=='commander' for c in cards): warnings.append('Assign a commander before evaluating color identity.')
    if unknown: warnings.append('%d nonland cards need mana-value metadata; curve is partial.'%unknown)
    ids=set()
    for c in cards:
        ci=c.get('color_identity')
        if c['zone']=='commander' and ci is not None: ids.update(ci)
    if ids:
        off=[c['name'] for c in cards if c.get('color_identity') is not None and not set(c['color_identity'])<=ids]
        if off: warnings.append('Outside commander color identity: '+', '.join(off))
    dupes=[c['name'] for c in cards if c['qty']>1 and 'Basic' not in c.get('type_line','') and key(c['name']) not in [key(x) for x in ['Forest','Swamp','Mountain','Plains','Island','Wastes','Snow-Covered Forest','Snow-Covered Swamp','Snow-Covered Plains','Snow-Covered Island','Snow-Covered Mountain']]]
    if dupes: warnings.append('Review singleton exceptions: '+', '.join(dupes))
    return {'total':total,'lands':lands,'mdfc':mdfc,'average':round(sum(c['mv']*c['qty'] for c in known)/n,2) if n else None,'hist':hist,'roles':roles,'unknown':unknown,'warnings':warnings}

def availability(state,name,exclude_deck=None):
    owned=sum(c['qty'] for c in state['collection'] if key(c['name'])==key(name))
    assigned=sum(c['qty'] for d in state['decks'] if d['id']!=exclude_deck for c in d['cards'] if c['zone'] in ['main','commander'] and key(c['name'])==key(name))
    return {'owned':owned,'assigned_elsewhere':assigned,'available':max(0,owned-assigned),'collection_imported':bool(state['collection'])}

def mana_sample(deck,runs=3000,seed=16):
    rng=random.Random(seed)
    cards=[c for c in deck['cards'] if c['zone']=='main']
    if any(not c.get('meta_source') for c in cards): pass
    pool=[bool(c.get('land') or c.get('mdfc')) for c in cards for _ in range(c['qty'])]
    if len(pool)<14: raise ValueError('Need at least 14 mainboard cards to sample.')
    success={t:0 for t in [2,3,4,5,6]}
    opening=0
    for _ in range(runs):
        order=rng.sample(pool,len(pool)); opening+=2<=sum(order[:7])<=4
        for turn in success:
            # Multiplayer draw on turn one; land can only be played once each turn.
            played=0
            for t in range(1,turn+1):
                available=sum(order[:7+t])-played
                if available>0: played+=1
            if played==turn: success[turn]+=1
    return {'runs':runs,'seed':seed,'opening_two_to_four':round(opening/runs*100,1),'land_drop':{t:round(n/runs*100,1) for t,n in success.items()},'assumptions':'Seeded opening-hand sample. No mulligans, ramp, extra draw, interaction, or tapped/color restrictions. Multiplayer draw on turn one. Every MDFC treated as a land. Measures uninterrupted land drops, not win rate.'}

def apply_swap(state,deck,proposal,new_card,override=False):
    old=next((c for c in deck['cards'] if c['zone']=='main' and key(c['name'])==key(proposal['cut'])),None)
    if not old: raise ValueError('The proposed cut is not in this mainboard anymore.')
    if old.get('protected') and not override: raise ValueError('This card is protected. Unprotect it explicitly before accepting this swap.')
    if any(c['zone'] in ['main','commander'] and key(c['name'])==key(new_card['name']) for c in deck['cards']): raise ValueError('The proposed add is already in this deck.')
    before=copy.deepcopy(deck['cards'])
    old['qty']-=1
    if old['qty']==0: deck['cards'].remove(old)
    new_card=copy.deepcopy(new_card); new_card.update({'id':uid(),'qty':1,'zone':'main'})
    auto_categorize_card(deck,new_card)
    deck['cards'].append(new_card)
    proposal['status']='accepted'
    deck['history'].append({'id':uid(),'type':'swap','before':before,'proposal_id':proposal['id'],'summary':proposal['cut']+' → '+new_card['name']})

# These are presentation defaults, not verified strategic role classifications.
GENERIC_CATEGORIES={'','uncategorized','main','mainboard','maybe','maybeboard','considering','sideboard','commander'}
CATEGORY_RULES=[
 ('Draw',['Card Draw','Draw'],r'\bdraw(?:s)?\b'),
 ('Removal',['Removal','Interaction'],r'\b(?:destroy|exile) (?:target|all|each)\b|\b(?:each|target) opponent sacrifices\b|\beach player sacrifices a (?:nontoken )?creature\b'),
 ('Ramp',['Ramp','Mana'],r'\badd (?:an amount|one|two|three|[0-9]|\{)|search your library for (?:a|an|up to [^.,]+) [^.,]*land'),
 ('Mill',['Mill'],r'\bmill(?:s)?\b'),
 ('Recursion',['Recursion','Reanimation'],r'\breturn\b[^.]*\bfrom (?:your|a) graveyard\b'),
 ('Protection',['Protection'],r'\b(?:hexproof|indestructible)\b'),
 ('Tokens',['Tokens','Token Generation'],r'\bcreate\b[^.]*\btoken'),
 ('Sacrifice',['Sacrifice','Sac Outlets'],r'\bsacrifice\b'),
 ('Food',['Food'],r'\bfood\b')
]

def auto_category_candidate(card,zone=None,include_manual=False):
    return card.get('zone') in ['main','maybe'] and (zone is None or card.get('zone')==zone) and (include_manual or not card.get('category_manual')) and str(card.get('group','')).casefold() in GENERIC_CATEGORIES

def auto_categorize_card(deck,card,include_manual=False):
    """Fill an unassigned board category; never replace a deliberate category."""
    if not auto_category_candidate(card,include_manual=include_manual):return False
    previous=card.get('group');label=None
    for peer in deck['cards']:
        if peer is not card and key(peer['name'])==key(card['name']) and str(peer.get('group','')).casefold() not in GENERIC_CATEGORIES:
            label=peer['group'];break
    names=category_names(deck);existing={n.casefold():n for n in names}
    def choose(default,aliases):return next((existing[a.casefold()] for a in aliases if a.casefold() in existing),default)
    roles=[str(role).split(':')[0].strip().casefold() for role in card.get('roles',[])]
    if not label and (card.get('land') or 'land' in roles):label=choose('Land',['Land','Lands'])
    if not label:
        for default,aliases,pattern in CATEGORY_RULES:
            if any(role in [a.casefold() for a in aliases] for role in roles):label=choose(default,aliases);break
    if not label:
        for default,aliases,pattern in CATEGORY_RULES:
            if re.search(pattern,card.get('oracle_text') or '',re.I):label=choose(default,aliases);break
    if not label:
        typ=card.get('type_line') or ''
        for kind in ['Creature','Planeswalker','Instant','Sorcery','Enchantment','Artifact','Battle']:
            if kind in typ:label=choose(kind,[kind,kind+'s']);break
    card['group']=label or 'Uncategorized'
    if label and include_manual:card.pop('category_manual',None)
    return bool(label and card['group']!=previous)

# Primary presentation categories are separate from overlapping analytical roles.
def category_names(deck):
    return sorted(set(deck.get('categories',[])) | {c.get('group') or ('Commander' if c.get('zone')=='commander' else 'Uncategorized') for c in deck['cards']},key=str.casefold)

def category_label(value):
    if not isinstance(value,str) or not value.strip():raise ValueError('Enter a category name.')
    name=value.strip()
    if len(name)>80 or any(ord(c)<32 for c in name):raise ValueError('Category names must be 1–80 characters without line breaks.')
    return name

def normalize_category_changes(deck,changes):
    if not isinstance(changes,list) or not 1<=len(changes)<=50:raise ValueError('Provide between 1 and 50 category changes.')
    probe=copy.deepcopy(deck);probe['categories']=category_names(probe);normalized=[]
    for raw in changes:
        if not isinstance(raw,dict):raise ValueError('Invalid category change.')
        action=raw.get('action');item={'action':action}
        if action in ['create','move','rename','merge']:item['to']=category_label(raw.get('to'))
        if action in ['rename','merge','delete']:item['from']=category_label(raw.get('from'))
        if action not in ['create','move','rename','merge','delete']:raise ValueError('Unknown category action.')
        if action in ['rename','merge','delete'] and item['from'] not in category_names(probe):raise ValueError('Category not found: '+item['from'])
        if action in ['rename','merge'] and item['from']==item['to']:raise ValueError('Choose a different category name.')
        if action=='move':
            names=raw.get('cards')
            if not isinstance(names,list) or not 1<=len(names)<=100 or any(not isinstance(n,str) for n in names):raise ValueError('Select between 1 and 100 cards to move.')
            canonical=[]
            for name in names:
                matches=[c['name'] for c in probe['cards'] if key(c['name'])==key(name)]
                if not matches:raise ValueError('Card not found in this deck: '+name)
                if matches[0] not in canonical:canonical.append(matches[0])
            item['cards']=canonical
            if 'ids' in raw:
                ids=raw['ids']
                if not isinstance(ids,list) or not ids or len(ids)>10000 or any(not isinstance(i,str) for i in ids):raise ValueError('Invalid card selection.')
                selected=[c for c in probe['cards'] if c['id'] in set(ids)]
                if len(selected)!=len(set(ids)) or {key(c['name']) for c in selected}!={key(n) for n in canonical}:raise ValueError('Selection changed. Reopen the category editor.')
                item['ids']=list(dict.fromkeys(ids))
        item['reason']=str(raw.get('reason',''))[:1000]
        _perform_category_change(probe,item);normalized.append(item)
    return normalized

def _perform_category_change(deck,item):
    categories=set(category_names(deck));action=item['action']
    if action in ['create','move','rename','merge']:categories.add(item['to'])
    if action in ['rename','merge']:
        for c in deck['cards']:
            if c.get('group','Uncategorized')==item['from']:c['group']=item['to']
        categories.discard(item['from'])
    elif action=='move':
        names={key(n) for n in item['cards']}
        for c in deck['cards']:
            if key(c['name']) in names and ('ids' not in item or c['id'] in item['ids']):c['group']=item['to'];c['category_manual']=True
    elif action=='delete':
        if any(c.get('group','Uncategorized')==item['from'] for c in deck['cards']):raise ValueError('This category contains cards. Move them or merge the category first; cards will not be deleted.')
        categories.discard(item['from'])
    deck['categories']=sorted(categories,key=str.casefold)

def apply_category_changes(deck,changes,plan_id=None):
    normalized=normalize_category_changes(deck,changes)  # Atomic validation before mutation.
    before=copy.deepcopy(deck['cards']);before_categories=copy.deepcopy(deck.get('categories'))
    for item in normalized:_perform_category_change(deck,item)
    parts=[]
    for item in normalized:
        if item['action'] in ['rename','merge']:parts.append(item['from']+' → '+item['to'])
        elif item['action']=='move':parts.append('Move '+', '.join(item['cards'])+' → '+item['to'])
        elif item['action']=='create':parts.append('Create category '+item['to'])
        else:parts.append('Remove empty category '+item['from'])
    deck['history'].append({'id':uid(),'type':'category','summary':'; '.join(parts),'before':before,'before_categories':before_categories,'category_plan_id':plan_id})
    return normalized

def normalize_workspace_changes(deck,changes):
    if not isinstance(changes,list) or len(changes)>50:raise ValueError('Too many workspace changes.')
    out=[]
    for raw in changes:
        if not isinstance(raw,dict):raise ValueError('Invalid workspace change.')
        action=raw.get('action')
        if action=='rename_deck':out.append({'action':action,'name':category_label(raw.get('name'))})
        elif action=='set_card':
            matches=[c for c in deck['cards'] if key(c['name'])==key(str(raw.get('card','')))]
            if len(matches)!=1:raise ValueError('Card name is missing or ambiguous: '+str(raw.get('card','')))
            fields=raw.get('fields')
            if not isinstance(fields,dict) or not fields or set(fields)-{'group','roles','protected','zone','qty'}:raise ValueError('Unsupported card settings.')
            fields=copy.deepcopy(fields)
            if 'group'in fields:fields['group']=category_label(fields['group'])
            if 'roles'in fields:
                if not isinstance(fields['roles'],list) or len(fields['roles'])>30:raise ValueError('Roles must be a list of at most 30 labels.')
                fields['roles']=[category_label(r) for r in fields['roles']]
            if 'protected'in fields and not isinstance(fields['protected'],bool):raise ValueError('Protected status must be true or false.')
            if 'zone'in fields and fields['zone'] not in ['main','maybe','commander']:raise ValueError('Invalid board.')
            if 'qty'in fields and (type(fields['qty']) is not int or not 1<=fields['qty']<=100000):raise ValueError('Invalid quantity.')
            out.append({'action':action,'card':matches[0]['name'],'fields':fields})
        elif action=='set_view':
            fields=raw.get('fields')
            if not isinstance(fields,dict) or not fields or set(fields)-{'card_mode','group_by','sort_by','card_size','deck_expanded'}:raise ValueError('Unsupported view settings.')
            for k,choices in [('card_mode',['stacks','grid','list']),('group_by',['category','type','mana','color']),('sort_by',['name','mana'])]:
                if k in fields and fields[k] not in choices:raise ValueError('Invalid '+k)
            if 'card_size'in fields and (type(fields['card_size']) is not int or not 145<=fields['card_size']<=255):raise ValueError('Card size must be 145–255.')
            if 'deck_expanded'in fields and not isinstance(fields['deck_expanded'],bool):raise ValueError('Expanded deck must be true or false.')
            out.append({'action':action,'fields':copy.deepcopy(fields)})
        else:raise ValueError('Unknown workspace action.')
    return out

def apply_workspace_plan(deck,categories,changes,plan_id=None):
    probe=copy.deepcopy(deck)
    cats=normalize_category_changes(probe,categories) if categories else []
    for c in cats:_perform_category_change(probe,c)
    edits=normalize_workspace_changes(probe,changes)
    if not cats and not edits:raise ValueError('No changes to apply.')
    for c in edits:
        if c['action']=='rename_deck':probe['name']=c['name']
        elif c['action']=='set_card':
            for card in probe['cards']:
                if card['name']==c['card']:
                    card.update(c['fields'])
                    if 'group' in c['fields']:card['category_manual']=True
                    elif c['fields'].get('zone') in ['main','maybe']:auto_categorize_card(probe,card)
        elif c['action']=='set_view':probe.setdefault('view_settings',{}).update(c['fields'])
    history={'id':uid(),'type':'workspace','summary':'Apply '+str(len(cats)+len(edits))+' category / workspace changes','before':copy.deepcopy(deck['cards']),'before_categories':copy.deepcopy(deck.get('categories')),'before_name':deck['name'],'before_view_settings':copy.deepcopy(deck.get('view_settings')),'category_plan_id':plan_id}
    for k in ['cards','categories','name','view_settings']:
        if k in probe:deck[k]=probe[k]
    deck['history'].append(history)
    return cats,edits


def remove_selected_cards(deck, ids, category):
    """Validate the entire selection before an undoable, deck-only removal."""
    if not isinstance(ids,list) or not ids or len(ids)>10000 or any(not isinstance(i,str) or not i for i in ids):
        raise ValueError('Select cards to remove.')
    if not isinstance(category,str) or not category:
        raise ValueError('Category required.')
    wanted=set(ids)
    selected=[c for c in deck['cards'] if c['id'] in wanted]
    if len(selected)!=len(wanted):raise ValueError('Selection changed. Reopen the category editor.')
    for c in selected:
        if (c.get('group') or ('Commander' if c.get('zone')=='commander' else 'Uncategorized'))!=category:
            raise ValueError('Selection changed. Reopen the category editor.')
        if c.get('protected'):raise ValueError('Unselect protected cards before removing cards.')
        if c.get('zone')=='commander':raise ValueError('Remove commanders individually from card details.')
    before=copy.deepcopy(deck['cards'])
    deck['cards']=[c for c in deck['cards'] if c['id'] not in wanted]
    deck['history'].append({'id':uid(),'type':'card','summary':'Remove selected cards: '+str(len(selected))+' entries from '+category,'before':before})
