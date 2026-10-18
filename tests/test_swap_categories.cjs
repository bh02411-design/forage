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
assert.deepEqual(Cards.boardGroups(cards,'category','name',{},false).swaps,[]);
assert.deepEqual(Cards.boardGroups([{...cards[2],group:'Incoming picks'}],'category','name',{swap_categories:{in:'Incoming picks',out:'Outgoing picks'}}).swaps.map(([g])=>g),['Incoming picks','Outgoing picks']);
const elements={};const el=s=>elements[s]??=( {value:'',hidden:false,innerHTML:'',contains:()=>false} );let bindings=[];
const context={ForageCards:Cards,state:{collection:[]},deck:()=>({cards,categories:['a_Likely Add','Empty import artifact']}),zone:'main',cardMode:'stacks',groupBy:'mana',sortBy:'name',esc:s=>String(s),$:el,$$:()=>[],filterStatus:()=>{},bindVisualCards:e=>bindings.push(e)};
vm.createContext(context);const app=fs.readFileSync('static/app.js','utf8');vm.runInContext(app.slice(app.indexOf('function renderDeck(){'),app.indexOf('function findVisualCard(')),context);
context.renderDeck();assert.equal(el('#swap-categories').hidden,false);assert.match(el('#swap-categories').innerHTML,/data-edit-category="Swap In"/);assert.match(el('#swap-categories').innerHTML,/data-drop-group="Swap Out"/);assert.equal(bindings.length,2);assert.doesNotMatch(el('#deck-list').innerHTML,/a_Likely Add|Empty import artifact|Incoming|Outgoing/);
context.zone='maybe';context.renderDeck();assert.equal(el('#swap-categories').hidden,true);assert.equal(el('#swap-categories').innerHTML,'');
context.zone='main';context.groupBy='category';context.renderDeck();assert.doesNotMatch(el('#deck-list').innerHTML,/a_Likely Add|Empty import artifact/);
const html=fs.readFileSync('static/index.html','utf8'),css=fs.readFileSync('static/style.css','utf8');assert.match(html,/class="deck-surface"/);assert.match(css,/\.deck-surface\{display:grid;grid-template-columns:minmax\(0,1fr\)/);
console.log('Pinned swap category grouping and rendering checks passed');
