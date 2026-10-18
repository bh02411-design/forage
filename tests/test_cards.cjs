const assert=require('node:assert/strict');
const {groups,art,tile,groupName}=require('../static/card-view.js');
const cards=[{id:'a',name:'Swamp',qty:13,zone:'main',group:'Land',land:true,mv:0},{id:'b',name:'Ygra, Eater of All',qty:1,zone:'commander',mv:5,color_identity:['B','G']},{id:'c',name:'Greater Good',qty:1,zone:'main',group:'Draw',mv:4,type_line:'Enchantment',protected:true},{id:'d',name:'Unknown',qty:1,zone:'main',group:'Draw',mv:null}];
const before=JSON.stringify(cards);
assert.equal(groups(cards)[0][0],'Commander');
assert.equal(groups(cards).at(-1)[0],'Land');
assert.equal(groups(cards,'category','mana').find(([g])=>g==='Draw')[1][0].name,'Greater Good');
assert.equal(JSON.stringify(cards),before);
assert.equal(groupName(cards[2],'type'),'Enchantment');
assert.equal(groupName(cards[1],'color'),'Commander');
assert.equal(groupName(cards[3],'mana'),'Unknown mana value');
assert.equal(art({name:'A',image:'javascript:alert(1)'}),'');
assert.equal(art({name:'A'},[{name:'A',image:'https://cards.scryfall.io/normal/front/a/test.jpg'}]),'https://cards.scryfall.io/normal/front/a/test.jpg');
assert.ok(tile(cards[2]).includes('Resolve card data for artwork'));
assert.ok(tile(cards[2]).includes('draggable="true"'));
assert.ok(tile(cards[2]).includes('tile-protected'));
assert.ok(!tile({id:'x',name:'<script>',qty:1}).includes('<script>'));
assert.ok(tile({id:'x',name:'Test',qty:1,image:'https://evil.example/track'}).includes('no-art'));
console.log('14 card-view checks passed.');

// Commander placement follows board assignment, regardless of display category.
const pinCards=[
 {id:'leader',name:'Zulu leader',qty:1,zone:'commander',group:'Z custom group',mv:8,color_identity:['B'],type_line:'Creature'},
 {id:'a',name:'Alpha',qty:1,zone:'main',group:'A category',mv:1},
 {id:'b',name:'Before the leader',qty:1,zone:'main',group:'Commander',mv:0},
 {id:'partner',name:'Partner leader',qty:1,zone:'commander',group:'Other leaders',mv:2}
];
const pinBefore=JSON.stringify(pinCards);
for(const by of ['category','type','mana','color'])for(const sort of ['name','mana']){
 const arranged=groups(pinCards,by,sort);
 assert.equal(arranged[0][0],'Commander');
 assert.deepEqual(new Set(arranged[0][1].map(c=>c.id)),new Set(['leader','partner']));
 assert.ok(arranged.slice(1).every(([,list])=>list.every(c=>c.zone!=='commander')));
}
assert.equal(groupName(pinCards[0],'category'),'Commander');
assert.equal(JSON.stringify(pinCards),pinBefore);
assert.equal(groups([]).length,0);
assert.equal(groups(pinCards.filter(c=>c.zone==='main'),'category')[0][0],'A category');
console.log('28 commander-placement checks passed.');

const {recommendation}=require('../static/card-view.js');
const rec={id:'rec',card:{id:'candidate',name:'New <Card>',mv:2,mana_cost:'{1}{B}',image:'https://cards.scryfall.io/normal/front/a/test.jpg'},reason:'Benefit <script>',status:'pending'};
const proposed=[{id:'p',add:rec.card.name,cut:'Greater Good',reason:'Tradeoff',status:'pending'}];
const graphic=recommendation(rec,[],cards,proposed);
assert.match(graphic,/data-rec-action="accept"/);assert.match(graphic,/data-rec-action="different"/);
assert.match(graphic,/data-rec-side="cut"/);assert.match(graphic,/Greater Good/);
assert.match(graphic,/cards.scryfall.io/);assert.ok(!graphic.includes('New <Card>'));
const noSwap=recommendation(rec);assert.match(noSwap,/data-rec-action="find"/);assert.match(noSwap,/data-rec-action="main"/);
assert.ok(!recommendation({...rec,status:'passed'},[],cards,proposed).includes('data-rec-action="accept"'));
assert.match(recommendation(rec,[],[{...rec.card,zone:'main'}],proposed),/In mainboard/);
assert.ok(!recommendation({...rec,card:{...rec.card,image:'javascript:alert(1)'}}).includes('javascript:'));
console.log('11 graphical recommendation checks passed.');

const matchGraphic=recommendation({...rec,kind:'match'});
assert.match(matchGraphic,/COLLECTION MATCH/);assert.match(matchGraphic,/data-rec-action="find"/);
assert.match(matchGraphic,/data-rec-action="pass"/);
console.log('3 fallback-match graphic checks passed.');

const {pendingDecisions}=require('../static/card-view.js');
const pendingDeck={cards:[],chat:[{id:'first',recommendations:[rec]},{id:'latest',recommendations:[{...rec,id:'new'}]}],proposals:[{...proposed[0]}],category_plans:[{id:'plan',status:'pending'}]};
const decisions=pendingDecisions(pendingDeck);
assert.equal(decisions.recommendations.length,1);assert.equal(decisions.recommendations[0].message,'latest');
assert.equal(decisions.proposals.length,0);assert.equal(decisions.plans.length,1);
assert.equal(pendingDecisions({...pendingDeck,cards:[{...rec.card,zone:'main'}]}).recommendations.length,0);
assert.equal(pendingDecisions({...pendingDeck,proposals:[],cards:[{...rec.card,zone:'maybe'}]}).recommendations.length,0);
assert.equal(pendingDecisions({...pendingDeck,cards:[{...rec.card,zone:'maybe'}]}).recommendations.length,1);
assert.equal(pendingDecisions({...pendingDeck,chat:[...pendingDeck.chat,{id:'pass',recommendations:[{...rec,status:'passed'}]}],proposals:[]}).recommendations.length,0);
assert.equal(pendingDecisions({...pendingDeck,chat:[]}).proposals.length,1); // Legacy swaps remain reachable.
assert.deepEqual(pendingDecisions({}),{recommendations:[],proposals:[],plans:[]});
console.log('10 pending-decision checks passed.');

{
 const {manaStats}=require('../static/card-view.js');
 const fixture=[
  {name:'Forest',qty:4,zone:'main',land:true},
  {name:'Typed Dual',qty:1,zone:'main',land:true,type_line:'Land — Plains Swamp'},
  {name:'Two Mana Rock',qty:1,zone:'main',type_line:'Artifact',mana_cost:'{2}',mv:2,oracle_text:'{T}: Add {C}{C}.'},
  {name:'Green Dork',qty:2,zone:'main',type_line:'Creature',mana_cost:'{G}',mv:1,oracle_text:'{T}: Add {G}.'},
  {name:'Hybrid',qty:1,zone:'main',type_line:'Creature',mana_cost:'{B/G}{B/G}',mv:2},
  {name:'Counter Color',qty:1,zone:'main',type_line:'Artifact',mana_cost:'{1}{C}',mv:2},
  {name:'Commander',qty:1,zone:'commander',type_line:'Creature',mana_cost:'{B}{G}',mv:2,color_identity:['B','G']},
  {name:'Considering Source',qty:30,zone:'maybe',land:true,oracle_text:'{T}: Add {U}.'},
  {name:'Conditional',qty:1,zone:'main',land:true,type_line:'Land',oracle_text:'{T}: Add one mana of any color a land an opponent controls could produce.'},
  {name:'Treasure Maker',qty:1,zone:'main',type_line:'Creature',mana_cost:'{3}',mv:3,oracle_text:'Create a Treasure token. (It is an artifact with “{T}, Sacrifice this artifact: Add one mana of any color.”)'},
  {name:'Ritual',qty:1,zone:'main',type_line:'Instant',mana_cost:'{B}',mv:1,oracle_text:'Add {B}{B}{B}.'}
 ];
 const before=JSON.stringify(fixture),stats=manaStats(fixture),by=Object.fromEntries(stats.rows.map(r=>[r.color,r]));
 assert.equal(by.G.cost,4);assert.equal(by.B.cost,3);assert.equal(by.C.cost,1);assert.equal(by.G.production,6);assert.equal(by.C.production,2);assert.equal(by.C.production_cards,1);assert.equal(by.W.production,1);assert.equal(by.B.production,1);assert.equal(by.U.production,0);
 assert.ok(stats.conditionalSources.includes('Conditional'));assert.equal(JSON.stringify(fixture),before);
 assert.equal(manaStats(fixture,false).rows.find(r=>r.color==='G').production,4);
 const flexible=manaStats([{name:'Commander',zone:'commander',qty:1,color_identity:['B','G'],mana_cost:'{B}{G}',mv:2},{name:'Flexible',zone:'main',qty:1,land:true,type_line:'Land',oracle_text:'{T}: Add one mana of any color in your commander’s color identity.'}]);
 assert.equal(flexible.productionTotal,2);assert.equal(flexible.rows.find(r=>r.color==='W').production,0);
 assert.equal(manaStats([]).rows.every(r=>r.cost_percent===0&&r.production_percent===0),true);
 console.log('Mana demand/production, hybrid, flexible and conditional source checks passed.');
}

{
 const Cards=require('../static/card-view.js');
 const deck={swap_categories:{in:'Incoming picks',out:'Cuts'},cards:[
  {name:'Commander fixture',zone:'commander',qty:1,group:'Cuts'},
  {name:'Main fixture',zone:'main',qty:62,group:'Sacrifice & Draw'},
  {name:'Forest',zone:'main',qty:37,group:'Untapped Lands'},
  {name:'Waiting fixture',zone:'maybe',qty:15,group:'Draw'},
  {name:'Staged main fixture',zone:'main',qty:12,group:'Cuts'},
  {name:'Staged maybe fixture',zone:'maybe',qty:8,group:'Incoming picks'}
 ]};
 const before=JSON.stringify(deck),out=Cards.archidektExport(deck);
 assert.equal(out.total,100);assert.equal(out.staging,20);assert.equal(out.considering,15);
 assert.equal(out.text,'1 Commander fixture [Commander{top}]\n62 Main fixture [Sacrifice & Draw]\n37 Forest [Untapped Lands]');
 assert.equal(JSON.stringify(deck),before);
 assert.doesNotMatch(out.text,/Waiting fixture|Staged/);
 assert.equal(Cards.archidektExport({cards:[]}).total,0);
 assert.throws(()=>Cards.archidektExport({cards:[{name:'Fixture',zone:'main',qty:1,group:'Draw,Ramp'}]}),/Rename category/);
 console.log('Archidekt export preserves categories and quantities, excludes both boards’ staging, handles renamed pins and matches 100-card mainboard totals.');
}

{
 const {manaCostMarkup}=require('../static/card-view.js');
 const ordinary=manaCostMarkup({mana_cost:'{2}{B}{B}'});
 assert.equal((ordinary.match(/class="checklist-pip/g)||[]).length,3);
 assert.equal((ordinary.match(/mana-B/g)||[]).length,2);assert.match(ordinary,/2, black, black/);
 const special=manaCostMarkup({mana_cost:'{X}{W/U}{B/P}{C}{S}{0}'});
 for(const symbol of ['X','W/U','B/P','C','S','0'])assert.ok(special.includes('>'+symbol+'</span>'));
 assert.match(special,/white or blue/);assert.match(special,/black or Phyrexian/);
 assert.match(manaCostMarkup({land:true}),/Land · no mana cost/);
 assert.match(manaCostMarkup({}),/Mana cost unknown/);
 assert.match(manaCostMarkup({mana_cost:''}),/No mana cost/);
 assert.ok(!manaCostMarkup({mana_cost:'<img src=x>'}).includes('<img'));
 console.log('Checklist mana pips retain repeated, generic, hybrid, Phyrexian, variable and missing-cost distinctions.');
}
