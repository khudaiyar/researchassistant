/* ── State ────────────────────────────────────────────────────────────────── */
let lastThoughts        = [];
let conversations       = [];   // [{ id, title, html, history }]
let activeConvId        = null;
let conversationHistory = [];
let currentUser         = null;

/* ── DOM ──────────────────────────────────────────────────────────────────── */
const $homeView    = document.getElementById("home-view");
const $chatView    = document.getElementById("chat-view");
const $messages    = document.getElementById("messages");
const $homeInput   = document.getElementById("home-input");
const $chatInput   = document.getElementById("user-input");
const $sendBtn     = document.getElementById("send-btn");
const $thinking    = document.getElementById("thinking-bar");
const $statusDot   = document.getElementById("status-dot");
const $panel       = document.getElementById("panel");
const $panelTitle  = document.getElementById("panel-title");
const $overlay     = document.getElementById("overlay");
const $panelBody   = document.getElementById("panel-body");
const $recentsList = document.getElementById("recents-list");

/* ── Cycling placeholder ──────────────────────────────────────────────────── */
const PLACEHOLDERS = [
  "Search for recent papers on large language models…",
  "Who are the most cited researchers in computer vision?",
  "Find papers by Geoffrey Hinton published after 2020…",
  "What did Yann LeCun publish this year?",
  "Save this paper to my local database…",
  "List all NeurIPS 2023 papers in the database…",
  "Search for breakthroughs in reinforcement learning…",
  "Add a new researcher: name, university, research area…",
];
let phIndex = 0;
const $fakePh = document.getElementById("fake-placeholder");

function cyclePlaceholder() {
  if (!$fakePh) return;
  $fakePh.style.opacity = "0";
  setTimeout(() => {
    phIndex = (phIndex + 1) % PLACEHOLDERS.length;
    $fakePh.textContent = PLACEHOLDERS[phIndex];
    $fakePh.style.opacity = "1";
  }, 500);
}

function onHomeType() {
  if (!$fakePh) return;
  $fakePh.style.opacity = $homeInput.value.length > 0 ? "0" : "1";
}

/* ── Boot ─────────────────────────────────────────────────────────────────── */
window.addEventListener("DOMContentLoaded", () => {
  $chatInput?.addEventListener("input", () => autoResize($chatInput));
  if ($fakePh) {
    $fakePh.textContent = PLACEHOLDERS[0];
    $fakePh.style.opacity = "1";
    setInterval(cyclePlaceholder, 3200);
  }
  checkSession();
});

/* ── Smart title generation ───────────────────────────────────────────────── */
function generateTitle(text) {
  const t = text.trim();
  const lower = t.toLowerCase();

  // Greetings → fixed label
  const greetWords = ["hi", "hello", "hey", "hiya", "yo", "sup", "howdy",
                      "good morning", "good afternoon", "good evening", "good day"];
  if (greetWords.some(g => lower === g || lower.startsWith(g + " ") || lower.startsWith(g + "!"))) {
    return "Greeting";
  }

  // Strip leading filler verbs
  let title = t.replace(
    /^(find me|find|search for|search|look for|show me|show|list all|list|get me|get|give me|give|tell me about|tell me|what is|what are|who is|who are|can you|please|i want to know|i want|i need|help me with|help me|download|save|add)\s+/i,
    ""
  );

  // Capitalize first letter
  title = title.charAt(0).toUpperCase() + title.slice(1);

  // Trim to ~42 chars at word boundary
  if (title.length > 42) {
    const cut = title.slice(0, 42);
    const lastSpace = cut.lastIndexOf(" ");
    title = (lastSpace > 20 ? cut.slice(0, lastSpace) : cut) + "…";
  }

  return title || t.slice(0, 42);
}

/* ── Conversation store ───────────────────────────────────────────────────── */
function saveCurrentConversation() {
  if (!$messages.innerHTML.trim()) return;
  const existing = conversations.find(c => c.id === activeConvId);
  if (existing) {
    existing.html    = $messages.innerHTML;
    existing.history = [...conversationHistory];
  } else {
    const id    = Date.now();
    const title = generateTitle(conversationHistory[0]?.content || "Conversation");
    conversations.unshift({ id, title, html: $messages.innerHTML, history: [...conversationHistory] });
    if (conversations.length > 10) conversations.pop();
    activeConvId = id;
  }
  renderRecents();
}

function restoreConversation(id) {
  saveCurrentConversation();
  const conv = conversations.find(c => c.id === id);
  if (!conv) return;
  activeConvId        = conv.id;
  $messages.innerHTML = conv.html;
  conversationHistory = [...conv.history];
  $messages.scrollTop = $messages.scrollHeight;
  showChat();
  renderRecents();
}

function deleteConversation(id, e) {
  e.stopPropagation();
  conversations = conversations.filter(c => c.id !== id);
  if (activeConvId === id) {
    activeConvId        = null;
    conversationHistory = [];
    $messages.innerHTML = "";
    $homeView.style.display = "flex";
    $chatView.style.display = "none";
  }
  renderRecents();
}

/* ── Navigation ───────────────────────────────────────────────────────────── */
function goHome() {
  saveCurrentConversation();
  $chatView.style.display = "none";
  $homeView.style.display = "flex";
  setNavActive("home");
}

function newConversation() {
  saveCurrentConversation();
  activeConvId        = null;
  conversationHistory = [];
  $messages.innerHTML = "";
  $homeView.style.display = "flex";
  $chatView.style.display = "none";
  setNavActive("home");
}

function showChat() {
  $homeView.style.display = "none";
  $chatView.style.display = "flex";
  setTimeout(() => $chatInput?.focus(), 50);
}

/* ── Quick query from suggestion / chip ───────────────────────────────────── */
function quickQuery(text) {
  if ($chatView.style.display !== "flex") showChat();
  sendQuery(text);
}

/* ── Send from home input ─────────────────────────────────────────────────── */
function sendFromHome() {
  const text = $homeInput.value.trim();
  if (!text) return;
  $homeInput.value = "";
  // Save any current conversation, then start a fresh one
  saveCurrentConversation();
  activeConvId        = null;
  conversationHistory = [];
  $messages.innerHTML = "";
  showChat();
  sendQuery(text);
}

function handleHomeKey(e) {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendFromHome();
  }
}

/* ── Send from chat input ─────────────────────────────────────────────────── */
function sendMessage(e) {
  if (e) e.preventDefault();
  const text = $chatInput.value.trim();
  if (!text) return;
  $chatInput.value = "";
  autoResize($chatInput);
  sendQuery(text);
}

function handleKey(e) {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage(null);
  }
}

/* ── Core send ────────────────────────────────────────────────────────────── */
async function sendQuery(text) {
  appendMsg("user", text);
  setLoading(true);

  // Register conversation on first message
  if (!activeConvId) {
    const id    = Date.now();
    const title = generateTitle(text);
    conversations.unshift({ id, title, html: "", history: [] });
    if (conversations.length > 10) conversations.pop();
    activeConvId = id;
    renderRecents();
  }

  try {
    const res  = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, history: conversationHistory }),
    });
    const data = await res.json();

    if (data.error) {
      appendMsg("ai", `Error: ${data.error}`, { error: true });
    } else {
      lastThoughts = data.thoughts || [];
      appendMsg("ai", data.answer, { showReasoning: true });
      conversationHistory.push({ role: "user",      content: text });
      conversationHistory.push({ role: "assistant", content: data.answer });
      if (conversationHistory.length > 10) conversationHistory.splice(0, 2);

      // Sync saved conversation
      const conv = conversations.find(c => c.id === activeConvId);
      if (conv) { conv.html = $messages.innerHTML; conv.history = [...conversationHistory]; }

      // Trigger browser download if agent downloaded a file
      if (data.download_url) {
        const a = document.createElement("a");
        a.href = data.download_url;
        a.download = "";
        a.style.display = "none";
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
      }
    }
  } catch (err) {
    appendMsg("ai", `Network error: ${err.message}`, { error: true });
  }

  setLoading(false);
}

/* ── Render message ───────────────────────────────────────────────────────── */
function appendMsg(role, text, opts = {}) {
  const div = document.createElement("div");
  div.className = `msg ${role}${opts.error ? " error" : ""}`;

  const speaker   = role === "user" ? "You" : "Atlas";
  const reasoning = opts.showReasoning
    ? `<button class="reasoning-link" onclick="openPanel('reasoning')">
         <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
           <circle cx="6" cy="6" r="4.5" stroke="currentColor" stroke-width="1.3"/>
           <path d="M6 4v3l1.5 1.5" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>
         </svg>
         View reasoning
       </button>`
    : "";

  div.innerHTML = `
    <div class="msg-speaker">${speaker}</div>
    <div class="msg-body">${renderText(text)}</div>
    ${reasoning}
  `;

  $messages.appendChild(div);
  $messages.scrollTop = $messages.scrollHeight;
}

/* ── Text renderer ────────────────────────────────────────────────────────── */
function renderText(raw) {
  const lines = esc(raw).split("\n");
  const out   = [];
  for (const line of lines) {
    if (!line.trim()) continue;
    const l = line
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/`([^`]+)`/g, "<code>$1</code>");
    out.push(`<p>${l}</p>`);
  }
  return out.join("") || `<p>${esc(raw)}</p>`;
}

/* ── Loading state ────────────────────────────────────────────────────────── */
function setLoading(on) {
  $thinking.style.display = on ? "flex" : "none";
  if ($sendBtn)   $sendBtn.disabled   = on;
  if ($chatInput) $chatInput.disabled = on;
  if ($statusDot) $statusDot.className = on ? "status-dot working" : "status-dot active";
  if (on)  $messages.scrollTop = $messages.scrollHeight;
  if (!on && $chatInput) $chatInput.focus();
}

/* ── Recents ──────────────────────────────────────────────────────────────── */
function renderRecents() {
  if (!conversations.length) {
    $recentsList.innerHTML = `<li class="recents-empty">No recent conversations</li>`;
    return;
  }
  $recentsList.innerHTML = conversations.map(c => {
    const isActive = c.id === activeConvId;
    return `<li onclick="restoreConversation(${c.id})" style="${isActive ? "color:#e8e8e8;font-weight:500" : ""}">
      <span class="recent-title">${esc(c.title)}</span>
      <button class="recent-del" title="Delete" onclick="deleteConversation(${c.id}, event)">×</button>
    </li>`;
  }).join("");
}

/* ── Panel: reasoning or DB data ──────────────────────────────────────────── */
function openPanel(mode) {
  if (mode === "reasoning") {
    $panelTitle.textContent = "Reasoning trace";
    $panelBody.style.fontFamily  = "'JetBrains Mono', monospace";
    $panelBody.style.fontSize    = "11.5px";
    $panelBody.style.whiteSpace  = "pre-wrap";
    $panelBody.style.lineHeight  = "1.8";
    $panelBody.textContent = lastThoughts.join("\n\n─────────────────────────\n\n");
  }
  $panel.classList.add("open");
  $overlay.classList.add("open");
}

function closePanel() {
  $panel.classList.remove("open");
  $overlay.classList.remove("open");
}

/* ── Papers / Researchers panels (no new conversation) ────────────────────── */
async function showPapers() {
  $panelTitle.textContent      = "Papers";
  $panelBody.style.fontFamily  = "var(--font)";
  $panelBody.style.fontSize    = "13px";
  $panelBody.style.whiteSpace  = "normal";
  $panelBody.style.lineHeight  = "1.6";
  $panelBody.innerHTML = `<p style="color:var(--muted);font-style:italic">Loading…</p>`;
  $panel.classList.add("open");
  $overlay.classList.add("open");

  try {
    const papers = await (await fetch("/api/papers")).json();
    if (!Array.isArray(papers) || !papers.length) {
      $panelBody.innerHTML = `<p style="color:var(--muted);font-style:italic">No papers in the database yet.</p>`;
    } else {
      $panelBody.innerHTML = papers.map(p => `
        <div class="db-entry">
          <div class="db-entry-title">${esc(p.title)}</div>
          <div class="db-entry-meta">${esc(p.authors || "—")} &nbsp;·&nbsp; ${p.year || "?"} &nbsp;·&nbsp; ${esc(p.venue || "?")}</div>
          ${p.url ? `<div class="db-entry-url">${esc(p.url)}</div>` : ""}
        </div>
      `).join("");
    }
  } catch (_) {
    $panelBody.innerHTML = `<p style="color:#ef4444">Error loading papers.</p>`;
  }
}

async function showResearchers() {
  $panelTitle.textContent      = "Researchers";
  $panelBody.style.fontFamily  = "var(--font)";
  $panelBody.style.fontSize    = "13px";
  $panelBody.style.whiteSpace  = "normal";
  $panelBody.style.lineHeight  = "1.6";
  $panelBody.innerHTML = `<p style="color:var(--muted);font-style:italic">Loading…</p>`;
  $panel.classList.add("open");
  $overlay.classList.add("open");

  try {
    const rows = await (await fetch("/api/researchers")).json();
    if (!Array.isArray(rows) || !rows.length) {
      $panelBody.innerHTML = `<p style="color:var(--muted);font-style:italic">No researchers in the database yet.</p>`;
    } else {
      $panelBody.innerHTML = rows.map(r => `
        <div class="db-entry">
          <div class="db-entry-title">${esc(r.name)}</div>
          <div class="db-entry-meta">${esc(r.affiliation || "—")}</div>
          <div class="db-entry-meta">${esc(r.research_area || "—")}</div>
        </div>
      `).join("");
    }
  } catch (_) {
    $panelBody.innerHTML = `<p style="color:#ef4444">Error loading researchers.</p>`;
  }
}

/* ── Clear ────────────────────────────────────────────────────────────────── */
function clearChat() {
  $messages.innerHTML = "";
  conversationHistory = [];
  const conv = conversations.find(c => c.id === activeConvId);
  if (conv) { conv.html = ""; conv.history = []; }
}

/* ── Nav active state ─────────────────────────────────────────────────────── */
function setNavActive(id) {
  document.querySelectorAll(".nav-item").forEach(el => el.classList.remove("active"));
}

/* ── Auth: check existing session ────────────────────────────────────────── */
async function checkSession() {
  try {
    const d = await (await fetch("/auth/me", { credentials: "include" })).json();
    if (d.logged_in) setLoggedIn(d.name, d.email, d.is_admin);
  } catch (_) {}
}

/* ── Auth: update UI ──────────────────────────────────────────────────────── */
function setLoggedIn(name, email, is_admin = false) {
  currentUser = { name, email, is_admin };
  document.getElementById("open-auth-btn").style.display = "none";
  const row = document.getElementById("user-row");
  row.style.display = "flex";
  document.getElementById("user-avatar").textContent      = name.charAt(0).toUpperCase();
  document.getElementById("user-name-label").textContent  = name;
  document.getElementById("user-email-label").textContent = email;
  const adminLink = document.getElementById("admin-nav-link");
  if (adminLink) adminLink.style.display = is_admin ? "flex" : "none";
  // Mobile topbar
  const mobSignin = document.getElementById("mob-signin-btn");
  const mobUser   = document.getElementById("mob-user-row");
  const mobName   = document.getElementById("mob-user-name");
  if (mobSignin) mobSignin.style.display = "none";
  if (mobUser)   mobUser.style.display   = "flex";
  if (mobName)   mobName.textContent     = name;
}

function setLoggedOut() {
  currentUser = null;
  document.getElementById("open-auth-btn").style.display = "flex";
  document.getElementById("user-row").style.display      = "none";
  // Mobile topbar
  const mobSignin = document.getElementById("mob-signin-btn");
  const mobUser   = document.getElementById("mob-user-row");
  if (mobSignin) mobSignin.style.display = "flex";
  if (mobUser)   mobUser.style.display   = "none";
}

/* ── Auth: open / close modal ─────────────────────────────────────────────── */
function openAuth(tab = "signin") {
  document.getElementById("modal-backdrop").classList.add("open");
  document.getElementById("auth-modal").classList.add("open");
  switchTab(tab);
}

function closeAuth() {
  document.getElementById("modal-backdrop").classList.remove("open");
  document.getElementById("auth-modal").classList.remove("open");
  document.getElementById("signin-error").textContent   = "";
  document.getElementById("register-error").textContent = "";
}

/* ── Auth: switch tabs ────────────────────────────────────────────────────── */
function switchTab(tab) {
  const isSignin = tab === "signin";
  document.getElementById("tab-signin").classList.toggle("active", isSignin);
  document.getElementById("tab-register").classList.toggle("active", !isSignin);
  document.getElementById("form-signin").style.display   = isSignin ? "block" : "none";
  document.getElementById("form-register").style.display = isSignin ? "none"  : "block";
}

/* ── Auth: sign in ────────────────────────────────────────────────────────── */
async function submitSignIn(e) {
  e.preventDefault();
  const btn   = document.getElementById("signin-btn");
  const errEl = document.getElementById("signin-error");
  errEl.textContent = "";
  btn.disabled = true;
  btn.textContent = "Signing in…";

  try {
    const res  = await fetch("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({
        email:    document.getElementById("signin-email").value.trim(),
        password: document.getElementById("signin-password").value,
      }),
    });
    const data = await res.json();
    if (data.error) {
      errEl.textContent = data.error;
    } else {
      setLoggedIn(data.name, data.email, data.is_admin);
      closeAuth();
      if (data.is_admin) window.location.href = "/admin";
    }
  } catch (_) {
    errEl.textContent = "Network error. Please try again.";
  }

  btn.disabled = false;
  btn.textContent = "Sign in";
}

/* ── Auth: register ───────────────────────────────────────────────────────── */
async function submitRegister(e) {
  e.preventDefault();
  const btn   = document.getElementById("register-btn");
  const errEl = document.getElementById("register-error");
  errEl.textContent = "";
  btn.disabled = true;
  btn.textContent = "Creating account…";

  const password = document.getElementById("reg-password").value;
  const confirm  = document.getElementById("reg-confirm").value;
  if (password !== confirm) {
    errEl.textContent = "Passwords do not match.";
    btn.disabled = false;
    btn.textContent = "Create account";
    return;
  }

  try {
    const res  = await fetch("/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({
        name:     document.getElementById("reg-name").value.trim(),
        email:    document.getElementById("reg-email").value.trim(),
        password,
      }),
    });
    const data = await res.json();
    if (data.error) {
      errEl.textContent = data.error;
    } else {
      setLoggedIn(data.name, data.email, data.is_admin);
      closeAuth();
    }
  } catch (_) {
    errEl.textContent = "Network error. Please try again.";
  }

  btn.disabled = false;
  btn.textContent = "Create account";
}

/* ── Auth: sign out ───────────────────────────────────────────────────────── */
async function signOut() {
  await fetch("/auth/logout", { method: "POST", credentials: "include" });
  setLoggedOut();
}

/* ── Utils ────────────────────────────────────────────────────────────────── */
function autoResize(el) {
  el.style.height = "auto";
  el.style.height = Math.min(el.scrollHeight, 160) + "px";
}

function esc(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
