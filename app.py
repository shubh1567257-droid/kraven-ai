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
<!DOCTYPE html>
<html>
<head>

<meta charset="UTF-8">

<meta name="viewport"
      content="width=device-width, initial-scale=1">

<title>KRAVEN AI</title>

<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>

<script src="https://cdn.jsdelivr.net/npm/dompurify@3.2.6/dist/purify.min.js"></script>

<script>
window.MathJax = {
    tex: {
        inlineMath: [['\\(', '\\)']],
        displayMath: [['\\[', '\\]']]
    },
    svg: {
        fontCache: 'global'
    }
};
</script>

<script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js"></script>

<style>

* {
    box-sizing: border-box;
}

body {
    margin: 0;
    background: #080b12;
    color: #f5f7fb;
    font-family: Arial, Helvetica, sans-serif;
}

header {
    position: sticky;
    top: 0;
    z-index: 10;
    background: rgba(8,11,18,.96);
    border-bottom: 1px solid #263244;
    backdrop-filter: blur(10px);
}

.header-inner {
    max-width: 950px;
    margin: auto;
    padding: 15px;
    display: flex;
    align-items: center;
    justify-content: space-between;
}

.brand {
    display: flex;
    align-items: center;
    gap: 10px;
}

.logo {
    width: 42px;
    height: 42px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: #2563eb;
    font-size: 20px;
    font-weight: bold;
}

.title {
    font-size: 20px;
    font-weight: bold;
}

.model {
    color: #60a5fa;
    font-size: 12px;
    margin-top: 3px;
}

.clear-button {
    background: transparent;
    color: #cbd5e1;
    border: 1px solid #334155;
    padding: 8px 12px;
    border-radius: 9px;
    cursor: pointer;
}

.clear-button:hover {
    background: #151b24;
}

#messages {
    max-width: 950px;
    margin: auto;
    padding: 24px 16px 130px;
}

.message-row {
    display: flex;
    margin: 14px 0;
}

.user-row {
    justify-content: flex-end;
}

.message {
    max-width: 82%;
    padding: 13px 16px;
    border-radius: 16px;
    line-height: 1.55;
    overflow-wrap: anywhere;
}

.user {
    background: #2563eb;
    border-bottom-right-radius: 5px;
}

.assistant {
    background: #151b24;
    border: 1px solid #293548;
    border-bottom-left-radius: 5px;
}

.message p:first-child {
    margin-top: 0;
}

.message p:last-child {
    margin-bottom: 0;
}

.message pre {
    overflow-x: auto;
    background: #090d14;
    padding: 12px;
    border-radius: 10px;
}

.message code {
    font-family: monospace;
}

.thinking {
    display: flex;
    gap: 5px;
    align-items: center;
}

.dot {
    width: 7px;
    height: 7px;
    background: #60a5fa;
    border-radius: 50%;
    animation: pulse 1.2s infinite;
}

.dot:nth-child(2) {
    animation-delay: .15s;
}

.dot:nth-child(3) {
    animation-delay: .30s;
}

@keyframes pulse {
    0%, 80%, 100% {
        opacity: .25;
        transform: translateY(0);
    }

    40% {
        opacity: 1;
        transform: translateY(-3px);
    }
}

.input-area {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    z-index: 20;
    padding: 12px;
    background: rgba(8,11,18,.97);
    border-top: 1px solid #263244;
    backdrop-filter: blur(10px);
}

.input-box {
    max-width: 950px;
    margin: auto;
    display: flex;
    gap: 9px;
}

#input {
    flex: 1;
    min-width: 0;
    padding: 14px 15px;
    border-radius: 12px;
    border: 1px solid #303d50;
    background: #151b24;
    color: white;
    font-size: 16px;
    outline: none;
}

#input:focus {
    border-color: #3b82f6;
}

#send {
    padding: 0 20px;
    border: none;
    border-radius: 12px;
    background: #2563eb;
    color: white;
    font-weight: bold;
    cursor: pointer;
}

#send:disabled {
    opacity: .55;
    cursor: not-allowed;
}

.empty {
    text-align: center;
    color: #64748b;
    padding-top: 25vh;
}

@media (max-width: 600px) {

    .header-inner {
        padding: 12px;
    }

    .logo {
        width: 38px;
        height: 38px;
    }

    .title {
        font-size: 17px;
    }

    .message {
        max-width: 92%;
        font-size: 15px;
    }

    #messages {
        padding-left: 10px;
        padding-right: 10px;
    }

    #send {
        padding: 0 15px;
    }
}

</style>
<script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>
</head>

<body>
<div style="text-align:center; padding:15px;">
    <button id="googleSignInButton">
        Sign in with Google
    </button>
</div>
<header>

<div class="header-inner">

<div class="brand">

<div class="logo">K</div>

<div>
<div class="title">KRAVEN AI</div>
<div class="model">KRAVEN 1.0 TITAN</div>
</div>

</div>

<button
    class="clear-button"
    id="clear">
    Clear
</button>

</div>

</header>
<div id="authStatus" style="text-align:center;padding:10px;"></div>
<button id="signOutButton" style="display:block;margin:0 auto 15px;">
    Sign out
</button>
<div id="messages">

<div class="empty" id="empty">

<h2>KRAVEN AI</h2>

<p>Ask anything.</p>

</div>

</div>


<div class="input-area">

<div class="input-box">

<input
    id="input"
    autocomplete="off"
    placeholder="Message Kraven AI..."
>

<button id="send">Send</button>

</div>

</div>


<script>

const input = document.getElementById("input");
const send = document.getElementById("send");
const clearButton = document.getElementById("clear");
const messages = document.getElementById("messages");


function scrollDown() {
    window.scrollTo({
        top: document.body.scrollHeight,
        behavior: "smooth"
    });
}


function addMessage(role, text) {

    const empty =
        document.getElementById("empty");

    if (empty) {
        empty.remove();
    }

    const row =
        document.createElement("div");

    row.className =
        "message-row " +
        (role === "user"
            ? "user-row"
            : "assistant-row");

    const div =
        document.createElement("div");

    div.className =
        "message " +
        (role === "user"
            ? "user"
            : "assistant");

    if (role === "assistant") {

        try {

            const rendered =
                marked.parse(text);

            div.innerHTML =
                DOMPurify.sanitize(rendered);

        } catch (error) {

            div.textContent = text;

        }

    } else {

        div.textContent = text;

    }

    row.appendChild(div);
    messages.appendChild(row);

    if (
        window.MathJax &&
        typeof MathJax.typesetPromise === "function"
    ) {

        MathJax.typesetPromise([div])
            .catch(function(error) {
                console.warn(
                    "Math rendering error:",
                    error
                );
            });

    }

    scrollDown();
}


function addThinking() {

    const row =
        document.createElement("div");

    row.className =
        "message-row assistant-row";

    row.id = "thinking-row";

    row.innerHTML = `
        <div class="message assistant thinking">
            <span class="dot"></span>
            <span class="dot"></span>
            <span class="dot"></span>
        </div>
    `;

    messages.appendChild(row);

    scrollDown();
}


function removeThinking() {

    const thinking =
        document.getElementById(
            "thinking-row"
        );

    if (thinking) {
        thinking.remove();
    }
}


async function sendMessage() {

    const text =
        input.value.trim();

    if (!text) {
        return;
    }

    addMessage("user", text);

    input.value = "";
    input.disabled = true;
    send.disabled = true;

    addThinking();

    try {

        const response =
            await fetch(
                "/chat",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json",
                        "Authorization":
                            "Bearer " + (
                                (await supabaseClient.auth.getSession()).data.session?.access_token || ""
                            )
                    },

                    body:
                        JSON.stringify({
                            message: text
                        })
                }
            );

        const data =
            await response.json();

        removeThinking();

        addMessage(
            "assistant",
            data.reply ||
            "No response received."
        );

    } catch (error) {

        removeThinking();

        addMessage(
            "assistant",
            "Connection error: " +
            error.message
        );
    }

    input.disabled = false;
    send.disabled = false;
    input.focus();
}


async function clearChat() {

    try {

        await fetch(
            "/clear",
            {
                method: "POST",
                headers: {
                    "Authorization":
                        "Bearer " + (
                            (await window.supabaseClient.auth.getSession()).data.session?.access_token || ""
                        )
                }
            }
        );

    } catch (error) {

        console.warn(
            "Could not clear memory:",
            error
        );
    }

    messages.innerHTML = `
        <div class="empty" id="empty">
            <h2>KRAVEN AI</h2>
            <p>Ask anything.</p>
        </div>
    `;

    input.focus();
}


send.addEventListener(
    "click",
    sendMessage
);


clearButton.addEventListener(
    "click",
    clearChat
);


input.addEventListener(
    "keydown",
    function(event) {

        if (
            event.key === "Enter" &&
            !event.shiftKey
        ) {

            event.preventDefault();
            sendMessage();

        }

    }
);


input.focus();

</script>
<script>
const SUPABASE_URL = "https://czewyhjowsmgcnucxdrk.supabase.co";
const SUPABASE_ANON_KEY = "sb_publishable_K7oJRO_0PajMI9PKu13tZw_lhu3Sbsc";

const script = document.createElement("script");
script.src = "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2";

script.onload = async function() {
    window.supabaseClient = window.supabase.createClient(
        SUPABASE_URL,
        SUPABASE_ANON_KEY
    );

    document.getElementById("signOutButton").addEventListener("click", async function() {
        const { error } = await window.supabaseClient.auth.signOut();

        if (error) {
            alert(error.message);
        } else {
            location.reload();
        }
    });

    const status = document.getElementById("authStatus");
    const button = document.getElementById("googleSignInButton");

    button.addEventListener("click", async function() {
        const { error } = await window.supabaseClient.auth.signInWithOAuth({
            provider: "google",
            options: {
                redirectTo: window.location.origin
            }
        });

        if (error) alert(error.message);
    });

    async function updateAuthStatus() {
        const { data: { session } } =
            await window.supabaseClient.auth.getSession();

        if (session && session.user) {
            status.textContent =
                "Signed in as " + (session.user.email || "Google user");
        } else {
            status.textContent = "Not signed in";
        }
    }

    window.supabaseClient.auth.onAuthStateChange(function() {
        updateAuthStatus();
    });

    await updateAuthStatus();
};

document.head.appendChild(script);



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
