/* Pure card-view helpers shared by the browser and regression checks. */
(function(root){
'use strict';
const escape=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const norm=s=>String(s).toLowerCase().split(' // ')[0].replace(/[^a-z0-9]/g,'');
const imageUrl=s=>{try{const u=new URL(s);return u.protocol==='https:'&&u.hostname==='cards.scryfall.io'?u.href:''}catch{return ''}};
function art(card,collection=[]){if(imageUrl(card.image))return imageUrl(card.image);const found=collection.find(c=>norm(c.name)===norm(card.name)&&imageUrl(c.image));return found?imageUrl(found.image):''}
function groupName(card,by){
 if(card.zone==='commander')return 'Commander';
 if(by==='mana')return card.land?'Lands':card.mv==null?'Unknown mana value':'MV '+(Number(card.mv)>=7?'7+':card.mv);
 if(by==='type'){if(card.land)return 'Land';const type=String(card.type_line||'').split('—')[0];return ['Creature','Planeswalker','Instant','Sorcery','Enchantment','Artifact','Battle'].find(t=>type.includes(t))||'Unresolved type'}
 if(by==='color'){if(card.color_identity==null)return 'Unresolved color';const colors=[...card.color_identity].sort();return colors.length?colors.join(' / '):'Colorless'}
 return card.group||'Uncategorized';
}
function groups(cards,by='category',sort='name'){
 const commanders=cards.filter(c=>c.zone==='commander'),map=new Map();
 for(const c of cards){if(c.zone==='commander')continue;const g=groupName(c,by);if(!map.has(g))map.set(g,[]);map.get(g).push(c)}
 const entries=[...map.entries()].sort(([a],[b])=>a===b?0:(a==='Land'||a==='Lands')?1:(b==='Land'||b==='Lands')?-1:a.localeCompare(b,undefined,{numeric:true}));
 if(commanders.length)entries.unshift(['Commander',commanders]);
 for(const [,list] of entries)list.sort((a,b)=>sort==='mana'?((a.mv??1000)-(b.mv??1000)||a.name.localeCompare(b.name)):a.name.localeCompare(b.name));return entries;
}
function swapCategoryNames(deck){return {in:deck.swap_categories?.in||'Swap In',out:deck.swap_categories?.out||'Swap Out'}}
function onBoard(card,zone){return zone==='main'?['main','commander'].includes(card.zone):card.zone==='maybe'}
function countedBoardCards(deck,zone){
 const shared=Object.values(swapCategoryNames(deck));
 return (deck.cards||[]).filter(c=>onBoard(c,zone)&&(c.zone==='commander'||!shared.includes(c.group)));
}
function manaCostMarkup(card){
 const cost=card.mana_cost;
 if(cost==null)return `<span class="checklist-cost muted">${card.land?'Land · no mana cost':'Mana cost unknown'}</span>`;
 if(!String(cost).trim())return `<span class="checklist-cost muted">${card.land?'Land · no mana cost':'No mana cost'}</span>`;
 const tokens=[...String(cost).matchAll(/\{([^{}]+)\}/g)].map(m=>m[1]);
 if(!tokens.length||String(cost).replace(/\{[^{}]+\}/g,'').trim())return `<span class="checklist-cost">${escape(cost)}</span>`;
 const names={W:'white',U:'blue',B:'black',R:'red',G:'green',C:'colorless',S:'snow',P:'Phyrexian',X:'X',Y:'Y',Z:'Z'};
 return `<span class="checklist-cost" role="img" aria-label="${escape('Mana cost '+tokens.map(t=>t.split('/').map(p=>names[p]||p).join(' or ')).join(', '))}" title="${escape(cost)}">${tokens.map(t=>{
  const colors=t.split('/').filter(p=>['W','U','B','R','G','C'].includes(p));
  return `<span class="checklist-pip${colors.length===1?' mana-'+colors[0]:''}" aria-hidden="true">${escape(t)}</span>`;
 }).join('')}</span>`;
}
function archidektExport(deck){
 const cards=countedBoardCards(deck,'main');
 const lines=cards.map(c=>{
  const category=c.zone==='commander'?'Commander':String(c.group||'Uncategorized');
  if(/[\[\]{},\r\n]/.test(category))throw Error('Rename category "'+category+'" before exporting: Archidekt category syntax reserves commas, brackets, braces and line breaks.');
  if(/[\r\n]/.test(c.name))throw Error('Card names must not contain line breaks.');
  return `${c.qty} ${c.name} [${category}${c.zone==='commander'?'{top}':''}]`;
 });
 const pins=Object.values(swapCategoryNames(deck));
 return {text:lines.join('\n'),total:cards.reduce((n,c)=>n+c.qty,0),considering:(deck.cards||[]).filter(c=>c.zone==='maybe'&&!pins.includes(c.group)).reduce((n,c)=>n+c.qty,0),staging:(deck.cards||[]).filter(c=>['main','maybe'].includes(c.zone)&&pins.includes(c.group)).reduce((n,c)=>n+c.qty,0)};
}
function boardCards(deck,zone){
 const shared=Object.values(swapCategoryNames(deck));
 return (deck.cards||[]).filter(c=>onBoard(c,zone)||(['main','maybe'].includes(c.zone)&&shared.includes(c.group)));
}
function boardGroups(cards,by='category',sort='name',deck={}){
 const pins=swapCategoryNames(deck),names=Object.values(pins);
 const ordinary=cards.filter(c=>c.zone==='commander'||!names.includes(c.group));
 const swaps=names.map(name=>[name,cards.filter(c=>c.zone!=='commander'&&c.group===name).sort((a,b)=>sort==='mana'?((a.mv??1000)-(b.mv??1000)||a.name.localeCompare(b.name)):a.name.localeCompare(b.name))]);
 return {main:groups(ordinary,by,sort),swaps};
}
function manaStats(cards,includeNonlands=true){
 const colors=['W','U','B','R','G','C'],basic={plains:'W',island:'U',swamp:'B',mountain:'R',forest:'G',wastes:'C'};
 const active=cards.filter(c=>['main','commander'].includes(c.zone)),commanders=active.filter(c=>c.zone==='commander');
 const identityKnown=commanders.length>0&&commanders.every(c=>Array.isArray(c.color_identity)),identity=identityKnown?[...new Set(commanders.flatMap(c=>c.color_identity))]:colors.slice(0,5);
 const rows=colors.map(color=>({color,cost:0,cost_cards:0,production:0,production_cards:0})),by=Object.fromEntries(rows.map(r=>[r.color,r]));
 const missingCosts=[],unknownSources=[],conditionalSources=[],optionalMdfcs=[];
 for(const c of active){
  const qty=Number(c.qty)||1,typ=c.type_line||'',land=c.land||(/\bLand\b/.test(typ)&&!c.mdfc),touched=new Set();
  if(!land){
   if(c.mana_cost==null||c.mana_cost===''&&c.mv!==0)missingCosts.push(c.name);
   for(const match of String(c.mana_cost||'').matchAll(/\{([^}]+)\}/g)){
    const choices=match[1].split('/').filter(x=>colors.includes(x));
    for(const color of choices){by[color].cost+=qty/choices.length;touched.add(color)}
   }
   for(const color of touched)by[color].cost_cards+=qty;
  }
  if(c.mdfc&&!c.land){optionalMdfcs.push(c.name);continue}
  if(!land&&(!includeNonlands||!/(?:Creature|Artifact|Enchantment|Planeswalker|Battle)/.test(typ)))continue;
  const units=Object.fromEntries(colors.map(color=>[color,0])),name=norm(c.name.replace(/^Snow-Covered /i,''));
  if(basic[name])units[basic[name]]=1;
  if(land)for(const [name,color] of Object.entries(basic))if(name!=='wastes'&&new RegExp('\\b'+name+'\\b','i').test(typ))units[color]=Math.max(units[color],1);
  const text=(c.oracle_text||'').replace(/\([^)]*\)/g,'');let uncertain=false,found=false;
  for(const line of text.split('\n')){
   const colon=line.indexOf(':');if(colon<0)continue;const output=line.slice(colon+1);
   if(!/\badd\b/i.test(output))continue;found=true;
   if(/could produce|opponent|spend this mana only|activate only|for each|an amount|search your library|equal to/i.test(line)){uncertain=true;continue}
   const counts=Object.fromEntries(colors.map(color=>[color,0]));
   for(const match of output.matchAll(/\{([WUBRGC])\}/g))counts[match[1]]++;
   if(/any colou?r/i.test(output)){
    if(/commander/i.test(output)&&!identityKnown){uncertain=true;continue}
    const amount=output.match(/add\s+(one|two|three|four|five|[1-9][0-9]?)\s+mana/i),numbers={one:1,two:2,three:3,four:4,five:5};
    const n=amount?(numbers[amount[1].toLowerCase()]||Number(amount[1])):1;
    for(const color of identity)counts[color]=Math.max(counts[color],n);
   }
   for(const color of colors)units[color]=Math.max(units[color],counts[color]);
  }
  if(uncertain)conditionalSources.push(c.name);
  if(land&&!Object.values(units).some(Boolean)&&!c.oracle_text)unknownSources.push(c.name);
  if(!land&&/\badd\b/i.test(text)&&!found)conditionalSources.push(c.name);
  for(const color of colors)if(units[color]){by[color].production+=units[color]*qty;by[color].production_cards+=qty}
 }
 const costTotal=rows.reduce((n,r)=>n+r.cost,0),productionTotal=rows.reduce((n,r)=>n+r.production,0);
 for(const row of rows){row.cost_percent=costTotal?row.cost/costTotal*100:0;row.production_percent=productionTotal?row.production/productionTotal*100:0}
 const spells=active.filter(c=>!c.land&&!(/\bLand\b/.test(c.type_line||'')&&!c.mdfc)),known=spells.filter(c=>typeof c.mv==='number'&&Number.isFinite(c.mv));
 const totalMV=known.reduce((n,c)=>n+c.mv*(Number(c.qty)||1),0),spellCount=known.reduce((n,c)=>n+(Number(c.qty)||1),0);
 return {rows,costTotal,productionTotal,totalMV,averageMV:spellCount?totalMV/spellCount:null,unknownMV:spells.length-known.length,missingCosts,unknownSources,conditionalSources:[...new Set(conditionalSources)],optionalMdfcs};
}
function tile(card,collection=[],source='deck',availability=null,duplicate=null){
 const image=art(card,collection);const qty=card.qty??1;
 const fullyAssigned=source==='collection'&&availability&&availability.owned>0&&availability.free===0;
 return `<button class="card-visual ${image?'has-art':'no-art'}${fullyAssigned?' fully-assigned':''}${duplicate?' duplicate-card':''}" draggable="true" data-visual-card="${escape(card.id)}" data-card-source="${source}" aria-label="${escape(card.name)}${duplicate?', '+escape(duplicate.message):''}${fullyAssigned?', all copies assigned to decks':''}${card.protected?', protected':''}${card.needs_sleeving?', needs sleeving':''}" title="${escape(duplicate?duplicate.message:card.name)}"><span class="art-frame">${image?`<img src="${escape(image)}" draggable="false" loading="lazy" decoding="async" alt="${escape(card.name)}">`:`<span class="art-placeholder"><span class="placeholder-symbol">✳</span><strong>${escape(card.name)}</strong><small>Resolve card data for artwork</small></span>`}<span class="tile-badges"><span class="tile-quantity">${qty}×</span>${card.protected?'<span class="tile-protected" title="Protected">◆</span>':''}</span></span>${card.needs_sleeving?'<span class="tile-sleeving">Needs sleeving</span>':''}<span class="tile-caption"><strong>${escape(card.name)}</strong>${duplicate?`<small class="duplicate-label">${duplicate.unresolved?'Duplicate · verify rules':`Duplicate · ${duplicate.quantity} copies / limit ${duplicate.limit}`}</small>`:''}<small>${availability?`${availability.owned} owned · ${availability.free} unassigned${fullyAssigned?' · All copies assigned':''}`:card.land?'Land':'MV '+(card.mv??'?')}</small></span></button>`;
}
function recommendation(rec,collection=[],cards=[],proposals=[]){
 const c=rec.card,p=[...proposals].reverse().find(p=>norm(p.add)===norm(c.name)&&p.status==='pending');
 const cut=p&&cards.find(x=>norm(x.name)===norm(p.cut)&&x.zone==='main');
 const active=cards.some(x=>norm(x.name)===norm(c.name)&&['main','commander'].includes(x.zone));
 const maybe=cards.some(x=>norm(x.name)===norm(c.name)&&x.zone==='maybe');
 const passed=rec.status==='passed',disabled=passed||active;
 const picture=(card,label)=>{const url=art(card,collection);return `<button class="recommendation-art" data-rec-action="inspect" data-rec-side="${label}" aria-label="Inspect ${escape(card.name)}"><span class="art-frame">${url?`<img src="${escape(url)}" alt="${escape(card.name)}" loading="lazy" decoding="async">`:`<span class="art-placeholder"><strong>${escape(card.name)}</strong><small>Artwork not resolved · click to inspect</small></span>`}</span><strong>${escape(card.name)}</strong><small>${escape(card.mana_cost||'')} · MV ${escape(card.mv??'?')}</small></button>`};
 return `<article class="recommendation-card" data-rec-id="${escape(rec.id)}"><div class="recommendation-pair"><div><span class="eyebrow green">${rec.kind==='match'?'COLLECTION MATCH':'ADD'}</span>${picture(c,'add')}</div>${cut?`<div><span class="eyebrow">CUT</span>${picture(cut,'cut')}</div>`:''}</div><p>${escape(p?.reason||rec.reason||'Review this card for your deck.')}</p><div class="recommendation-actions">${disabled?`<span class="muted small">${passed?'Passed': 'In mainboard'}</span>`:`<button class="button primary" data-rec-action="${p?'accept':'find'}">${p?'Accept swap':'Find a swap'}</button><button class="button secondary" data-rec-action="${p?'different':'main'}">${p?'Different cut':'Add to Mainboard'}</button><button class="button secondary" data-rec-action="maybe" ${maybe?'disabled':''}>${maybe?'In Considering':'Considering'}</button><button class="quiet" data-rec-action="pass">Pass</button>`}</div></article>`;
}
function pendingDecisions(deck){
 const proposals=(deck.proposals||[]).filter(p=>p.status==='pending');
 const latest=new Map();
 for(const message of deck.chat||[])for(const rec of message.recommendations||[])latest.set(norm(rec.card.name),{message:message.id,rec});
 const recommendations=[...latest.values()].filter(({rec})=>rec.status==='pending'&&!(deck.cards||[]).some(c=>norm(c.name)===norm(rec.card.name)&&(['main','commander'].includes(c.zone)||(c.zone==='maybe'&&!proposals.some(p=>norm(p.add)===norm(c.name))))));
 const shown=new Set(recommendations.map(({rec})=>norm(rec.card.name)));
 return {recommendations,proposals:proposals.filter(p=>!shown.has(norm(p.add))),plans:(deck.category_plans||[]).filter(p=>p.status==='pending')};
}
// Local Scryfall-style subset. Unknown metadata is not equivalent to a negative match.
function compileSearch(query){
 query=String(query||'').trim();if(query.length>2000)throw Error('Keep filters under 2,000 characters.');
 const tokens=[];let token='',quote='',escaped=false;
 const emit=()=>{if(token){tokens.push(token);token=''}};
 for(const ch of query){if(quote){token+=ch;if(escaped)escaped=false;else if(ch==='\\')escaped=true;else if(ch===quote)quote='';continue}if(ch==='"'||(ch==="'"&&(!token||/[:=!<>]$/.test(token)))){quote=ch;token+=ch}else if(/\s/.test(ch))emit();else if(ch==='('||ch===')'){emit();tokens.push(ch)}else token+=ch}
 emit();if(quote)throw Error('Close the quoted phrase.');if(tokens.length>150)throw Error('Use fewer than 150 search terms.');
 const value=s=>{if(!s)throw Error('Add a value after the operator.');if((s[0]==='"'||s[0]==="'")&&s.at(-1)===s[0])return s.slice(1,-1).replace(/\\(["'\\])/g,'$1');return s};
 const contains=(actual,needle)=>actual==null?null:String(actual).toLowerCase().includes(needle.toLowerCase());
 const number=(x,op,y)=>{if(x==null||!/^[-+]?\d+(?:\.\d+)?$/.test(String(x)))return null;x=Number(x);return op==='<'?x<y:op==='<='?x<=y:op==='>'?x>y:op==='>='?x>=y:op==='!='?x!==y:x===y};
 const and=(a,b)=>a===false||b===false?false:a===null||b===null?null:true;
 const or=(a,b)=>a===true||b===true?true:a===null||b===null?null:false;
 const not=a=>a===null?null:!a;
 const colorNames={white:'w',blue:'u',black:'b',red:'r',green:'g',colorless:'',c:'',azorius:'wu',dimir:'ub',rakdos:'br',gruul:'rg',selesnya:'gw',orzhov:'wb',izzet:'ur',golgari:'bg',boros:'rw',simic:'gu',esper:'wub',grixis:'ubr',jund:'brg',naya:'rgw',bant:'gwu',abzan:'wbg',jeskai:'urw',sultai:'bgu',mardu:'rwb',temur:'gur',fivecolor:'wubrg'};
 function term(raw){
  if(raw.startsWith('-')&&raw.length>1){const child=term(raw.slice(1));return c=>not(child(c))}
  if(raw.startsWith('!"')||raw.startsWith("!'")){const exact=value(raw.slice(1)).toLowerCase();return c=>String(c.name).toLowerCase()===exact}
  const m=/^([a-z_]+)(:|!=|<=|>=|=|<|>)(.*)$/i.exec(raw);
  if(!m){if(/[<>:=]/.test(raw)&&!/^['"]/.test(raw))throw Error('Use a supported field such as o:draw, t:creature or mv<=3.');const text=value(raw);return c=>contains([c.name,c.type_line,c.oracle_text,...(c.roles||[])].filter(x=>x!=null).join(' '),text)}
  const field=m[1].toLowerCase(),op=m[2],v=value(m[3]);
  if(v.startsWith('/'))throw Error('Regular-expression searches are not supported locally.');
  const numeric={mv:'mv',cmc:'mv',manavalue:'mv',pow:'power',power:'power',tou:'toughness',toughness:'toughness',qty:'qty'};
  if(numeric[field]){if(!/^-?\d+(?:\.\d+)?$/.test(v))throw Error(field+' needs a number, such as '+field+'<=3.');return c=>number(c[numeric[field]],op,Number(v))}
  if(['c','color','id','identity','ci','commander'].includes(field)){
   const identity=!['c','color'].includes(field),source=identity?'color_identity':'colors';
   const multi=['m','multicolor','multicolored'].includes(v.toLowerCase());let wanted=colorNames[v.toLowerCase()]??v.toLowerCase();
   if(!multi&&!/^\d+$/.test(wanted)&&!/^[wubrg]*$/.test(wanted))throw Error('Use W, U, B, R, G, color names, guild names or a color count.');
   if(multi&&![':','=','!='].includes(op))throw Error('Use c:m or id:m for multicolor, or compare a numeric color count.');
   wanted=[...new Set(wanted)];
   return c=>{if(!Array.isArray(c[source]))return null;const actual=[...new Set(c[source].map(x=>x.toLowerCase()))];
    if(multi)return op==='!='?actual.length<2:actual.length>=2;
    if(/^\d+$/.test(v))return number(actual.length,op,Number(v));
    const a=actual.every(x=>wanted.includes(x)),b=wanted.every(x=>actual.includes(x));
    const cmp=op===':'?(!wanted.length?'=':identity?'<=':'>='):op;
    return cmp==='='?a&&b:cmp==='!='?!(a&&b):cmp==='<='?a:cmp==='<'?a&&actual.length<wanted.length:cmp==='>'?b&&actual.length>wanted.length:b;
   };
  }
  const textFields={n:'name',name:'name',o:'oracle_text',oracle:'oracle_text',fo:'oracle_text',fulloracle:'oracle_text',t:'type_line',type:'type_line',role:'roles',group:'group',category:'group',s:'set',set:'set',r:'rarity',rarity:'rarity',kw:'keywords',keyword:'keywords'};
  if(textFields[field]){
   if(![':','=','!='].includes(op))throw Error('Use : or = for '+field+'.');
   let needle=v.toLowerCase();if(['r','rarity'].includes(field)){needle=({c:'common',u:'uncommon',r:'rare',m:'mythic',s:'special',b:'bonus'})[needle]||needle;if(!['common','uncommon','rare','mythic','special','bonus'].includes(needle))throw Error('Unknown rarity. Try r:common or r:mythic.')}
   return c=>{let actual=c[textFields[field]];if(actual==null||(actual===''&&['type_line','set','rarity'].includes(textFields[field])))return null;
    if(Array.isArray(actual))actual=actual.join(' ');
    if(['o','oracle'].includes(field)){let depth=0,plain='';for(const ch of String(actual)){if(ch==='(')depth++;else if(ch===')')depth=Math.max(0,depth-1);else if(!depth)plain+=ch}actual=plain}
    let result=['set','s','rarity','r','kw','keyword'].includes(field)?(Array.isArray(c[textFields[field]])?c[textFields[field]].some(x=>String(x).toLowerCase()===needle):String(actual).toLowerCase()===needle):op===':'?contains(actual,needle):String(actual).toLowerCase()===needle;
    return op==='!='?!result:result;
   };
  }
  if(['f','format','legal','banned','restricted'].includes(field)){
   if(op!==':')throw Error('Use '+field+':commander for format filters.');const format=v.toLowerCase()==='edh'?'commander':v.toLowerCase();
   return c=>{const status=c.legalities?.[format];if(status==null)return null;return field==='banned'?status==='banned':field==='restricted'?status==='restricted':['legal','restricted'].includes(status)};
  }
  if(field==='is'){
   if(op!==':')throw Error('Use is:permanent, is:dfc or is:mdfc.');const kind=v.toLowerCase();if(!['permanent','spell','dfc','mdfc','modal_dfc'].includes(kind))throw Error('This is: filter is not supported locally.');
   return c=>{if(['dfc','mdfc','modal_dfc'].includes(kind)){if(c.layout==null)return null;return kind==='dfc'?['transform','modal_dfc','reversible_card','double_faced_token'].includes(c.layout):c.layout==='modal_dfc'}if(c.type_line==null)return null;return kind==='spell'?!/\bLand\b/.test(c.type_line):/\b(Creature|Artifact|Enchantment|Planeswalker|Battle|Land)\b/.test(c.type_line)};
  }
  throw Error('Unsupported local filter: '+field+'. See the Syntax key for supported fields.');
 }
 let pos=0;
 function unary(){if(['-','NOT'].includes(tokens[pos]?.toUpperCase())){pos++;const f=unary();return c=>not(f(c))}if(tokens[pos]==='('){pos++;const f=expr();if(tokens[pos++]!==')')throw Error('Close the search parentheses.');return f}if(!tokens[pos]||[')', 'OR','AND'].includes(tokens[pos].toUpperCase()))throw Error('Add a term beside the search operator.');return term(tokens[pos++])}
 function both(){let f=unary();while(pos<tokens.length&&tokens[pos]!==')'&&tokens[pos].toUpperCase()!=='OR'){if(tokens[pos].toUpperCase()==='AND')pos++;const g=unary(),previous=f;f=c=>and(previous(c),g(c))}return f}
 function expr(){let f=both();while(tokens[pos]?.toUpperCase()==='OR'){pos++;const g=both(),previous=f;f=c=>or(previous(c),g(c))}return f}
 if(!tokens.length)return ()=>true;const filter=expr();if(pos!==tokens.length)throw Error('Check the search parentheses.');return filter;
}
function search(cards,query){try{const test=compileSearch(query),matches=[];let unknown=0;for(const c of cards){const result=test(c);if(result===true)matches.push(c);else if(result===null)unknown++}return {matches,unknown,error:null}}catch(error){return {matches:[],unknown:0,error:error.message}}}
function inventory(collection=[],decks=[]){
 const counts=new Map(),entry=name=>{const k=norm(name);if(!counts.has(k))counts.set(k,{owned:0,assigned:0,free:0});return counts.get(k)};
 for(const c of collection)entry(c.name).owned+=Number(c.qty)||0;
 for(const deck of decks)for(const c of deck.cards||[])if(['main','commander'].includes(c.zone))entry(c.name).assigned+=Number(c.qty)||0;
 for(const item of counts.values())item.free=Math.max(0,item.owned-item.assigned);
 return counts;
}
function sortCollection(cards,by='name',direction='asc',counts=new Map()){
 const collator=new Intl.Collator(undefined,{numeric:true,sensitivity:'base'}),sign=direction==='desc'?-1:1;
 const ranks={common:0,uncommon:1,rare:2,mythic:3,special:4,bonus:5},colors='WUBRG';
 const value=c=>{
  if(by==='mana')return c.mv==null||c.mv===''||!Number.isFinite(Number(c.mv))?null:Number(c.mv);
  if(by==='color'){if(!Array.isArray(c.color_identity))return null;const ci=[...new Set(c.color_identity)].sort((a,b)=>colors.indexOf(a)-colors.indexOf(b));return ci.length+':'+ci.map(c=>colors.indexOf(c)).join('')}
  if(by==='type'){if(c.land)return 'Land';if(!c.type_line)return null;return ['Creature','Planeswalker','Instant','Sorcery','Enchantment','Artifact','Battle','Land'].find(t=>c.type_line.includes(t))||c.type_line.split('—')[0].trim()}
  if(by==='rarity')return ranks[c.rarity]??null;
  if(by==='owned')return counts.get(norm(c.name))?.owned??(Number(c.qty)||0);
  if(by==='available')return counts.get(norm(c.name))?.free??null;
  return c.name;
 };
 return cards.map(card=>({card,value:value(card)})).sort((a,b)=>{
  if(a.value==null&&b.value!=null)return 1;if(b.value==null&&a.value!=null)return -1;
  let result=a.value==null?0:typeof a.value==='number'&&typeof b.value==='number'?a.value-b.value:collator.compare(String(a.value),String(b.value));
  return result*sign||collator.compare(a.card.name,b.card.name);
 }).map(row=>row.card);
}
const api={manaStats,groups,onBoard,countedBoardCards,manaCostMarkup,archidektExport,boardCards,boardGroups,swapCategoryNames,art,tile,groupName,recommendation,pendingDecisions,search,compileSearch,inventory,sortCollection};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.ForageCards=api;
})(typeof window!=='undefined'?window:globalThis);
