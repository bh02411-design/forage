const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const Cards=require('../static/card-view.js');
const cards=[
 {id:'draw',name:'Quiet Scholar',type_line:'Creature — Human',oracle_text:'When this creature enters, draw a card.',mv:2,power:'2',toughness:'1',colors:['B'],color_identity:['B','G'],set:'blb',rarity:'common',keywords:[],legalities:{commander:'legal'},roles:['Draw'],group:'Card Draw',qty:2,layout:'normal'},
 {id:'mill',name:'Grave Reader',type_line:'Creature — Squirrel',oracle_text:'Mill three cards.',mv:3,power:'3',toughness:'4',colors:['G'],color_identity:['G'],set:'mh3',rarity:'rare',keywords:['Reach'],legalities:{commander:'legal'},roles:['Mill'],qty:1,layout:'normal'},
 {id:'land',name:'Still Forest',type_line:'Basic Land — Forest',oracle_text:'{T}: Add {G}.',mv:0,colors:[],color_identity:['G'],set:'blb',rarity:'common',keywords:[],legalities:{commander:'legal'},qty:5,layout:'normal'},
 {id:'spell',name:'Bright Insight',type_line:'Instant',oracle_text:'Draw two cards. (This reminder mentions sacrifice.)',mv:2,colors:['R'],color_identity:['R'],set:'otc',rarity:'uncommon',keywords:[],legalities:{commander:'banned'},qty:1,layout:'normal'},
 {id:'star',name:'Mystery Star',type_line:'Creature — Horror',oracle_text:'Flying',mv:4,power:'*',toughness:'1+*',colors:['U','B'],color_identity:['U','B'],set:'mh3',rarity:'mythic',keywords:['Flying'],legalities:{commander:'legal'},qty:1,layout:'modal_dfc'},
 {id:'unknown',name:'Unresolved Candidate',qty:1}
];
const ids=query=>Cards.search(cards,query).matches.map(c=>c.id);
const tests=[['o:draw',['draw','spell']],['o:"draw two cards"',['spell']],['t:creature mv<=3',['draw','mill']],['t:creature pow<=3',['draw','mill']],['tou>=4',['mill']],['cmc=0',['land']],['id<=bg',['draw','mill','land']],['id:bg',['draw','mill','land']],['id=bg',['draw']],['c:b',['draw','star']],['c=0',['land']],['c:c',['land']],['c:colorless',['land']],['c>=ub',['star']],['id=golgari',['draw']],['c=2',['star']],['-t:land',['draw','mill','spell','star']],['NOT t:land',['draw','mill','spell','star']],['(o:draw OR o:mill) mv<=3',['draw','mill','spell']],['o:draw OR t:squirrel mv=3',['draw','mill','spell']],['-o:draw t:creature',['mill','star']],['!"Quiet Scholar"',['draw']],['name:"Quiet Scholar"',['draw']],['r:c s:blb',['draw','land']],['rarity:mythic',['star']],['kw:flying',['star']],['f:commander t:instant',[]],['banned:commander',['spell']],['f:edh mv<=2',['draw','land']],['role:draw',['draw']],['group:"Card Draw"',['draw']],['qty>=2',['draw','land']],['is:mdfc',['star']],['is:dfc',['star']],['o:sacrifice',[]],['fo:sacrifice',['spell']],['quiet scholar',['draw']]];
for(const [query,expected] of tests){const result=Cards.search(cards,query);assert.equal(result.error,null,query);assert.deepEqual(result.matches.map(c=>c.id),expected,query)}
assert.equal(Cards.search(cards,'-o:draw').unknown,1);
assert.deepEqual(ids('name:Unresolved OR o:draw'),['draw','spell','unknown']);
assert.ok(Cards.search(cards,'usd<5').error);assert.ok(Cards.search(cards,'otag:draw').error);
for(const query of ['o:/draw/','mv<=no','(t:land','t:land OR','o:"draw','r:fake','c:fake','is:commander',')','t:land AND'])assert.ok(Cards.search(cards,query).error,query);
assert.deepEqual(Cards.search([{name:'Known colorless',colors:[],color_identity:[]},{name:'Unknown'}],'id<=bg').matches.map(c=>c.name),['Known colorless']);
assert.equal(Cards.search([{name:'Mystery',type_line:''}],'-t:land').unknown,1);
console.log(tests.length+' search queries and 17 error/missing-data checks passed.');

// Exercise actual collection rendering: match printings before merging their names.
const app=fs.readFileSync(require.resolve('../static/app.js'),'utf8'),elements={},tiles=[];
const element=selector=>elements[selector]??(elements[selector]={value:'s:blb',classList:{toggle:()=>{}},setAttribute:()=>{},hidden:false});
const ctx={state:{collection:[{...cards[0],qty:1,set:'mh3'},{...cards[0],id:'other-print',qty:3,set:'blb'}],collection_source:'Test'},$:element,$$:()=>[],norm:s=>s.toLowerCase(),esc:s=>String(s),collectionLimit:60,collectionMode:'grid',collectionSort:'name',collectionDirection:'asc',filterStatus:()=>{},available:()=>({owned:4,free:4}),bindVisualCards:()=>{},ForageCards:{...Cards,tile:c=>{tiles.push(c);return c.name}}};
vm.createContext(ctx);vm.runInContext(app.slice(app.indexOf('function renderCollection('),app.indexOf('function cardPreview(')),ctx);ctx.renderCollection();
assert.equal(tiles.length,1);assert.equal(tiles[0].qty,3);assert.equal(tiles[0].set,'blb');
console.log('3 printing-aware collection integration checks passed.');

const example={dataset:{filterQuery:'t:creature pow<=3'}},input={value:'',focus:()=>{}},help={where:null,html:''};let collectionRenders=0;
const helpContext={esc:s=>String(s),modal:(title,html)=>{help.html=html},$$:()=>[example],$:()=>input,closeModal:()=>{},collectionLimit:0,renderCollection:()=>collectionRenders++,renderDeck:()=>{}};
vm.createContext(helpContext);vm.runInContext(app.slice(app.indexOf('function syntaxKey('),app.indexOf('function renderDeck(')),helpContext);helpContext.syntaxKey('collection');example.onclick();
assert.equal(input.value,'t:creature pow<=3');assert.equal(collectionRenders,1);assert.equal(helpContext.collectionLimit,60);assert.match(help.html,/scryfall.com\/docs\/syntax/);
console.log('4 clickable syntax-key checks passed.');

assert.equal(Cards.search([{name:"Nadier's Nightblade"}],"Nadier's").matches.length,1);
assert.equal(Cards.search(cards,"o:'draw two cards'").matches[0].id,'spell');
console.log('2 apostrophe/quoted-phrase checks passed.');
