"""Evidence selection and checks; heuristics are labelled, never Oracle substitutes."""
import re
from core import key, availability

FACT_FIELDS = ['mv','mana_cost','power','toughness','oracle_text','type_line','color_identity','legalities','scryfall_uri','scryfall_id','meta_source']
ABILITIES = {'draw':r'\bdraw(?:s|ing)?\b','discard':r'\bdiscard(?:s|ing)?\b','mill':r'\bmill(?:s|ing)?\b','sacrifice':r'\bsacrific(?:e|es|ing)\b','flashback':r'\bflashback\b','food':r'\bfood\b','mana':r'\bmana\b|\badd\b.*\{[WUBRG0-9C]'}

def card_facts(card,with_source=False):
    """Only Commander-relevant facts belong in model context, not the full API row."""
    fields=['mv','mana_cost','power','toughness','oracle_text','type_line','color_identity']
    if with_source:fields+=['scryfall_uri','meta_source']
    result={f:card[f] for f in fields if card.get(f) is not None}
    legality=card.get('legalities') or {}
    if legality.get('commander') is not None:result['legalities']={'commander':legality['commander']}
    return result

def mana_value_filter(query):
    """Recognize explicit ranges such as 2-3 CMC or mana value 2 to 3."""
    unit=r'(?:cmc|mv|mana(?:\s+value)?)'
    bounds=r'(\d{1,2})\s*(?:[-–—]|to)\s*(\d{1,2})'
    patterns=[bounds+r'\s*'+unit+r'\b',r'\b'+unit+r'\s*(?:between\s+)?'+bounds]
    for pattern in patterns:
        found=re.search(pattern,query,re.I)
        if found:
            low,high=map(int,found.groups())
            if low<=high:return {'min':low,'max':high}
    return None

def search_prompt(result,limit=10):
    """Keep enough evidence to compare candidates without repeated database metadata."""
    data={k:v for k,v in result.items() if k!='cards'}
    data['cards']=[]
    for c in result.get('cards',[])[:limit]:
        row={k:c[k] for k in ['name','already_in_deck','owned','assigned_elsewhere','available','color_check','roles'] if k in c}
        row.update(card_facts(c,with_source=True))
        data['cards'].append(row)
    data['returned']=len(data['cards'])
    data['note']='Oracle ability matches, not a strategic ranking. Unknown metadata may hide matches. Compare supplied costs, setup, available copies and current deck membership.'
    return data

def intents(query):
    q=query.lower()
    return [k for k,p in ABILITIES.items() if re.search(p,q,re.I)]

def commander_colors(deck):
    commanders=[c for c in deck['cards'] if c['zone']=='commander']
    if not commanders or any(c.get('color_identity') is None for c in commanders):return None
    return set(x for c in commanders for x in c['color_identity'])

def catalog(state,deck):
    """Deduplicate names, taking the most complete lookup as a whole record."""
    merged={}
    for c in state['collection']+deck['cards']:
        k=key(c['name'])
        rank=(bool(c.get('scryfall_id')),sum(c.get(f) is not None for f in FACT_FIELDS),bool(c.get('oracle_text')))
        old=merged.get(k)
        if old is None or rank>old[0]:merged[k]=(rank,c)
    return {k:c for k,(_,c) in merged.items()}

def draw_profile(card):
    text=card.get('oracle_text','');low=text.lower()
    if not re.search(ABILITIES['draw'],low):return None
    creature='Creature' in card.get('type_line','')
    discard=bool(re.search(ABILITIES['discard'],low))
    triggered=bool(re.search(r'\b(when|whenever|at the beginning)\b',low))
    labels=[]
    if discard:labels.append('draw/discard: distinguish filtering from net hand gain; count spell spent')
    if triggered:labels.append('triggered draw: inspect exact trigger and any once-per-turn limit')
    if ':' in low:labels.append('activated draw: count activation, tapping and sacrifices separately')
    if not triggered and ':' not in low and not discard:labels.append('inspect immediate draw and all additional costs')
    if creature:labels.append('creature: compare printed power with commander eligibility; casting draw may only replace itself')
    if 'flashback' in low:labels.append('flashback available: quote its separate cost')
    return {'heuristics':labels,'warning':'Text-pattern hints only, not verified strategic classification. Read full Oracle text; multiple abilities can have different costs.'}

def evidence(card,state,deck):
    ci=card.get('color_identity');colors=commander_colors(deck)
    return {'name':card['name'],**card_facts(card,with_source=True),**availability(state,card['name'],deck['id']),
            'color_check':'unknown' if ci is None or colors is None else 'legal' if set(ci)<=colors else 'outside identity',
            'draw_review':draw_profile(card)}

def cut_request(message):
    """Resolve explicit removal requests before matching desired replacement abilities."""
    text=message.lower().replace('’',"'")
    if re.search(r'\b(?:recommend|suggest|give|list|find)(?:\s+\w+){0,5}\s+swaps?\b|\bcuts?\s+and\s+(?:additions?|replacements?)\b',text):return None
    patterns=[r'\bcards?\s+(?:you\s+would\s+recommend\s+)?(?:swapping out|cutting|removing)\b',r'\bcards?\s+(?:(?:you|i|we)\s+(?:should|could|can)\s+)?to\s+(?:cut|remove|swap out)\b',
              r'\b(?:what|which)(?:\s+\w+){0,4}\s+(?:should|could|can|would)\s+(?:i|we|you)\s+(?:cut|remove|replace)\b',
              r'\b(?:recommend|suggest|find|give|list|identify)(?:\s+\w+){0,6}\s+cuts?\b',
              r'\b(?:cut|remove)\s+(?:me\s+)?(?:[1-9][0-9]?|one|two|three|four|five|six|seven|eight|nine|ten)\s+cards?\b']
    if not any(re.search(p,text) for p in patterns):return None
    if re.search(r"\b(?:do not|don't|without)\s+(?:cut|remove|cutting|removing)\b",text):return None
    words={'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,'seven':7,'eight':8,'nine':9,'ten':10}
    match=re.search(r'\b([1-9][0-9]?|one|two|three|four|five|six|seven|eight|nine|ten)\s+(?:cards?|cuts?)\b',text)
    count=(int(match[1]) if match[1].isdigit() else words[match[1]]) if match else None
    return {'task':'cuts','board':'main','count':count,'instruction':'Recommend removal candidates from the current MAINBOARD only. The desired draw/ramp/etc. describes why space is needed, not a request for collection additions. Do not search for additions. Return cuts: [{"name":"exact mainboard name","reason":"tradeoff and why expendable"}]. Exclude commanders, Considering and protected cards. Use the requested count; if evidence prevents that count, provide cut_limitations explaining the shortfall. Do not execute removals.'}

def check_cuts(deck,data,task):
    issues=[];cuts=data.get('cuts');main={key(c['name']):c for c in deck['cards'] if c['zone']=='main'};seen=set()
    if data.get('recommendations') or data.get('proposals'):issues.append('This request is for cuts only, not additions or swaps.')
    if not isinstance(cuts,list):return issues+['Return a cuts array of mainboard removal candidates.']
    requested=task.get('count');limited=isinstance(data.get('cut_limitations'),str) and bool(data['cut_limitations'].strip())
    if requested is not None and (len(cuts)>requested or len(cuts)<requested and not limited):issues.append('Return '+str(requested)+' distinct cuts or explain the shortfall in cut_limitations.')
    if not cuts and not data.get('cut_limitations'):issues.append('Provide cuts or explain missing evidence in cut_limitations.')
    for item in cuts:
        if not isinstance(item,dict) or not isinstance(item.get('name'),str):issues.append('Each cut needs an exact mainboard name and reason.');continue
        k=key(item['name']);card=main.get(k)
        if not card:issues.append(item['name']+': not in the current mainboard.')
        elif card.get('protected'):issues.append(card['name']+': protected from cuts.')
        if k in seen:issues.append(item['name']+': duplicate cut.')
        seen.add(k)
        if not isinstance(item.get('reason'),str) or not item['reason'].strip():issues.append(item['name']+': explain the removal tradeoff.')
    return list(dict.fromkeys(issues))

def cut_reply(deck,data):
    main={key(c['name']):c for c in deck['cards'] if c['zone']=='main'}
    def cell(value):return str(value).replace('|','\\|').replace('\n',' ').replace('\r',' ')
    rows=[]
    for item in data.get('cuts',[]):
        c=main[key(item['name'])];rows.append('| '+cell(c['name'])+' | '+cell(c.get('mv') if c.get('mv') is not None else 'Unknown')+' | '+cell(item['reason'])+' |')
    reply='Candidates to remove from your current mainboard:\n\n| Card | Mana value | Why consider cutting it |\n|---|---:|---|\n'+'\n'.join(rows) if rows else 'No removal candidates could be verified.'
    if data.get('cut_limitations'):reply+='\n\n'+str(data['cut_limitations'])
    return reply+'\n\nThese are suggestions; no cards have been removed.'

def wants_draw_advice(message):
    return not cut_request(message) and bool(re.search(r'\bdraw\b',message,re.I) and re.search(r'\b(help|recommend|efficient|reliable|find|add|options)\b',message,re.I))

GUIDANCE='''Recommendation procedure: first identify the user's actual problem from the current request, recent corrections and saved preferences. Diagnose the existing mainboard across ALL categories; category labels are not exclusive roles. Search owned alternatives by Oracle abilities. Compare immediate return, net hand change including the spell spent, setup, additional/activation costs, commander independence, and recurrence. A cantrip creature replaces itself in hand when cast but leaves a body; reanimating it can add a card without spending a card from hand. Discard/draw is not automatically net card advantage. Cathartic Reunion-style additional discard costs are paid even if countered. Do not label all discard effects bad: graveyard setup matters. For Terra use her supplied Oracle text: power eligibility, combat connection and reanimation mana all matter; do not substitute mana value for power. Flashback is a preference for noncreatures, not a mandatory restriction unless the user says so. Explain the strongest few choices and real tradeoffs, not an exhaustive keyword list. Never recommend cards already in the active mainboard as additions. Flag unavailable copies and unknown metadata. Use exact supplied mana_cost, mv and power; if missing, state unknown, never fill from memory. Retrieval hints are heuristics, not authoritative rulings. Give a concise comparison including full costs and dependencies. Use markdown tables only when helpful. When recommending additions include a recommendations array [{"name":"exact owned name","mana_cost":"exact supplied cost or null","mv":2,"reason":"concrete benefit and dependencies"}]. This manifest is checked before displaying the response. Do not repeat every field or disclose internal reasoning. Before finalizing verify ownership, identity, existing membership, and any protected cut. For draw ADDITION advice (not removal/cut requests) return at least one checked recommendation if the supplied evidence supports one, or explain the concrete data limitation. Suggest reusable preferences only from explicit user statements; save neither assistant guesses nor unverified rules as preferences.'''

def check_recommendations(state,deck,data):
    issues=[];known=catalog(state,deck);active={key(c['name']):c for c in deck['cards'] if c['zone'] in ['main','commander']}
    recs=data.get('recommendations',[])
    if not isinstance(recs,list):return ['recommendations must be an array']
    proposals=data.get('proposals',[])
    if not isinstance(proposals,list):return ['proposals must be an array']
    for item in recs:
        if isinstance(item,dict) and not all(f in item for f in ['name','mana_cost','mv','reason']):issues.append('recommendation requires name, mana_cost, mv and reason; use null for unknown facts')
    for item in recs+proposals:
        if not isinstance(item,dict):issues.append('recommendation must be an object');continue
        name=item.get('name',item.get('add',''));k=key(name) if isinstance(name,str) else ''
        card=known.get(k)
        if not card:issues.append(str(name)+': no supplied card evidence');continue
        if k in active:issues.append(card['name']+': already in mainboard/commander')
        a=availability(state,card['name'],deck['id'])
        if state['settings'].get('collection_only',True) and a['available']<1:issues.append(card['name']+': no available owned copy')
        colors=commander_colors(deck);ci=card.get('color_identity')
        if colors is not None and ci is not None and not set(ci)<=colors:issues.append(card['name']+': outside commander color identity')
        if card.get('legalities',{}).get('commander') in ['banned','not_legal']:issues.append(card['name']+': not Commander legal')
        for f in ['mana_cost','mv']:
            if f in item and item[f]!=card.get(f):issues.append(card['name']+': '+f+' differs from supplied facts')
        if 'cut' in item:
            cut=active.get(key(item['cut'])) if isinstance(item['cut'],str) else None
            if cut is None or cut.get('zone')!='main':issues.append('cut must be an exact mainboard card')
            elif cut.get('protected'):issues.append(cut['name']+': protected from cuts')
    return list(dict.fromkeys(issues))

def preference_suggestion(message):
    """Keep explicit user wording; never turn a bare yes/no into a preference."""
    if len(message)<=1000 and re.match(r"\s*(remember\b|i prefer\b|i (?:do not|don't) want\b|i want my\b|only recommend\b)",message,re.I):
        return {'text':message.strip(),'scope':'deck'}
    return None
