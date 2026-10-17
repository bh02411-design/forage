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
