const chat = document.querySelector('#chat'), form = document.querySelector('#form'), input = document.querySelector('#message');
const finish = document.querySelector('#finish'), analytics = document.querySelector('#analytics');
let conversationId;
function add(text, who) { const el = document.createElement('div'); el.className = `message ${who}`; el.textContent = text; chat.append(el); chat.scrollTop = chat.scrollHeight; }
form.addEventListener('submit', async (e) => { e.preventDefault(); const message = input.value.trim(); if (!message) return; add(message, 'customer'); input.value = ''; input.disabled = true;
  try { const r = await fetch('/api/chat', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({message, conversation_id:conversationId})}); const data = await r.json(); if (!r.ok) throw new Error(data.detail); conversationId = data.conversation_id; add(data.reply, 'agent'); finish.disabled = false; if (data.conversation_ended) { input.disabled = true; form.querySelector('button').disabled = true; } }
  catch(err) { add(`Sorry, ${err.message}`, 'agent'); } finally { if (!conversationId || !document.querySelector('button[type="submit"]')?.disabled) input.disabled = false; input.focus(); }
});
finish.addEventListener('click', async () => { if (!conversationId) return; const r = await fetch(`/api/conversations/${conversationId}/end`, {method:'POST'}); const data = await r.json(); analytics.hidden = false; analytics.textContent = 'Conversation analytics\n' + JSON.stringify(data, null, 2); finish.disabled = true; });

