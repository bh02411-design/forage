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
  toast:()=>{},sendChat:async()=>calls.push(['chat',draft.value]),run:async fn=>fn(),mutate:async(...args)=>calls.push(args)};
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
