'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const html = fs.readFileSync('static/index.html','utf8');
const app = fs.readFileSync('static/app.js','utf8');
const css = fs.readFileSync('static/style.css','utf8');
for (const id of ['deck-conversation','chat-form','message','focus-deck','collapse-chat']) {
  assert.doesNotMatch(html,new RegExp('id="'+id+'"'),'Removed local chat element: '+id);
}
for (const id of ['deck-list','deck-drop','pending-decisions','sample','settings-open']) {
  assert.match(html,new RegExp('id="'+id+'"'),'Preserved core interface element: '+id);
}
assert.doesNotMatch(app,/renderChat\(|sendChat\(|setChatCollapsed\(/);
assert.match(css,/\.workspace\{grid-template-columns:minmax\(0,1fr\)!important\}/);
console.log('Local chatbot absent; deck, sample, pending decisions, and settings remain.');
