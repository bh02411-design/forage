const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('static/app.js','utf8');
const Cards=require('../static/card-view.js');
const card={id:'card',name:'Fixture',qty:1,zone:'main',group:'Draw'};
const d={id:'deck',cards:[card],history:[]},other={id:'other',cards:[],history:[]};
const calls=[],renders=[];let release,fail=false;
const context={state:{active:'deck',decks:[d,other]},duplicateWarnings:{},ForageCards:Cards,
 api:async(path,payload)=>{
  calls.push({path,payload});await new Promise(resolve=>release=resolve);
  if(fail){fail=false;throw Error('Save failed')}
  return {deck_move:{cards:[{...card,group:payload.group}],categories:[payload.group],history:[{summary:'Moved'}],duplicate_violations:[]}};
 },
 renderDeckSummary:()=>renders.push('summary'),renderManaStats:()=>renders.push('mana'),
 renderDeck:()=>renders.push('deck'),renderHistory:()=>renders.push('history'),renderCollection:()=>renders.push('collection')};
vm.createContext(context);
vm.runInContext(source.slice(source.indexOf('let deckMoveQueue='),source.indexOf('function modal(')),context);
const tick=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
 const first=context.mutateDeckMove('card',{id:'card',group:'Ramp'});
 const second=context.mutateDeckMove('card',{id:'card',group:'Draw'});
 await tick();assert.equal(calls.length,1,'rapid moves must save in gesture order');
 assert.equal(d.cards[0].group,'Draw','unsaved moves must not alter local data');
 release();await first;await tick();assert.equal(calls.length,2);assert.equal(d.cards[0].group,'Ramp');
 assert.equal(calls[0].payload.deck_move_response,true);assert.equal(calls[0].payload.deck,'deck');
 assert.ok(!renders.includes('collection'),'category-only moves must not redraw the collection');
 release();await second;assert.equal(d.cards[0].group,'Draw');
 fail=true;const failed=context.mutateDeckMove('card',{id:'card',group:'Failed'});await tick();
 const rejected=assert.rejects(failed,/Save failed/);release();await rejected;
 assert.equal(d.cards[0].group,'Draw');
 const retry=context.mutateDeckMove('card',{id:'card',group:'Retry'});await tick();
 context.state.active='other';renders.length=0;release();await retry;
 assert.equal(d.cards[0].group,'Retry');assert.equal(other.cards.length,0);assert.equal(renders.length,0);
 context.state.active='deck';const staging=context.mutateDeckMove('card',{id:'card',group:'Swap Out'});
 await tick();release();await staging;assert.ok(renders.includes('collection'),'staging affects available copies');
 console.log('Compact moves: ordering, scoped renders, staging inventory, failed saves, retry and deck switching passed.');
})().catch(e=>{console.error(e);process.exitCode=1});
