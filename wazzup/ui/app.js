// wazzup browser UI — section 13 of the lesson.
//
// Plain fetch + DOM updates, no framework. Every interaction is the same
// shape: fetch → check status → parse JSON → update DOM.
//
// User-facing surface (post v0.2): two concepts only — **People** (the
// users you can DM) and **Topics** (public rooms). Conversations are
// internal plumbing; the word never appears in the UI.
//
// Auth in dev mode is just the X-User-Slug header (server is run with
// AUTH_DISABLED=1). When real auth lands, the only place that changes is
// authHeaders() — the rest of this file doesn't know.

const API = "http://localhost:8000";
const USER_SLUG_KEY = "wazzup.user_slug";

// Module state.
//
// ``currentConvSlug`` / ``Id`` / ``Name`` track which conversation is
// currently displayed. The conversation can be either a topic's
// default conversation or a DM — the UI doesn't care which; the slug
// + id are enough to load and post messages.
//
// ``currentUserName`` is cached at login (``renderUserInfo``) so the
// optimistic-render path can show the right display name on the
// message *before* the server roundtrip completes.
let currentConvSlug = null;
let currentConvId = null;
let currentConvName = null;
let currentUserName = null;


// ----- auth + fetch wrapper -----

function getCurrentUserSlug() {
  return localStorage.getItem(USER_SLUG_KEY) || "alice";
}

function setCurrentUserSlug(slug) {
  localStorage.setItem(USER_SLUG_KEY, slug);
}

function applyUrlSlugOverride() {
  // ``?as=<slug>`` URL param is a one-time bootstrap for power users
  // and demos: open multiple tabs with different identities by URL.
  // We write the slug to localStorage, then *strip* the param via
  // ``history.replaceState`` so the dropdown becomes the persistent
  // control in this tab — without the strip, every reload would
  // override whatever the user just picked from the dropdown.
  const params = new URLSearchParams(window.location.search);
  const as = params.get("as");
  if (!as) return;
  setCurrentUserSlug(as);
  params.delete("as");
  const newSearch = params.toString();
  const newUrl = window.location.pathname
    + (newSearch ? "?" + newSearch : "")
    + window.location.hash;
  window.history.replaceState({}, "", newUrl);
}

function authHeaders() {
  return {
    "X-User-Slug": getCurrentUserSlug(),
    "Content-Type": "application/json",
  };
}

async function fetchAPI(path, options = {}) {
  // Single fetch wrapper: attaches auth headers, parses JSON, throws on
  // non-2xx with the server's `detail` message when available. Every
  // load/post helper sits on top of this.
  const r = await fetch(`${API}${path}`, {
    ...options,
    headers: { ...authHeaders(), ...(options.headers || {}) },
  });
  if (!r.ok) {
    let detail;
    try { detail = (await r.json()).detail; } catch { /* non-JSON body */ }
    throw new Error(`${r.status} ${r.statusText}${detail ? `: ${detail}` : ""}`);
  }
  // Some endpoints (POST 201) might return a body, others might not — try
  // to parse JSON but tolerate empty bodies.
  const text = await r.text();
  return text ? JSON.parse(text) : null;
}


// ----- UI helpers -----

function showError(msg) {
  const b = document.getElementById("error-banner");
  b.textContent = msg;
  b.hidden = false;
  setTimeout(() => { b.hidden = true; }, 5000);
}

function highlightSelected(ul, target) {
  // Visual feedback: mark the clicked <li> and unmark its siblings (and
  // any selection in the *other* sidebar list — selecting a person
  // should clear any topic highlight, and vice versa).
  for (const list of document.querySelectorAll("aside ul")) {
    for (const sibling of list.children) {
      sibling.classList.remove("selected");
    }
  }
  target.classList.add("selected");
}

async function fetchUsers() {
  return await fetchAPI("/users");
}

async function renderUserInfo() {
  // Dev-mode identity picker. Renders a labeled dropdown of seeded
  // users (humans + agents); selecting one writes localStorage and
  // reloads. Failure modes:
  //  - API down → showError + dropdown shows just the current slug.
  //  - localStorage slug isn't a real user → dropdown shows it with
  //    a "(?)" suffix, alongside the real users.
  const slug = getCurrentUserSlug();
  const div = document.getElementById("user-info");
  div.innerHTML = "";

  const label = document.createElement("span");
  label.className = "switch-label";
  label.textContent = "Pretend as: ";
  div.appendChild(label);

  const select = document.createElement("select");
  select.id = "user-switch";

  try {
    const users = await fetchUsers();
    let foundCurrent = false;
    for (const u of users) {
      const opt = document.createElement("option");
      const suffix = u.type === "agent" ? " (agent)" : "";
      opt.value = u.slug;
      opt.textContent = `${u.name}${suffix}`;
      if (u.slug === slug) {
        opt.selected = true;
        foundCurrent = true;
        currentUserName = u.name;     // cache for optimistic-render in postMessage
      }
      select.appendChild(opt);
    }
    if (!foundCurrent) {
      const opt = document.createElement("option");
      opt.value = slug;
      opt.textContent = `${slug} (?)`;
      opt.selected = true;
      select.insertBefore(opt, select.firstChild);
    }
  } catch (e) {
    showError(`load users: ${e.message}`);
    const opt = document.createElement("option");
    opt.value = slug;
    opt.textContent = slug;
    opt.selected = true;
    select.appendChild(opt);
  }

  select.onchange = () => {
    if (select.value !== slug) {
      setCurrentUserSlug(select.value);
      window.location.reload();
    }
  };
  div.appendChild(select);
}


// ----- sidebar lists -----

async function loadUsers() {
  // People sidebar: every live user except the current one (no self-DM).
  // Click → POST /dms/{peer_slug} → loadMessages on the returned conversation.
  // Empty-state hint when no peers exist so the sidebar doesn't look broken.
  // Sorted alphabetically by display name with localeCompare so unicode
  // collation is correct (e.g., Min Ho before Plato regardless of locale).
  try {
    const users = await fetchUsers();
    const me = getCurrentUserSlug();
    const ul = document.getElementById("users-list");
    ul.innerHTML = "";
    const peers = users
      .filter((u) => u.slug !== me)
      .sort((a, b) => a.name.localeCompare(b.name));
    if (peers.length === 0) {
      const hint = document.createElement("li");
      hint.classList.add("empty-state");
      hint.textContent = "No other users yet — run `python -m examples.add_user \"Bob\"`.";
      ul.appendChild(hint);
      return;
    }
    for (const u of peers) {
      const li = document.createElement("li");
      const suffix = u.type === "agent" ? " (agent)" : "";
      li.textContent = `${u.name}${suffix}`;
      li.onclick = () => {
        highlightSelected(ul, li);
        openDM(u.slug, u.name);
      };
      ul.appendChild(li);
    }
  } catch (e) {
    showError(`load users: ${e.message}`);
  }
}

async function loadTopics() {
  try {
    const topics = await fetchAPI("/topics");
    const ul = document.getElementById("topics-list");
    ul.innerHTML = "";
    for (const t of topics) {
      const li = document.createElement("li");
      li.textContent = t.name;
      li.onclick = () => {
        highlightSelected(ul, li);
        openTopic(t);
      };
      ul.appendChild(li);
    }
  } catch (e) {
    showError(`load topics: ${e.message}`);
  }
}


// ----- open conversation: topic-default or DM -----

// Tracks whether the open conversation is a DM. Drives the visibility
// of the "Clear chat" button (DMs only — clearing a public topic
// would wipe everyone else's content, server enforces this too).
let currentConvIsDM = false;

function setClearButtonVisible(visible) {
  document.getElementById("clear-chat").hidden = !visible;
}

function openTopic(topic) {
  // TopicRead carries both the default conversation id and slug — see
  // wazzup/models.py and wazzup/api/topics.py. Carrying both spares the
  // UI a round-trip (the api needs the id to POST messages and the
  // slug to GET messages). Sentinel values flag DB drift loudly.
  if (topic.default_conversation_slug === "<missing>"
      || topic.default_conversation_id === 0) {
    showError(`topic ${topic.slug} has no default conversation — DB drift, run seed`);
    return;
  }
  currentConvId = topic.default_conversation_id;
  currentConvSlug = topic.default_conversation_slug;
  currentConvName = `Topic: ${topic.name}`;
  currentConvIsDM = false;
  document.getElementById("conversation-name").textContent = currentConvName;
  setClearButtonVisible(false);
  loadMessagesForCurrent();
}

async function openDM(peerSlug, peerName) {
  try {
    const conv = await fetchAPI(
      `/dms/${encodeURIComponent(peerSlug)}`,
      { method: "POST" },
    );
    currentConvId = conv.id;
    currentConvSlug = conv.slug;
    currentConvName = `DM with ${peerName}`;
    currentConvIsDM = true;
    document.getElementById("conversation-name").textContent = currentConvName;
    setClearButtonVisible(true);
    await loadMessagesForCurrent();
  } catch (e) {
    showError(`open DM: ${e.message}`);
  }
}

async function clearCurrentChat() {
  if (!currentConvSlug || !currentConvIsDM) return;
  // Destructive — confirm. Soft-delete on the server, but the user
  // sees them disappear; the recover path is "ask an admin" / SQL.
  if (!window.confirm(`Clear all messages in ${currentConvName}? This can't be undone from the UI.`)) {
    return;
  }
  try {
    await fetchAPI(
      `/conversations/${encodeURIComponent(currentConvSlug)}/messages`,
      { method: "DELETE" },
    );
    await loadMessagesForCurrent();
  } catch (e) {
    showError(`clear chat: ${e.message}`);
  }
}

function renderMessageItem(m, myslug) {
  // Build one <li> for a message. Used by both the canonical render
  // (loadMessagesForCurrent) and the optimistic render (postMessage).
  // Keeps the two paths visually identical so the swap-after-fetch
  // doesn't flicker.
  const li = document.createElement("li");
  li.classList.add("message");
  li.classList.add(`sender-${m.sender_slug}`);
  if (m.sender_slug === myslug) li.classList.add("mine");

  const senderEl = document.createElement("span");
  senderEl.className = "sender";
  senderEl.textContent = m.sender_name;
  const textEl = document.createElement("span");
  textEl.className = "text";
  textEl.textContent = m.text;
  li.append(senderEl, document.createTextNode(": "), textEl);
  return li;
}

function scrollMessagesToBottom() {
  const ol = document.getElementById("messages-list");
  ol.scrollTop = ol.scrollHeight;
}

async function loadMessagesForCurrent() {
  if (!currentConvSlug) return;
  try {
    const messages = await fetchAPI(
      `/conversations/${encodeURIComponent(currentConvSlug)}/messages`,
    );
    const ol = document.getElementById("messages-list");
    ol.innerHTML = "";
    const myslug = getCurrentUserSlug();
    for (const m of messages) {
      // Server returns MessageReadInConversation (the route denormalizes
      // through the sent_by rel). Each row carries sender_name + sender_slug
      // so we can render multi-party threads cleanly.
      ol.appendChild(renderMessageItem(m, myslug));
    }
    scrollMessagesToBottom();
  } catch (e) {
    showError(`load messages: ${e.message}`);
  }
}


// ----- compose -----

async function postMessage(text) {
  if (currentConvId === null) {
    showError("select a topic or DM first");
    return;
  }

  // ----- 1. Optimistic UI -----
  // Append the message to the DOM *before* the server roundtrip. The
  // server's POST /messages handler runs the agent dispatcher (one
  // LLM call per agent) before returning, which can take 5-15s — too
  // long to leave the user staring at an empty composer wondering if
  // anything happened. So: render the message immediately, then let
  // ``loadMessagesForCurrent`` rebuild the list when the server returns.
  // The rebuild replaces the optimistic <li> with the canonical one
  // *plus* the agent replies; the visual shape is the same so the
  // swap is seamless.
  const myslug = getCurrentUserSlug();
  const optimistic = renderMessageItem(
    { sender_slug: myslug, sender_name: currentUserName || myslug, text },
    myslug,
  );
  optimistic.classList.add("optimistic");
  const ol = document.getElementById("messages-list");
  ol.appendChild(optimistic);

  // Typing indicator — tells the user "agents are working" while the
  // server's dispatcher loops. Removed when the canonical fetch
  // completes (loadMessagesForCurrent rebuilds the list).
  const typing = document.createElement("li");
  typing.className = "message typing";
  typing.textContent = "agents are typing…";
  ol.appendChild(typing);
  scrollMessagesToBottom();

  // ----- 2. Server roundtrip -----
  try {
    await fetchAPI("/messages", {
      method: "POST",
      // sender_id is intentionally absent — the server fills it from
      // current_user. See http/messages.py MessageCreateRequest.
      body: JSON.stringify({
        conversation_id: currentConvId,
        text: text,
      }),
    });
    // Refresh from server: replaces optimistic + typing indicator with
    // canonical list (now includes our message and any agent replies).
    await loadMessagesForCurrent();
  } catch (e) {
    showError(`post message: ${e.message}`);
    // Rollback: re-fetch to remove the dangling optimistic <li>.
    await loadMessagesForCurrent();
  }
}


// ----- wiring -----

document.getElementById("compose-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const ta = document.getElementById("compose-text");
  const text = ta.value.trim();
  if (text) {
    postMessage(text);
    ta.value = "";
  }
});

document.getElementById("clear-chat").addEventListener("click", () => {
  clearCurrentChat();
});

// Initial load.
applyUrlSlugOverride();
renderUserInfo();
loadUsers();
loadTopics();
