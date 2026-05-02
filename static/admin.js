let allUsers  = [];
let deleteTarget = null;

window.addEventListener("DOMContentLoaded", () => {
  loadStats();
  loadUsers();
});

/* ── Stats ────────────────────────────────────────────────────────────────── */
async function loadStats() {
  try {
    const d = await (await fetch("/admin/api/stats", { credentials: "include" })).json();
    document.getElementById("s-users").textContent       = d.users;
    document.getElementById("s-papers").textContent      = d.papers;
    document.getElementById("s-researchers").textContent = d.researchers;
    document.getElementById("s-queries").textContent     = d.queries;
  } catch (_) {}
}

/* ── Users table ──────────────────────────────────────────────────────────── */
async function loadUsers() {
  try {
    const res = await fetch("/admin/api/users", { credentials: "include" });
    allUsers  = await res.json();
    renderUsers(allUsers);
  } catch (e) {
    document.getElementById("users-body").innerHTML =
      `<tr><td colspan="5" class="loading-row">Error loading users.</td></tr>`;
  }
}

function renderUsers(users) {
  const tbody = document.getElementById("users-body");
  if (!users.length) {
    tbody.innerHTML = `<tr><td colspan="5" class="loading-row">No users found.</td></tr>`;
    return;
  }

  tbody.innerHTML = users.map(u => `
    <tr id="row-${u.id}">
      <td><strong>${esc(u.name)}</strong></td>
      <td style="color:#9b9b97">${esc(u.email)}</td>
      <td>
        <span class="role-badge ${u.is_admin ? 'admin' : 'user'}">
          ${u.is_admin ? 'Admin' : 'User'}
        </span>
      </td>
      <td style="color:#666; font-size:12px; font-family:var(--mono)">${u.created_at.slice(0,10)}</td>
      <td>
        <div class="action-btns">
          <button class="btn-sm btn-toggle" onclick="toggleAdmin(${u.id}, ${u.is_admin})">
            ${u.is_admin ? 'Remove admin' : 'Make admin'}
          </button>
          <button class="btn-sm btn-del" onclick="confirmDelete(${u.id}, '${esc(u.name)}')">
            Delete
          </button>
        </div>
      </td>
    </tr>
  `).join("");
}

function filterUsers() {
  const q = document.getElementById("user-search").value.toLowerCase();
  const filtered = allUsers.filter(u =>
    u.name.toLowerCase().includes(q) || u.email.toLowerCase().includes(q)
  );
  renderUsers(filtered);
}

/* ── Toggle admin ─────────────────────────────────────────────────────────── */
async function toggleAdmin(uid, currentlyAdmin) {
  try {
    const res  = await fetch(`/admin/api/users/${uid}/toggle-admin`, {
      method: "POST", credentials: "include"
    });
    const data = await res.json();
    if (data.error) { alert(data.error); return; }
    // update local state and re-render
    const u = allUsers.find(x => x.id === uid);
    if (u) u.is_admin = data.is_admin;
    renderUsers(allUsers);
    loadStats();
  } catch (_) { alert("Network error."); }
}

/* ── Delete ───────────────────────────────────────────────────────────────── */
function confirmDelete(uid, name) {
  deleteTarget = uid;
  document.getElementById("del-user-name").textContent = name;
  document.getElementById("del-backdrop").classList.add("open");
  document.getElementById("del-modal").classList.add("open");
  document.getElementById("del-confirm-btn").onclick = () => doDelete(uid);
}

function closeDelModal() {
  deleteTarget = null;
  document.getElementById("del-backdrop").classList.remove("open");
  document.getElementById("del-modal").classList.remove("open");
}

async function doDelete(uid) {
  try {
    const res  = await fetch(`/admin/api/users/${uid}`, {
      method: "DELETE", credentials: "include"
    });
    const data = await res.json();
    if (data.error) { alert(data.error); return; }
    allUsers = allUsers.filter(u => u.id !== uid);
    renderUsers(allUsers);
    loadStats();
    closeDelModal();
  } catch (_) { alert("Network error."); }
}

/* ── Sign out ─────────────────────────────────────────────────────────────── */
async function signOut() {
  await fetch("/auth/logout", { method: "POST", credentials: "include" });
  window.location.href = "/";
}

/* ── Util ─────────────────────────────────────────────────────────────────── */
function esc(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
