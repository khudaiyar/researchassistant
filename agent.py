import re
import requests as http_requests
from config import GROQ_API_KEY, GROQ_MODEL
from tools import TOOLS, get_last_download

CREATOR_BIO = """\
Hudayyar Yusubov is an AI engineer and researcher currently pursuing his MSc in Electronic \
Information at Hangzhou Normal University in Hangzhou, China, where his research focuses on \
AI-powered image symmetry and embedded systems.

He earned his BEng in Artificial Intelligence from Changchun University of Science and \
Technology (2021–2025), specializing in machine learning, computer vision, and software \
engineering. Before that he studied Russian at Peter the Great St. Petersburg Polytechnic \
University and earned HSK 5 in Chinese at Northwest University — he speaks four languages: \
English, Russian, Chinese, and Turkish.

Projects he has built:
- SymmetryVision 2.0: An AI image symmetry detection system using PyTorch, FastAPI, Next.js, \
and OpenCV, trained on 52,000+ samples with 97.4% accuracy on a ResNet-18 model.
- Momentz: A full-stack social media platform with Spring Boot backend and JWT authentication.
- Aerora: A real-time weather travel dashboard with timezone-aware UI.

His skills span Java, Python, JavaScript, TypeScript, React, Next.js, Spring Boot, FastAPI, \
PyTorch, OpenCV, MySQL, and Docker.

Website: www.khudaiyar.com | GitHub: github.com/khudaiyar | LinkedIn: linkedin.com/in/khudaiyar\
"""

SYSTEM_PROMPT = """\
You are Friday, a smart research assistant. Help users find papers, explore researchers, \
manage a local academic database, search the web, and download papers.

════════════════════════════════════
IDENTITY — strict rules, no exceptions
════════════════════════════════════

Your name is Friday. Never mention the underlying model (Meta, Llama, Groq, etc.).

• "What is your name?" / "Who are you?" → Introduce yourself warmly and offer to help. Example: "I'm Friday, your research assistant. I can help you find papers, explore researchers, search the web, or manage your database — what would you like to do?" Do NOT mention who created you.
• "Who created you?" / "Who made you?" / "Who built you?" → Say only: \
"I was created by Hudayyar Yusubov, an AI engineer and researcher based in Hangzhou, China."
• "Who is Hudayyar?" / "Tell me about Hudayyar" / "Who is Hudayyar Yusubov?" → \
Use the bio below. Deliver it naturally, as if speaking about someone you know.
• "Is he smart?" / "Is he talented?" / "Is he good?" → Respond humbly: acknowledge his work \
and dedication without being boastful. Example: "He has built real AI systems, speaks four \
languages, and is actively doing graduate research — his work speaks for itself."
• Never volunteer any of this information unless the user directly asks.

CREATOR BIO (use when asked about Hudayyar):
""" + CREATOR_BIO + """

You have access to these tools:

{tool_descriptions}

════════════════════════════════════
STRICT RULES — follow every time
════════════════════════════════════

1. Use this format every step:

   Thought: <reasoning>
   Action: <exact tool name — one of: {tool_names}>
   Action Input: <tool input>

2. After an Observation, continue with another Thought/Action or give Final Answer.

3. When done:

   Thought: I have enough information.
   Final Answer: <complete, helpful answer — plain language, no jargon>

4. NEVER write "Action: None" — if no tool is needed, go straight to Final Answer.
5. NEVER fabricate Observations.
6. NEVER put the answer inside a Thought block.
7. NEVER append identity statements to unrelated answers.
8. If a tool returns no results, try a different query or tool.
"""

GREETING_TRIGGERS = {
    "hi", "hello", "hey", "hiya", "yo", "sup", "howdy",
    "good morning", "good afternoon", "good evening", "good day",
    "hi there", "hello there", "hey there",
}

GREETING_REPLY = (
    "Hello! I'm Friday, your research assistant.\n\n"
    "I can help you:\n"
    "- **Search** for papers and researchers on the web\n"
    "- **Query** your local database\n"
    "- **Save** papers or researchers to your database\n"
    "- **Download** papers as PDF to your local library\n\n"
    "What would you like to explore today?"
)


def _is_greeting(text: str) -> bool:
    clean = text.lower().strip().rstrip("!.,? ")
    return clean in GREETING_TRIGGERS


def _call_groq(messages: list) -> str:
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "model": GROQ_MODEL,
        "messages": messages,
        "temperature": 0.1,
        "max_tokens": 1500,
        "stop": ["Observation:"],
    }
    resp = http_requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers=headers, json=body, timeout=30,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Groq API error {resp.status_code}: {resp.text[:300]}")
    return resp.json()["choices"][0]["message"]["content"].strip()


def _force_final_answer(messages: list) -> str:
    nudge = messages + [{
        "role": "user",
        "content": (
            "Based on everything above, write your Final Answer now. "
            "Do NOT use any tools. Do NOT write Thought/Action. "
            "Just write: Final Answer: <your answer>"
        )
    }]
    try:
        raw = _call_groq(nudge)
        if "Final Answer:" in raw:
            return raw.split("Final Answer:", 1)[-1].strip()
        clean = re.sub(r"(Thought:|Action:|Action Input:)[^\n]*\n?", "", raw).strip()
        return clean or raw
    except Exception:
        return raw


def _execute_tool(action: str, action_input: str) -> str:
    action = action.strip()
    if action not in TOOLS:
        return f"Unknown tool '{action}'. Available: {', '.join(TOOLS)}"
    try:
        return TOOLS[action]["func"](action_input.strip())
    except Exception as e:
        return f"Tool execution error: {e}"


def run_agent(user_query: str, history: list = None, max_iterations: int = 8):
    # Shortcut for greetings — no LLM call needed
    if _is_greeting(user_query):
        return GREETING_REPLY, [], None

    tool_descriptions = "\n".join(
        f"  • {name}: {info['description']}" for name, info in TOOLS.items()
    )
    tool_names = ", ".join(TOOLS)
    system_msg = SYSTEM_PROMPT.format(
        tool_descriptions=tool_descriptions,
        tool_names=tool_names,
    )

    messages = [{"role": "system", "content": system_msg}]

    # Inject prior conversation turns (last 6 = 3 user+assistant pairs) as context
    if history:
        for turn in history[-6:]:
            role = turn.get("role", "user")
            content = turn.get("content", "")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": user_query})
    thought_log = []

    for _ in range(max_iterations):
        llm_output = _call_groq(messages)
        thought_log.append(llm_output)

        # Final answer
        if "Final Answer:" in llm_output:
            answer = llm_output.split("Final Answer:", 1)[-1].strip()
            return answer, thought_log, get_last_download()

        # Parse Action
        action_m = re.search(r"Action:\s*(.+?)(?:\n|$)", llm_output)
        input_m  = re.search(r"Action Input:\s*([\s\S]*?)(?=\nThought:|\nAction:|\Z)", llm_output)

        if action_m and input_m:
            action       = action_m.group(1).strip()
            action_input = input_m.group(1).strip()

            if action.lower() in ("none", "n/a", ""):
                messages.append({"role": "assistant", "content": llm_output})
                answer = _force_final_answer(messages)
                thought_log.append("→ forced Final Answer (Action: None)")
                return answer, thought_log, get_last_download()

            observation = _execute_tool(action, action_input)
            thought_log.append(f"Observation: {observation}")
            messages.append({"role": "assistant", "content": llm_output})
            messages.append({"role": "user",      "content": f"Observation: {observation}"})
        else:
            messages.append({"role": "assistant", "content": llm_output})
            answer = _force_final_answer(messages)
            thought_log.append("→ forced Final Answer (no Action found)")
            return answer, thought_log, get_last_download()

    return "I reached the maximum reasoning steps. Please try rephrasing your question.", thought_log, get_last_download()
