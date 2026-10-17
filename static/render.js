/* Small safe chat renderer: no raw HTML from the model enters the page. */
(function(root){
'use strict';
const escape=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function embeddedReply(s){
 const candidates=[...s.matchAll(/\{\s*"(?:reply|recommendations|proposals|memory_suggestions|collection_search|category_changes|workspace_changes)"\s*:/g)];
 for(const match of candidates){
  const start=match.index;let depth=0,quoted=false,escaped=false;
  for(let i=start;i<s.length;i++){
   const ch=s[i];
   if(quoted){if(escaped)escaped=false;else if(ch==='\\')escaped=true;else if(ch==='"')quoted=false;continue}
   if(ch==='"'){quoted=true;continue}if(ch==='{')depth++;if(ch==='}'&&--depth===0){try{const d=JSON.parse(s.slice(start,i+1));if(typeof d.reply==='string')return d.reply}catch{}break}
  }
  const m=/"reply"\s*:\s*/.exec(s.slice(start));
  if(m){const offset=start+m.index+m[0].length;if(s[offset]==='"'){let escaped=false;for(let i=offset+1;i<s.length;i++){if(escaped){escaped=false;continue}if(s[i]==='\\'){escaped=true;continue}if(s[i]==='"'){try{return JSON.parse(s.slice(offset,i+1))}catch{break}}}}}
 }
 return null;
}
function cleanReply(text){
 if(/<\|tool_call>|<tool_call\|>|<tool_call>/.test(String(text??'')))return 'This earlier reply was an unhandled collection-search request. Retry the question with the updated app.';
 let s=String(text??'').trim();
 for(let depth=0;depth<4;depth++){
  const reply=embeddedReply(s);
  if(reply===null){
   if(s.startsWith('{')||/\{\s*"reply"\s*:/.test(s))return 'This saved response has malformed formatting. Please ask Forage to retry it.';
   return s.replace(/\\n/g,'\n');
  }
  s=reply.trim();
 }
 return 'This saved response has nested formatting that could not be displayed. Please ask Forage to retry it.';
}
function inline(text){return String(text).split(/(`[^`]+`)/g).map(part=>part.startsWith('`')&&part.endsWith('`')?'<code>'+escape(part.slice(1,-1))+'</code>':escape(part).replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>').replace(/\*(.+?)\*/g,'<em>$1</em>')).join('')}
function render(text){
 const lines=cleanReply(text).replace(/\r\n/g,'\n').split('\n');let output='',paragraph=[],list='',code=null;
 function flush(){if(paragraph.length){output+='<p>'+paragraph.map(inline).join('<br>')+'</p>';paragraph=[]}if(list){output+='</'+list+'>';list=''}}
 for(const line of lines){
  if(/^```/.test(line)){flush();if(code!==null){output+='<pre><code>'+escape(code.join('\n'))+'</code></pre>';code=null}else code=[];continue}
  if(code!==null){code.push(line);continue}
  if(!line.trim()){flush();continue}
  const heading=/^#{1,6}\s+(.+)$/.exec(line);if(heading){flush();output+='<h3>'+inline(heading[1])+'</h3>';continue}
  const bullet=/^\s*[-*+]\s+(.+)$/.exec(line),number=/^\s*\d+[.)]\s+(.+)$/.exec(line);
  if(bullet||number){if(paragraph.length){output+='<p>'+paragraph.map(inline).join('<br>')+'</p>';paragraph=[]}const tag=number?'ol':'ul';if(list!==tag){if(list)output+='</'+list+'>';output+='<'+tag+'>';list=tag}output+='<li>'+inline((bullet||number)[1])+'</li>';continue}
  if(list){output+='</'+list+'>';list=''}paragraph.push(line);
 }
 flush();if(code!==null)output+='<pre><code>'+escape(code.join('\n'))+'</code></pre>';return output;
}
const api={cleanReply,render};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.ForageText=api;
})(typeof window!=='undefined'?window:globalThis);
