"""Evidence selection and checks; heuristics are labelled, never Oracle substitutes."""
import re
from core import key, availability

FACT_FIELDS = ['mv','mana_cost','power','toughness','oracle_text','type_line','color_identity','legalities','scryfall_uri','scryfall_id','meta_source']
ABILITIES = {'draw':r'\bdraw(?:s|ing)?\b','discard':r'\bdiscard(?:s|ing)?\b','mill':r'\bmill(?:s|ing)?\b','sacrifice':r'\bsacrific(?:e|es|ing)\b','flashback':r'\bflashback\b','food':r'\bfood\b','mana':r'\bmana\b|\badd\b.*\{[WUBRG0-9C]'}

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
    return {'name':card['name'],**{f:card.get(f) for f in FACT_FIELDS},**availability(state,card['name'],deck['id']),
            'color_check':'unknown' if ci is None or colors is None else 'legal' if set(ci)<=colors else 'outside identity',
            'draw_review':draw_profile(card)}

def wants_draw_advice(message):
    return bool(re.search(r'\bdraw\b',message,re.I) and re.search(r'\b(help|recommend|efficient|reliable|find|add|options)\b',message,re.I))

GUIDANCE='''Recommendation procedure: first identify the user's actual problem from the current request, recent corrections and saved preferences. Diagnose the existing mainboard across ALL categories; category labels are not exclusive roles. Search owned alternatives by Oracle abilities. Compare immediate return, net hand change including the spell spent, setup, additional/activation costs, commander independence, and recurrence. A cantrip creature replaces itself in hand when cast but leaves a body; reanimating it can add a card without spending a card from hand. Discard/draw is not automatically net card advantage. Cathartic Reunion-style additional discard costs are paid even if countered. Do not label all discard effects bad: graveyard setup matters. For Terra use her supplied Oracle text: power eligibility, combat connection and reanimation mana all matter; do not substitute mana value for power. Flashback is a preference for noncreatures, not a mandatory restriction unless the user says so. Explain the strongest few choices and real tradeoffs, not an exhaustive keyword list. Never recommend cards already in the active mainboard as additions. Flag unavailable copies and unknown metadata. Use exact supplied mana_cost, mv and power; if missing, state unknown, never fill from memory. Retrieval hints are heuristics, not authoritative rulings. Give a concise comparison including full costs and dependencies. Use markdown tables only when helpful. When recommending additions include a recommendations array [{"name":"exact owned name","mana_cost":"exact supplied cost or null","mv":2,"reason":"concrete benefit and dependencies"}]. This manifest is checked before displaying the response. Do not repeat every field or disclose internal reasoning. Before finalizing verify ownership, identity, existing membership, and any protected cut. For draw advice return at least one checked recommendation if the supplied evidence supports one, or explain the concrete data limitation. Suggest reusable preferences only from explicit user statements; save neither assistant guesses nor unverified rules as preferences.'''

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
