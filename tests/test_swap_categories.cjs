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
const context={ForageCards:Cards,state:{collection:[]},deck:()=>({cards,categories:['a_Likely Add','Empty import artifact']}),zone:'main',cardMode:'stacks',groupBy:'mana',sortBy:'name',esc:s=>String(s),$:el,$$:()=>[],filterStatus:()=>{},bindVisualCards:e=>bindings.push(e)};
vm.createContext(context);const app=fs.readFileSync('static/app.js','utf8');vm.runInContext(app.slice(app.indexOf('function renderDeck(){'),app.indexOf('function findVisualCard(')),context);
context.renderDeck();assert.equal(el('#swap-categories').hidden,false);assert.match(el('#swap-categories').innerHTML,/data-edit-category="Swap In"/);assert.match(el('#swap-categories').innerHTML,/data-drop-group="Swap Out"/);assert.equal(bindings.length,2);assert.doesNotMatch(el('#deck-list').innerHTML,/a_Likely Add|Empty import artifact|Incoming|Outgoing/);
context.zone='maybe';context.renderDeck();assert.equal(el('#swap-categories').hidden,false);assert.match(el('#swap-categories').innerHTML,/Considering Incoming/);assert.match(el('#swap-categories').innerHTML,/Mainboard/);assert.match(el('#swap-categories').innerHTML,/Considering/);assert.equal(el('#card-count').textContent,'3 cards');
context.zone='main';context.groupBy='category';context.renderDeck();assert.doesNotMatch(el('#deck-list').innerHTML,/a_Likely Add|Empty import artifact/);assert.equal(el('#card-count').textContent,'5 cards');
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
