const roles = {
  admin: { label: "Dean's office", initials: "AD", color: "violet" },
  coordinator: { label: "Department coordinator", initials: "DC", color: "teal" },
  faculty: { label: "Faculty", initials: "FC", color: "amber" },
  club: { label: "Club representative", initials: "CR", color: "coral" }
};

const days = ["Mon", "Tue", "Wed", "Thu", "Fri"];
const periods = ["09:00", "10:00", "11:00", "12:00", "14:00", "15:00"];
const sessions = [
  ["CS201", "Data Structures", "Dr. Mehta", "BCA-2", "Mon", "09:00", "A-201"],
  ["MA102", "Discrete Mathematics", "Prof. Iyer", "BCA-1", "Mon", "10:00", "A-105"],
  ["EC210", "Digital Systems", "Dr. Rao", "ECE-2", "Mon", "14:00", "Lab E-1"],
  ["CS305", "Operating Systems", "Dr. Mehta", "BCA-3", "Tue", "09:00", "A-201"],
  ["HU110", "Professional Communication", "Ms. Khan", "BCA-1", "Tue", "11:00", "B-104"],
  ["EC302", "Microprocessors", "Dr. Das", "ECE-3", "Tue", "14:00", "Lab E-2"],
  ["CS220", "Database Systems", "Dr. Menon", "BCA-2", "Wed", "10:00", "A-201"],
  ["MA205", "Probability & Statistics", "Prof. Iyer", "BCA-2", "Wed", "12:00", "A-105"],
  ["EC202", "Signals & Systems", "Dr. Rao", "ECE-2", "Wed", "15:00", "A-203"],
  ["CS401", "Cloud Computing", "Dr. Kapoor", "BCA-4", "Thu", "09:00", "A-201"],
  ["EC415", "Embedded Systems Lab", "Dr. Das", "ECE-4", "Thu", "11:00", "Lab E-2"],
  ["HU205", "Ethics & Society", "Ms. Khan", "BCA-3", "Fri", "10:00", "B-104"]
].map(([code, title, faculty, group, day, time, room], id) => ({ id, code, title, faculty, group, day, time, room }));

const rooms = [
  { name: "A-201", capacity: 72, type: "Lecture hall", features: ["Projector", "AC"], accessibility: true, status: "Available" },
  { name: "A-105", capacity: 48, type: "Classroom", features: ["Projector", "Whiteboard"], accessibility: true, status: "Available" },
  { name: "Lab E-1", capacity: 36, type: "Computer lab", features: ["32 PCs", "AC"], accessibility: false, status: "Maintenance · Fri" },
  { name: "Lab E-2", capacity: 40, type: "Electronics lab", features: ["Oscilloscope", "AC"], accessibility: true, status: "Available" },
  { name: "B-104", capacity: 64, type: "Classroom", features: ["Projector"], accessibility: true, status: "Available" },
  { name: "Auditorium", capacity: 450, type: "Auditorium", features: ["Stage", "AV", "Green room"], accessibility: true, status: "Available" }
];

const bookingSeed = [
  { id: "BK-1048", title: "Spectra opening ceremony", requester: "Cultural Council", kind: "Institute event", room: "Auditorium", slot: "Fri · 16:00–19:00", status: "Approved", reason: "Highest eligible priority; room is available." },
  { id: "BK-1047", title: "Robotics club showcase", requester: "Robotics Club", kind: "Club event", room: "Lab E-2", slot: "Thu · 16:00–18:00", status: "Rejected", reason: "Conflicts with the scheduled ECE-4 practical session." },
  { id: "BK-1046", title: "BCA alumni guest lecture", requester: "Alumni Cell", kind: "Guest lecture", room: "A-201", slot: "Wed · 10:00–12:00", status: "Pending admin", reason: "Would displace a regular class; Dean approval required." }
];

let state = { role: null, page: "dashboard", toast: null, bookings: [...bookingSeed], loginRole: "admin", authMode: "login", error: "" };
const API_BASE = window.ORBIT_API_BASE || "";
const api = async (path, options = {}) => {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  const token = sessionStorage.getItem("orbit_token");
  if (token) headers.Authorization = `Bearer ${token}`;
  const result = await fetch(`${API_BASE}${path}`, { ...options, headers });
  const data = await result.json().catch(() => ({}));
  if (!result.ok) throw new Error(data.error || "Request failed");
  return data;
};

const icon = (name) => ({
  grid: "▦", calendar: "▣", rooms: "⌂", ticket: "◇", exam: "◫", shuffle: "↝", settings: "⚙", plus: "+", arrow: "→", check: "✓", close: "×"
}[name] || "•");

function render() {
  document.querySelector("#app").innerHTML = state.role ? appShell() : signIn();
  bindEvents();
}

function signIn() {
  const role = roles[state.loginRole];
  const signup = state.authMode === "signup";
  return `<main class="auth-page">
    <section class="auth-hero"><div class="brand"><span class="brand-mark">◒</span> orbit</div>
      <div class="hero-copy"><p class="eyebrow">Campus operations, made predictable.</p><h1>One calm place for every room, session, and change.</h1><p>Generate schedules, resolve room requests, and keep every decision explainable.</p></div>
      <div class="hero-stat"><strong>189</strong><span>weekly sessions<br>in the starter dataset</span></div>
    </section>
    <section class="auth-panel"><div class="auth-header"><span class="eyebrow">${signup ? "REQUEST ACCESS" : "SECURE SIGN IN"}</span><h2>${signup ? "Create a pending account" : "Sign in to Orbit"}</h2><p>${signup ? "Privileged access remains pending until an administrator approves it." : "Your role comes from the authenticated account, not this selection."}</p></div>
      ${!signup ? `<div class="role-grid compact-roles">${Object.entries(roles).map(([key, item]) => `<button class="role-card ${state.loginRole === key ? "selected" : ""}" data-login-role="${key}"><span class="avatar ${item.color}">${item.initials}</span><span><strong>${item.label}</strong><small>${key === "admin" ? "Schedule control & approvals" : key === "coordinator" ? "Department requests" : key === "faculty" ? "Your teaching day" : "Venue requests"}</small></span><b>${state.loginRole === key ? "✓" : "→"}</b></button>`).join("")}</div>` : ""}
      <form class="auth-form" data-auth-form><input name="display_name" placeholder="Full name" ${signup ? "required" : "hidden"} /><input name="email" type="email" placeholder="College email" required /><input name="password" type="password" minlength="${signup ? "12" : "1"}" placeholder="${signup ? "Password (12+ characters)" : "Password"}" required />${signup ? `<select name="role"><option value="coordinator">Department Coordinator</option><option value="faculty">Faculty</option><option value="club">Club Representative</option></select><input name="department" placeholder="Department (optional)" />` : ""}<button class="primary" type="submit">${signup ? "Submit for approval" : `Sign in as ${role.label}`} →</button></form>
      ${state.error ? `<p class="auth-error">${state.error}</p>` : ""}
      <button class="text-btn auth-toggle" data-toggle-auth>${signup ? "Back to sign in" : "Need access? Request a verified account"}</button>
      <p class="auth-note">${signup ? "Admin accounts cannot be self-created. Email OTP and password providers must be configured for production." : "Demo accounts are available only in development mode. Production deployments must configure external bootstrap credentials and HTTPS."}</p>
    </section>
  </main>`;
}

function appShell() {
  const role = roles[state.role];
  return `<div class="shell"><aside class="sidebar"><div class="brand"><span class="brand-mark">◒</span> orbit</div>
    <div class="workspace-label">WORKSPACE</div><div class="current-role"><span class="avatar ${role.color}">${role.initials}</span><span><strong>${role.label}</strong><small>Spring term · 2025</small></span></div>
    <nav>${navItems().map(item => `<button class="${state.page === item.id ? "active" : ""}" data-page="${item.id}"><span>${icon(item.icon)}</span>${item.label}</button>`).join("")}</nav>
    <div class="sidebar-bottom"><button data-page="settings"><span>⚙</span>Settings</button><button class="sign-out" data-signout><span>↪</span>Sign out</button></div>
  </aside><main class="main"><header class="topbar"><div><p class="eyebrow">Saturday, 12 April 2025</p><h1>${pageTitle()}</h1></div><div class="top-actions"><button class="icon-btn">⌕</button><button class="icon-btn">♧<i></i></button><span class="avatar ${role.color}">${role.initials}</span></div></header>${pageContent()}</main>${state.toast ? `<div class="toast">${icon("check")} ${state.toast}</div>` : ""}</div>`;
}

function navItems() {
  const items = [{ id: "dashboard", label: "Overview", icon: "grid" }, { id: "timetable", label: "Timetable", icon: "calendar" }, { id: "rooms", label: "Room finder", icon: "rooms" }, { id: "bookings", label: "Bookings", icon: "ticket" }, { id: "exams", label: "Exams", icon: "exam" }];
  if (state.role === "admin") items.push({ id: "reschedule", label: "Rescheduling", icon: "shuffle" });
  return items;
}
function pageTitle() { return ({ dashboard: "Good morning, Akash", timetable: "Weekly timetable", rooms: "Room finder", bookings: "Booking requests", exams: "Exams & events", reschedule: "Rescheduling studio", settings: "Workspace settings" })[state.page]; }
function pageContent() {
  return ({ dashboard: dashboard, timetable: timetable, rooms: roomFinder, bookings: bookings, exams: exams, reschedule: reschedule, settings: settings })[state.page]();
}

function dashboard() {
  const isAdmin = state.role === "admin";
  return `<div class="content"><section class="welcome-banner"><div><span class="eyebrow">SATURDAY SNAPSHOT</span><h2>Your campus is in rhythm.</h2><p>12 sessions are running today across 8 rooms. No hard constraint violations in the active schedule.</p></div><button class="primary" data-page="timetable">View timetable ${icon("arrow")}</button></section>
    <div class="metric-grid"><div class="metric"><span class="metric-label">Sessions this week</span><strong>189</strong><em class="up">+8.4%</em><small>vs. last published schedule</small></div><div class="metric"><span class="metric-label">Rooms in use</span><strong>21 <small>/ 27</small></strong><em class="neutral">78%</em><small>peak utilization · Tue 11:00</small></div><div class="metric"><span class="metric-label">Open requests</span><strong>${state.bookings.filter(b => b.status.includes("Pending")).length}</strong><em class="attention">Needs review</em><small>1 decision impacts a class</small></div><div class="metric"><span class="metric-label">Schedule health</span><strong class="health">100%</strong><em class="up">✓ Validated</em><small>0 hard constraint violations</small></div></div>
    <div class="section-grid"><section class="panel"><div class="panel-head"><div><span class="eyebrow">NEXT UP</span><h3>Today on campus</h3></div><button class="text-btn" data-page="timetable">Full timetable ${icon("arrow")}</button></div><div class="mini-list">${sessions.slice(0, 4).map(s => `<div class="mini-row"><span class="time">${s.time}</span><span class="dot ${s.day === "Mon" ? "violet" : "teal"}"></span><span class="grow"><strong>${s.title}</strong><small>${s.code} · ${s.room} · ${s.group}</small></span><span class="status-pill live">On track</span></div>`).join("")}</div></section>
    <section class="panel"><div class="panel-head"><div><span class="eyebrow">DECISIONS</span><h3>Needs your attention</h3></div></div>${state.bookings.map(b => `<div class="decision"><span class="decision-icon ${b.status === "Rejected" ? "bad" : "warn"}">${b.status === "Rejected" ? "!" : "◷"}</span><div class="grow"><strong>${b.title}</strong><small>${b.status} · ${b.reason}</small></div><button class="icon-btn small" data-page="bookings">→</button></div>`).join("")}</section></div>
    ${isAdmin ? `<section class="panel admin-strip"><div><span class="eyebrow">ADMIN CONTROL</span><h3>Generation is ready</h3><p>Latest export was produced from the official starter dataset and passed deterministic validation.</p></div><div class="admin-score"><strong>0</strong><span>hard violations</span></div><div class="admin-score"><strong>94</strong><span>soft score</span></div><button class="secondary" data-page="reschedule">Open studio</button></section>` : ""}</div>`;
}

function timetable() {
  return `<div class="content"><div class="toolbar"><div class="filter-group"><button class="filter active">All departments⌄</button><button class="filter">All rooms⌄</button><button class="filter">This week⌄</button></div><button class="secondary">${icon("plus")} Add filter</button></div><section class="panel schedule-panel"><div class="schedule-head"><span class="eyebrow">WEEK 15 · 7–11 APRIL</span><div class="legend"><span><i class="legend-dot violet"></i> BCA</span><span><i class="legend-dot teal"></i> ECE</span><span><i class="legend-dot amber"></i> Shared</span></div></div><div class="schedule"><div class="time-col"><div></div>${periods.map(p => `<span>${p}</span>`).join("")}</div>${days.map(day => `<div class="day-col"><strong>${day}</strong>${periods.map(p => { const s = sessions.find(x => x.day === day && x.time === p); return `<div class="slot">${s ? `<article class="session-card ${s.group.startsWith("ECE") ? "teal-card" : "violet-card"}"><strong>${s.code}</strong><span>${s.title}</span><small>${s.room}</small></article>` : ""}</div>`; }).join("")}</div>`).join("")}</div></section></div>`;
}

function roomFinder() {
  return `<div class="content"><div class="search-row"><label class="search"><span>⌕</span><input placeholder="Search rooms, features, or capacity" /></label><button class="secondary">Filters <span class="count">2</span></button></div><div class="room-grid">${rooms.map(r => `<article class="room-card"><div class="room-top"><div><span class="eyebrow">${r.type}</span><h3>${r.name}</h3></div><span class="availability ${r.status.startsWith("Available") ? "available" : "maintenance"}">${r.status}</span></div><div class="room-meta"><span>♙ ${r.capacity} seats</span><span>◉ ${r.accessibility ? "Accessible" : "No lift access"}</span></div><div class="chips">${r.features.map(f => `<span>${f}</span>`).join("")}</div><button class="room-action" data-book="${r.name}">Request this room ${icon("arrow")}</button></article>`).join("")}</div></div>`;
}

function bookings() {
  return `<div class="content"><div class="toolbar"><div class="filter-group"><button class="filter active">All requests⌄</button><button class="filter">All statuses⌄</button></div><button class="primary" data-new-booking>${icon("plus")} New request</button></div><section class="panel"><div class="table-head"><span>REQUEST</span><span>TYPE</span><span>ROOM & SLOT</span><span>STATUS</span><span></span></div>${state.bookings.map(b => `<div class="table-row"><div class="request-cell"><span class="request-avatar">${b.requester.slice(0, 2).toUpperCase()}</span><span><strong>${b.title}</strong><small>${b.id} · ${b.requester}</small></span></div><span class="muted">${b.kind}</span><span><strong>${b.room}</strong><small>${b.slot}</small></span><span class="status-pill ${b.status === "Approved" ? "approved" : b.status === "Rejected" ? "rejected" : "pending"}">${b.status}</span><button class="icon-btn small" data-reason="${b.reason}">⋯</button></div>`).join("")}</section><div class="explain-card"><div class="decision-icon violet-bg">✦</div><div><strong>Every decision has a reason</strong><p>Orbit checks priority, ownership, capacity, availability, and class conflicts deterministically before an approval can be made.</p></div></div></div>`;
}

function exams() {
  const exams = [["CS201", "Data Structures", "Mon · 21 Apr", "A-201", "BCA-2"], ["MA102", "Discrete Mathematics", "Tue · 22 Apr", "A-105", "BCA-1"], ["EC210", "Digital Systems", "Wed · 23 Apr", "Lab E-1", "ECE-2"], ["CS305", "Operating Systems", "Thu · 24 Apr", "A-201", "BCA-3"]];
  return `<div class="content"><section class="welcome-banner compact"><div><span class="eyebrow">MIDSEM EXAMINATION · 41 PAPERS</span><h2>Exam timetable is published.</h2><p>Room assignments are locked at priority level one. Students see the same source of truth.</p></div><span class="published">✓ Published 2h ago</span></section><section class="panel"><div class="panel-head"><div><span class="eyebrow">UPCOMING</span><h3>Exam slots</h3></div><button class="text-btn">Download timetable ↓</button></div>${exams.map(e => `<div class="exam-row"><span class="exam-date">${e[2].split(" · ")[0]}<small>${e[2].split(" · ")[1]}</small></span><span class="grow"><strong>${e[0]} · ${e[1]}</strong><small>${e[4]} · ${e[3]}</small></span><span class="status-pill approved">Room locked</span></div>`).join("")}</section></div>`;
}

function reschedule() {
  return `<div class="content"><section class="studio-banner"><div><span class="eyebrow">DISRUPTION WORKFLOW</span><h2>Move less. Explain more.</h2><p>Apply a disruption, compare the solver's valid revision, then approve with a complete audit trail.</p></div><div class="studio-actions"><button class="secondary" data-disruption>Apply sample disruption</button><button class="primary" data-approve>Approve revision ${icon("arrow")}</button></div></section><div class="metric-grid"><div class="metric"><span class="metric-label">Hard violations</span><strong>0</strong><em class="up">✓ Valid</em></div><div class="metric"><span class="metric-label">Sessions moved</span><strong>2</strong><em class="neutral">Minimal</em></div><div class="metric"><span class="metric-label">Soft penalty</span><strong>6.2</strong><em class="up">−18%</em></div><div class="metric"><span class="metric-label">Booking score</span><strong>94</strong><em class="up">Excellent</em></div></div><section class="panel comparison"><div class="panel-head"><div><span class="eyebrow">PROPOSED REVISION · REV-006</span><h3>Before and after</h3></div><span class="status-pill pending">Awaiting approval</span></div><div class="compare-head"><span>SESSION</span><span>ORIGINAL</span><span>REVISED</span><span>WHY</span></div>${[sessions[0], sessions[6]].map((s, i) => `<div class="compare-row"><span><strong>${s.code}</strong><small>${s.title}</small></span><span>${s.day} · ${s.time}<small>${s.room}</small></span><span class="revised">${i ? "Thu · 12:00" : "Fri · 09:00"}<small>${i ? "A-203" : "A-201"}</small></span><span class="muted">${i ? "Room freed for approved exam" : "Faculty unavailability"}</span></div>`).join("")}</section><p class="audit-note">⌁ Created by deterministic scheduler · sample_disruption.json · 12 Apr 2025 09:42 · Approval is restricted to Admin.</p></div>`;
}

function settings() {
  return `<div class="content"><section class="panel settings"><div class="panel-head"><div><span class="eyebrow">OPERATIONS</span><h3>Policy controls</h3></div></div><div class="setting-row"><div><strong>Booking priority</strong><small>Applied to every room conflict before approval.</small></div><div class="priority-list"><span>1 · Exams</span><span>2 · Regular classes</span><span>3 · Institute events</span><span>4 · Guest lectures</span><span>5 · Department events</span><span>6 · Club events</span></div></div><div class="setting-row"><div><strong>Authentication providers</strong><small>Demo uses role-scoped accounts. Production OTP remains disabled until configured.</small></div><span class="status-pill pending">OTP disabled</span></div><div class="setting-row"><div><strong>Audit history</strong><small>All approvals, resets, priority changes, and revisions are retained.</small></div><button class="secondary">View audit log</button></div></section></div>`;
}

function bindEvents() {
  document.querySelectorAll("[data-login-role]").forEach(b => b.onclick = () => { state.loginRole = b.dataset.loginRole; state.error = ""; render(); });
  document.querySelector("[data-toggle-auth]")?.addEventListener("click", () => { state.authMode = state.authMode === "login" ? "signup" : "login"; state.error = ""; render(); });
  document.querySelector("[data-auth-form]")?.addEventListener("submit", async event => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const payload = Object.fromEntries(form.entries());
    try {
      const result = await api(state.authMode === "signup" ? "/api/auth/signup" : "/api/auth/login", { method: "POST", body: JSON.stringify(payload) });
      if (state.authMode === "signup") { state.authMode = "login"; state.error = "Account submitted. An administrator must approve it before you can sign in."; render(); return; }
      sessionStorage.setItem("orbit_token", result.token);
      state.role = result.user.role; state.page = "dashboard"; state.error = ""; render();
    } catch (error) { state.error = error.message; render(); }
  });
  document.querySelectorAll("[data-page]").forEach(b => b.onclick = () => { state.page = b.dataset.page; render(); });
  document.querySelector("[data-signout]")?.addEventListener("click", async () => { try { await api("/api/auth/logout", { method: "POST", body: "{}" }); } catch {} sessionStorage.removeItem("orbit_token"); state.role = null; render(); });
  document.querySelector("[data-new-booking]")?.addEventListener("click", () => { state.toast = "Request form opened — structured validation is ready."; render(); clearToast(); });
  document.querySelectorAll("[data-book]").forEach(b => b.onclick = () => { state.toast = `${b.dataset.book} is available to request. Capacity and conflict checks will run on submit.`; render(); clearToast(); });
  document.querySelectorAll("[data-reason]").forEach(b => b.onclick = () => { state.toast = b.dataset.reason; render(); clearToast(); });
  document.querySelector("[data-disruption]")?.addEventListener("click", () => { state.toast = "sample_disruption.json applied. Valid revision found with 2 sessions moved."; render(); clearToast(); });
  document.querySelector("[data-approve]")?.addEventListener("click", () => { if (state.role !== "admin") { state.toast = "Only an authenticated Admin can approve a revision."; } else { state.toast = "Revision approval must be submitted through the server workflow."; } render(); clearToast(); });
}
function clearToast() { setTimeout(() => { state.toast = null; render(); }, 3200); }
async function bootstrap() {
  if (!sessionStorage.getItem("orbit_token")) return render();
  try {
    const user = await api("/api/me");
    state.role = user.role;
  } catch {
    sessionStorage.removeItem("orbit_token");
    state.role = null;
  }
  render();
}
bootstrap();
