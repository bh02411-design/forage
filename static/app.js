'use strict';
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
let chatRenderedDeck=null;
let state,token,zone='main',view='workbench',pendingCard=null,pendingImage=null,busy=false,aiConnected=false;
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const norm=s=>s.toLowerCase().split(' // ')[0].replace(/[^a-z0-9]/g,'');
const uiRead=(k,fallback)=>{try{return localStorage.getItem('forage.'+k)||fallback}catch{return fallback}};
const uiSave=(k,v)=>{try{localStorage.setItem('forage.'+k,v)}catch{}};
let cardMode=uiRead('cardMode','stacks'),groupBy=uiRead('groupBy','category'),sortBy=uiRead('sortBy','name'),collectionMode=uiRead('collectionMode','grid'),collectionSort=uiRead('collectionSort','name'),collectionDirection=uiRead('collectionDirection','asc'),collectionLimit=60,deckExpanded=false;
if(!['name','mana','color','type','rarity','owned','available'].includes(collectionSort))collectionSort='name';
if(!['asc','desc'].includes(collectionDirection))collectionDirection='asc';
if(!['stacks','grid','list'].includes(cardMode))cardMode='stacks';
if(!['category','type','mana','color'].includes(groupBy))groupBy='category';
if(!['name','mana'].includes(sortBy))sortBy='name';
const deck=()=>state.decks.find(d=>d.id===state.active);
const mainCards=()=>deck().cards.filter(c=>['main','commander'].includes(c.zone));
const safeUrl=s=>{try{const u=new URL(s);return u.protocol==='https:'?u.href:''}catch{return ''}};
function toast(text){$('#toast').textContent=text;$('#toast').hidden=false;clearTimeout(toast.timer);toast.timer=setTimeout(()=>$('#toast').hidden=true,5000)}
async function api(path,payload){const options=payload===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json','X-Forage-Token':token},body:JSON.stringify(payload)};const r=await fetch('/api/'+path,options);let data;try{data=await r.json()}catch{throw Error('Server unavailable. Open Forage from the tray or Start menu, or restart its launcher.')}if(!r.ok)throw Error(data.error||'Request failed');return data}
async function refresh(){const r=await api('state');state=r.state;token=r.token;render()}
async function mutate(path,payload){const r=await api(path,{deck:state.active,...payload});await refresh();return r}
function modal(title,content){$('#modal').classList.toggle('card-modal',content.includes('class="card-detail"'));$('#modal-title').textContent=title;$('#modal-content').innerHTML=content;if(!$('#modal').open)$('#modal').showModal()}
function closeModal(){$('#modal').close()}
function stat(label,value,detail){return `<div class="stat"><div class="stat-label">${label}</div><div class="stat-value">${esc(value)}<small>${detail}</small></div></div>`}
function render(){
  syncViewSettings();
  $('#deck-select').innerHTML=state.decks.map(d=>`<option value="${d.id}" ${d.id===state.active?'selected':''}>${esc(d.name)}</option>`).join('');
  $('#deck-name').textContent=deck().name;$('#deck-source').textContent=deck().source;
  const cards=mainCards(),total=cards.reduce((a,c)=>a+c.qty,0),lands=cards.filter(c=>c.land).reduce((a,c)=>a+c.qty,0),mdfc=cards.filter(c=>c.mdfc&&!c.land).reduce((a,c)=>a+c.qty,0);
  const known=cards.filter(c=>!c.land&&c.mv!==null&&c.mv!==undefined),knownN=known.reduce((a,c)=>a+c.qty,0),unknown=cards.filter(c=>!c.land&&c.mv==null).reduce((a,c)=>a+c.qty,0);
  const avg=knownN?(known.reduce((a,c)=>a+c.mv*c.qty,0)/knownN).toFixed(2):'—';
  const roles={};for(const c of cards)for(const r of new Set(c.roles||[]))roles[r]=(roles[r]||0)+c.qty;
  $('#stats').innerHTML=stat('DECK SIZE',total,'/ 100 cards')+stat('MANA VALUE',avg,unknown?'partial data':'nonland average')+stat('LAND SOURCES',lands+mdfc,`${lands} lands + ${mdfc} MDFC`)+stat('ACTIVE MEMORIES',state.memories.filter(m=>m.scope==='global'||m.deck===state.active).length,'shaping this deck');
  $('#roles').innerHTML=Object.entries(roles).filter(([r])=>r!=='Land').sort((a,b)=>b[1]-a[1]).map(([r,n])=>`<span class="chip">${esc(r)} · ${n}</span>`).join('')||'<p class="muted">Resolve card data or assign roles.</p>';
  const hist=Array.from({length:8},(_,i)=>known.filter(c=>Math.min(Math.floor(c.mv),7)===i).reduce((a,c)=>a+c.qty,0));const max=Math.max(1,...hist);
  $('#curve').innerHTML=hist.map((n,i)=>`<div class="bar-wrap"><span class="bar-value">${n}</span><div class="bar"></div><span class="bar-label">${i===7?'7+':i}</span></div>`).join('');
  // Numeric bar heights are set without inline CSS to preserve the strict CSP.
  $$('#curve .bar').forEach((b,i)=>b.style.height=Math.max(2,80*hist[i]/max)+'px');
  const warnings=[];if(total!==100)warnings.push(`Deck contains ${total} cards including commander; expected 100.`);if(unknown)warnings.push(`${unknown} nonland cards need mana metadata. Curve is partial.`);if(!cards.some(c=>c.zone==='commander'))warnings.push('Assign your commander in card details.');
  if(!state.collection.length)warnings.push('Collection not imported: ownership and available copies are unknown.');
  const commanders=cards.filter(c=>c.zone==='commander'&&c.color_identity);if(commanders.length){const colors=new Set(commanders.flatMap(c=>c.color_identity));const off=cards.filter(c=>c.color_identity?.some(x=>!colors.has(x)));if(off.length)warnings.push('Outside commander color identity: '+off.map(c=>c.name).join(', '))}
  $('#warnings').innerHTML=warnings.map(w=>`<div>↳ ${esc(w)}</div>`).join('');
  renderDeck();renderChat();renderProposals();renderMemory();renderCollection();renderHistory();bindWorkspacePlans();
  $('#collection-count').textContent=state.collection.reduce((n,c)=>n+c.qty,0).toLocaleString();$('#memory-count').textContent=state.memories.length;
}
function filterStatus(where,result,query,pinned=false){
 const el=$('#'+where+'-filter-status');el.classList.toggle('filter-error',!!result.error);
 el.textContent=result.error||[result.unknown?result.unknown+' entries have unresolved search data. Resolve card data to include them.':'',pinned?'Commander remains pinned.':''].filter(Boolean).join(' ');
 $('#'+where+'-search').setAttribute('aria-invalid',String(!!result.error));
}
function syntaxKey(where){
 const examples=[['o:draw','Rules text contains draw; ignores reminder text.'],['o:"sacrifice a creature"','Match a rules-text phrase.'],['t:creature -t:artifact','Creature cards excluding artifacts.'],['mv<=3','Mana value at most 3; cmc is an alias.'],['t:creature pow<=3','Creatures with numeric power at most 3.'],['tou>=4','Numeric toughness at least 4.'],['id<=bg','Color identity within black/green, including colorless.'],['id=wbr','Exactly white/black/red identity.'],['c:r','Card colors contain red (distinct from identity).'],['c=0','Colorless cards.'],['r:rare','Rarity; also common, uncommon, mythic.'],['s:blb','The stored printing is from BLB.'],['kw:flying','Saved keyword list contains flying.'],['f:commander','Legal in Commander; legal:commander is an alias.'],['is:mdfc','Modal double-faced cards.'],['!"Deadly Dispute"','Exact card name.'],['(o:draw OR o:mill) mv<=3','Group alternatives, then combine with another condition.'],['role:draw','Forage extra: search assigned role labels.'],['group:"Card Draw"','Forage extra: search a category.'],['qty>=2','Forage extra: owned copies / deck-row quantity.']];
 modal('Filter syntax key',`<p class="modal-note">Forage supports these common Scryfall-style filters locally. Plain words still search names, rules, types and roles. Spaces mean AND; use OR, NOT, a leading minus, quotes and parentheses to refine a search. Use operators without spaces inside a term, such as mv&lt;=3.</p><div class="syntax-table"><table><thead><tr><th>Click to try</th><th>Meaning</th></tr></thead><tbody>${examples.map(([q,note])=>`<tr><td><button class="syntax-example quiet" data-filter-query="${esc(q)}">${esc(q)}</button></td><td>${esc(note)}</td></tr>`).join('')}</tbody></table></div><p class="modal-note">Search uses stored card metadata. Resolve card data for missing fields; unknown values are excluded even under NOT. Set/rarity filters match the stored printing before merging names; a name-only import may resolve to a different edition than your physical copy. The deck’s commander stays pinned.</p><p class="modal-note">This is a supported subset. Prices, Scryfall Tagger tags (otag:), regex and other unlisted fields are unavailable locally. <a href="https://scryfall.com/docs/syntax" target="_blank" rel="noopener noreferrer">Full Scryfall syntax reference ↗</a></p>`);
 $$('[data-filter-query]').forEach(b=>b.onclick=()=>{const input=$('#'+where+'-search');input.value=b.dataset.filterQuery;closeModal();if(where==='collection'){collectionLimit=60;renderCollection()}else renderDeck();input.focus()});
}
function renderDeck(){
 $('#auto-categorize').title='Categorize unassigned cards on '+(zone==='main'?'Mainboard':'Considering');
 const filter=$('#deck-search').value,board=deck().cards.filter(c=>zone==='main'?['main','commander'].includes(c.zone):c.zone==='maybe');
 const result=ForageCards.search(board,filter),visible=new Set(result.matches.map(c=>c.id));
 const cards=board.filter(c=>c.zone==='commander'||visible.has(c.id));
 filterStatus('deck',result,filter,zone==='main'&&board.some(c=>c.zone==='commander'&&!visible.has(c.id)));
 $('#card-count').textContent=cards.reduce((a,c)=>a+c.qty,0)+' cards';
 const arranged=ForageCards.boardGroups(cards,groupBy,sortBy,deck(),zone==='main'),entries=arranged.main;
 const swapPanel=$('#swap-categories');swapPanel.hidden=zone!=='main';swapPanel.className='swap-categories mode-'+cardMode;
 $('#deck-list').className='deck-list card-board mode-'+cardMode;
 const groupMarkup=([g,list],swap=false)=>{
  const pinned=list.length>0&&list.every(c=>c.zone==='commander');
  const heading=pinned?'<span title="Commander position is fixed first">Commander · pinned</span>':(swap||groupBy==='category')?`<button class="category-heading" data-edit-category="${esc(g)}" title="Edit category">${esc(g)} <span class="edit-pencil">✎</span></button>`:esc(g);
  return `<section class="visual-group${pinned?' commander-group':''}" ${pinned?'data-pinned-commander="true"':`data-drop-group="${esc(g)}"`}><div class="group-label">${heading}<span>${list.reduce((n,c)=>n+c.qty,0)}</span></div><div class="group-cards">`+list.map(c=>cardMode==='list'?`<button class="card-row" draggable="true" data-visual-card="${esc(c.id)}" data-card-source="deck"><span class="qty">${c.qty}</span><span class="card-name">${esc(c.name)}</span>${c.protected?'<span class="lock" title="Protected card">◆</span>':''}<span class="card-mv">${c.land?'◇':c.mv??'?'}</span></button>`:ForageCards.tile(c,state.collection)).join('')+'</div></section>';
 };
 $('#deck-list').innerHTML=entries.map(entry=>groupMarkup(entry)).join('')||'<div class="empty">Nothing here yet.<br>Import a list or drop a card.</div>';
 swapPanel.innerHTML=zone==='main'?'<div class="swap-panel-heading">PINNED CATEGORIES</div>'+arranged.swaps.map(entry=>groupMarkup(entry,true)).join(''):'';
 $$('[data-card-mode]').forEach(b=>{b.classList.toggle('selected',b.dataset.cardMode===cardMode);b.setAttribute('aria-pressed',String(b.dataset.cardMode===cardMode))});
 $('#group-cards').value=groupBy;$('#sort-cards').value=sortBy;
 if(cardMode==='stacks')$('#deck-list').innerHTML='<div class="stack-columns">'+$('#deck-list').innerHTML+'</div>';
 bindVisualCards($('#deck-list'));bindVisualCards(swapPanel);
 $$('[data-edit-category]').forEach(b=>b.onclick=()=>categoryDialog(b.dataset.editCategory));
 $$('[data-drop-group]').filter(el=>groupBy==='category'||swapPanel.contains(el)).forEach(el=>{
  el.addEventListener('dragover',e=>{if(e.dataTransfer.types.includes('application/x-forage-card')){e.preventDefault();e.stopPropagation();el.classList.add('category-dragover')}});
  el.addEventListener('dragleave',e=>{if(!el.contains(e.relatedTarget))el.classList.remove('category-dragover')});
  el.addEventListener('drop',e=>{const raw=e.dataTransfer.getData('application/x-forage-card');if(!raw)return;e.preventDefault();e.stopPropagation();el.classList.remove('category-dragover');run(()=>internalDrop(JSON.parse(raw),zone,el.dataset.dropGroup))});
 });
}
function findVisualCard(id,source){return (source==='collection'?state.collection:deck().cards).find(c=>c.id===id)}
function bindVisualCards(container){
 container.querySelectorAll('[data-visual-card]').forEach(button=>{
  const card=findVisualCard(button.dataset.visualCard,button.dataset.cardSource);if(!card)return;
  button.onclick=()=>{hideCardHover();button.dataset.cardSource==='collection'?showCandidate(card):editCard(card.id)};
  button.addEventListener('dragstart',e=>{hideCardHover();e.dataTransfer.effectAllowed='copyMove';e.dataTransfer.setData('application/x-forage-card',JSON.stringify({id:card.id,source:button.dataset.cardSource,deck:state.active}));e.dataTransfer.setData('text/plain',card.name)});
  button.addEventListener('mouseenter',()=>showCardHover(button,card));button.addEventListener('mouseleave',hideCardHover);
  button.addEventListener('focus',()=>showCardHover(button,card));button.addEventListener('blur',hideCardHover);
 });
 container.querySelectorAll('img').forEach(img=>img.addEventListener('error',()=>{img.hidden=true;img.closest('.card-visual')?.classList.add('image-failed')}));
}
function showCardHover(button,card){
 const hover=$('#card-hover'),image=ForageCards.art(card,state.collection);if(!image)return;
 hover.innerHTML=`<img src="${esc(image)}" alt=""><strong>${esc(card.name)}</strong><small>${card.land?'Land':'Mana value '+(card.mv??'?')}${card.protected?' · Protected':''}</small>`;
 hover.hidden=false;const r=button.getBoundingClientRect(),width=Math.min(290,innerWidth-32),height=width*1.397+60;
 let left=r.right+14;if(left+width>innerWidth-12)left=r.left-width-14;
 hover.style.width=width+'px';hover.style.left=Math.max(12,left)+'px';hover.style.top=Math.max(12,Math.min(r.top,innerHeight-height-12))+'px';
}
function hideCardHover(){$('#card-hover').hidden=true}
async function internalDrop(item,destination,category=null){
 if(item.deck!==state.active)throw Error('Switch back to the source deck before moving this card.');
 const c=findVisualCard(item.id,item.source);if(!c)throw Error('This card changed. Refresh and try again.');
 if(item.source==='collection'){
  const newCard={...c};if(category&&category!=='Commander')newCard.group=category;
  await mutate('card',{action:'add',card:newCard,zone:category==='Commander'?'commander':destination});toast('Card added. Ownership quantity was unchanged.');
 }else{
  const payload={id:c.id,action:'edit',zone:category==='Commander'?'commander':destination};
  if(category&&category!=='Commander')payload.group=category;
  await mutate('card',payload);toast('Card moved. Role tags were preserved.');
 }
}
function renderChat(forceLatest=false){
 const body=$('#conversation-body'),deckId=state.active,previousTop=body.scrollTop;
 const followLatest=forceLatest||chatRenderedDeck!==deckId||body.scrollHeight-body.scrollTop-body.clientHeight<=60;
 $('#welcome').hidden=!!deck().chat.length;
 $('#messages').innerHTML=deck().chat.map(m=>`<article class="message ${m.role==='user'?'user':'assistant'}"><div class="message-heading"><div class="message-label">${m.role==='user'?'YOU':'FORAGE · LOCAL AI'}</div>${m.context_trace?`<button class="context-inspect" data-context-message="${m.id}">Context used · ${(m.context_trace.recent_messages||[]).length} messages</button>`:''}</div><div class="message-content">${ForageText.render(m.text)}</div>${m.role==='assistant'&&(m.recommendations||[]).length?`<section class="recommendation-tray" aria-label="Card options" data-rec-message="${esc(m.id)}"><h3>${m.recommendations.every(r=>r.kind==='match')?'Collection matches · not ranked':'Recommended additions'}</h3>${m.recommendations.map(r=>ForageCards.recommendation(r,state.collection,deck().cards,deck().proposals)).join('')}</section>`:''}${m.category_plan_id?workspacePlanMarkup((deck().category_plans||[]).find(p=>p.id===m.category_plan_id)):''}${(m.memory_suggestions||[]).map(s=>`<button class="memory-save" data-save-memory="${s.id}" data-message="${m.id}">Remember: ${esc(s.text)}</button>`).join('')}</article>`).join('');
 $$('[data-rec-action]').forEach(b=>b.onclick=()=>recommendationAction(b));
 $$('.recommendation-art img').forEach(img=>img.onerror=()=>{img.hidden=true;img.closest('.recommendation-art').classList.add('image-failed')});
 $$('[data-context-message]').forEach(b=>b.onclick=()=>showContextUsed(b.dataset.contextMessage));
 $$('[data-save-memory]').forEach(b=>b.onclick=async()=>{const m=deck().chat.find(m=>m.id===b.dataset.message).memory_suggestions.find(s=>s.id===b.dataset.saveMemory);if(!state.memories.some(x=>x.text===m.text)){await mutate('memory',{text:m.text,scope:m.scope});toast('Memory saved.')}else toast('Already remembered.');});
 requestAnimationFrame(()=>{if(state.active!==deckId||!body.clientHeight)return;body.scrollTop=followLatest?body.scrollHeight:previousTop;chatRenderedDeck=deckId;});
}
async function recommendationAction(button){
 const tray=button.closest('[data-rec-message]'),item=button.closest('[data-rec-id]');
 const m=deck().chat.find(m=>m.id===tray.dataset.recMessage),rec=m?.recommendations.find(r=>r.id===item.dataset.recId);
 if(!rec)return;
 const c=rec.card,action=button.dataset.recAction;
 const p=[...deck().proposals].reverse().find(p=>norm(p.add)===norm(c.name)&&p.status==='pending');
 if(action==='inspect'){
  const shown=button.dataset.recSide==='cut'?deck().cards.find(x=>norm(x.name)===norm(p?.cut||'')):c;
  if(shown)modal(shown.name,cardPreview(shown));return;
 }
 if(busy){toast('Wait for the current reply to finish.');return}
 if(action==='find'||action==='different'){
  if($('#message').value.trim()||pendingCard||pendingImage){toast('Send or clear your current draft first.');return}
  const request=`Find one concrete swap to add ${c.name} to my current mainboard. Keep ${c.name} as the addition. ${action==='different'&&p?`Suggest a different cut from ${p.cut}; I have not accepted that swap.`:'Compare my current cards and suggest the best cut.'} Explain the tradeoff and propose the swap.`;
  closeModal();$('#message').value=request;await sendChat();return;
 }
 await run(async()=>{
  button.disabled=true;
  if(action==='accept'&&p){await mutate('proposal',{id:p.id,action:'accept'});toast('Swap accepted. You can undo it from the deck toolbar.');}
  else if(action==='pass'){await mutate('recommendation',{message:m.id,id:rec.id,action:'pass'});toast('Passed. Decision saved to the conversation.');}
  else if(['main','maybe'].includes(action)){
   if(deck().cards.some(x=>norm(x.name)===norm(c.name)&&x.zone===action)){toast('Already on this board.');return}
   await mutate('card',{action:'add',card:c,zone:action});toast('Added to '+(action==='main'?'Mainboard':'Considering')+'.');
  }
 });
}
function available(name,excludeActive=false){const owned=state.collection.filter(c=>norm(c.name)===norm(name)).reduce((n,c)=>n+c.qty,0),assigned=state.decks.filter(d=>!excludeActive||d.id!==state.active).flatMap(d=>d.cards).filter(c=>['main','commander'].includes(c.zone)&&norm(c.name)===norm(name)).reduce((n,c)=>n+c.qty,0);return {owned,assigned,free:Math.max(0,owned-assigned)}}
function renderProposals(){
 const pending=ForageCards.pendingDecisions(deck()),count=pending.recommendations.length+pending.proposals.length+pending.plans.length;
 $('#pending-decisions').textContent='Pending decisions · '+count;
 $('#pending-decisions').classList.toggle('has-pending',count>0);
 if($('#modal').open&&$('#modal-title').textContent==='Pending decisions')showPendingDecisions();
}
function showPendingDecisions(){
 const pending=ForageCards.pendingDecisions(deck());
 const graphics=pending.recommendations.map(({message,rec})=>`<section data-rec-message="${esc(message)}">${ForageCards.recommendation(rec,state.collection,deck().cards,deck().proposals)}</section>`).join('');
 modal('Pending decisions',`<div class="pending-decisions-list">${graphics}<div id="proposals"></div></div>`);
 $$('[data-rec-action]').forEach(b=>b.onclick=()=>recommendationAction(b));
 $$('.recommendation-art img').forEach(img=>img.onerror=()=>{img.hidden=true;img.closest('.recommendation-art').classList.add('image-failed')});
 renderPendingProposals(pending.proposals,!!graphics);bindWorkspacePlans();
}
function renderPendingProposals(list,hasGraphics=false){$('#proposals').innerHTML=list.map(p=>{const a=available(p.add,true);return `<article class="proposal-card"><div class="proposal-tag">PROPOSED SWAP</div><div class="swap-line"><span>＋</span>${esc(p.add)}</div><div class="swap-line cut"><span>−</span>${esc(p.cut)}</div><p>${esc(p.reason)}</p><div class="availability">${state.collection.length?`${a.owned} owned · ${a.free} available outside other decks`:'Ownership unknown · import your collection'}</div><div class="proposal-actions"><button data-accept="${p.id}" class="button primary">Accept swap ↗</button><button data-reject="${p.id}" class="button secondary">Skip</button></div></article>`}).join('')||(!hasGraphics?'<div class="empty">No pending decisions. New suggestions will appear in your conversation.</div>':'');
 const pendingPlans=(deck().category_plans||[]).filter(p=>p.status==='pending');if(pendingPlans.length&&!list.length)$('#proposals').innerHTML='';if(pendingPlans.length)$('#proposals').insertAdjacentHTML('beforeend',pendingPlans.map(p=>'<article class="proposal-card">'+workspacePlanMarkup(p)+'</article>').join(''));
 $$('[data-accept]').forEach(b=>b.onclick=()=>run(async()=>{b.disabled=true;await mutate('proposal',{id:b.dataset.accept,action:'accept'});toast('Swap accepted. Saved to decision history.');}));
 $$('[data-reject]').forEach(b=>b.onclick=()=>{modal('Skip this suggestion',`<p class="modal-note">An optional reason helps future recommendations. A blank reason records this decision without inventing a preference.</p><label class="field">Your reason<textarea id="reject-reason" placeholder="For example: I need this independent Food producer."></textarea></label><button id="confirm-reject" class="button primary">Skip suggestion</button>`);$('#confirm-reject').onclick=()=>run(async()=>{await mutate('proposal',{id:b.dataset.reject,action:'reject',feedback:$('#reject-reason').value});closeModal();toast('Decision saved.');});});
}
function renderMemory(){const entries=state.memories.filter(m=>m.scope==='global'||m.deck===state.active);$('#memories').innerHTML=entries.map(m=>`<article class="memory-card"><div class="eyebrow">${m.scope==='global'?'ALL DECKS':'THIS DECK'}</div><p>${esc(m.text)}</p><button data-memory-edit="${m.id}" class="quiet">Edit</button><button data-memory-delete="${m.id}" class="quiet">Forget</button></article>`).join('');
 $$('[data-memory-edit]').forEach(b=>b.onclick=()=>memoryDialog(state.memories.find(m=>m.id===b.dataset.memoryEdit)));
 $$('[data-memory-delete]').forEach(b=>b.onclick=()=>run(async()=>{await mutate('memory',{id:b.dataset.memoryDelete,action:'delete'});toast('Memory removed.')}));
 $('#rules').innerHTML=state.rules.map(r=>`<article class="rule-note"><strong>${esc(r.title)}</strong><p>${esc(r.text)}</p><a href="${esc(safeUrl(r.source))}" target="_blank" rel="noopener noreferrer">Reference ↗</a><p class="muted small">${esc(r.status)}</p></article>`).join('');
}
function renderCollection(){
 const q=$('#collection-search').value;$('#collection-source').textContent=state.collection_source;
 const result=ForageCards.search(state.collection,q);filterStatus('collection',result,q);
 const counts=ForageCards.inventory(state.collection,state.decks||[]),stock=name=>counts.get(norm(name))||{owned:0,assigned:0,free:0};
 const merged=new Map();for(const c of result.matches){const k=norm(c.name);if(!merged.has(k))merged.set(k,{...c});else merged.get(k).qty+=c.qty}
 const matches=ForageCards.sortCollection([...merged.values()],collectionSort,collectionDirection,counts);
 $('#collection-sort').value=collectionSort;$('#collection-direction').value=collectionDirection;
 const cards=matches.slice(0,collectionLimit);
 $('#collection-results').textContent=`${matches.length.toLocaleString()} unique matches · showing ${cards.length}`;
 $('#collection-grid').hidden=collectionMode!=='grid';$('#collection-table-wrap').hidden=collectionMode!=='list';
 $('#collection-grid').innerHTML=cards.map(c=>ForageCards.tile(c,state.collection,'collection',stock(c.name))).join('')||'<div class="empty">Import your collection, or try a different search.</div>';
 // For duplicate printing rows, the visual tile carries the first record id but shows the summed quantity.
 bindVisualCards($('#collection-grid'));
 $('#collection-table').innerHTML=cards.map(c=>{const a=stock(c.name);return `<tr><td>${esc(c.name)}</td><td>${a.owned}</td><td>${a.assigned}</td><td>${a.free}</td></tr>`}).join('')||'<tr><td colspan="4" class="empty">No matching cards.</td></tr>';
 $$('[data-collection-mode]').forEach(b=>b.classList.toggle('selected',b.dataset.collectionMode===collectionMode));
 $('#collection-more').hidden=matches.length<=collectionLimit;
}
function renderHistory(){const proposals=deck().proposals.filter(p=>p.status!=='pending');$('#history-list').innerHTML=[...deck().history].reverse().map(h=>`<div class="history-item">${esc(h.summary)}<small>Deck change · undo available in reverse order</small></div>`).join('')+proposals.map(p=>`<div class="history-item">${p.status==='accepted'?'✓ ACCEPTED':'↷ SKIPPED'} · ${esc(p.cut)} → ${esc(p.add)}<small>${esc(p.feedback||p.reason)}</small></div>`).join('')||'<div class="empty">Your decisions will appear here.</div>'}
function changeView(next){hideCardHover();view=next;$$('.view').forEach(el=>el.hidden=el.id!==next);$$('[data-view]').forEach(b=>b.classList.toggle('active',b.dataset.view===next));if(next==='workbench')renderChat(true)}
async function run(fn){try{await fn()}catch(e){toast(e.message);$$('button:disabled').forEach(b=>b.disabled=false)}}
function memoryDialog(m={}){modal(m.id?'Edit memory':'Add a memory',`<label class="field">Applies to<select id="memory-scope"><option value="deck" ${m.scope!=='global'?'selected':''}>This deck</option><option value="global" ${m.scope==='global'?'selected':''}>All decks</option></select></label><label class="field">What should Forage remember?<textarea id="memory-text" rows="4">${esc(m.text||'')}</textarea></label><button id="save-memory" class="button primary">Save memory</button>`);$('#save-memory').onclick=()=>run(async()=>{await mutate('memory',{id:m.id,text:$('#memory-text').value,scope:$('#memory-scope').value});closeModal();toast('Memory saved.');});}
function importDialog(target='deck'){modal(target==='collection'?'Import your collection':'Import a deck',`<p class="modal-note">Paste an Archidekt text export, or choose a CSV/TXT file. Deck imports replace the active list and can be undone. Collection imports replace owned quantities; deck assignments come from imported decks.</p><label class="field">Import into<select id="import-target"><option value="deck" ${target==='deck'?'selected':''}>Active deck</option><option value="collection" ${target==='collection'?'selected':''}>Collection</option></select></label><label class="field">Choose export file<input id="import-file" type="file" accept=".csv,.txt,.tsv"></label><label class="field">Or paste a list<textarea id="import-text" rows="9" placeholder="1 Ygra, Eater of All [Commander]&#10;1 Arcbound Ravager [Sacrifice]&#10;11 Forest [Land]"></textarea></label><p class="modal-note">CSV: Name / Card Name and Quantity / Qty columns. Use category Commander, Mainboard, or Maybeboard to identify boards. Sideboard imports go to Considering.</p><button id="confirm-import" class="button primary">Import list</button>`);$('#import-file').onchange=async e=>{if(e.target.files[0])$('#import-text').value=await e.target.files[0].text()};$('#confirm-import').onclick=()=>run(async()=>{const r=await mutate('import',{text:$('#import-text').value,target:$('#import-target').value});closeModal();toast(r.warnings?.length?'Imported with warnings: '+r.warnings.join(' '):'Import complete.');});}
function cardPreview(c,controls=''){const a=available(c.name,true),previewImage=ForageCards.art(c,state.collection);return `<div class="card-detail"><div class="card-detail-art">${previewImage?`<img src="${esc(previewImage)}" alt="${esc(c.name)}">`:'<div class="empty">Card image not loaded</div>'}</div><div class="card-detail-controls"><div class="eyebrow green">${esc(c.mana_cost||'')} · MV ${c.mv??'?'}</div><p>${esc(c.type_line||'Metadata not resolved')}</p><div class="oracle">${esc(c.oracle_text||'Resolve card data to load current text.')}</div><p class="modal-note">${state.collection.length?`${a.owned} owned · ${a.free} available outside other decks`:'Collection not imported; ownership unknown.'}</p>${c.scryfall_uri?`<a href="${esc(safeUrl(c.scryfall_uri))}" target="_blank" rel="noopener noreferrer">Scryfall ↗</a>`:''}${controls}</div></div>`}
function editCard(id){const c=deck().cards.find(c=>c.id===id);modal(c.name,cardPreview(c,`<div class="field-row"><label class="field">Board<select id="edit-zone"><option value="main" ${c.zone==='main'?'selected':''}>Mainboard</option><option value="commander" ${c.zone==='commander'?'selected':''}>Commander</option><option value="maybe" ${c.zone==='maybe'?'selected':''}>Considering</option></select></label><label class="field">Category<input id="edit-group" value="${esc(c.group)}"></label></div><div class="field-row"><label class="field">Quantity<input id="edit-qty" type="number" min="1" value="${c.qty}"></label><label class="field">Mana value<input id="edit-mv" type="number" min="0" step=".5" value="${c.mv??''}"></label></div><label class="field">Roles (one per line)<textarea id="edit-roles" rows="3">${esc((c.roles||[]).join('\n'))}</textarea></label><label class="field"><input type="checkbox" id="edit-protected" ${c.protected?'checked':''}>Protect this card from suggested cuts</label><label class="field"><input type="checkbox" id="edit-land" ${c.land?'checked':''}>Land face (exclude from spell curve)</label><label class="field"><input type="checkbox" id="edit-mdfc" ${c.mdfc?'checked':''}>MDFC with a land face</label><div class="modal-actions"><button id="save-card" class="button primary">Save changes</button><button id="resolve-card" class="button secondary">Resolve Scryfall data</button><button id="remove-card" class="quiet">Remove card</button></div><p class="modal-note">${esc(c.meta_source)}</p>`));
 $('#save-card').onclick=()=>run(async()=>{await mutate('card',{id,action:'edit',zone:$('#edit-zone').value,group:$('#edit-group').value,qty:Number($('#edit-qty').value),mv:$('#edit-mv').value===''?null:Number($('#edit-mv').value),roles:$('#edit-roles').value.split('\n').map(s=>s.trim()).filter(Boolean),protected:$('#edit-protected').checked,land:$('#edit-land').checked,mdfc:$('#edit-mdfc').checked});closeModal();toast('Card updated.');});
 $('#remove-card').onclick=()=>run(async()=>{await mutate('card',{id,action:'remove'});closeModal();toast('Card removed.');});
 $('#resolve-card').onclick=()=>run(async()=>{const r=await api('lookup?name='+encodeURIComponent(c.name));await mutate('card',{id,action:'enrich',card:r.card});editCard(id)});
}
function showCandidate(c,target='maybe'){modal('Confirm recognized card',cardPreview(c,`<p class="modal-note">Check the card identity before adding it. This does not mark a physical copy as owned.</p><div class="modal-actions"><button id="candidate-chat" class="button primary">Discuss this card</button><button id="candidate-maybe" class="button secondary">Add to Considering</button><button id="candidate-main" class="button secondary">Add to Mainboard</button></div>`));$('#candidate-chat').onclick=()=>{pendingCard=c;renderAttachment();closeModal();$('#message').focus()};for(const [id,zone] of [['candidate-maybe','maybe'],['candidate-main','main']])$('#'+id).onclick=()=>run(async()=>{await mutate('card',{action:'add',card:c,zone});closeModal();toast('Added to '+(zone==='main'?'Mainboard':'Considering')+'.');});}
function lookupDialog(){modal('Find a card',`<form id="lookup-form"><label class="field">Card name<input id="lookup-name" placeholder="For example: Experimental Confectioner" autofocus></label><button class="button primary">Look up card</button></form><p class="modal-note">Looks up card text and an image on Scryfall. You can also paste a Scryfall or EDHREC card link.</p><div id="lookup-error" class="error"></div>`);$('#lookup-form').onsubmit=async e=>{e.preventDefault();$('#lookup-error').textContent='Looking up…';try{const val=$('#lookup-name').value;const r=val.includes('://')?await api('drop',{text:val}):await api('lookup?name='+encodeURIComponent(val));showCandidate(r.card)}catch(e){$('#lookup-error').textContent=e.message}};$('#lookup-name').focus();}
function renderAttachment(){$('#attachment').hidden=!pendingCard&&!pendingImage;$('#attachment').innerHTML=(pendingCard?esc(pendingCard.name):'Image attached · requires a vision-capable model')+'<button id="clear-attachment" class="quiet">×</button>';$('#clear-attachment').onclick=()=>{pendingCard=null;pendingImage=null;renderAttachment()}}
async function imageFile(file){if(!['image/png','image/jpeg','image/webp'].includes(file.type))throw Error('Use PNG, JPEG or WebP.');if(file.size>6*1024*1024)throw Error('Use an image smaller than 6 MB.');pendingImage=await new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result);r.onerror=reject;r.readAsDataURL(file)});pendingCard=null;renderAttachment();modal('Identify this image',`<p class="modal-note">A vision-capable local model can read the card name. You can also enter the name manually. Nothing is added until you confirm the result.</p><div class="modal-actions"><button id="vision-identify" class="button primary">Identify with local AI</button><button id="vision-manual" class="button secondary">Enter card name</button><button id="vision-chat" class="quiet">Discuss image directly</button></div><div id="vision-error" class="error"></div>`);$('#vision-identify').onclick=async()=>{$('#vision-error').textContent='Reading image locally…';try{const r=await api('vision',{image:pendingImage});pendingImage=null;renderAttachment();showCandidate(r.card)}catch(e){$('#vision-error').textContent=e.message}};$('#vision-manual').onclick=()=>{pendingImage=null;renderAttachment();lookupDialog()};$('#vision-chat').onclick=()=>{closeModal();$('#message').focus()};}
async function handleDrop(e){e.preventDefault();e.stopPropagation();e.currentTarget.classList.remove('dragover');const dt=e.dataTransfer;try{const own=dt.getData('application/x-forage-card');if(own){const item=JSON.parse(own);const c=findVisualCard(item.id,item.source);if(!c)throw Error('Card no longer available.');if(e.currentTarget.id==='chat-form'){pendingCard=c;pendingImage=null;renderAttachment();$('#message').focus()}else await internalDrop(item,zone);return}const html=dt.getData('text/html'),text=dt.getData('text/uri-list')||dt.getData('text/plain');if(html||text){try{const r=await api('drop',{html,text});showCandidate(r.card);return}catch(err){if(!dt.files.length)throw err}}if(dt.files.length){const file=dt.files[0];if(/\.(csv|txt|tsv)$/i.test(file.name)){importDialog();$('#import-text').value=await file.text()}else await imageFile(file)}else toast('Drop a card image, card link, or deck export.')}catch(e){toast(e.message)}}
function bindDrop(el){el.addEventListener('dragover',e=>{e.preventDefault();el.classList.add('dragover')});el.addEventListener('dragleave',()=>el.classList.remove('dragover'));el.addEventListener('drop',handleDrop)}
async function sendChat(e){e?.preventDefault();if(busy)return;let message=$('#message').value.trim();if(!message&&!pendingCard&&!pendingImage)return;if(pendingCard)message+=(message?'\n\n':'')+'Card under discussion (confirmed lookup): '+JSON.stringify({name:pendingCard.name,mv:pendingCard.mv,oracle_text:pendingCard.oracle_text});if(!message)message='Please analyze this card image for the current deck. State any uncertainty about its identity.';
 busy=true;$('#send').disabled=true;$('#chat-error').textContent='Thinking locally… This can take a while for a large model.';
 try{await api('chat',{deck:state.active,message,image:pendingImage});$('#message').value='';pendingCard=null;pendingImage=null;renderAttachment();await refresh();$('#chat-error').textContent='';aiConnected=true;updateAIStatus()}catch(e){$('#chat-error').textContent=e.message}finally{busy=false;$('#send').disabled=false}}
function updateAIStatus(){$('#ai-status').textContent=aiConnected?'● Local AI connected':'○ Connect local AI';$('#ai-status').classList.toggle('connected',aiConnected)}
async function probeModels(){const r=await api('models');aiConnected=!!r.models.length;updateAIStatus();return r.models}
function settingsDialog(){const s=state.settings;modal('Local AI & settings',`<p class="modal-note">Run LM Studio on this PC, load a model, and start its local server. Forage sends your active deck, applicable memories, recent conversation, excerpts of earlier requests, and relevant local collection search results to that loopback server. No cloud AI endpoint is accepted.</p><label class="field">Local API address<input id="lm-url" value="${esc(s.lm_url)}"></label><label class="field">Model identifier<input id="lm-model" value="${esc(s.model)}" placeholder="Choose a model after checking connection" list="model-options"><datalist id="model-options"></datalist></label><button id="check-ai" class="button secondary">Check connection & list models</button><div id="settings-status" class="modal-note"></div><label class="field"><input id="collection-only" type="checkbox" ${s.collection_only?'checked':''}>Require an available owned copy when accepting a swap</label><p class="modal-note">Turn this off only for deliberate wishlist changes. Collection assignments only cover decks you have imported. AI-generated advice and role matches still need your review.</p><p><button id="updates-open" class="button secondary">Application updates</button> <button id="desktop-open" class="button secondary">Windows tray & startup</button></p><div class="modal-actions"><button id="save-settings" class="button primary">Save settings</button><label class="button secondary">Restore backup<input id="restore-file" type="file" accept=".json" hidden></label></div><p class="modal-note">Backups include your decks, chats, and memory. Before restoring, Forage saves an additional copy of the current workspace in its data folder.</p>`);
 $('#updates-open').onclick=()=>run(updatesDialog);
 $('#desktop-open').onclick=()=>run(desktopDialog);
 $('#check-ai').onclick=async()=>{try{await mutate('settings',{lm_url:$('#lm-url').value,model:$('#lm-model').value,collection_only:$('#collection-only').checked});const models=await probeModels();$('#model-options').innerHTML=models.map(m=>`<option value="${esc(m.id)}"></option>`).join('');if(models.length&&!$('#lm-model').value)$('#lm-model').value=models[0].id;$('#settings-status').textContent=models.length?models.length+' model(s) found. Select the intended chat model and save.':'Server reached; no models found. Load a model in LM Studio.';}catch(e){$('#settings-status').textContent=e.message;aiConnected=false;updateAIStatus()}};
 $('#save-settings').onclick=()=>run(async()=>{await mutate('settings',{lm_url:$('#lm-url').value,model:$('#lm-model').value,collection_only:$('#collection-only').checked});closeModal();toast('Settings saved.');});
 $('#restore-file').onchange=()=>run(async()=>{const f=$('#restore-file').files[0];if(!f)return;const data=JSON.parse(await f.text());if(!confirm('Replace the current workspace with this backup? A copy of the current data will be saved first.'))return;await mutate('restore',{state:data});closeModal();toast('Backup restored.');});
}
function download(name,text,type='text/plain'){const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([text],{type}));a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)}
async function enrichDeck(){const button=$('#enrich');button.disabled=true;let count=0,failed=[];const id=state.active;const cards=[...deck().cards];try{for(const c of cards){$('#resolve-status').textContent=`${++count}/${cards.length}`;try{const r=await api('lookup?name='+encodeURIComponent(c.name));await api('card',{deck:id,id:c.id,action:'enrich',card:r.card})}catch(e){failed.push(c.name);if(failed.length>=3&&count<=3)break}}await refresh();toast(failed.length?'Some cards were unresolved: '+failed.join(', '):'Card data resolved. Editable role tags were preserved.')}finally{button.disabled=false;$('#resolve-status').textContent=''}}
async function sample(){const r=await api('sample',{deck:state.active});modal('Land-drop sample',`<p class="modal-note">${esc(r.assumptions)}</p><p class="notice">${r.opening_two_to_four}% of opening hands had 2–4 potential lands.</p><table><thead><tr><th>Through turn</th><th>Hit every land drop</th></tr></thead><tbody>${Object.entries(r.land_drop).map(([t,p])=>`<tr><td>${t}</td><td>${p}%</td></tr>`).join('')}</tbody></table><p class="modal-note">${r.runs.toLocaleString()} seeded samples · seed ${r.seed}. This does not estimate whether you can cast Ygra on time: colored sources, tapped lands, ramp, and draw engines are excluded.</p>`)}
$('#modal-close').onclick=closeModal;$('#modal').addEventListener('click',e=>{if(e.target===$('#modal')){const r=$('#modal').getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)closeModal()}});
$$('[data-view]').forEach(b=>b.onclick=()=>changeView(b.dataset.view));
$('#deck-select').onchange=e=>run(()=>mutate('active',{id:e.target.value}));
$('#new-deck').onclick=()=>{modal('Start another deck','<label class="field">Deck name<input id="new-name" placeholder="Terra · Reanimator"></label><button id="create-deck" class="button primary">Create deck</button>');$('#create-deck').onclick=()=>run(async()=>{await mutate('new-deck',{name:$('#new-name').value});closeModal();changeView('workbench')})};
$('#deck-syntax-key').onclick=()=>syntaxKey('deck');$('#collection-syntax-key').onclick=()=>syntaxKey('collection');
$('#deck-search').oninput=renderDeck;$('#collection-search').oninput=()=>{collectionLimit=60;renderCollection()};
$$('[data-zone]').forEach(b=>b.onclick=()=>{zone=b.dataset.zone;$$('[data-zone]').forEach(x=>x.classList.toggle('active',x===b));renderDeck()});
$('#pending-decisions').onclick=showPendingDecisions;
$('#settings-open').onclick=settingsDialog;$('#setup-link').onclick=settingsDialog;$('#ai-status').onclick=settingsDialog;
$('#import-open').onclick=()=>importDialog(view==='collection'?'collection':'deck');$('#collection-import').onclick=()=>importDialog('collection');$('#lookup-open').onclick=lookupDialog;$('#deck-drop').onclick=lookupDialog;
$('#add-memory').onclick=()=>memoryDialog();$('#enrich').onclick=()=>run(enrichDeck);
for(const id of ['undo','history-undo'])$('#'+id).onclick=()=>run(async()=>{await mutate('undo',{});toast('Last deck change undone.');});
$('#backup').onclick=()=>download('forage-backup-'+new Date().toISOString().slice(0,10)+'.json',JSON.stringify(state,null,2),'application/json');
$('#export').onclick=()=>download('forage-deck.txt',deck().cards.map(c=>`${c.qty} ${c.name} [${c.zone==='commander'?'Commander':c.zone==='maybe'?'Maybeboard':c.group==='Land'?'Land':'Mainboard'}]`).join('\n'));
$('#chat-form').onsubmit=sendChat;$('#message').onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendChat()}};
$$('[data-prompt]').forEach(b=>b.onclick=()=>{$('#message').value=b.dataset.prompt;$('#message').focus()});$('#sample').onclick=()=>run(sample);
bindDrop($('#deck-drop'));bindDrop($('#chat-form'));
$('#image-upload').onchange=e=>run(async()=>{if(e.target.files[0])await imageFile(e.target.files[0]);e.target.value=''});
$('#message').addEventListener('paste',e=>{const item=[...e.clipboardData.items].find(i=>i.type.startsWith('image/'));if(item){e.preventDefault();run(()=>imageFile(item.getAsFile()))}});
window.addEventListener('dragover',e=>e.preventDefault());window.addEventListener('drop',e=>e.preventDefault());
refresh().then(()=>{probeModels().catch(()=>updateAIStatus())}).catch(e=>toast(e.message));

$('#collection-enrich').onclick=()=>run(async()=>{
 const button=$('#collection-enrich');button.disabled=true;
 const unique=new Map();for(const c of state.collection)if(!c.scryfall_id||!Object.hasOwn(c,'power'))unique.set(norm(c.name),c.name);
 const names=[...unique.values()];let done=0,missing=[];
 if(!names.length){toast(state.collection.length?'Collection data is already resolved.':'Import your collection first.');button.disabled=false;return}
 try{for(let i=0;i<names.length;i+=75){button.textContent=`Resolving ${done}/${names.length}…`;const r=await api('collection-enrich',{deck:state.active,names:names.slice(i,i+75)});done+=names.slice(i,i+75).length;missing.push(...r.not_found)}await refresh();toast(`Collection resolved. ${missing.length} unresolved name(s).`)}finally{button.disabled=false;button.textContent='Resolve card data'}
});

// Visual deck controls. Persist presentation locally; they never alter the deck itself.
$$('[data-card-mode]').forEach(b=>b.onclick=()=>{cardMode=b.dataset.cardMode;uiSave('cardMode',cardMode);renderDeck()});
$('#group-cards').onchange=e=>{groupBy=e.target.value;uiSave('groupBy',groupBy);renderDeck()};
$('#sort-cards').onchange=e=>{sortBy=e.target.value;uiSave('sortBy',sortBy);renderDeck()};
const savedSize=Math.max(145,Math.min(255,Number(uiRead('cardSize','175'))||175));
$('#card-size').value=savedSize;document.documentElement.style.setProperty('--card-width',savedSize+'px');
$('#card-size').oninput=e=>{document.documentElement.style.setProperty('--card-width',e.target.value+'px');uiSave('cardSize',e.target.value)};
$('#focus-deck').onclick=()=>{deckExpanded=!deckExpanded;$('.workspace').classList.toggle('deck-expanded',deckExpanded);$('#focus-deck').textContent=deckExpanded?'Show conversation ↙':'Expand deck ↗';$('#focus-deck').setAttribute('aria-pressed',String(deckExpanded));hideCardHover();if(!deckExpanded)renderChat(true)};
$$('[data-collection-mode]').forEach(b=>b.onclick=()=>{collectionMode=b.dataset.collectionMode;uiSave('collectionMode',collectionMode);renderCollection()});
$('#collection-sort').onchange=e=>{collectionSort=e.target.value;uiSave('collectionSort',collectionSort);collectionLimit=60;renderCollection()};
$('#collection-direction').onchange=e=>{collectionDirection=e.target.value;uiSave('collectionDirection',collectionDirection);collectionLimit=60;renderCollection()};
$('#collection-more').onclick=()=>{collectionLimit+=60;renderCollection()};
$$('[data-zone]').forEach(tab=>{tab.addEventListener('dragover',e=>{if(e.dataTransfer.types.includes('application/x-forage-card')){e.preventDefault();tab.classList.add('dragover')}});tab.addEventListener('dragleave',()=>tab.classList.remove('dragover'));tab.addEventListener('drop',e=>{const raw=e.dataTransfer.getData('application/x-forage-card');if(!raw)return;e.preventDefault();e.stopPropagation();tab.classList.remove('dragover');run(()=>internalDrop(JSON.parse(raw),tab.dataset.zone))})});
$('#deck-list').addEventListener('scroll',hideCardHover);window.addEventListener('resize',hideCardHover);window.addEventListener('scroll',hideCardHover,true);

function categoryDialog(name){
 const pinned=Object.values(ForageCards.swapCategoryNames(deck())).includes(name);
 const cards=deck().cards.filter(c=>(c.group||(c.zone==='commander'?'Commander':'Uncategorized'))===name).sort((a,b)=>a.name.localeCompare(b.name));
 modal('Edit category',`<p class="modal-note">Categories span both boards. Selected entries include all copies shown. Removing cards changes this deck only; Undo is available.</p><label class="field">Category name<input id="category-name" maxlength="80" value="${esc(name)}"></label><div class="modal-actions"><button id="category-rename" class="button primary">Save name</button><button id="category-delete" class="button secondary" ${cards.length||pinned?'disabled':''} title="${pinned?'Swap categories remain pinned':''}">Remove empty category</button></div><h3 class="category-subtitle">Select cards in this category</h3><label class="category-selection"><input type="checkbox" id="category-select-all" ${cards.length?'':'disabled'}> Select all <span id="category-selection-count" aria-live="polite"></span></label><div class="category-card-checks">${cards.map(c=>`<label><input type="checkbox" name="category-card" value="${esc(c.id)}"><span>${esc(c.name)} ×${c.qty} <small class="muted">· ${c.zone==='maybe'?'Considering':c.zone==='commander'?'Commander':'Mainboard'}${c.protected?' · Protected':''}</small></span></label>`).join('')||'<p class="muted">This category is empty. Drag a card here to add it.</p>'}</div><label class="field">Move selected cards to<input id="category-target" list="category-options" placeholder="Choose or create a category"><datalist id="category-options">${allCategoryNames().filter(n=>n!==name).map(n=>`<option value="${esc(n)}"></option>`).join('')}</datalist></label><div class="modal-actions"><button id="category-move" class="button secondary" disabled>Move selected cards</button><button id="category-remove" class="button secondary" disabled>Remove selected cards</button></div><p id="category-selection-note" class="muted small" aria-live="polite"></p>`);
 const selected=()=>{const ids=new Set($$('input[name="category-card"]:checked').map(c=>c.value));return cards.filter(c=>ids.has(c.id))};
 const syncSelection=()=>{const chosen=selected(),all=$('#category-select-all');all.checked=cards.length>0&&chosen.length===cards.length;all.indeterminate=chosen.length>0&&chosen.length<cards.length;$('#category-selection-count').textContent=`(${chosen.length} of ${cards.length} selected)`;$('#category-move').disabled=!chosen.length;const blocked=chosen.some(c=>c.protected||c.zone==='commander');$('#category-remove').disabled=!chosen.length||blocked;$('#category-selection-note').textContent=blocked?'Unselect protected cards and commanders before removing cards.':''};
 $('#category-select-all').onchange=e=>{$$('input[name="category-card"]').forEach(c=>c.checked=e.target.checked);syncSelection()};
 $$('input[name="category-card"]').forEach(c=>c.onchange=syncSelection);syncSelection();
 $('#category-rename').onclick=()=>run(async()=>{const to=$('#category-name').value.trim();if(to===name){closeModal();return}await mutate('category',{changes:[{action:'rename',from:name,to}]});closeModal();toast('Category renamed. Undo is available.');});
 $('#category-delete').onclick=()=>run(async()=>{await mutate('category',{changes:[{action:'delete',from:name}]});closeModal();toast('Empty category removed.');});
 $('#category-move').onclick=()=>run(async()=>{await mutate('category',{changes:[{action:'move',cards:[...new Set(selected().map(c=>c.name))],ids:selected().map(c=>c.id),to:$('#category-target').value}]});closeModal();toast('Cards moved. Role tags were preserved.');});
 $('#category-remove').onclick=()=>run(async()=>{const chosen=selected();if(!chosen.length)return;$('#category-remove').disabled=true;await mutate('cards-remove',{ids:chosen.map(c=>c.id),category:name});closeModal();toast('Selected cards removed from this deck. Undo is available.');});
}
function allCategoryNames(){return [...new Set([...Object.values(ForageCards.swapCategoryNames(deck())),...(deck().categories||[]),...deck().cards.map(c=>c.group||(c.zone==='commander'?'Commander':'Uncategorized'))])].sort()}
function workspacePlanMarkup(plan){
 if(!plan)return '';
 const lines=(plan.changes||[]).map(c=>c.action==='move'?`Move ${c.cards.join(', ')} → ${c.to}`:c.action==='create'?`Create category: ${c.to}`:c.action==='delete'?`Remove empty category: ${c.from}`:`${c.action==='merge'?'Merge':'Rename'} ${c.from} → ${c.to}`);
 const labels={roles:'Roles',protected:'Protected',zone:'Board',group:'Category',qty:'Quantity',card_mode:'Card view',group_by:'Group by',sort_by:'Sort',card_size:'Card size',deck_expanded:'Expanded deck'};
 for(const c of plan.workspace_changes||[]){if(c.action==='rename_deck')lines.push('Rename deck → '+c.name);else lines.push((c.action==='set_card'?c.card+': ':'View: ')+Object.entries(c.fields).map(([k,v])=>(labels[k]||k)+' → '+(Array.isArray(v)?v.join(', '):v===true?'Yes':v===false?'No':v==='maybe'?'Considering':v==='main'?'Mainboard':v)).join('; '))}
 return `<div class="workspace-plan"><div class="eyebrow green">${plan.status==='pending'?'REVIEW WORKSPACE CHANGES':plan.status==='accepted'?'APPLIED':'SKIPPED'}</div><ul>${lines.map(l=>'<li>'+esc(l)+'</li>').join('')}</ul>${plan.status==='pending'?`<div class="modal-actions"><button class="button primary" data-apply-plan="${plan.id}">Apply changes</button><button class="button secondary" data-skip-plan="${plan.id}">Skip</button></div>`:'<p class="muted small">Decision saved. Applied deck edits can be undone.</p>'}</div>`;
}
function bindWorkspacePlans(){
 $$('[data-apply-plan]').forEach(b=>b.onclick=()=>run(async()=>{await mutate('category',{plan_id:b.dataset.applyPlan});toast('Workspace changes applied. Undo is available.');}));
 $$('[data-skip-plan]').forEach(b=>b.onclick=()=>run(async()=>{await mutate('category',{plan_id:b.dataset.skipPlan,action:'reject'});toast('Plan skipped.');}));
}
function syncViewSettings(){
 const v=deck().view_settings||{};
 cardMode=v.card_mode||uiRead('cardMode','stacks');groupBy=v.group_by||uiRead('groupBy','category');sortBy=v.sort_by||uiRead('sortBy','name');
 const size=v.card_size||Math.max(145,Math.min(255,Number(uiRead('cardSize','175'))||175));$('#card-size').value=size;document.documentElement.style.setProperty('--card-width',size+'px');
 deckExpanded=typeof v.deck_expanded==='boolean'?v.deck_expanded:false;
 $('.workspace').classList.toggle('deck-expanded',deckExpanded);$('#focus-deck').textContent=deckExpanded?'Show conversation ↙':'Expand deck ↗';$('#focus-deck').setAttribute('aria-pressed',String(deckExpanded));
}
function persistView(fields){run(()=>mutate('view',{settings:fields}))}
$('#auto-categorize').onclick=()=>run(async()=>{
 const button=$('#auto-categorize');if(button.disabled)return;const label=button.textContent,board=zone;button.disabled=true;button.textContent='Resolving & categorizing…';
 try{
  const result=await mutate('auto-categorize',{zone:board,resolve:true});groupBy='category';await mutate('view',{settings:{group_by:'category'}});
  toast(result.categorized+' cards categorized. Custom categories kept.'+(result.metadata_resolved?' Card data resolved for '+result.metadata_resolved+' names.':'')+(result.unresolved?' '+result.unresolved+' remain uncategorized.':'')+(result.metadata_fetch_failed?' Card data could not be retrieved; check your connection and retry.':'')+(result.undo_available?' Undo is available.':''));
 }finally{button.disabled=false;button.textContent=label}
});
$('#new-category').onclick=()=>{modal('New category','<label class="field">Category name<input id="create-category-name" maxlength="80" placeholder="For example: Free sacrifice outlets"></label><button id="create-category" class="button primary">Create category</button>');$('#create-category').onclick=()=>run(async()=>{await mutate('category',{changes:[{action:'create',to:$('#create-category-name').value}]});groupBy='category';closeModal();persistView({group_by:'category'});toast('Category created. Drag cards into it.');});};
$('#deck-name').onclick=()=>{modal('Rename deck',`<label class="field">Deck name<input id="rename-deck-name" value="${esc(deck().name)}" maxlength="80"></label><button id="rename-deck-save" class="button primary">Save name</button>`);$('#rename-deck-save').onclick=()=>run(async()=>{await mutate('category',{changes:[],workspace_changes:[{action:'rename_deck',name:$('#rename-deck-name').value}]});closeModal();toast('Deck renamed.');});};
$('#deck-name').onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();$('#deck-name').click()}};
// Mirror the existing view controls into saved per-deck settings, making them available to the AI.
$$('[data-card-mode]').forEach(b=>b.addEventListener('click',()=>persistView({card_mode:b.dataset.cardMode})));
$('#group-cards').addEventListener('change',e=>persistView({group_by:e.target.value}));
$('#sort-cards').addEventListener('change',e=>persistView({sort_by:e.target.value}));
$('#card-size').addEventListener('change',e=>persistView({card_size:Number(e.target.value)}));
$('#focus-deck').addEventListener('click',()=>persistView({deck_expanded:deckExpanded}));

function showContextUsed(id){
 const msg=deck().chat.find(m=>m.id===id),trace=msg?.context_trace;if(!trace)return;
 const history=trace.recent_messages||[],brief=trace.conversation_context||{};
 modal('Conversation context used',`<p class="modal-note">${esc(trace.note||'Context sent to the local model for this reply.')}</p>${trace.recommendation_checks?`<h3 class="category-subtitle">Addition checks: ${esc(trace.recommendation_checks.status)}</h3><p class="modal-note">${esc(trace.recommendation_checks.scope||'The answer failed checks and was withheld.')}</p>${(trace.recommendation_checks.issues||[]).map(x=>'<p>'+esc(x)+'</p>').join('')}${(trace.recommendation_checks.cards||[]).map(c=>`<article class="context-excerpt"><strong>${esc(c.name)}</strong><p>Cost ${esc(c.mana_cost??'unknown')} · MV ${esc(c.mv??'unknown')} · Power ${esc(c.power??'n/a or unknown')}</p><p>${esc(c.available)} available · Color check: ${esc(c.color_check)}</p><p>${esc(c.oracle_text||'Rules unresolved')}</p><p class="muted small">${esc(c.meta_source||'Source unknown')}</p></article>`).join('')}`:''}<h3 class="category-subtitle">Recent messages actually sent</h3>${history.map(m=>`<article class="context-excerpt"><div class="eyebrow green">${m.role==='user'?'YOU':'EARLIER ASSISTANT'}</div>${ForageText.render(m.text)}</article>`).join('')||'<p class="muted small">No prior chat messages were included for this reply.</p>'}<h3 class="category-subtitle">Earlier user requests retained</h3>${(brief.earlier_user_requests||[]).map(m=>'<article class="context-excerpt">'+ForageText.render(m.text)+'</article>').join('')||'<p class="muted small">No earlier substantial requests were available.</p>'}${(brief.related_older_excerpts||[]).length?'<h3 class="category-subtitle">Related older excerpts</h3>':''}${(brief.related_older_excerpts||[]).map(m=>'<article class="context-excerpt"><div class="eyebrow green">'+esc(m.role)+'</div>'+ForageText.render(m.excerpt)+'</article>').join('')}${(trace.collection_searches||[]).length?'<h3 class="category-subtitle">Collection searches executed</h3>':''}${(trace.collection_searches||[]).map(s=>'<article class="context-excerpt"><strong>'+esc(s.query)+'</strong><p>'+esc(s.matches)+' matching cards</p><p>'+esc((s.cards||[]).join(', '))+'</p></article>').join('')}<p class="modal-note">Deck data and saved preferences are sent separately. Earlier assistant messages are conversation history, not verified rules or proof of accepted edits.</p>`);
}


async function updatesDialog(){
 const info=await api('updates/status'),cfg=info.config,last=info.last_check;
 modal('Application updates',`<p class="modal-note">Installed version: <strong>${esc(info.current_version)}</strong>. Updates replace application files after the server stops. Your data folder stays local. A rollback copy and workspace snapshot are kept.</p><label class="field">GitHub release repository<input id="update-repo" placeholder="owner/repository" value="${esc(cfg.repository)}"></label><label class="field"><input type="checkbox" id="update-start" ${cfg.check_on_start?'checked':''}>Check for updates on launch</label><p class="modal-note">Use a trusted public repository containing Forage releases. This version does not store GitHub credentials or download private releases. Checks contact GitHub with the repository name; decks, collection and chats are not sent.</p><button id="update-save" class="button secondary">Save update settings</button><button id="update-check" class="button secondary">Check now</button><button id="update-history" class="button secondary">Update history & versions</button><p id="update-message" class="modal-note">${esc(last.status==='available'?'Version '+last.version+' is available.':last.status==='up_to_date'?'You are up to date.':last.message||'Configure a repository, then check for updates.')}</p>${last.notes?`<details><summary>Release notes</summary><div class="context-excerpt">${esc(last.notes)}</div></details>`:''}<div class="modal-actions"><button id="update-install" class="button primary" ${(!info.pending&&last.status!=='available')?'disabled':''}>${info.pending?'Restart to install '+esc(info.pending.version):'Update and restart'}</button><button id="update-rollback" class="button secondary" ${info.rollback_available?'':'disabled'}>Roll back${info.rollback_version?' to '+esc(info.rollback_version):' application'}</button></div>${!info.supervised?'<p class="modal-note">Restart using Start-Forage.bat to enable supervised installation and rollback.</p>':''}<p class="modal-note">Installation verifies download and per-file SHA-256 hashes, keeps a previous-code copy, and restores it if the updated server fails its startup check. These checks verify integrity against the configured release source; trust that repository. Rollback restores application code, not your current deck data.</p>`);
 const save=async()=>api('updates',{action:'configure',repository:$('#update-repo').value,check_on_start:$('#update-start').checked});
 $('#update-history').onclick=()=>run(updateHistoryDialog);
 $('#update-save').onclick=()=>run(async()=>{await save();toast('Update settings saved.');await updatesDialog()});
 $('#update-check').onclick=()=>run(async()=>{$('#update-message').textContent='Checking releases…';await save();await api('updates',{action:'check'});await updatesDialog()});
 const install=async rollback=>{
   const button=rollback?$('#update-rollback'):$('#update-install');button.disabled=true;
   try{
     if(!info.supervised)throw new Error('Close Forage and start it with Start-Forage.bat, then retry.');
     if(rollback&&!info.version_switch_supported)throw new Error('Close Forage and reopen Start-Forage.bat once to enable compatibility-checked rollback.');
     if(!rollback&&!info.pending){$('#update-message').textContent='Downloading and verifying…';await api('updates',{action:'stage'})}
     $('#update-message').textContent=rollback?'Restoring previous application…':'Restarting to install…';
     await api('updates',{action:rollback?'rollback':'restart'});
     $('#update-message').textContent='Forage is restarting. Waiting for it to return…';
     let failures=0;
     const poll=setInterval(async()=>{try{const health=await api('health');if(health.instance!==info.instance){clearInterval(poll);location.reload()}}catch(e){if(++failures>=60){clearInterval(poll);$('#update-message').textContent='Restart is taking longer than expected. Check the Forage terminal, then reload.'}}},1000);
   }catch(e){button.disabled=false;$('#update-message').textContent=e.message}
 };
 $('#update-install').onclick=()=>install(false);$('#update-rollback').onclick=()=>install(true);
}

async function updateHistoryDialog(){
 const info=await api('updates/status');
 modal('Update history',`<p class="modal-note">Installed: <strong>${esc(info.current_version)}</strong></p><p class="modal-note">Loading release history…</p>`);
 const history=await api('updates/history');
 modal('Update history',`<p class="modal-note">Installed: <strong>${esc(info.current_version)}</strong> · Workspace format ${esc(history.workspace_version)}</p><p class="modal-note">Version changes preserve your current decks, collection, chat and preferences. Each switch checks compatibility and saves a workspace snapshot before replacing application files. Switching back to an older version also restores that version’s interface; use its Application updates screen to return to the latest release.</p>${history.offline_error?`<p class="notice">GitHub could not be reached. Showing saved history. ${esc(history.offline_error)}</p>`:''}${!info.version_switch_supported?'<p class="notice">After installing this update, close Forage and reopen Start-Forage.bat once to enable version switching in the new launcher.</p>':''}<div class="release-history">${history.releases.map(release=>`<article class="release-entry"><div class="release-heading"><h3>Forage ${esc(release.version)}</h3>${release.installed?'<span class="release-installed">Installed</span>':''}</div>${release.changes?`<ul>${release.changes.map(note=>'<li>'+esc(note)+'</li>').join('')}</ul>`:ForageText.render(release.notes||'No release notes provided.')}<div class="modal-actions">${!release.installed&&release.available?`<button class="button secondary" data-release-version="${esc(release.version)}" ${!info.supervised||!info.version_switch_supported?'disabled':''}>${release.direction==='older'?'Switch back to':'Install'} ${esc(release.version)}</button>`:release.installed?'':'<span class="muted small">No verified release package listed.</span>'}</div></article>`).join('')}</div><button id="history-updates-back" class="button secondary">Back to application updates</button>`);
 $('#history-updates-back').onclick=()=>run(updatesDialog);
 $$('[data-release-version]').forEach(button=>button.onclick=()=>confirmVersionSwitch(button.dataset.releaseVersion,info));
}
function confirmVersionSwitch(target,info){
 modal('Switch Forage version',`<p>Switch from <strong>${esc(info.current_version)}</strong> to <strong>${esc(target)}</strong>?</p><p class="modal-note">Your current workspace is kept. Forage will download and verify the selected release, check that it supports your workspace format, then save the current application and a workspace snapshot before switching. If a check fails, it will keep the current application. Deck edits are not reverted.</p><div id="version-switch-message" class="modal-note" role="status"></div><div class="modal-actions"><button id="version-switch-confirm" class="button primary">Switch and restart</button><button id="version-switch-cancel" class="button secondary">Back to history</button></div>`);
 $('#version-switch-cancel').onclick=()=>run(updateHistoryDialog);
 $('#version-switch-confirm').onclick=async()=>{
  const button=$('#version-switch-confirm'),message=$('#version-switch-message');button.disabled=true;$('#version-switch-cancel').disabled=true;
  try{
   if(!info.supervised||!info.version_switch_supported)throw Error('Close Forage and reopen Start-Forage.bat to enable version switching.');
   message.textContent='Downloading and checking workspace compatibility…';
   await api('updates',{action:'stage',version:target});
   message.textContent='Saving a workspace snapshot and restarting…';await api('updates',{action:'restart'});
   let failures=0;
   const poll=setInterval(async()=>{try{const health=await api('health');if(health.instance!==info.instance){clearInterval(poll);location.reload()}}catch(e){if(++failures>=60){clearInterval(poll);message.textContent='Restart is taking longer than expected. Check the Forage terminal, then reload.'}}},1000);
  }catch(error){button.disabled=false;$('#version-switch-cancel').disabled=false;message.textContent=error.message}
 };
}

async function desktopDialog(){
 const info=await api('desktop/status');
 modal('Windows tray & startup',info.supported?`<p class="modal-note">Current mode: <strong>${info.tray_running?'System tray':'Console launcher'}</strong>. Forage can keep running when you close its browser tab. Double-click the tray icon to open it, or right-click for Open Forage, Start with Windows and Quit Forage.</p><label class="field"><input id="desktop-startup" type="checkbox" ${info.startup_enabled||!info.tray_running?'checked':''}>Start Forage quietly when I sign in to Windows</label><p class="modal-note">This creates a Forage shortcut in your Start menu and uses your Windows account’s startup settings. The browser opens when you choose Open Forage; signing in only starts the tray service. Your existing data folder is retained. No administrator access is required.</p><div id="desktop-message" class="modal-note" role="status"></div><button id="desktop-save" class="button primary">${info.tray_running?'Save startup preference':'Save & run in tray'}</button>`:'<p class="modal-note">The system tray integration currently supports Windows. Continue using your normal launcher on this operating system.</p>');
 if(!info.supported)return;
 $('#desktop-save').onclick=async()=>{
  const button=$('#desktop-save'),message=$('#desktop-message');button.disabled=true;
  try{
   const result=await api('desktop',{action:'configure',startup:$('#desktop-startup').checked});
   if(result.status!=='tray_starting'){message.textContent='Saved. Open Forage from your Start menu or tray icon.';button.disabled=false;return}
   message.textContent='Starting the tray service. You can close the old CMD window if it remains open.';
   let failures=0;const poll=setInterval(async()=>{try{const status=await api('desktop/status');if(status.tray_running){clearInterval(poll);location.reload()}}catch(error){if(++failures>=60){clearInterval(poll);message.textContent='Open Forage from your Start menu. If it does not start, check forage.log in your data folder.'}}},1000);
  }catch(error){button.disabled=false;message.textContent=error.message}
 };
}
