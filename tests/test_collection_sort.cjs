const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const {inventory,sortCollection}=require('../static/card-view.js');
const cards=[
 {id:'a',name:'Zulu',qty:5,mv:2,color_identity:['B'],type_line:'Creature — Squirrel',rarity:'common'},
 {id:'b',name:'Alpha',qty:2,mv:0,color_identity:[],type_line:'Land',land:true,rarity:'mythic'},
 {id:'c',name:'Beta',qty:1,mv:null},
 {id:'d',name:'Delta',qty:3,mv:3,color_identity:['G','W'],type_line:'Artifact',rarity:'rare'}
];
const decks=[{cards:[{name:'Zulu',qty:4,zone:'main'},{name:'Alpha',qty:2,zone:'commander'},{name:'Delta',qty:12,zone:'maybe'}]}];
const counts=inventory(cards,decks),before=JSON.stringify(cards);
const expected={name:['b','c','d','a'],mana:['b','a','d','c'],color:['b','a','d','c'],type:['d','a','b','c'],rarity:['a','d','b','c'],owned:['c','b','d','a'],available:['b','c','a','d']};
for(const [field,ids] of Object.entries(expected))assert.deepEqual(sortCollection(cards,field,'asc',counts).map(c=>c.id),ids,field);
assert.deepEqual(sortCollection(cards,'mana','desc',counts).map(c=>c.id),['d','a','b','c']);
assert.deepEqual(sortCollection(cards,'color','desc',counts).map(c=>c.id),['d','a','b','c']);
assert.deepEqual(sortCollection(cards,'rarity','desc',counts).map(c=>c.id),['b','d','a','c']);
assert.deepEqual(sortCollection(cards,'available','desc',counts).map(c=>c.id),['d','c','a','b']);
assert.equal(JSON.stringify(cards),before);
assert.equal(counts.get('delta').free,3);assert.equal(counts.get('zulu').free,1);assert.equal(counts.get('alpha').free,0);
const extra=inventory([...cards,{name:'Zulu',qty:7}],decks);assert.equal(extra.get('zulu').owned,12);assert.equal(extra.get('zulu').free,8);
const zeroAndMissing=[{name:'Blank',mv:''},{name:'Unknown'},{name:'Zero',mv:0}];
assert.equal(sortCollection(zeroAndMissing,'mana','asc')[0].name,'Zero');assert.equal(sortCollection(zeroAndMissing,'mana','desc')[0].name,'Zero');
assert.deepEqual(sortCollection([{name:'Card 10'},{name:'Card 2'}]).map(c=>c.name),['Card 2','Card 10']);
console.log('20 collection sort/inventory checks passed.');
const app=fs.readFileSync(require.resolve('../static/app.js'),'utf8'),elements={};let renders=0;const saved=[];
const ctx={$:s=>elements[s]??(elements[s]={}),collectionSort:'name',collectionDirection:'asc',collectionLimit:120,uiSave:(...args)=>saved.push(args),renderCollection:()=>renders++};
vm.createContext(ctx);vm.runInContext(app.slice(app.indexOf("$('#collection-sort').onchange="),app.indexOf("$('#collection-more').onclick=")),ctx);
elements['#collection-sort'].onchange({target:{value:'available'}});assert.equal(ctx.collectionSort,'available');assert.equal(ctx.collectionLimit,60);assert.deepEqual(saved[0],['collectionSort','available']);
elements['#collection-direction'].onchange({target:{value:'desc'}});assert.equal(ctx.collectionDirection,'desc');assert.deepEqual(saved[1],['collectionDirection','desc']);assert.equal(renders,2);
console.log('6 collection sorting control/persistence checks passed.');
