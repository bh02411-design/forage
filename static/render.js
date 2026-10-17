/* Small safe chat renderer: no raw HTML from the model enters the page. */
(function(root){
'use strict';
const escape=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function cleanReply(text){
 if(/<\|tool_call>|<tool_call\|>|<tool_call>/.test(String(text??'')))return 'This earlier reply was an unhandled collection-search request. Retry the question with the updated app.';
 let s=String(text??'').trim().replace(/^```(?:json)?\s*|\s*```$/g,'');
 if(!s.startsWith('{'))return s;
 try{const d=JSON.parse(s);if(typeof d.reply==='string')return d.reply.replace(/\\n/g,'\n')}catch{}
 const m=/"reply"\s*:\s*/.exec(s);
 if(m){const start=m.index+m[0].length;if(s[start]==='"'){let escaped=false;for(let i=start+1;i<s.length;i++){if(escaped){escaped=false;continue}if(s[i]==='\\'){escaped=true;continue}if(s[i]==='"'){try{return JSON.parse(s.slice(start,i+1)).replace(/\\n/g,'\n')}catch{break}}}}}
 return 'This saved response has malformed formatting. Please ask Forage to retry it.';
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
