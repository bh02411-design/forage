const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const app=fs.readFileSync('static/app.js','utf8');
for(const source of ['deck','collection']){
 const listeners={},image={draggable:true,addEventListener(){}},card={id:source+'-card',name:'Test card'};
 let keyboard=false,shown=0,hidden=0,opened=0,stopped=0;
 const button={dataset:{visualCard:card.id,cardSource:source},addEventListener:(name,handler)=>listeners[name]=handler,querySelectorAll:()=>[image],matches:()=>keyboard};
 const classes=new Set(['dragover','category-dragover']);
 const context={state:{active:'test-deck'},findVisualCard:()=>card,showCandidate:()=>opened++,editCard:()=>opened++,hideCardHover:()=>hidden++,showCardHover:()=>shown++,$$:()=>[{classList:{remove:(...names)=>names.forEach(n=>classes.delete(n))}}]};
 vm.createContext(context);
 vm.runInContext(app.slice(app.indexOf('function bindVisualCards('),app.indexOf('function showCardHover(')),context);
 context.bindVisualCards({querySelectorAll:selector=>selector==='img'?[image]:[button]});
 assert.equal(image.draggable,false,'inner image must not compete for the source drag');
 listeners.mouseenter({buttons:0});assert.equal(shown,1);
 listeners.pointerdown({buttons:1});assert.equal(hidden,1);
 listeners.focus();assert.equal(shown,1,'mouse focus must not recreate the preview');
 const data=new Map(),event={stopPropagation:()=>stopped++,dataTransfer:{setData:(type,value)=>data.set(type,value)}};
 listeners.dragstart(event);
 assert.equal(event.dataTransfer.effectAllowed,'copyMove');
 assert.deepEqual(JSON.parse(data.get('application/x-forage-card')),{id:card.id,source,deck:'test-deck'});
 assert.equal(data.get('text/plain'),card.name);assert.equal(stopped,1);
 assert.equal(hidden,1,'dragstart must not change preview visibility while the browser captures the drag');
 listeners.mouseenter({buttons:1});keyboard=true;listeners.focus();assert.equal(shown,1,'preview stays suppressed during a drag');
 listeners.dragend();assert.equal(button.dataset.dragging,undefined);assert.equal(classes.size,0);
 listeners.focus();assert.equal(shown,2,'keyboard preview remains available after a drag');
 button.onclick();assert.equal(opened,1,'ordinary card clicks remain available');
 // A cancelled drag leaves the next first attempt usable with a new transfer object.
 const next=new Map();listeners.pointerdown();listeners.dragstart({stopPropagation(){},dataTransfer:{setData:(k,v)=>next.set(k,v)}});
 assert.equal(JSON.parse(next.get('application/x-forage-card')).id,card.id);listeners.dragend();
}
const Cards=require('../static/card-view.js');
const html=Cards.tile({id:'image-card',name:'Image card',image:'https://cards.scryfall.io/normal/front/a/card.jpg'});
assert.match(html,/<button[^>]+draggable="true"/);assert.match(html,/<img[^>]+draggable="false"/);
console.log('First-attempt deck/collection drag payloads, preview timing, cancellation cleanup, keyboard previews and clicks passed.');
