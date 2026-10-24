const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const app=fs.readFileSync('static/app.js','utf8');
const source=app.slice(app.indexOf('function manageDecksDialog('),app.indexOf("$('#deck-select').onchange"));
const escape=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const nodes=new Map(),calls=[];let title='',markup='',focused='';
const node=key=>{if(!nodes.has(key))nodes.set(key,{disabled:false,focus(){focused=key}});return nodes.get(key)};
const d={id:'one',name:'Terra <test>',cards:[{qty:2},{qty:1}]};
const context={state:{active:d.id,decks:[d]},esc:escape,$:node,$$:()=>[],
 modal:(t,m)=>{title=t;markup=m},run:fn=>fn(),toast:()=>{},
 mutate:async(path,payload)=>{calls.push([path,payload]);context.state={active:'fresh',decks:[{id:'fresh',name:'My deck',cards:[]}],deleted_decks:[{deck:d,position:0,deleted_at:'2026-01-01T00:00:00Z'}]}}};
vm.createContext(context);vm.runInContext(source,context);
(async()=>{
 context.manageDecksDialog();assert.match(markup,/Terra &lt;test&gt;/);assert.ok(!markup.includes('Terra <test>'));assert.match(markup,/No deleted decks/);
 context.deleteDeckDialog(d.id);assert.equal(title,'Delete deck?');assert.match(markup,/3 cards across all boards/);assert.match(markup,/fresh empty deck/);assert.equal(focused,'#cancel-delete-deck');assert.equal(calls.length,0);
 node('#cancel-delete-deck').onclick();assert.equal(title,'Manage decks');assert.equal(calls.length,0);
 context.deleteDeckDialog(d.id);await node('#confirm-delete-deck').onclick();
 assert.equal(calls.length,1);assert.equal(calls[0][0],'delete-deck');assert.equal(calls[0][1].id,d.id);assert.equal(calls[0][1].confirmed_name,d.name);
 assert.equal(title,'Manage decks');assert.match(markup,/data-restore-deck="one"/);assert.ok(!node('#confirm-delete-deck').disabled);
 let restored=false;
 context.$$=selector=>selector==='[data-restore-deck]'?[{dataset:{restoreDeck:d.id},set onclick(fn){this.handler=fn;context.restoreButton=this}}]:[];
 context.mutate=async(path,payload)=>{assert.equal(path,'restore-deck');assert.equal(payload.id,d.id);restored=true;context.state={active:d.id,decks:[d],deleted_decks:[]}};
 context.manageDecksDialog();await context.restoreButton.handler();assert.ok(restored);assert.match(markup,/No deleted decks/);
 context.mutate=async()=>{throw Error('Server unavailable')};context.deleteDeckDialog(d.id);
 await assert.rejects(node('#confirm-delete-deck').onclick(),/Server unavailable/);assert.equal(node('#confirm-delete-deck').disabled,false);
 console.log('Deck manager checks passed: confirmation, escaping, cancellation, deletion, restoration, and retry after errors.');
})().catch(e=>{console.error(e);process.exitCode=1});
