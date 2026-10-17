/* Pure card-view helpers shared by the browser and regression checks. */
(function(root){
'use strict';
const escape=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const norm=s=>String(s).toLowerCase().split(' // ')[0].replace(/[^a-z0-9]/g,'');
const imageUrl=s=>{try{const u=new URL(s);return u.protocol==='https:'&&u.hostname==='cards.scryfall.io'?u.href:''}catch{return ''}};
function art(card,collection=[]){if(imageUrl(card.image))return imageUrl(card.image);const found=collection.find(c=>norm(c.name)===norm(card.name)&&imageUrl(c.image));return found?imageUrl(found.image):''}
function groupName(card,by){
 if(card.zone==='commander')return 'Commander';
 if(by==='mana')return card.land?'Lands':card.mv==null?'Unknown mana value':'MV '+(Number(card.mv)>=7?'7+':card.mv);
 if(by==='type'){if(card.land)return 'Land';const type=String(card.type_line||'').split('—')[0];return ['Creature','Planeswalker','Instant','Sorcery','Enchantment','Artifact','Battle'].find(t=>type.includes(t))||'Unresolved type'}
 if(by==='color'){if(card.color_identity==null)return 'Unresolved color';const colors=[...card.color_identity].sort();return colors.length?colors.join(' / '):'Colorless'}
 return card.group||'Uncategorized';
}
function groups(cards,by='category',sort='name'){
 const commanders=cards.filter(c=>c.zone==='commander'),map=new Map();
 for(const c of cards){if(c.zone==='commander')continue;const g=groupName(c,by);if(!map.has(g))map.set(g,[]);map.get(g).push(c)}
 const entries=[...map.entries()].sort(([a],[b])=>a===b?0:(a==='Land'||a==='Lands')?1:(b==='Land'||b==='Lands')?-1:a.localeCompare(b,undefined,{numeric:true}));
 if(commanders.length)entries.unshift(['Commander',commanders]);
 for(const [,list] of entries)list.sort((a,b)=>sort==='mana'?((a.mv??1000)-(b.mv??1000)||a.name.localeCompare(b.name)):a.name.localeCompare(b.name));return entries;
}
function tile(card,collection=[],source='deck',availability=null){
 const image=art(card,collection);const qty=card.qty??1;
 return `<button class="card-visual ${image?'has-art':'no-art'}" draggable="true" data-visual-card="${escape(card.id)}" data-card-source="${source}" aria-label="${escape(card.name)}${card.protected?', protected':''}" title="${escape(card.name)}"><span class="art-frame">${image?`<img src="${escape(image)}" loading="lazy" decoding="async" alt="${escape(card.name)}">`:`<span class="art-placeholder"><span class="placeholder-symbol">✳</span><strong>${escape(card.name)}</strong><small>Resolve card data for artwork</small></span>`}<span class="tile-badges"><span class="tile-quantity">${qty}×</span>${card.protected?'<span class="tile-protected" title="Protected">◆</span>':''}</span></span><span class="tile-caption"><strong>${escape(card.name)}</strong><small>${availability?`${availability.owned} owned · ${availability.free} unassigned`:card.land?'Land':'MV '+(card.mv??'?')}</small></span></button>`;
}
const api={groups,art,tile,groupName};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.ForageCards=api;
})(typeof window!=='undefined'?window:globalThis);
