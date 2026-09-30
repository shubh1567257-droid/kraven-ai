import os

from dotenv import load_dotenv
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
from flask import Flask, request, jsonify, render_template_string
import os
import re
import requests

app = Flask(__name__)

MODEL = "KRAVEN 1.0 TITAN"
GROQ_MODEL = "openai/gpt-oss-20b"
PORT = 5051

conversation_histories = {}
MAX_HISTORY_MESSAGES = 20

SYSTEM_PROMPT = r"""
You are KRAVEN AI.

Your displayed model name is KRAVEN 1.0 TITAN.

Give accurate, useful and readable answers.

DEVELOPER INFORMATION:
If the user asks who developed you, who your developer is, or who worked on building you, answer exactly: "I was developed and configured by Sarvagya Rai." Do not invent achievements, credentials, companies, awards, qualifications, or other claims about Sarvagya Rai.

MATHEMATICS AND SCIENCE FORMATTING:

For normal calculations, prefer plain text.

Example:
Total distance = 120 km + 180 km = 300 km
Total time = 2 h + 2 h = 4 h
Average speed = 300 / 4 = 75 km/h

Only use LaTeX when the user explicitly asks for LaTeX.

When using LaTeX:
Inline math must use \( ... \).
Display math must use \[ ... \].

Use simple LaTeX only.

Allowed:
\frac{a}{b}
x^2
\sqrt{x}
\boxed{x}

Do NOT use:
\begin{aligned}
\begin{array}
\begin{matrix}
&&
\text{}

Do not use square brackets [ ] as math delimiters.
Do not leave math delimiters unmatched.
Do not put normal explanatory sentences inside math.
Do not put units or prose inside complicated math.
For step-by-step calculations, use separate simple equations.

Do not output HTML.
Keep answers readable.
"""


def clean_math(text):
    if not text:
        return text

    # Convert aligned environments into separate simple equations.
    def clean_aligned(match):
        body = match.group(1)
        body = body.replace("&=", "=")
        body = body.replace("&", "")

        lines = re.split(r"\\\\", body)
        result = []

        for line in lines:
            line = line.strip()
            if line:
                result.append("\\[\n" + line + "\n\\]")

        return "\n\n".join(result)

    text = re.sub(
        r"\\begin\{aligned\}([\s\S]*?)\\end\{aligned\}",
        clean_aligned,
        text
    )

    # Convert simple standalone [ ... ] math blocks.
    def square_math(match):
        body = match.group(1).strip()

        if (
            "=" in body
            or "\\" in body
            or "^" in body
            or "_" in body
            or "frac" in body
        ):
            return "\\[\n" + body + "\n\\]"

        return match.group(0)

    text = re.sub(
        r"(?ms)^\s*\[\s*([^\[\]]+?)\s*\]\s*$",
        square_math,
        text
    )

    # Remove accidental unmatched closing parenthesis after display math.
    text = re.sub(r"(\\\])\s*\)", r"\1", text)

    return text


def ask_kraven_ai(message, user_id):
    api_key = os.environ.get("GROQ_API_KEY")

    if not api_key:
        return "Groq API key is not set."

    url = "https://api.groq.com/openai/v1/chat/completions"

    headers = {
        "Authorization": "Bearer " + api_key,
        "Content-Type": "application/json"
    }

    history_list = conversation_histories.setdefault(user_id, [])

    history_list.append({
        "role": "user",
        "content": message
    })

    history = history_list[-MAX_HISTORY_MESSAGES:]

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            }
        ] + history,
        "max_completion_tokens": 1000,
        "reasoning_effort": "low",
        "include_reasoning": False
    }

    try:
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=120
        )

        try:
            data = response.json()
        except ValueError:
            history_list.pop()
            return (
                "Groq returned invalid JSON. HTTP "
                + str(response.status_code)
            )

        if response.status_code != 200:
            history_list.pop()

            error = data.get("error", {})

            return (
                "Groq API error "
                + str(response.status_code)
                + ": "
                + error.get("message", "Unknown error")
            )

        choices = data.get("choices", [])

        if not choices:
            history_list.pop()
            return "Groq returned no choices."

        message_data = choices[0].get("message", {})
        content = message_data.get("content", "")

        if not content:
            history_list.pop()
            return "Groq returned no text."

        content = clean_math(content)

        history_list.append({
            "role": "assistant",
            "content": content
        })

        return content

    except requests.exceptions.Timeout:
        history_list.pop()
        return "Groq took too long to respond."

    except requests.exceptions.RequestException as error:
        history_list.pop()
        return "Network error: " + str(error)

    except Exception as error:
        history_list.pop()
        return "Error: " + str(error)


HTML = r"""
<!doctype html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#111315">
<title>Kraven AI</title>
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/dompurify@3.2.6/dist/purify.min.js"></script>
<script>
window.MathJax={tex:{inlineMath:[["\\(","\\)"]],displayMath:[["\\[","\\]"]]},svg:{fontCache:"global"}};
</script>
<script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js"></script>
<script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>
<style>
:root{--bg:#111315;--side:#181a1d;--surface:#222529;--surface2:#1c1f22;--border:#34383d;--border2:#454b51;--text:#f2f3f5;--muted:#9ba1a8;--muted2:#70777f;--silver:#d8dce0}
*{box-sizing:border-box}html,body{height:100%;margin:0}body{background:var(--bg);color:var(--text);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;overflow:hidden}
button,input,textarea{font:inherit;color:inherit}.app{height:100dvh;display:flex}
.sidebar{width:292px;flex:0 0 292px;background:var(--side);border-right:1px solid var(--border);display:flex;flex-direction:column;padding:14px;gap:12px;z-index:60;transition:transform .22s ease}
.brandrow{display:flex;align-items:center;gap:9px}.brand{display:flex;align-items:center;gap:10px;flex:1;min-width:0;padding:4px}.logo{width:38px;height:38px;border-radius:12px;display:grid;place-items:center;background:linear-gradient(145deg,#34393e,#151719);border:1px solid #4a5056;color:#f2f3f5;font-weight:850;letter-spacing:-.08em;box-shadow:inset 0 1px rgba(255,255,255,.06)}.brand b{font-size:14px;letter-spacing:.02em}.brand small{display:block;margin-top:2px;color:var(--muted);font-size:9px;letter-spacing:.13em}.iconbtn{width:36px;height:36px;border:1px solid transparent;border-radius:10px;background:transparent;display:grid;place-items:center;cursor:pointer}.iconbtn:hover{background:var(--surface);border-color:var(--border)}
.newchat{width:100%;border:1px solid var(--border2);background:var(--surface);border-radius:12px;padding:10px 12px;cursor:pointer;text-align:left;font-weight:650}.newchat:hover{background:#292d31}.searchbox{position:relative}.searchbox .searchicon{position:absolute;left:10px;top:9px;color:var(--muted);font-size:14px}.searchbox input{width:100%;background:#141618;border:1px solid var(--border);border-radius:10px;padding:9px 10px 9px 29px;outline:none;font-size:12px}.searchbox input:focus{border-color:var(--border2)}
.sectionlabel{padding:3px 6px 0;color:var(--muted2);font-size:9px;font-weight:750;letter-spacing:.13em;text-transform:uppercase}.history{flex:1;overflow:auto;padding-right:2px}.day{margin:10px 0 5px;padding:0 6px;color:var(--muted2);font-size:9px;text-transform:uppercase;letter-spacing:.12em;font-weight:750}.historyitem{width:100%;display:flex;align-items:center;gap:9px;border:1px solid transparent;background:transparent;border-radius:10px;padding:9px;text-align:left;cursor:pointer;margin:2px 0}.historyitem:hover,.historyitem.active{background:#22262a;border-color:#343a40}.chatglyph{width:27px;height:27px;display:grid;place-items:center;border-radius:8px;background:#202327;border:1px solid #373d43;color:#aeb4ba;flex:0 0 auto;font-size:12px}.hcopy{min-width:0}.htitle{font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.hmeta{margin-top:2px;color:var(--muted);font-size:9px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.account{position:relative;border-top:1px solid var(--border);padding-top:9px}.accountbtn{width:100%;display:flex;align-items:center;gap:9px;padding:8px;border:1px solid transparent;background:transparent;border-radius:11px;text-align:left;cursor:pointer}.accountbtn:hover{background:#202327;border-color:#30353a}.avatar{width:34px;height:34px;border-radius:50%;display:grid;place-items:center;background:#30353a;border:1px solid #4b5157;overflow:hidden;flex:0 0 auto;font-size:12px;font-weight:750}.avatar img{width:100%;height:100%;object-fit:cover}.accountcopy{min-width:0;flex:1}.accountname,.accountemail{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.accountname{font-size:11px;font-weight:650}.accountemail{margin-top:2px;color:var(--muted);font-size:9px}.accountmenu{display:none;position:absolute;left:0;right:0;bottom:57px;padding:5px;background:#1c2023;border:1px solid var(--border);border-radius:11px;box-shadow:0 15px 40px rgba(0,0,0,.35)}.account.open .accountmenu{display:block}.accountmenu button{width:100%;border:0;background:transparent;border-radius:8px;padding:9px;text-align:left;cursor:pointer;font-size:12px}.accountmenu button:hover{background:#282d31}
.main{min-width:0;flex:1;height:100%;display:flex;flex-direction:column}.topbar{height:62px;flex:0 0 62px;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between;padding:0 17px;background:rgba(17,19,21,.9);backdrop-filter:blur(14px);z-index:20}.topleft{display:flex;align-items:center;gap:9px;min-width:0}.mobilemenu{display:none}.topbrand{width:30px;height:30px;border-radius:9px;display:grid;place-items:center;background:#25292d;border:1px solid #3c4248;font-weight:800;font-size:11px}.conversationtitle{font-size:13px;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.model{margin-top:2px;color:var(--muted);font-size:9px;letter-spacing:.08em}.clearbtn{border:1px solid var(--border);background:transparent;border-radius:9px;padding:7px 10px;color:var(--muted);cursor:pointer;font-size:11px}.clearbtn:hover{background:var(--surface);color:var(--text)}
.scroll{flex:1;overflow:auto;padding:26px 18px 130px}.inner{max-width:930px;margin:auto}.empty{min-height:calc(100dvh - 205px);display:flex;align-items:center;justify-content:center;text-align:center}.emptylogo{width:70px;height:70px;border-radius:21px;display:grid;place-items:center;margin:0 auto 16px;background:linear-gradient(145deg,#34393e,#151719);border:1px solid #4a5056;font-size:28px;font-weight:850;letter-spacing:-.1em}.empty h1{margin:0;font-size:28px;letter-spacing:-.035em}.empty p{margin:8px 0 20px;color:var(--muted);font-size:13px}.prompts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px;max-width:610px;margin:auto}.prompt{padding:12px;text-align:left;background:var(--surface);border:1px solid var(--border);border-radius:13px;cursor:pointer}.prompt:hover{border-color:#51575d;background:#272b2f}.prompt b{font-size:11px}.prompt small{display:block;margin-top:4px;color:var(--muted);font-size:9px}
.row{display:flex;margin:19px 0}.userrow{justify-content:flex-end}.message{max-width:min(780px,90%);font-size:14px;line-height:1.62;overflow-wrap:anywhere}.userbubble{padding:11px 14px;background:#292e33;border:1px solid #40464c;border-radius:17px 17px 6px 17px}.assistantwrap{display:flex;align-items:flex-start;gap:10px}.aiavatar{width:30px;height:30px;display:grid;place-items:center;flex:0 0 auto;border-radius:10px;background:linear-gradient(145deg,#34393e,#17191b);border:1px solid #484e54;font-weight:800;font-size:11px}.assistant{padding:1px 0}.message p:first-child{margin-top:0}.message p:last-child{margin-bottom:0}.message pre{overflow:auto;background:#0e1012;border:1px solid #2d3237;border-radius:11px;padding:12px}.message code{font-family:ui-monospace,SFMono-Regular,Consolas,monospace}.message a{color:#d9dde1}.thinking{display:flex;gap:5px;padding-top:6px}.dot{width:6px;height:6px;background:#c9ced2;border-radius:50%;animation:pulse 1.1s infinite}.dot:nth-child(2){animation-delay:.15s}.dot:nth-child(3){animation-delay:.3s}@keyframes pulse{0%,80%,100%{opacity:.25;transform:translateY(0)}40%{opacity:1;transform:translateY(-3px)}}
.dock{position:fixed;left:292px;right:0;bottom:0;padding:11px 16px 16px;background:linear-gradient(to top,#111315 56%,rgba(17,19,21,.88),transparent);z-index:30}.composer{max-width:930px;margin:auto;display:flex;align-items:flex-end;gap:5px;padding:8px 8px 8px 13px;background:#222529;border:1px solid #3b4045;border-radius:17px;box-shadow:0 8px 35px rgba(0,0,0,.18)}#input{flex:1;min-width:0;max-height:150px;resize:none;background:transparent;border:0;outline:0;padding:7px 2px;line-height:1.45;color:var(--text);font-size:14px}#input::placeholder{color:#7f868d}.tools{display:flex;gap:3px}.toolbtn,.sendbtn{width:35px;height:35px;border-radius:10px;border:1px solid transparent;background:transparent;display:grid;place-items:center;cursor:pointer}.toolbtn{color:var(--muted)}.toolbtn:hover{background:#2c3034;color:var(--text)}.sendbtn{width:38px;height:38px;background:#e0e3e6;color:#16191b;border-color:#777e84;font-weight:850}.sendbtn:disabled{opacity:.45}
.toast{position:fixed;left:50%;bottom:27px;transform:translate(-50%,18px);opacity:0;pointer-events:none;padding:9px 13px;background:#24282c;border:1px solid #4b5157;border-radius:10px;font-size:11px;z-index:100;transition:.18s}.toast.show{opacity:1;transform:translate(-50%,0)}.backdrop{display:none;position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:55}
@media(max-width:850px){.sidebar{position:fixed;left:0;top:0;bottom:0;width:min(88vw,320px);transform:translateX(-103%);box-shadow:0 20px 60px rgba(0,0,0,.5)}.sidebar-open .sidebar{transform:translateX(0)}.sidebar-open .backdrop{display:block}.mobilemenu{display:grid}.dock{left:0;padding:9px 10px 12px}.scroll{padding:19px 11px 125px}.prompts{grid-template-columns:1fr}.message{max-width:94%}.topbar{padding:0 11px}.clearbtn{padding:7px 9px}}
@media(max-width:430px){.empty h1{font-size:24px}.emptylogo{width:62px;height:62px;font-size:24px}.prompt{padding:11px}.message{font-size:14px}.toolbtn{display:none}.composer{border-radius:15px}}
</style>
</head>
<body>
<div class="app">
<aside class="sidebar" id="sidebar">
  <div class="brandrow">
    <div class="brand"><div class="logo">K</div><div><b>KRAVEN AI</b><small>KRAVEN 1.0 TITAN</small></div></div>
    <button class="iconbtn" id="closeSidebar" aria-label="Close sidebar">✕</button>
  </div>
  <button class="newchat" id="newChat">＋ New Chat</button>
  <div class="searchbox"><span class="searchicon">⌕</span><input id="historySearch" placeholder="Search conversations..." autocomplete="off"></div>
  <div class="sectionlabel">History</div>
  <div class="history" id="history"></div>
  <div class="account" id="account">
    <button class="accountbtn" id="accountBtn">
      <div class="avatar" id="avatar">K</div>
      <div class="accountcopy"><div class="accountname" id="accountName">Not signed in</div><div class="accountemail" id="accountEmail">Google sign-in available</div></div>
      <span style="color:var(--muted)">⋯</span>
    </button>
    <div class="accountmenu"><button id="accountAction">Sign in with Google</button></div>
  </div>
</aside>
<div class="backdrop" id="backdrop"></div>
<main class="main">
  <header class="topbar">
    <div class="topleft"><button class="iconbtn mobilemenu" id="openSidebar" aria-label="Open sidebar">☰</button><div class="topbrand">K</div><div><div class="conversationtitle" id="conversationTitle">New Chat</div><div class="model">KRAVEN 1.0 TITAN · <span id="authStatus">Not signed in</span></div></div></div>
    <button class="clearbtn" id="clear">Clear</button>
  </header>
  <div class="scroll" id="scroll"><div class="inner"><div class="empty" id="empty"><div><div class="emptylogo">K</div><h1>How can Kraven help?</h1><p>Ask, build, analyze, or explore anything.</p><div class="prompts"><button class="prompt" data-p="Help me understand something"><b>Explain something</b><small>Break a difficult topic down</small></button><button class="prompt" data-p="Write some code"><b>Write some code</b><small>Build or debug a project</small></button><button class="prompt" data-p="Analyze this"><b>Analyze this</b><small>Reason through a problem</small></button><button class="prompt" data-p="Help me plan a project"><b>Plan a project</b><small>Turn an idea into steps</small></button></div></div></div><div id="messages"></div></div></div>
</main>
</div>
<div class="dock"><div class="composer"><textarea id="input" rows="1" placeholder="Message Kraven AI..."></textarea><div class="tools"><button class="toolbtn" id="voice" title="Voice input">◉</button><button class="toolbtn" id="attach" title="Attachment">＋</button><button class="sendbtn" id="send" title="Send">➤</button></div></div></div>
<div class="toast" id="toast"></div>
<script>
const SUPABASE_URL="https://czewyhjowsmgcnucxdrk.supabase.co";
const SUPABASE_ANON_KEY="sb_publishable_K7oJRO_0PajMI9PKu13tZw_lhu3Sbsc";
const supabaseClient=window.supabase.createClient(SUPABASE_URL,SUPABASE_ANON_KEY);
const input=document.getElementById('input'),send=document.getElementById('send'),messages=document.getElementById('messages'),empty=document.getElementById('empty'),scroll=document.getElementById('scroll'),toast=document.getElementById('toast');
const sessions=[];let currentSession=null;
function toastMsg(t){toast.textContent=t;toast.classList.add('show');clearTimeout(window.__toast);window.__toast=setTimeout(()=>toast.classList.remove('show'),2200)}
function resize(){input.style.height='auto';input.style.height=Math.min(input.scrollHeight,150)+'px'}
function down(){requestAnimationFrame(()=>scroll.scrollTo({top:scroll.scrollHeight,behavior:'smooth'}))}
function renderMd(t){try{return DOMPurify.sanitize(marked.parse(t))}catch(e){return null}}
function addMessage(role,text,save=true){empty.style.display='none';const row=document.createElement('div');row.className='row '+(role==='user'?'userrow':'');if(role==='assistant'){const wrap=document.createElement('div');wrap.className='assistantwrap';const av=document.createElement('div');av.className='aiavatar';av.textContent='K';const m=document.createElement('div');m.className='message assistant';const html=renderMd(text);if(html!==null)m.innerHTML=html;else m.textContent=text;wrap.append(av,m);row.append(wrap);if(window.MathJax)MathJax.typesetPromise([m]).catch(()=>{})}else{const m=document.createElement('div');m.className='message userbubble';m.textContent=text;row.append(m)}messages.append(row);if(save&&currentSession)currentSession.messages.push({role,text});down()}
function showThinking(){const row=document.createElement('div');row.className='row';row.id='thinking';row.innerHTML='<div class="assistantwrap"><div class="aiavatar">K</div><div class="message assistant thinking"><i class="dot"></i><i class="dot"></i><i class="dot"></i></div></div>';messages.append(row);down()}
function hideThinking(){document.getElementById('thinking')?.remove()}
function titleFrom(text){const t=text.replace(/\s+/g,' ').trim();return t.length>42?t.slice(0,42)+'…':t||'New Chat'}
function createSession(title='New Chat'){const s={id:Date.now()+Math.random(),title,messages:[]};sessions.unshift(s);currentSession=s;renderHistory();document.getElementById('conversationTitle').textContent=title;messages.innerHTML='';empty.style.display='flex';return s}
function renderHistory(){const box=document.getElementById('history');box.innerHTML='';const today=document.createElement('div');today.className='day';today.textContent='Today';box.append(today);sessions.forEach(s=>{const b=document.createElement('button');b.className='historyitem '+(s===currentSession?'active':'');b.dataset.id=s.id;b.innerHTML='<div class="chatglyph">□</div><div class="hcopy"><div class="htitle"></div><div class="hmeta"></div></div>';b.querySelector('.htitle').textContent=s.title;b.querySelector('.hmeta').textContent=s.messages.length?`${Math.ceil(s.messages.length/2)} message${s.messages.length/2>1?'s':''}`:'Empty chat';box.append(b)})}
function loadSession(s){currentSession=s;messages.innerHTML='';if(!s.messages.length)empty.style.display='flex';else{s.messages.forEach(m=>addMessage(m.role,m.text,false));empty.style.display='none'}document.getElementById('conversationTitle').textContent=s.title;renderHistory();document.body.classList.remove('sidebar-open');down()}
async function getToken(){const {data:{session}}=await supabaseClient.auth.getSession();return session?.access_token||''}
async function chat(prefill){const text=(prefill??input.value).trim();if(!text)return;const tok=await getToken();if(!tok){toastMsg('Sign in with Google to chat');return}if(!currentSession||currentSession.messages.length===0){if(!currentSession)createSession(titleFrom(text));else{currentSession.title=titleFrom(text);document.getElementById('conversationTitle').textContent=currentSession.title;renderHistory()}}addMessage('user',text);input.value='';resize();input.disabled=true;send.disabled=true;showThinking();try{const r=await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+tok},body:JSON.stringify({message:text})});const d=await r.json();hideThinking();if(r.status===401){toastMsg(d.reply||'Please sign in again');return}addMessage('assistant',d.reply||'No response received.')}catch(e){hideThinking();addMessage('assistant','Connection error: '+e.message)}finally{input.disabled=false;send.disabled=false;input.focus();renderHistory()}}
async function clearChat(){const tok=await getToken();if(tok)try{await fetch('/clear',{method:'POST',headers:{'Authorization':'Bearer '+tok}})}catch(e){}createSession();}
function updateAuth(){supabaseClient.auth.getSession().then(({data:{session}})=>{const status=document.getElementById('authStatus'),name=document.getElementById('accountName'),email=document.getElementById('accountEmail'),av=document.getElementById('avatar'),action=document.getElementById('accountAction');if(session?.user){const u=session.user;status.textContent='Signed in';name.textContent=u.user_metadata?.full_name||'Signed in';email.textContent=u.email||'Google account';const pic=u.user_metadata?.avatar_url||u.user_metadata?.picture;if(pic)av.innerHTML='<img alt="" src="'+String(pic).replace(/"/g,'&quot;')+'">';else av.textContent=(u.email||'K')[0].toUpperCase();action.textContent='Sign out'}else{status.textContent='Not signed in';name.textContent='Not signed in';email.textContent='Google sign-in available';av.textContent='K';action.textContent='Sign in with Google'}})}
document.getElementById('newChat').onclick=()=>{createSession();document.body.classList.remove('sidebar-open');input.focus()};document.getElementById('clear').onclick=clearChat;send.onclick=()=>chat();input.oninput=resize;input.onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();chat()}};document.querySelectorAll('.prompt').forEach(b=>b.onclick=()=>{input.value=b.dataset.p;resize();input.focus()});document.getElementById('history').onclick=e=>{const b=e.target.closest('.historyitem');if(b){const s=sessions.find(x=>String(x.id)===b.dataset.id);if(s)loadSession(s)}};document.getElementById('historySearch').oninput=e=>{const q=e.target.value.toLowerCase();document.querySelectorAll('.historyitem').forEach(x=>x.style.display=x.innerText.toLowerCase().includes(q)?'flex':'none')};document.getElementById('openSidebar').onclick=()=>document.body.classList.add('sidebar-open');document.getElementById('closeSidebar').onclick=()=>document.body.classList.remove('sidebar-open');document.getElementById('backdrop').onclick=()=>document.body.classList.remove('sidebar-open');document.getElementById('accountBtn').onclick=()=>document.getElementById('account').classList.toggle('open');document.getElementById('attach').onclick=()=>toastMsg('Attachment support is not connected yet');document.getElementById('voice').onclick=()=>{const R=window.SpeechRecognition||window.webkitSpeechRecognition;if(!R){toastMsg('Voice input is not supported here');return}const r=new R();r.lang='en-US';r.onresult=e=>{input.value=e.results[0][0].transcript;resize()};r.start()};document.getElementById('accountAction').onclick=async()=>{const {data:{session}}=await supabaseClient.auth.getSession();if(session){const {error}=await supabaseClient.auth.signOut();if(error)toastMsg(error.message);else location.reload()}else{const {error}=await supabaseClient.auth.signInWithOAuth({provider:'google',options:{redirectTo:window.location.origin}});if(error)toastMsg(error.message)}};supabaseClient.auth.onAuthStateChange(()=>updateAuth());
createSession();updateAuth();resize();
</script>
</body>
</html>
"""


@app.route("/")
def home():
    return render_template_string(HTML)
def get_supabase_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": "Bearer " + SUPABASE_KEY,
        "Content-Type": "application/json"
    }

@app.route("/chat", methods=["POST"])
def chat():

    data = request.get_json(
        silent=True
    ) or {}

    auth_header = request.headers.get("Authorization", "")
    access_token = ""

    if auth_header.startswith("Bearer "):
        access_token = auth_header[7:].strip()

    message = data.get(
        "message",
        ""
    ).strip()

    if not message:
        return jsonify({
            "reply": "Please enter a message."
        })

    if not access_token:
        return jsonify({
            "reply": "Please sign in first."
        }), 401

    try:
        user_response = requests.get(
            SUPABASE_URL + "/auth/v1/user",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": "Bearer " + access_token
            },
            timeout=10
        )

        if user_response.status_code != 200:
            return jsonify({
                "reply": "Your login session is invalid. Please sign in again."
            }), 401

        user_data = user_response.json()
        user_id = user_data.get("id")

        if not user_id:
            return jsonify({
                "reply": "Could not identify your account."
            }), 401

    except requests.RequestException:
        return jsonify({
            "reply": "Could not verify your login."
        }), 401

    answer = ask_kraven_ai(message, user_id)

    return jsonify({
        "reply": answer
    })


@app.route("/clear", methods=["POST"])
def clear():

    auth_header = request.headers.get("Authorization", "")
    access_token = ""

    if auth_header.startswith("Bearer "):
        access_token = auth_header[7:].strip()

    if not access_token:
        return jsonify({
            "status": "not signed in"
        }), 401

    try:
        user_response = requests.get(
            SUPABASE_URL + "/auth/v1/user",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": "Bearer " + access_token
            },
            timeout=10
        )

        if user_response.status_code != 200:
            return jsonify({
                "status": "invalid session"
            }), 401

        user_id = user_response.json().get("id")

        if user_id:
            conversation_histories.pop(user_id, None)

    except requests.RequestException:
        return jsonify({
            "status": "could not verify session"
        }), 401

    return jsonify({
        "status": "cleared"
    })


if __name__ == "__main__":

    print()
    print("==============================")
    print("          KRAVEN AI")
    print("==============================")
    print()
    print(
        "Kraven AI model:",
        MODEL
    )
    print(
        "http://127.0.0.1:" +
        str(PORT)
    )
    print()

    app.run(
        host="127.0.0.1",
        port=PORT,
        debug=False
    )
