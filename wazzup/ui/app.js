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
let currentConvSlug = null;
let currentConvId = null;
let currentConvName = null;


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
  try {
    const users = await fetchUsers();
    const me = getCurrentUserSlug();
    const ul = document.getElementById("users-list");
    ul.innerHTML = "";
    const peers = users.filter((u) => u.slug !== me);
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
  document.getElementById("conversation-name").textContent = currentConvName;
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
    document.getElementById("conversation-name").textContent = currentConvName;
    await loadMessagesForCurrent();
  } catch (e) {
    showError(`open DM: ${e.message}`);
  }
}

async function loadMessagesForCurrent() {
  if (!currentConvSlug) return;
  try {
    const messages = await fetchAPI(
      `/conversations/${encodeURIComponent(currentConvSlug)}/messages`,
    );
    const ol = document.getElementById("messages-list");
    ol.innerHTML = "";
    for (const m of messages) {
      const li = document.createElement("li");
      // Sender display: MessageRead is stored-columns-only (no sender_id),
      // per the rels-only design. A future MessageReadInConversation route
      // would JOIN through the sent_by rel and surface the sender name.
      li.textContent = m.text;
      ol.appendChild(li);
    }
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
    await loadMessagesForCurrent();
  } catch (e) {
    showError(`post message: ${e.message}`);
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

// Initial load.
applyUrlSlugOverride();
renderUserInfo();
loadUsers();
loadTopics();
