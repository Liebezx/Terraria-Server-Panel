const $ = (id) => document.getElementById(id);
let stateData = null;
let currentPage = "Обзор";
let lastLogId = 0;
let adminData = null;
let selectedAccount = "";
let settingsDirty = false;
let modeDirty = false;
let toastTimer = null;

const subtitles = {
  "Обзор": "Состояние сервера и быстрые действия",
  "Серверы": "Профили, миры и настройки запуска",
  "Игроки": "Кто подключён к серверу",
  "Консоль": "Журнал, команды TShock и сообщения в чат",
  "Нагрузка": "Ресурсы машины, где запущен сервер",
  "Админка": "Аккаунты TShock, группы и права"
};

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]));
}
function fmtTime(seconds) {
  if (seconds == null) return "—";
  const h = Math.floor(seconds / 3600), m = Math.floor(seconds % 3600 / 60);
  return h ? `${h} ч ${m} мин` : `${m} мин`;
}
function showToast(text, bad=false) {
  const node = $("toast"); node.textContent = text; node.classList.toggle("bad", bad); node.classList.remove("hidden");
  clearTimeout(toastTimer); toastTimer = setTimeout(() => node.classList.add("hidden"), 4200);
}
async function request(path, body) {
  const options = body === undefined ? {credentials:"same-origin"} : {method:"POST", credentials:"same-origin", headers:{"Content-Type":"application/json"}, body:JSON.stringify(body)};
  const res = await fetch(path, options);
  const data = await res.json().catch(() => ({}));
  if (res.status === 401 && path !== "/api/login") { showLogin(); throw new Error("Сессия закончилась. Войди снова."); }
  if (!res.ok) throw new Error(data.error || `Ошибка ${res.status}`);
  return data;
}
function showLogin() { $("app").classList.add("hidden"); $("login").classList.remove("hidden"); $("login-password").focus(); }
function showApp() {
  $("login").classList.add("hidden"); $("app").classList.remove("hidden");
  const requested=decodeURIComponent(location.hash.slice(1));
  navigate(subtitles[requested]?requested:"Обзор",{replace:true});
  refresh(); pollLogs();
}
async function login(event) {
  event.preventDefault(); $("login-error").textContent = "";
  try { await request("/api/login", {password:$("login-password").value}); $("login-password").value = ""; showApp(); }
  catch (error) { $("login-error").textContent = error.message; }
}
function navigate(name, options={}) {
  if (!subtitles[name]) return;
  if (!options.fromHistory) {
    const method=options.replace?"replaceState":"pushState";
    if (options.replace || history.state?.panelPage!==name) history[method]({panelPage:name},"",`#${encodeURIComponent(name)}`);
  }
  currentPage = name; document.title=`${name} · TERRARIA CONTROL`; $("page-title").textContent = name; $("page-subtitle").textContent = subtitles[name];
  document.querySelectorAll(".page").forEach((el) => el.classList.toggle("active", el.dataset.view === name));
  document.querySelectorAll(".nav-item").forEach((el) => el.classList.toggle("active", el.dataset.page === name));
  if (name === "Админка") loadAdmin();
  if (name === "Нагрузка") refresh();
}
window.addEventListener("popstate",(event)=>{
  const target=event.state?.panelPage || decodeURIComponent(location.hash.slice(1)) || "Обзор";
  navigate(subtitles[target]?target:"Обзор",{fromHistory:true});
});
async function refresh() {
  try { stateData = await request("/api/state"); renderState(); await pollLogs(); }
  catch (error) { if (!$("login").classList.contains("hidden")) return; showToast(error.message, true); }
}
function renderState() {
  if (!stateData) return;
  const running = stateData.running;
  $("server-badge").textContent = running ? "● СЕРВЕР РАБОТАЕТ" : "● СЕРВЕР ВЫКЛЮЧЕН";
  $("server-badge").className = "badge " + (running ? "on" : "off");
  $("start-top").classList.toggle("hidden", running); $("stop-top").classList.toggle("hidden", !running);
  const online = stateData.players.length, max = stateData.settings.max_players || 8;
  $("stat-players").textContent = `${online} / ${max}`;
  $("stat-player-caption").textContent = running ? (online ? "игроки сейчас в мире" : "сервер ждёт игроков") : "сервер остановлен";
  $("stat-world").textContent = stateData.world.name || stateData.settings.world || "—";
  $("stat-mode").textContent = stateData.world.mode || "Сложность не определена";
  $("stat-runtime").textContent = running ? fmtTime(stateData.uptime_seconds) : "Остановлен";
  $("stat-api").textContent = stateData.api_connected ? "TShock подключён" : (running ? "REST TShock пока не отвечает" : "Ожидает запуска");
  const profile = stateData.profiles.find((x) => x.id === stateData.selected_profile);
  $("overview-profile").textContent = profile ? profile.name : "—";
  $("game-address").textContent = stateData.game_address || `${location.hostname}:7777`;
  renderProfiles(); renderWorlds(); renderPlayers(); renderMetrics(); renderWorldInfo();
}
function renderProfiles() {
  const select = $("profile-select"); const selected = stateData.selected_profile;
  select.innerHTML = stateData.profiles.map((p) => `<option value="${escapeHtml(p.id)}" ${p.id===selected?"selected":""}>${escapeHtml(p.name)}</option>`).join("");
}
function renderWorlds() {
  const select = $("world-select"); const wanted = stateData.settings.world; const draftWorld = select.value;
  select.innerHTML = stateData.worlds.map((w) => `<option value="${escapeHtml(w.name)}" ${w.name===wanted?"selected":""}>${escapeHtml(w.name)}</option>`).join("");
  if (settingsDirty && stateData.worlds.some((w) => w.name === draftWorld)) select.value = draftWorld;
  const chosenWorld = select.value || wanted;
  const info = stateData.worlds.find((w) => w.name === chosenWorld);
  $("world-detail").textContent = info ? `${info.size_mb} МБ · последнее изменение ${info.modified}` : (chosenWorld ? "Мир из профиля не найден среди файлов Worlds." : "Выбери существующий мир.");
  if (!settingsDirty) {
    $("setting-password").value = stateData.settings.password || "";
    $("setting-slots").value = stateData.settings.max_players || 8;
    $("setting-autosave").checked = Boolean(stateData.settings.autosave);
  }
  $("world-mode-label").textContent = stateData.world.mode || "Не определён";
  $("world-name-label").textContent = stateData.world.name || "Мир не загружен";
  if (!modeDirty) $("mode-select").value = stateData.world.mode || "Классический";
}
function playerRow(p, kick=false) {
  const safeName = escapeHtml(p.name);
  return `<tr><td><b>${safeName}</b></td><td>${escapeHtml(p.account)}</td><td>${escapeHtml(p.group)}</td><td>${escapeHtml(p.position)}</td>${kick?`<td><button class="danger" data-kick="${safeName}">Кикнуть</button></td>`:""}</tr>`;
}
function renderPlayers() {
  const items = stateData.players || [];
  $("overview-players").innerHTML = items.length ? `<div class="table-wrap"><table><thead><tr><th>ПЕРСОНАЖ</th><th>ГРУППА</th><th>X / Y</th></tr></thead><tbody>${items.map((p)=>`<tr><td>${escapeHtml(p.name)}</td><td>${escapeHtml(p.group)}</td><td>${escapeHtml(p.position)}</td></tr>`).join("")}</tbody></table></div>` : `<div class="empty">${stateData.running ? "Пока нет подключённых игроков." : "Список появится после запуска."}</div>`;
  $("players-table").innerHTML = items.map((p) => playerRow(p, true)).join("");
  $("players-empty").classList.toggle("hidden", items.length > 0);
}
function renderMetrics() {
  const m = stateData.metrics || {};
  $("metric-server-ram").textContent = m.server_memory_mb == null ? "—" : `${m.server_memory_mb} МБ`;
  $("metric-server-cpu").textContent = m.server_cpu_percent == null ? "—" : `${m.server_cpu_percent}%`;
  $("metric-host-ram").textContent = m.system_memory_percent == null ? "—" : `${m.system_memory_percent}%`;
  $("metric-load").textContent = m.system_load == null ? "—" : m.system_load;
}
function renderWorldInfo() {
  if (!stateData.api_connected) $("rest-note").textContent = stateData.api_error || "REST TShock ждёт запуска сервера.";
  else $("rest-note").textContent = "REST API подключено локально. Токен остаётся на серверном хосте и не передаётся браузеру.";
}
async function pollLogs() {
  if ($("app").classList.contains("hidden")) return;
  try {
    const data = await request(`/api/logs?since=${lastLogId}`);
    if (lastLogId === 0 && data.entries.length) {
      $("console-log").innerHTML = ""; $("overview-log").innerHTML = "";
    }
    for (const row of data.entries) appendLog(row);
    lastLogId = data.last_id || lastLogId;
  } catch (_) {}
}
function appendLog(row) {
  const line = document.createElement("div"); line.className = `log-line ${escapeHtml(row.level || "")}`;
  const time = document.createElement("span"); time.className = "time"; time.textContent = `[${row.time}]`;
  const text = document.createElement("span"); text.textContent = row.text;
  line.append(time, text); $("console-log").append(line);
  const preview = line.cloneNode(true); $("overview-log").append(preview);
  while ($("overview-log").children.length > 12) $("overview-log").firstElementChild.remove();
  while ($("console-log").children.length > 800) $("console-log").firstElementChild.remove();
  $("console-log").scrollTop = $("console-log").scrollHeight;
}
async function post(path, body={}, message="Готово.") {
  try { const data = await request(path, body); if (["/api/settings","/api/profile/select","/api/profile/create","/api/profile/remove"].includes(path)) settingsDirty=false; if (path === "/api/mode") modeDirty=false; showToast(data.message || message); await refresh(); if (currentPage === "Админка") await loadAdmin(); return data; }
  catch (error) { showToast(error.message, true); return null; }
}
async function startServer() {
  if (!stateData) await refresh();
  const body = {profile_id:$("profile-select").value || stateData?.selected_profile, world:$("world-select").value, password:$("setting-password").value, max_players:Number($("setting-slots").value || 8), autosave:$("setting-autosave").checked};
  await post("/api/start", body, "Сервер запускается.");
}
async function stopServer() {
  if (!confirm("Остановить сервер с сохранением мира? Игроки будут отключены.")) return;
  await post("/api/stop", {}, "Команда выключения отправлена.");
}
async function saveSettings() {
  await post("/api/settings", {profile_id:$("profile-select").value, world:$("world-select").value, password:$("setting-password").value, max_players:Number($("setting-slots").value), autosave:$("setting-autosave").checked}, "Настройки сохранены.");
}
async function loadAdmin() {
  try {
    adminData = await request("/api/admin"); renderAdmin();
  } catch (error) { showToast(error.message, true); }
}
function rowValue(row, ...keys) {
  if (!row || typeof row !== "object") return String(row ?? "");
  const entry = Object.entries(row).find(([key]) => keys.some((name) => name.toLowerCase() === key.toLowerCase()));
  return entry ? entry[1] : "";
}
function normalizeGroup(value) { return value && typeof value === "object" ? rowValue(value,"name") : (value || "—"); }
function renderAdmin() {
  if (!adminData) return;
  const users = adminData.users || [], groups = adminData.groups || [];
  const online = new Set((stateData?.players || []).map((p)=>String(p.account).toLowerCase()));
  $("accounts-table").innerHTML = users.map((u) => {
    const name = String(rowValue(u,"username","name","user") || "—"), group = String(normalizeGroup(rowValue(u,"group","groupname")));
    const onlineText = online.has(name.toLowerCase()) ? "Да" : "Нет";
    return `<tr class="selectable ${selectedAccount===name?"selected":""}" data-account="${escapeHtml(name)}" data-group="${escapeHtml(group)}"><td>${escapeHtml(name)}</td><td>${escapeHtml(group)}</td><td>${onlineText}</td></tr>`;
  }).join("");
  $("accounts-empty").classList.toggle("hidden", users.length > 0);
  const names = groups.map((g)=>String(g.name));
  const options = names.map((name)=>`<option value="${escapeHtml(name)}">${escapeHtml(name)}</option>`).join("");
  ["account-group","new-group","permission-group"].forEach((id)=> { const el=$(id); const old=el.value; el.innerHTML=options; if (names.includes(old)) el.value=old; });
  if (!names.includes($("account-group").value)) $("account-group").value = names.includes("admin") ? "admin" : names[0] || "";
  if (!names.includes($("new-group").value)) $("new-group").value = names.includes("default") ? "default" : names[0] || "";
  if (!names.includes($("permission-group").value)) $("permission-group").value = names.includes("admin") ? "admin" : names[0] || "";
  renderGroupPermissions();
}
function renderGroupPermissions() {
  if (!adminData) return;
  const group = adminData.groups.find((g)=>g.name === $("permission-group").value);
  const rights = group?.permissions;
  const list = Array.isArray(rights) ? rights.map((x)=>String(x)) : String(rights || "").split(",").map((x)=>x.trim()).filter(Boolean);
  $("permission-list").value = list.join("\n");
  $("group-summary").textContent = group ? `${group.name} · родитель: ${group.parent || "нет"} · ${list.length} прямо назначено` : "Нет данных о выбранной группе.";
}
async function permissionAction(mode) {
  const permissions = $("permission-list").value.split(/[\n,;]+/).map((x)=>x.trim()).filter(Boolean);
  if (!permissions.length) { showToast("Введи хотя бы одно право.", true); return; }
  const group = $("permission-group").value;
  if (["admin","superadmin"].includes(group.toLowerCase()) && mode === "allow" && !confirm(`Меняешь права группы ${group}. Продолжить?`)) return;
  await post("/api/group/permission", {group, mode, permissions}, "Права группы обновлены.");
}
$("login-form").addEventListener("submit", login);
$("logout").addEventListener("click", async () => { try { await request("/api/logout", {}); } catch (_) {} showLogin(); });
$("nav").addEventListener("click", (event) => { const btn=event.target.closest("[data-page]"); if (btn) navigate(btn.dataset.page); });
document.addEventListener("click", (event) => {
  const nav=event.target.closest("[data-page]"); if (nav && !nav.classList.contains("nav-item")) navigate(nav.dataset.page);
  if (event.target.closest("[data-action='refresh']")) refresh();
  const kick=event.target.closest("[data-kick]"); if (kick && confirm(`Отключить игрока ${kick.dataset.kick}?`)) post("/api/kick", {player:kick.dataset.kick}, "Игрок отключён.");
  const account=event.target.closest("[data-account]"); if (account) { selectedAccount=account.dataset.account; $("account-user").value=selectedAccount; $("account-group").value=account.dataset.group; renderAdmin(); }
});
$("start-top").addEventListener("click", startServer); $("start-from-profile").addEventListener("click", startServer); $("stop-top").addEventListener("click", stopServer);
$("save-settings").addEventListener("click", saveSettings); $("refresh-state").addEventListener("click", refresh); $("profile-select").addEventListener("change", async (e)=>{await post("/api/profile/select",{id:e.target.value},"Профиль выбран.");});
$("profile-create").addEventListener("click", async ()=>{const name=prompt("Название нового сервера:");if(name)await post("/api/profile/create",{name},"Новый профиль создан.");});
$("profile-rename").addEventListener("click", async ()=>{const p=stateData?.profiles.find((x)=>x.id===$("profile-select").value);if(!p)return;const name=prompt("Новое название:",p.name);if(name)await post("/api/profile/rename",{id:p.id,name},"Профиль переименован.");});
$("profile-remove").addEventListener("click", async ()=>{const p=stateData?.profiles.find((x)=>x.id===$("profile-select").value);if(p&&confirm(`Убрать профиль «${p.name}» из списка? Его файлы останутся.`))await post("/api/profile/remove",{id:p.id},"Профиль убран.");});
$("world-select").addEventListener("change",()=>{const w=stateData?.worlds.find((x)=>x.name===$("world-select").value);$("world-detail").textContent=w?`${w.size_mb} МБ · последнее изменение ${w.modified}`:"";});
for (const id of ["world-select","setting-password","setting-slots","setting-autosave"]) $(id).addEventListener("input",()=>{settingsDirty=true;});
$("apply-mode").addEventListener("click", async ()=>{const mode=$("mode-select").value;if(confirm(`Сменить сложность активного мира на «${mode}»? Панель сначала сохранит резервную копию.`))await post("/api/mode",{mode},"Команда смены режима отправлена.");});
$("mode-select").addEventListener("change",()=>{modeDirty=true;});
$("toggle-pass").addEventListener("click",()=>{const input=$("setting-password");input.type=input.type==="password"?"text":"password";$("toggle-pass").textContent=input.type==="password"?"Показать":"Скрыть";});
$("copy-address").addEventListener("click",async()=>{const address=stateData?.game_address||`${location.hostname}:7777`;try{await navigator.clipboard.writeText(address);showToast("Адрес игры скопирован: "+address);}catch(_){showToast("Адрес игры: "+address);}});
$("command-form").addEventListener("submit",async(e)=>{e.preventDefault();const input=$("command-input"),command=input.value.trim();if(command){input.value="";await post("/api/command",{command},"Команда отправлена.");}});
$("chat-form").addEventListener("submit",async(e)=>{e.preventDefault();const input=$("chat-input"),message=input.value.trim();if(message){input.value="";await post("/api/chat",{message},"Сообщение отправлено.");}});
$("clear-console").addEventListener("click",()=>{$("console-log").replaceChildren();});
$("load-admin").addEventListener("click",loadAdmin); $("permission-group").addEventListener("change",renderGroupPermissions);
$("assign-group").addEventListener("click",async()=>{const user=$("account-user").value.trim(),group=$("account-group").value;if(!user){showToast("Выбери аккаунт.",true);return;}if(["admin","superadmin"].includes(group.toLowerCase())&&!confirm(`Выдать ${user} группу ${group}? Это административные права.`))return;await post("/api/account/group",{user,group},"Группа назначена.");});
$("personal-group").addEventListener("click",async()=>{const user=$("account-user").value.trim(),parent=$("account-group").value;if(!user){showToast("Выбери аккаунт.",true);return;}if(confirm(`Создать отдельную группу для ${user} на основе ${parent}?`))await post("/api/group/personal",{user,parent},"Личная группа создана.");});
$("create-account").addEventListener("click",async()=>{const user=$("new-user").value.trim(),password=$("new-password").value,group=$("new-group").value;if(!user||!password){showToast("Введи имя и пароль аккаунта.",true);return;}if(["admin","superadmin"].includes(group.toLowerCase())&&!confirm(`Создать ${user} с группой ${group}?`))return;const ok=await post("/api/account/create",{user,password,group},"Аккаунт создан.");if(ok){$("new-password").value="";$("new-user").value="";}});
$("allow-permissions").addEventListener("click",()=>permissionAction("allow")); $("deny-permissions").addEventListener("click",()=>permissionAction("deny")); $("clear-permissions").addEventListener("click",()=>permissionAction("clear"));
async function boot() {
  try { const session=await request("/api/session"); if(session.authenticated)showApp(); else showLogin(); }
  catch (_) { showLogin(); }
}
boot();

setInterval(()=>{if(!$("app").classList.contains("hidden"))refresh();},5000);
setInterval(()=>{if(!$("app").classList.contains("hidden"))pollLogs();},2200);