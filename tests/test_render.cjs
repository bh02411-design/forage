const assert=require('node:assert/strict');
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
 await button.onclick();assert.equal(calls[0][1].zone,'main');assert.equal(calls[1][1].settings.group_by,'category');
 context.zone='maybe';await button.onclick();assert.equal(calls[2][1].zone,'maybe');
 console.log('3 board auto-categorization control checks passed.');
})().catch(error=>{console.error(error);process.exitCode=1});
