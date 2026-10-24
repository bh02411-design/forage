const assert=require('node:assert/strict');
require('./test_deck_lifecycle.cjs');
const {cleanReply,render}=require('../static/render.js');
assert.equal(cleanReply('{"reply":"Hello\\n\\n**World**"}, "proposals": []'),'Hello\n\n**World**');
assert.equal(cleanReply('{"reply":"Say \\"hello\\".","broken":['),'Say "hello".');
assert.equal(render('Hello\n\n**World**'),'<p>Hello</p><p><strong>World</strong></p>');
assert.match(render('1. First\n2. Second'),/<ol><li>First<\/li><li>Second<\/li><\/ol>/);
assert.match(render('- One\n- Two'),/<ul>/);
assert.equal(render('<img src=x onerror=alert(1)>'),'<p>&lt;img src=x onerror=alert(1)&gt;</p>');
assert.equal(render('`<script>`'),'<p><code>&lt;script&gt;</code></p>');
assert.ok(!render('{bad json').includes('{bad json'));
console.log('8 chat-rendering checks passed.');
assert.ok(!render('<|tool_call>call:collection_search{query:draw}<tool_call|>').includes('<|tool_call>'));
console.log('Saved tool-request display check passed.');

const embedded={reply:'**Readable** swap.\n\n### Tradeoff\n\n* One benefit\n* One cost',recommendations:[],proposals:[{add:'Candidate',cut:'Existing',reason:'Tradeoff'}],memory_suggestions:[]};
const wrapped='This proposal respects your preferences.\n\n```json\n'+JSON.stringify(embedded,null,2)+'\n```';
assert.equal(cleanReply(wrapped),embedded.reply);
assert.ok(!render(wrapped).includes('&quot;proposals&quot;'));assert.ok(!render(wrapped).includes('<pre>'));
assert.match(render(wrapped),/<h3>Tradeoff<\/h3>/);assert.match(render(wrapped),/<ul>/);
assert.equal(cleanReply('At {1}{B}, consider this.\n'+JSON.stringify(embedded)),embedded.reply);
assert.equal(cleanReply(JSON.stringify({reply:wrapped})),embedded.reply);
assert.equal(cleanReply('Intro\n```json\n{"reply":"Readable","proposals":['),'Readable');
assert.ok(!render('Intro\n```json\n{"reply":"<img src=x onerror=alert(1)>","proposals":[]}\n```').includes('<img'));
assert.equal(cleanReply('Ordinary prose with {1}{B}.'),'Ordinary prose with {1}{B}.');
console.log('10 mixed prose/JSON formatting checks passed.');

// Exercise the actual chat renderer against scroll metrics, not a separate model.
const vm=require('node:vm'),fs=require('node:fs');
const app=fs.readFileSync(require.resolve('../static/app.js'),'utf8');
const chatCode=app.slice(app.indexOf('function renderChat('),app.indexOf('function available('));
const body={scrollTop:0,scrollHeight:1000,clientHeight:300},elements={'#conversation-body':body,'#welcome':{},'#messages':{}};
const frames=[];
const context={state:{active:'deck-a',memories:[]},chatRenderedDeck:null,deck:()=>({chat:[]}),$:s=>elements[s],$$:()=>[],requestAnimationFrame:cb=>frames.push(cb)};
vm.createContext(context);vm.runInContext(chatCode,context);
const flush=()=>{while(frames.length)frames.shift()()};
context.renderChat();flush();assert.equal(body.scrollTop,1000); // First opening.
body.scrollTop=150;context.renderChat();flush();assert.equal(body.scrollTop,150); // Reading older replies.
body.scrollTop=690;context.renderChat();body.scrollHeight=1400;flush();assert.equal(body.scrollTop,1400); // Follow a new reply at bottom.
body.scrollTop=0;context.state.active='deck-b';context.renderChat();flush();assert.equal(body.scrollTop,1400); // Deck switch.
body.scrollTop=0;context.renderChat(true);flush();assert.equal(body.scrollTop,1400); // Reopen conversation.
context.state.active='deck-c';body.clientHeight=0;body.scrollTop=0;context.renderChat();flush();assert.equal(context.chatRenderedDeck,'deck-b'); // Hidden panels do not consume first-open scroll.
body.clientHeight=300;context.renderChat();flush();assert.equal(body.scrollTop,1400);
context.state.active='deck-d';body.scrollTop=10;context.renderChat();context.state.active='deck-e';flush();assert.equal(body.scrollTop,10); // Ignore stale deck callbacks.
console.log('8 chat-scroll regression checks passed.');

// Run actual decision handlers: generating an alternative must not mutate the deck.
(async()=>{
 const candidate={name:'Candidate',id:'c'},proposal={id:'p',add:'Candidate',cut:'Old Card',status:'pending'};
 const rec={id:'r',card:candidate,status:'pending'},message={id:'m',recommendations:[rec]};
 const d={chat:[message],proposals:[proposal],cards:[{name:'Old Card',zone:'main'}]},draft={value:''},calls=[];
 const ctx={deck:()=>d,norm:s=>s.toLowerCase(),busy:false,pendingCard:null,pendingImage:null,$:()=>draft,
  toast:()=>{},closeModal:()=>{},sendChat:async()=>calls.push(['chat',draft.value]),run:async fn=>fn(),mutate:async(...args)=>calls.push(args)};
 vm.createContext(ctx);vm.runInContext(app.slice(app.indexOf('async function recommendationAction('),app.indexOf('function available(')),ctx);
 const button=action=>({dataset:{recAction:action},closest:s=>({dataset:s==='[data-rec-message]'?{recMessage:'m'}:{recId:'r'}})});
 await ctx.recommendationAction(button('different'));
 assert.equal(calls.length,1);assert.equal(calls[0][0],'chat');assert.match(calls[0][1],/different cut from Old Card/);
 assert.match(calls[0][1],/Keep Candidate as the addition/);
 await ctx.recommendationAction(button('accept'));assert.equal(calls[1][0],'proposal');assert.equal(calls[1][1].action,'accept');
 await ctx.recommendationAction(button('pass'));assert.equal(calls[2][0],'recommendation');assert.equal(calls[2][1].action,'pass');
 await ctx.recommendationAction(button('maybe'));assert.equal(calls[3][0],'card');assert.equal(calls[3][1].zone,'maybe');
 console.log('8 graphical decision-action checks passed.');
})().catch(error=>{console.error(error);process.exitCode=1});

const pendingButton={textContent:'',classList:{toggle:(name,value)=>{pendingButton.highlight=value}}},dialog={open:false},title={textContent:''};
let pendingShown=0;
const pendingContext={ForageCards:require('../static/card-view.js'),deck:()=>({cards:[],chat:[],proposals:[{id:'old',status:'pending',add:'Candidate'}],category_plans:[{status:'pending'}]}),$:selector=>({'#pending-decisions':pendingButton,'#modal':dialog,'#modal-title':title})[selector],showPendingDecisions:()=>pendingShown++};
vm.createContext(pendingContext);vm.runInContext(app.slice(app.indexOf('function renderProposals('),app.indexOf('function showPendingDecisions(')),pendingContext);
pendingContext.renderProposals();assert.equal(pendingButton.textContent,'Pending decisions · 2');assert.equal(pendingButton.highlight,true);
dialog.open=true;title.textContent='Pending decisions';pendingContext.renderProposals();assert.equal(pendingShown,1);
pendingContext.deck=()=>({cards:[],chat:[],proposals:[]});pendingContext.renderProposals();assert.equal(pendingButton.textContent,'Pending decisions · 0');assert.equal(pendingButton.highlight,false);
const index=fs.readFileSync(require.resolve('../static/index.html'),'utf8');assert.ok(!index.includes('proposal-section'));assert.ok(index.includes('id="pending-decisions"'));assert.ok(!index.includes('id="proposals"'));
console.log('8 pending-decision header/layout checks passed.');

(async()=>{
 const requests=[],modals=[],nodes={};
 for(const id of ['history-updates-back','version-switch-confirm','version-switch-cancel','version-switch-message'])nodes['#'+id]={disabled:false,textContent:''};
 const releaseButton={dataset:{releaseVersion:'0.2.8'}};
 const info={current_version:'0.2.9',supervised:true,version_switch_supported:true,instance:'before'};
 const ctx={api:async(path,payload)=>{requests.push([path,payload]);return path==='updates/status'?info:path==='updates/history'?{workspace_version:1,releases:[{version:'0.2.9',installed:true,changes:['History screen']},{version:'0.2.8',direction:'older',available:true,changes:['Move analytics up']}]}:{}},
  modal:(title,html)=>modals.push({title,html}),esc:s=>String(s??'').replace(/</g,'&lt;'),ForageText:{render},$:s=>nodes[s],$$:()=>[releaseButton],run:fn=>fn(),setInterval:()=>123};
 vm.createContext(ctx);vm.runInContext(app.slice(app.indexOf('async function updateHistoryDialog(')),ctx);
 await ctx.updateHistoryDialog();assert.match(modals.at(-1).html,/Installed.*0.2.9/);assert.match(modals.at(-1).html,/Move analytics up/);assert.match(modals.at(-1).html,/Switch back to/);
 releaseButton.onclick();assert.equal(modals.at(-1).title,'Switch Forage version');assert.match(modals.at(-1).html,/Deck edits are not reverted/);
 await nodes['#version-switch-confirm'].onclick();assert.equal(requests.at(-2)[1].version,'0.2.8');assert.equal(requests.at(-1)[1].action,'restart');
 ctx.api=async()=>{throw Error('Incompatible workspace')};requests.length=0;
 await nodes['#version-switch-confirm'].onclick();assert.equal(nodes['#version-switch-message'].textContent,'Incompatible workspace');assert.equal(nodes['#version-switch-confirm'].disabled,false);
 console.log('9 update-history/version-selection checks passed.');
})().catch(error=>{console.error(error);process.exitCode=1});

(async()=>{
 const calls=[],button={},context={zone:'main',groupBy:'type',$:()=>button,run:fn=>fn(),toast:()=>{},mutate:async(path,payload)=>{calls.push([path,payload]);return {categorized:1,unresolved:0,undo_available:true}}};
 vm.createContext(context);vm.runInContext(app.slice(app.indexOf("$('#auto-categorize').onclick="),app.indexOf("$('#new-category').onclick=")),context);
 await button.onclick();assert.equal(calls[0][1].resolve,true);assert.equal(button.disabled,false);assert.equal(calls[0][1].zone,'main');assert.equal(calls[1][1].settings.group_by,'category');
 context.zone='maybe';await button.onclick();assert.equal(calls[2][1].zone,'maybe');
 console.log('3 board auto-categorization control checks passed.');
})().catch(error=>{console.error(error);process.exitCode=1});

(async()=>{
 const button={},message={},checkbox={checked:true},calls=[],modals=[];
 const ctx={api:async(path,payload)=>{calls.push([path,payload]);return path==='desktop/status'?{supported:true,tray_running:true,startup_enabled:false}:{ok:true,tray_running:true}},modal:(title,html)=>modals.push(html),$:s=>s==='#desktop-save'?button:s==='#desktop-message'?message:checkbox};
 vm.createContext(ctx);vm.runInContext(app.slice(app.indexOf('async function desktopDialog(')),ctx);
 await ctx.desktopDialog();assert.match(modals.at(-1),/Start Forage quietly/);await button.onclick();assert.equal(calls.at(-1)[1].startup,true);assert.equal(calls.at(-1)[0],'desktop');
 ctx.api=async()=>({supported:false});await ctx.desktopDialog();assert.match(modals.at(-1),/currently supports Windows/);
 console.log('4 desktop setup interface checks passed.');
})().catch(error=>{console.error(error);process.exitCode=1});

{
 const nodes={},toggles=[];
 const ctx={$:s=>nodes[s]??=( {open:false,classList:{toggle:(...args)=>toggles.push(args)},showModal(){this.open=true}} ),available:()=>({owned:1,free:1}),ForageCards:require('../static/card-view.js'),state:{collection:[]},esc:s=>String(s??''),safeUrl:s=>s};
 vm.createContext(ctx);vm.runInContext(app.slice(app.indexOf('function modal('),app.indexOf('function closeModal(')),ctx);vm.runInContext(app.slice(app.indexOf('function cardPreview('),app.indexOf('function editCard(')),ctx);
 const preview=ctx.cardPreview({name:'Detail fixture',image:'https://cards.scryfall.io/normal/front/a/test.jpg',oracle_text:'Draw a card.'},'<button id="test-control">Save</button>');
 ctx.modal('Detail',preview);assert.deepEqual(toggles.at(-1),['card-modal',true]);assert.ok(preview.indexOf('card-detail-controls')<preview.indexOf('test-control'));assert.match(preview,/card-detail-art/);
 ctx.modal('Category','Other content');assert.deepEqual(toggles.at(-1),['card-modal',false]);assert.equal(nodes['#modal'].open,true);
 console.log('Large card detail and modal reset checks passed.');
}

(async()=>{
 const nodes={},calls=[],plan={fingerprint:'reviewed',early:true,basic_count:20,rows:[{name:'Swamp',current:2,suggested:14,delta:12,protected:0,colored_pips:20,fixed_sources:2}],blocking:[],warnings:[],unknown_costs:[],unknown_lands:[],method:'Balance estimate',changed:true,can_apply:true};let content='',closed=false;
 const ctx={state:{active:'land-deck'},$:s=>nodes[s]??=( {} ),run:fn=>fn(),esc:s=>String(s),api:async(path,payload)=>{calls.push([path,payload]);return plan},mutate:async(path,payload)=>calls.push([path,payload]),modal:(title,html)=>{content=html},closeModal:()=>closed=true,toast:()=>{}};
 vm.createContext(ctx);vm.runInContext(app.slice(app.indexOf('async function basicLandDialog('),app.indexOf('async function sample(')),ctx);
 await nodes['#basic-land-optimizer'].onclick();assert.equal(calls[0][1].action,'preview');assert.match(content,/Apply basic land mix/);assert.match(content,/14/);assert.equal(calls.length,1);
 await nodes['#land-apply'].onclick();assert.equal(calls[1][1].fingerprint,'reviewed');assert.equal(calls[1][1].action,'apply');assert.equal(closed,true);
 console.log('Basic-land optimizer review and explicit apply checks passed.');
})().catch(error=>{console.error(error);process.exitCode=1});

{
 const nodes={},prefs={},Cards=require('../static/card-view.js');
 const ctx={ForageCards:Cards,deck:()=>({cards:[{name:'Demand',qty:1,zone:'main',mana_cost:'{W}{W}{B}',mv:3,type_line:'Creature'},{name:'Forest',qty:5,zone:'main',land:true},{name:'Rock',qty:1,zone:'main',mana_cost:'{2}',mv:2,type_line:'Artifact',oracle_text:'{T}: Add {C}{C}.'}]}),$:s=>nodes[s]??=( {} ),$$:()=>[],uiRead:(key,fallback)=>prefs[key]||fallback,uiSave:(key,value)=>prefs[key]=value,esc:s=>String(s)};
 vm.createContext(ctx);vm.runInContext(app.slice(app.indexOf('function renderManaStats('),app.indexOf('function filterStatus(')),ctx);ctx.renderManaStats();
 assert.match(nodes['#mana-stats'].innerHTML,/Cost · colored/);assert.match(nodes['#mana-stats'].innerHTML,/66.7%/);assert.match(nodes['#mana-stats'].innerHTML,/Average nonland mana value: 2.50/);
 nodes['#mana-nonland'].onchange({target:{checked:false}});assert.equal(prefs.manaProductionNonlands,'no');assert.equal(nodes['#mana-nonland'].checked,false);assert.match(nodes['#mana-stats'].innerHTML,/G 100.0%/);
 console.log('Mana cost/production rendering and production-toggle checks passed.');
}

{
 const nodes={},cards=[{name:'Commander',qty:1,zone:'commander',mana_cost:'{B}{G}',mv:2,color_identity:['B','G'],type_line:'Creature'},{name:'Forest',qty:5,zone:'main',land:true}];
 const ctx={ForageCards:require('../static/card-view.js'),deck:()=>({cards}),$:s=>nodes[s]??=( {} ),$$:()=>[],uiRead:(k,f)=>f,uiSave:()=>{},esc:s=>String(s)};
 vm.createContext(ctx);vm.runInContext(app.slice(app.indexOf('function renderManaStats('),app.indexOf('function filterStatus(')),ctx);ctx.renderManaStats();
 assert.doesNotMatch(nodes['#mana-stats'].innerHTML,/mana-color-card.*?<strong>White<\/strong>/);assert.doesNotMatch(nodes['#mana-stats'].innerHTML,/<strong>Blue<\/strong>|<strong>Red<\/strong>|<strong>Colorless<\/strong>/);assert.match(nodes['#mana-stats'].innerHTML,/<strong>Black<\/strong>/);assert.match(nodes['#mana-stats'].innerHTML,/<strong>Green<\/strong>/);
 cards.push({name:'Staged red',qty:4,zone:'main',group:'Swap In',mana_cost:'{R}',mv:1});ctx.renderManaStats();assert.doesNotMatch(nodes['#mana-stats'].innerHTML,/<strong>Red<\/strong>/);
 cards.push({name:'Partner',qty:1,zone:'commander',mana_cost:'{W}',mv:1,color_identity:['W'],type_line:'Creature'});ctx.renderManaStats();assert.match(nodes['#mana-stats'].innerHTML,/<strong>White<\/strong>/);
 cards.push({name:'Wastes',qty:1,zone:'main',land:true});ctx.renderManaStats();assert.match(nodes['#mana-stats'].innerHTML,/<strong>Colorless<\/strong>/);
 delete cards[0].color_identity;ctx.renderManaStats();assert.match(nodes['#mana-stats'].innerHTML,/<strong>Blue<\/strong>/);
 console.log('Commander-identity mana panel filtering and partner/colorless checks passed.');
}

// Run sidebar startup and clicks with persisted browser preferences.
{
 const code=app.slice(app.indexOf('function setSidebarCollapsed('),app.indexOf('let cardMode='));
 const boot=(saved)=>{
  const classes=new Set(),attributes={},button={setAttribute:(k,v)=>attributes[k]=v};
  const shell={classList:{toggle:(k,on)=>on?classes.add(k):classes.delete(k),contains:k=>classes.has(k)}};
  const storage={sidebarCollapsed:saved};
  const ctx={$:selector=>selector==='.shell'?shell:button,uiRead:(k,f)=>storage[k]||f,uiSave:(k,v)=>storage[k]=v};
  vm.createContext(ctx);vm.runInContext(code,ctx);
  return {classes,attributes,button,storage};
 };
 const first=boot('no');assert.equal(first.attributes['aria-expanded'],'true');
 first.button.onclick();assert.ok(first.classes.has('sidebar-collapsed'));
 assert.equal(first.storage.sidebarCollapsed,'yes');assert.equal(first.button.title,'Expand sidebar');
 assert.equal(first.attributes['aria-label'],'Expand sidebar');assert.equal(first.attributes['aria-expanded'],'false');
 const restored=boot(first.storage.sidebarCollapsed);assert.ok(restored.classes.has('sidebar-collapsed'));
 restored.button.onclick();assert.equal(restored.storage.sidebarCollapsed,'no');
 assert.equal(restored.attributes['aria-expanded'],'true');assert.equal(restored.button.title,'Collapse sidebar');
 console.log('Sidebar startup, persistence, navigation state and toggle checks passed.');
}

{
 const nodes={},classes=new Set(),attributes={},ctx={deckExpanded:false,$:s=>nodes[s]??=( {setAttribute:(k,v)=>{(attributes[s]??={})[k]=v}} )};
 nodes['.workspace']={classList:{toggle:(k,on)=>on?classes.add(k):classes.delete(k)}};
 vm.createContext(ctx);vm.runInContext(app.slice(app.indexOf('function setChatCollapsed('),app.indexOf("$('#focus-deck').onclick=")),ctx);
 ctx.setChatCollapsed(true);assert.ok(classes.has('deck-expanded'));assert.equal(nodes['#focus-deck'].textContent,'Show chat ↙');assert.equal(attributes['#focus-deck']['aria-expanded'],'false');
 ctx.setChatCollapsed(false);assert.ok(!classes.has('deck-expanded'));assert.equal(nodes['#focus-deck'].textContent,'Hide chat ↗');assert.equal(attributes['#collapse-chat']['aria-expanded'],'true');
 console.log('Chat collapse and reopen controls stay synchronized with accessible state.');
}
