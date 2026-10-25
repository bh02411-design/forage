const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const Cards=require('../static/card-view.js');
const cards=[{id:'c',name:'Leader',qty:1,zone:'commander',group:'Swap Out'},{id:'a',name:'Normal',qty:1,zone:'main',group:'Draw'},{id:'i',name:'Incoming',qty:2,zone:'main',group:'Swap In',mv:3},{id:'o',name:'Outgoing',qty:1,zone:'main',group:'Swap Out',mv:1}];
const before=JSON.stringify(cards);
for(const by of ['category','type','mana','color'])for(const sort of ['name','mana']){
 const result=Cards.boardGroups(cards,by,sort,{});
 assert.equal(result.main[0][0],'Commander');assert.deepEqual(result.swaps.map(([g])=>g),['Swap In','Swap Out']);
 assert.deepEqual(result.swaps.map(([,list])=>list.map(c=>c.id)),[['i'],['o']]);
 assert.ok(result.main.every(([,list])=>list.every(c=>!['i','o'].includes(c.id))));
}
assert.equal(JSON.stringify(cards),before);
assert.equal(Cards.boardGroups([], 'category','name',{}).swaps.length,2);
assert.equal(Cards.boardGroups(cards,'category','name',{}).swaps.length,2);
assert.deepEqual(Cards.boardGroups([{...cards[2],group:'Incoming picks'}],'category','name',{swap_categories:{in:'Incoming picks',out:'Outgoing picks'}}).swaps.map(([g])=>g),['Incoming picks','Outgoing picks']);
cards.push({id:'m',name:'Considering Incoming',qty:3,zone:'maybe',group:'Swap In'});
assert.deepEqual(Cards.boardCards({cards},'maybe').map(c=>c.id),['i','o','m']);
assert.equal(Cards.boardCards({cards},'main').length,5);
const elements={};const el=s=>elements[s]??=( {value:'',hidden:false,innerHTML:'',contains:()=>false} );let bindings=[];
const context={duplicateWarnings:{},ForageCards:Cards,state:{collection:[]},deck:()=>({cards,categories:['a_Likely Add','Empty import artifact']}),zone:'main',cardMode:'stacks',groupBy:'mana',sortBy:'name',esc:s=>String(s),$:el,$$:()=>[],filterStatus:()=>{},bindVisualCards:e=>bindings.push(e)};
vm.createContext(context);const app=fs.readFileSync('static/app.js','utf8');vm.runInContext(app.slice(app.indexOf('function renderDeck(){'),app.indexOf('function findVisualCard(')),context);
context.renderDeck();assert.equal(el('#swap-categories').hidden,false);assert.match(el('#swap-categories').innerHTML,/data-edit-category="Swap In"/);assert.match(el('#swap-categories').innerHTML,/data-drop-group="Swap Out"/);assert.equal(bindings.length,2);assert.doesNotMatch(el('#deck-list').innerHTML,/a_Likely Add|Empty import artifact|Incoming|Outgoing/);
context.zone='maybe';context.renderDeck();assert.equal(el('#swap-categories').hidden,false);assert.match(el('#swap-categories').innerHTML,/Considering Incoming/);assert.doesNotMatch(el('#swap-categories').innerHTML,/swap-origin|>Mainboard<|>Considering</);assert.equal(el('#card-count').textContent,'0 cards');
context.zone='main';context.groupBy='category';context.renderDeck();assert.doesNotMatch(el('#deck-list').innerHTML,/a_Likely Add|Empty import artifact/);assert.equal(el('#card-count').textContent,'2 cards');
const html=fs.readFileSync('static/index.html','utf8'),css=fs.readFileSync('static/style.css','utf8');assert.match(html,/class="deck-surface"/);assert.match(css,/\.deck-surface\{display:grid;grid-template-columns:minmax\(0,1fr\)/);
console.log('Pinned swap category grouping and rendering checks passed');

(async()=>{
 const calls=[],collection=[{id:'stock',name:'Stock Candidate',qty:1,zone:'main'}];
 const ctx={state:{active:'deck'},deck:()=>({cards}),ForageCards:Cards,findVisualCard:(id,source)=>(source==='collection'?collection:cards).find(c=>c.id===id),mutate:async(path,payload)=>calls.push({path,...payload}),toast:()=>{}};
 vm.createContext(ctx);vm.runInContext(app.slice(app.indexOf('async function internalDrop('),app.indexOf('function renderChat(')),ctx);
 await ctx.internalDrop({deck:'deck',id:'o',source:'deck'},'maybe','Swap Out');assert.equal(calls.at(-1).zone,'main');
 await ctx.internalDrop({deck:'deck',id:'m',source:'deck'},'main','Swap In');assert.equal(calls.at(-1).zone,'maybe');
 await ctx.internalDrop({deck:'deck',id:'stock',source:'collection'},'main','Swap In');assert.equal(calls.at(-1).zone,'maybe');
 await ctx.internalDrop({deck:'deck',id:'m',source:'deck'},'main');assert.equal(calls.at(-1).zone,'main');
 await assert.rejects(()=>ctx.internalDrop({deck:'deck',id:'c',source:'deck'},'main','Swap Out'),/commander stays pinned/);
 console.log('Shared swap categories preserve assignments and board counts.');
})().catch(error=>{console.error(error);process.exitCode=1});

// Staging is visible on both boards but never included in board totals.
assert.deepEqual(Cards.countedBoardCards({cards},'main').map(c=>c.id),['c','a']);
assert.deepEqual(Cards.countedBoardCards({cards},'maybe'),[]);
const renamed={cards:[{...cards[2],group:'Incoming picks'},{id:'regular',zone:'maybe',qty:4,group:'Draw'}],swap_categories:{in:'Incoming picks',out:'Outgoing picks'}};
assert.deepEqual(Cards.countedBoardCards(renamed,'main'),[]);
assert.equal(Cards.countedBoardCards(renamed,'maybe')[0].qty,4);
renamed.cards[0].group='Draw';
assert.equal(Cards.countedBoardCards(renamed,'main')[0].qty,2);
renamed.cards[0].group='Incoming picks';
assert.deepEqual(Cards.countedBoardCards(renamed,'main'),[]);
console.log('Staging totals exclude both pins, support renamed categories and update on moves.');

cards[1].needs_sleeving=true;
el('#needs-sleeving-only').checked=true;
context.zone='main';context.renderDeck();
assert.match(el('#deck-list').innerHTML,/Normal/);assert.doesNotMatch(el('#deck-list').innerHTML,/Leader/);
assert.equal(el('#card-count').textContent,'1 cards');
assert.match(Cards.tile(cards[1]),/tile-sleeving/);
assert.match(Cards.tile(cards[1]),/needs sleeving/);
assert.doesNotMatch(Cards.tile({...cards[1],needs_sleeving:false}),/tile-sleeving/);
el('#needs-sleeving-only').checked=false;
console.log('Physical-deck markers render and the checklist filter selects only marked entries.');

// Full-deck duplicate results survive searches and apply in every board display mode.
context.duplicateWarnings={undefined:[{ids:['a'],quantity:2,limit:1,message:'Normal: 2 copies; Commander limit 1.',unresolved:false}]};
context.zone='main';el('#deck-search').value='Normal';
for(const mode of ['stacks','grid','list']){
 context.cardMode=mode;context.renderDeck();
 assert.match(el('#deck-list').innerHTML,/duplicate-card/);
 assert.match(el('#deck-list').innerHTML,/Duplicate/);
 assert.doesNotMatch(el('#swap-categories').innerHTML,/duplicate-card/);
}
context.duplicateWarnings={};context.renderDeck();assert.doesNotMatch(el('#deck-list').innerHTML,/duplicate-card/);
console.log('Duplicate warnings remain visible under filters in stack, grid and list modes and clear after edits.');
