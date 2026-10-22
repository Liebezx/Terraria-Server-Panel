// History & Tab Navigation
let pageHistory = ["server"];
let historyIndex = 0;
let currentPlayers = [];
let selectedPlayerIndex = -1;
let genTimerInterval = null;
let genStartTime = 0;

const titles = {
  server: { title: "Управление сервером", subtitle: "Состояние сервера и быстрые действия" },
  players: { title: "Список игроков", subtitle: "Кто сейчас в игре и какими аккаунтами пользуется" },
  console: { title: "Консоль сервера", subtitle: "Журнал событий и отправка команд TShock" },
  worlds: { title: "Миры Terraria", subtitle: "Выбор активного мира, смена сложности и создание новых" },
  settings: { title: "Настройки и профили", subtitle: "Параметры сервера, пароль и изоляция миров" },
  gameplay: { title: "Геймплей и Защита TShock", subtitle: "Позиция игроков, авторизация, мобы, правила мира и цветные роли" },
  metrics: { title: "Нагрузка процесса", subtitle: "Потребление процессора и памяти процессом TShock" },
  admin: { title: "Админка TShock", subtitle: "Управление группами и правами доступа" }
};

function switchPage(pageName, addToHistory = true) {
  const targetPage = document.getElementById("page-" + pageName);
  if (!targetPage) return;

  // Update tabs
  document.querySelectorAll(".nav-item").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.page === pageName);
  });

  // Update pages
  document.querySelectorAll(".page").forEach(sec => {
    sec.classList.remove("active");
  });
  targetPage.classList.add("active");

  const contentEl = document.querySelector(".content");
  if (contentEl) contentEl.scrollTop = 0;
  window.scrollTo(0, 0);

  // Update headers
  if (titles[pageName]) {
    document.getElementById("page-title").textContent = titles[pageName].title;
    document.getElementById("page-subtitle").textContent = titles[pageName].subtitle;
  }

  // Update history
  if (addToHistory && pageHistory[historyIndex] !== pageName) {
    pageHistory = pageHistory.slice(0, historyIndex + 1);
    pageHistory.push(pageName);
    historyIndex = pageHistory.length - 1;
  }

  // Actions on switch
  if (pageName === "players") {
    refreshPlayersList();
  } else if (pageName === "worlds") {
    loadWorldsList();
  } else if (pageName === "settings") {
    loadSettingsData();
  } else if (pageName === "gameplay") {
    loadGameplayData();
  } else if (pageName === "metrics") {
    requestMetricsUpdate();
    if (metricsTimer) clearInterval(metricsTimer);
    metricsTimer = setInterval(requestMetricsUpdate, 1500);
  } else if (pageName === "admin") {
    loadAdminData();
  }

  if (pageName !== "metrics" && metricsTimer) {
    clearInterval(metricsTimer);
    metricsTimer = null;
  }

  // Inform backend about active page
  if (window.pywebview && window.pywebview.api && window.pywebview.api.on_page_switched) {
    window.pywebview.api.on_page_switched(pageName);
  }
}

// Mouse4 / Mouse5 Navigation
window.addEventListener("mouseup", (e) => {
  if (e.button === 3) {
    if (historyIndex > 0) {
      historyIndex--;
      switchPage(pageHistory[historyIndex], false);
    }
  } else if (e.button === 4) {
    if (historyIndex < pageHistory.length - 1) {
      historyIndex++;
      switchPage(pageHistory[historyIndex], false);
    }
  }
});

// Sidebar & DOM initialization
document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".nav-item").forEach(btn => {
    btn.addEventListener("click", () => {
      switchPage(btn.dataset.page);
    });
  });

  // Init custom dropdowns for all native select elements
  initCustomDropdowns();

  // Check if world generation is active
  if (window.pywebview && window.pywebview.api && window.pywebview.api.get_world_gen_status) {
    window.pywebview.api.get_world_gen_status().then(status => {
      if (status && status.active) {
        updateWorldGenProgress(status);
      }
    });
  }

  appendLog("Панель управления Terraria инициализирована.", "system");
});

// Tactile Button Border Frame Pulse (Frame only)
document.addEventListener("click", (e) => {
  const btn = e.target.closest(".btn, .nav-item, .custom-dropdown-trigger");
  if (!btn) return;
  btn.classList.remove("btn-border-pulse");
  void btn.offsetWidth;
  btn.classList.add("btn-border-pulse");
  setTimeout(() => btn.classList.remove("btn-border-pulse"), 380);
});

// Global Anti-Lag Click Debounce (300ms)
let lastGlobalClickTime = 0;
document.addEventListener("click", (e) => {
  const target = e.target.closest(".btn-refresh, #btn-toggle-server, .custom-dropdown-option");
  if (!target) return;
  const now = Date.now();
  if (now - lastGlobalClickTime < 300) {
    // Throttled rapid spam click
    return;
  }
  lastGlobalClickTime = now;
}, true);

// --- Custom Themed Modal Dialogs (Alert & Confirm) ---
let customDialogResolve = null;

function showCustomConfirm(message, title = "Подтверждение") {
  return new Promise(resolve => {
    customDialogResolve = resolve;
    const modal = document.getElementById("modal-custom-dialog");
    document.getElementById("custom-dialog-title").textContent = title;
    document.getElementById("custom-dialog-message").textContent = message;
    document.getElementById("btn-dialog-cancel").style.display = "inline-flex";
    document.getElementById("btn-dialog-ok").textContent = "Подтвердить";
    modal.classList.add("open");
    setTimeout(() => {
      const okBtn = document.getElementById("btn-dialog-ok");
      if (okBtn) okBtn.focus();
    }, 50);
  });
}

function showCustomAlert(message, title = "Уведомление") {
  return new Promise(resolve => {
    customDialogResolve = resolve;
    const modal = document.getElementById("modal-custom-dialog");
    document.getElementById("custom-dialog-title").textContent = title;
    document.getElementById("custom-dialog-message").textContent = message;
    document.getElementById("btn-dialog-cancel").style.display = "none";
    document.getElementById("btn-dialog-ok").textContent = "Понятно";
    modal.classList.add("open");
    setTimeout(() => {
      const okBtn = document.getElementById("btn-dialog-ok");
      if (okBtn) okBtn.focus();
    }, 50);
  });
}

function closeCustomDialog(result) {
  const modal = document.getElementById("modal-custom-dialog");
  modal.classList.remove("open");
  if (customDialogResolve) {
    const res = customDialogResolve;
    customDialogResolve = null;
    res(Boolean(result));
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const btnOk = document.getElementById("btn-dialog-ok");
  const btnCancel = document.getElementById("btn-dialog-cancel");
  if (btnOk) btnOk.addEventListener("click", () => closeCustomDialog(true));
  if (btnCancel) btnCancel.addEventListener("click", () => closeCustomDialog(false));

  window.addEventListener("keydown", (e) => {
    const modal = document.getElementById("modal-custom-dialog");
    if (modal && modal.classList.contains("open")) {
      if (e.key === "Escape") {
        closeCustomDialog(false);
      } else if (e.key === "Enter") {
        closeCustomDialog(true);
      }
    }
  });
});

// --- Custom Animated Dropdowns System ---
function initCustomDropdowns() {
  document.querySelectorAll("select.select-custom").forEach(select => {
    setupCustomDropdown(select);
  });
}

function setupCustomDropdown(select) {
  if (!select) return;
  let wrapper = select.nextElementSibling;
  if (!wrapper || !wrapper.classList.contains("custom-dropdown")) {
    wrapper = document.createElement("div");
    wrapper.className = "custom-dropdown";
    wrapper.id = "custom-dd-" + (select.id || Math.random().toString(36).substr(2, 9));

    const trigger = document.createElement("button");
    trigger.type = "button";
    trigger.className = "custom-dropdown-trigger";

    const label = document.createElement("span");
    label.className = "custom-dropdown-label";

    const chevron = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    chevron.setAttribute("viewBox", "0 0 24 24");
    chevron.setAttribute("class", "custom-dropdown-chevron");
    chevron.innerHTML = '<path fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" d="M6 9l6 6 6-6"/>';

    trigger.appendChild(label);
    trigger.appendChild(chevron);

    const menu = document.createElement("div");
    menu.className = "custom-dropdown-menu";

    wrapper.appendChild(trigger);
    wrapper.appendChild(menu);

    select.style.display = "none";
    select.parentNode.insertBefore(wrapper, select.nextSibling);

    trigger.addEventListener("click", (e) => {
      e.stopPropagation();
      openCustomDropdown(wrapper);
    });
  }

  refreshCustomDropdown(select);
}

function openCustomDropdown(wrapper) {
  const wasOpen = wrapper.classList.contains("open");
  closeAllCustomDropdowns();
  if (!wasOpen) {
    wrapper.classList.add("open");
    const parentCard = wrapper.closest(".card, .modal-card");
    const menu = wrapper.querySelector(".custom-dropdown-menu");
    if (parentCard && menu) {
      parentCard.classList.add("dropdown-active");
      const count = menu.children.length || 1;
      const menuH = Math.min(270, Math.max(45, count * 38));
      const basePadding = parentCard.classList.contains("modal-card") ? 24 : 20;
      parentCard.style.paddingBottom = (basePadding + menuH + 14) + "px";
    }
  }
}

function refreshCustomDropdown(select) {
  if (!select) return;
  const wrapper = select.nextElementSibling;
  if (!wrapper || !wrapper.classList.contains("custom-dropdown")) return;

  const label = wrapper.querySelector(".custom-dropdown-label");
  const menu = wrapper.querySelector(".custom-dropdown-menu");
  menu.innerHTML = "";

  const options = Array.from(select.options);
  if (options.length === 0) {
    label.textContent = "—";
    return;
  }

  let selectedOpt = select.options[select.selectedIndex] || options[0];
  label.textContent = selectedOpt.textContent || selectedOpt.value;

  options.forEach((opt, idx) => {
    const item = document.createElement("div");
    item.className = "custom-dropdown-option" + (opt.selected ? " selected" : "");
    item.textContent = opt.textContent;
    item.dataset.value = opt.value;

    item.addEventListener("click", (e) => {
      e.stopPropagation();
      select.selectedIndex = idx;
      select.value = opt.value;
      label.textContent = opt.textContent;

      menu.querySelectorAll(".custom-dropdown-option").forEach(el => el.classList.remove("selected"));
      item.classList.add("selected");
      closeAllCustomDropdowns();

      select.dispatchEvent(new Event("change", { bubbles: true }));
    });

    menu.appendChild(item);
  });
}

function closeAllCustomDropdowns() {
  document.querySelectorAll(".custom-dropdown.open").forEach(dd => {
    dd.classList.remove("open");
    const parentCard = dd.closest(".card, .modal-card");
    if (parentCard) {
      parentCard.classList.remove("dropdown-active");
      parentCard.style.paddingBottom = "";
    }
  });
}

document.addEventListener("click", () => {
  closeAllCustomDropdowns();
});

// --- Custom Frameless Window Controls ---
function windowMinimize() {
  if (window.pywebview && window.pywebview.api && window.pywebview.api.minimize_window) {
    window.pywebview.api.minimize_window();
  }
}

function windowToggleMaximize() {
  if (window.pywebview && window.pywebview.api && window.pywebview.api.toggle_maximize_window) {
    window.pywebview.api.toggle_maximize_window();
  }
}

function windowClose() {
  if (window.pywebview && window.pywebview.api && window.pywebview.api.close_window) {
    window.pywebview.api.close_window();
  }
}

// Backend State Updates
let serverToggleBusy = false;
let currentServerRunning = false;

function updateServerState(state) {
  if (!state) return;

  currentServerRunning = Boolean(state.running);
  serverToggleBusy = false;

  const dot = document.getElementById("server-status-dot");
  const text = document.getElementById("server-status-text");
  const btn = document.getElementById("btn-toggle-server");
  const btnText = document.getElementById("btn-toggle-text");
  const btnIcon = document.getElementById("btn-toggle-icon");

  if (btn) btn.disabled = false;

  if (state.running) {
    if (dot) dot.className = "status-dot running";
    if (text) text.textContent = "СЕРВЕР РАБОТАЕТ";
    if (btn) btn.className = "btn btn-danger";
    if (btnIcon) btnIcon.innerHTML = "⏹";
    if (btnText) btnText.textContent = "Остановить сервер";
  } else {
    if (dot) dot.className = "status-dot stopped";
    if (text) text.textContent = "СЕРВЕР ВЫКЛЮЧЕН";
    if (btn) btn.className = "btn btn-primary";
    if (btnIcon) btnIcon.innerHTML = "▶";
    if (btnText) btnText.textContent = "Запустить сервер";
  }

  if (state.profile_name) {
    document.getElementById("action-server-name").textContent = "Текущий профиль: " + state.profile_name;
  }

  if (state.world_name) {
    document.getElementById("card-world-name").textContent = state.world_name;
  }
  if (state.world_mode) {
    document.getElementById("card-world-mode").textContent = "Режим: " + state.world_mode;
  }
  if (state.players_count !== undefined) {
    document.getElementById("card-players-count").textContent = state.players_count + " / " + (state.max_players || 8);
  }
  if (state.uptime) {
    document.getElementById("card-uptime").textContent = state.uptime;
    document.getElementById("card-uptime-desc").textContent = state.running ? "Сервер онлайн" : "Сервер выключен";
  }
  if (state.address) {
    document.getElementById("card-address").textContent = state.address;
  }
  if (state.rest_status) {
    document.getElementById("card-rest-status").textContent = state.rest_status;
  }

  if (Array.isArray(state.players)) {
    renderPlayers(state.players);
  }
}

function copyServerAddress() {
  const el = document.getElementById("card-address");
  if (!el) return;
  const addr = el.textContent.trim();
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(addr).then(() => {
      alert("✓ Адрес для подключения скопирован:\n" + addr + "\n\nОтправьте его друзьям для подключения к серверу!");
    }).catch(() => {
      prompt("Скопируйте адрес сервера для друзей:", addr);
    });
  } else {
    prompt("Скопируйте адрес сервера для друзей:", addr);
  }
}

window.updatePlayitAddress = function(newAddr) {
  if (!newAddr) return;
  const el = document.getElementById("card-address");
  const st = document.getElementById("card-rest-status");
  if (el) {
    el.textContent = newAddr;
    el.style.color = "var(--neon)";
  }
  if (st) {
    st.textContent = "🌐 Туннель Playit.gg активен • Локально: localhost:7777";
  }
};

function toggleServer() {
  if (serverToggleBusy) return;
  serverToggleBusy = true;

  const btn = document.getElementById("btn-toggle-server");
  const btnText = document.getElementById("btn-toggle-text");
  const btnIcon = document.getElementById("btn-toggle-icon");

  if (btn) btn.disabled = true;

  if (currentServerRunning) {
    // Stopping
    if (btnIcon) btnIcon.innerHTML = '<span class="btn-spinner-circle"></span>';
    if (btnText) btnText.textContent = "Остановка сервера...";
    appendLog("Отправка команды выключения сервера...", "notice");
  } else {
    // Starting
    if (btnIcon) btnIcon.innerHTML = '<span class="btn-spinner-circle"></span>';
    if (btnText) btnText.textContent = "Запуск сервера...";
    appendLog("Инициализация запуска сервера TShock...", "notice");
  }

  if (window.pywebview && window.pywebview.api) {
    window.pywebview.api.toggle_server();
  }
}

// Players Management
function renderPlayers(players) {
  currentPlayers = players || [];
  const tbody = document.getElementById("players-tbody");
  if (!tbody) return;

  if (currentPlayers.length === 0) {
    tbody.innerHTML = '<tr><td colspan="4" class="empty-state">Сейчас на сервере нет игроков онлайн.</td></tr>';
    selectedPlayerIndex = -1;
    updateSelectedPlayerLabel();
    return;
  }

  let html = "";
  currentPlayers.forEach((p, idx) => {
    const isSel = idx === selectedPlayerIndex ? "selected" : "";
    const name = escapeHtml(p.nickname || p.name || "—");
    const user = escapeHtml(p.username || p.user || p.account || "—");
    const group = escapeHtml(p.group || p.role || "default");
    const pos = escapeHtml(formatPosition(p));

    html += `<tr class="${isSel}" onclick="selectPlayerRow(${idx})">
      <td><strong>${name}</strong></td>
      <td>${user}</td>
      <td><span style="color: var(--neon); font-size: 12px;">${group}</span></td>
      <td style="color: var(--dim);">${pos}</td>
    </tr>`;
  });
  tbody.innerHTML = html;
  updateSelectedPlayerLabel();
}

function selectPlayerRow(index) {
  selectedPlayerIndex = index;
  renderPlayers(currentPlayers);
}

function updateSelectedPlayerLabel() {
  const lbl = document.getElementById("selected-player-label");
  if (!lbl) return;
  if (selectedPlayerIndex >= 0 && selectedPlayerIndex < currentPlayers.length) {
    const p = currentPlayers[selectedPlayerIndex];
    lbl.textContent = `Выбран: ${p.nickname || p.name || "—"}`;
    lbl.style.color = "var(--text)";
  } else {
    lbl.textContent = "Игрок не выбран";
    lbl.style.color = "var(--muted)";
  }
}

function formatPosition(p) {
  if (p.position && typeof p.position === "object") {
    const x = Math.round(p.position.x || 0);
    const y = Math.round(p.position.y || 0);
    return `${x}, ${y}`;
  }
  if (p.x !== undefined && p.y !== undefined) {
    return `${Math.round(p.x)}, ${Math.round(p.y)}`;
  }
  return "—";
}

async function kickSelectedPlayer() {
  if (selectedPlayerIndex < 0 || selectedPlayerIndex >= currentPlayers.length) {
    await showCustomAlert("Сначала выбери игрока в таблице.", "Выбор игрока");
    return;
  }
  const p = currentPlayers[selectedPlayerIndex];
  const name = p.nickname || p.name;
  const reason = document.getElementById("kick-reason").value.trim();

  const ok = await showCustomConfirm(`Отключить игрока "${name}" от сервера?`, "Кик игрока");
  if (!ok) return;

  if (window.pywebview && window.pywebview.api) {
    window.pywebview.api.kick_player(name, reason).then(res => {
      document.getElementById("kick-reason").value = "";
      refreshPlayersList();
    });
  }
}

function spinButtonIcon(btn) {
  if (!btn) return;
  const icon = btn.querySelector(".refresh-icon") || btn;
  icon.classList.remove("spin-icon");
  void icon.offsetWidth;
  icon.classList.add("spin-icon");
  setTimeout(() => icon.classList.remove("spin-icon"), 600);
}

function refreshPlayersList(btn) {
  if (btn) {
    if (btn.disabled) return;
    btn.disabled = true;
    spinButtonIcon(btn);
    setTimeout(() => { if (btn) btn.disabled = false; }, 800);
  }
  if (window.pywebview && window.pywebview.api) {
    window.pywebview.api.get_players().then(players => {
      renderPlayers(players);
    });
  }
}

// Console & Log Management
const MAX_CONSOLE_LINES = 500;

function appendLog(line, tag = "stdout") {
  const box = document.getElementById("console-output");
  if (!box) return;

  const now = new Date();
  const timeStr = now.toTimeString().split(" ")[0];

  const div = document.createElement("div");
  div.className = "console-line";

  let tagClass = "tag-stdout";
  let tagText = "LOG";
  if (tag === "stderr") {
    tagClass = "tag-stderr";
    tagText = "ERR";
  } else if (tag === "system") {
    tagClass = "tag-system";
    tagText = "SYS";
  } else if (tag === "notice") {
    tagClass = "tag-notice";
    tagText = "INF";
  }

  div.innerHTML = `<span class="time">[${timeStr}]</span> <span class="tag ${tagClass}">[${tagText}]</span> <span class="msg">${escapeHtml(line)}</span>`;
  box.appendChild(div);

  // Enforce 500 lines limit to prevent lag
  while (box.children.length > MAX_CONSOLE_LINES) {
    box.removeChild(box.firstChild);
  }

  // Auto-scroll to bottom
  box.scrollTop = box.scrollHeight;
}

async function copyConsoleLog(btn) {
  const output = document.getElementById("console-output");
  if (!output) return;
  const text = output.innerText || output.textContent;
  if (!text || text.trim() === "") {
    await showCustomAlert("Журнал консоли пуст.", "Буфер обмена");
    return;
  }
  try {
    await navigator.clipboard.writeText(text);
    appendLog("Весь журнал консоли скопирован в буфер обмена.", "notice");
    if (btn) {
      const orig = btn.innerHTML;
      btn.innerHTML = "✓ Скопировано!";
      setTimeout(() => { btn.innerHTML = orig; }, 1800);
    }
  } catch (e) {
    await showCustomAlert("Не удалось скопировать журнал: " + e, "Буфер обмена");
  }
}

function clearConsoleLog() {
  const box = document.getElementById("console-output");
  if (box) box.innerHTML = "";
  appendLog("Журнал консоли очищен.", "system");
}

function sendServerCommand() {
  const input = document.getElementById("cmd-input");
  const cmd = input.value.trim();
  if (!cmd) return;

  input.value = "";
  appendLog("> " + cmd, "notice");

  if (window.pywebview && window.pywebview.api) {
    window.pywebview.api.send_command(cmd).then(res => {
      if (res && res.error) {
        appendLog("Ошибка команды: " + res.error, "error");
      } else if (res && res.response && res.response !== "Команда выполнена.") {
        appendLog(res.response, "system");
      }
    }).catch(err => {
      appendLog("Ошибка отправки команды: " + err, "error");
    });
  }
}

function sendChatMessage() {
  const input = document.getElementById("chat-input");
  const msg = input.value.trim();
  if (!msg) return;

  input.value = "";

  if (window.pywebview && window.pywebview.api) {
    window.pywebview.api.send_chat(msg).then(res => {
      if (res && res.error) {
        appendLog("Ошибка чата: " + res.error, "error");
      }
    }).catch(err => {
      appendLog("Ошибка отправки в чат: " + err, "error");
    });
  }
}

// Worlds Management
function loadWorldsList(btn) {
  if (btn) {
    if (btn.disabled) return;
    btn.disabled = true;
    spinButtonIcon(btn);
    setTimeout(() => { if (btn) btn.disabled = false; }, 800);
  }
  if (window.pywebview && window.pywebview.api) {
    window.pywebview.api.get_worlds_list().then(data => {
      const select = document.getElementById("worlds-select");
      if (!select) return;
      select.innerHTML = "";

      const worlds = data.worlds || [];
      const current = data.current || "";

      if (worlds.length === 0) {
        const opt = document.createElement("option");
        opt.value = "";
        opt.textContent = "Миры не найдены — нажмите «Создать мир»";
        select.appendChild(opt);
      } else {
        worlds.forEach(w => {
          const opt = document.createElement("option");
          opt.value = w.filename;
          opt.textContent = `${w.name} (${w.filename}) • ${w.size_mb} МБ`;
          if (w.filename === current) opt.selected = true;
          select.appendChild(opt);
        });
      }

      if (current) {
        select.value = current;
      }

      refreshCustomDropdown(select);
      updateWorldInfoDisplay(data.info);
    });
  }
}

function onWorldSelectedChange() {
  const select = document.getElementById("worlds-select");
  if (!select) return;
  const picked = select.value;
  if (window.pywebview && window.pywebview.api) {
    window.pywebview.api.get_world_details(picked).then(info => {
      updateWorldInfoDisplay(info);
    });
  }
}

async function applyActiveWorld() {
  if (currentServerRunning) {
    await showCustomAlert("Перед выбором другого мира остановите сервер. Смена активного мира 'на лету' приводит к повреждению кэша карты и рассинхронизации у игроков!", "Защита мира Terraria");
    return;
  }
  const select = document.getElementById("worlds-select");
  if (!select) return;
  const filename = select.value;
  if (!filename) {
    await showCustomAlert("Мир не выбран.", "Выбор мира");
    return;
  }
  if (window.pywebview && window.pywebview.api) {
    window.pywebview.api.set_active_world(filename).then(async res => {
      if (res.ok) {
        appendLog(`Активный мир изменён на "${filename}"`, "notice");
        loadWorldsList();
        await showCustomAlert(`Мир проверен и успешно активирован: ${filename}`, "Мир сервера");
      } else {
        await showCustomAlert(res.error || "Не удалось выбрать мир", "Ошибка");
      }
    });
  }
}

async function archiveSelectedWorld() {
  const select = document.getElementById("worlds-select");
  if (!select) return;
  const filename = select.value;
  if (!filename) {
    await showCustomAlert("Мир не выбран.", "Выбор мира");
    return;
  }

  if (currentServerRunning) {
    await showCustomAlert("Нельзя убрать активный мир во время работы сервера. Сначала остановите сервер!", "Защита сервера");
    return;
  }

  const ok = await showCustomConfirm(
    `Убрать мир "${filename}" из списка миров?\nФайл мира будет безопасно сохранён в архив резервных копий (Worlds/Backups/RemovedWorlds).`,
    "Убрать мир из списка"
  );
  if (!ok) return;

  if (window.pywebview && window.pywebview.api && window.pywebview.api.remove_world_from_list) {
    window.pywebview.api.remove_world_from_list(filename).then(async res => {
      if (res.ok) {
        appendLog(res.message || `Мир "${filename}" убран из списка.`, "notice");
        loadWorldsList();
        await showCustomAlert(`Мир "${filename}" успешно убран из списка и сохранён в архив.`, "Мир убран");
      } else {
        await showCustomAlert(res.error || "Не удалось убрать мир", "Ошибка");
      }
    });
  }
}

function updateWorldInfoDisplay(info) {
  if (!info) return;
  document.getElementById("wi-name").textContent = info.name || "—";
  document.getElementById("wi-mode").textContent = info.mode_name || "—";

  const hmEl = document.getElementById("wi-hardmode");
  if (info.special_seeds && info.special_seeds.some(s => s.force_hardmode)) {
    hmEl.innerHTML = '<span style="color: #fbbf24; font-weight: 700;">Да (Хардмод · сид Tooeasy)</span>';
  } else if (info.hardmode) {
    hmEl.innerHTML = '<span style="color: #10b981; font-weight: 700;">Да (Хардмод)</span>';
  } else {
    hmEl.innerHTML = '<span style="color: var(--dim);">Нет (Пре-хардмод)</span>';
  }

  document.getElementById("wi-size").textContent = (info.size_mb ? info.size_mb + " МБ" : "—");

  // Render special seeds pills
  const seedsBox = document.getElementById("wi-special-seeds-box");
  if (seedsBox) {
    if (info.special_seeds && info.special_seeds.length > 0) {
      seedsBox.style.display = "flex";
      let html = "";
      info.special_seeds.forEach(s => {
        const color = s.color || "amber";
        const icon = s.force_hardmode ? "⚡" : (color === "orange" ? "🎃" : (color === "red" ? "🔥" : (color === "purple" ? "🔮" : "✨")));
        html += `<div class="special-seed-pill ${escapeHtml(color)}">
          <span class="seed-pill-icon">${icon}</span>
          <div class="seed-pill-content">
            <span class="seed-pill-title">${escapeHtml(s.title || "Секретный сид")}</span>
            <span class="seed-pill-desc">${escapeHtml(s.desc || "")}</span>
          </div>
        </div>`;
      });
      seedsBox.innerHTML = html;
    } else {
      seedsBox.style.display = "none";
      seedsBox.innerHTML = "";
    }
  }

  const rawBox = document.getElementById("world-raw-box");
  if (rawBox && info.raw) {
    rawBox.textContent = info.raw;
  }
}

function toggleWorldRawInfo(btn) {
  const box = document.getElementById("world-raw-box");
  if (!box) return;
  const isOpen = box.classList.toggle("open");
  if (btn) {
    btn.textContent = isOpen ? "Скрыть технический лог" : "Показать технический лог";
  }
}

// Modal: Import World from Documents or Disk
function openImportWorldModal() {
  document.getElementById("modal-import-world").classList.add("open");
  loadGameDocumentsWorlds();
}

function closeImportWorldModal() {
  document.getElementById("modal-import-world").classList.remove("open");
}

function loadGameDocumentsWorlds(btn) {
  if (btn) {
    if (btn.disabled) return;
    btn.disabled = true;
    spinButtonIcon(btn);
    setTimeout(() => { if (btn) btn.disabled = false; }, 800);
  }
  const container = document.getElementById("game-worlds-list");
  if (!container) return;
  container.innerHTML = '<div class="empty-state">Поиск миров в Документах...</div>';

  if (window.pywebview && window.pywebview.api) {
    window.pywebview.api.get_game_documents_worlds().then(worlds => {
      if (!worlds || worlds.length === 0) {
        container.innerHTML = '<div class="empty-state">Миры Terraria в Документах не найдены.<br>Используй кнопку ниже, чтобы выбрать файл вручную.</div>';
        return;
      }
      container.innerHTML = "";
      worlds.forEach(w => {
        const card = document.createElement("div");
        card.className = "doc-world-card";

        const info = document.createElement("div");
        info.innerHTML = `
          <div style="font-size: 13px; font-weight: 600; color: #fff;">${escapeHtml(w.name)}</div>
          <div style="font-size: 11px; color: var(--muted); margin-top: 3px;">
            ${escapeHtml(w.filename)} • ${w.size_mb} МБ • <span style="color: var(--neon); font-weight: 500;">${escapeHtml(w.mode_name)}</span> • <span style="color: var(--dim);">${w.mtime}</span>
          </div>
        `;

        const actionBtn = document.createElement("button");
        actionBtn.className = "btn btn-primary btn-small";
        actionBtn.textContent = "Выбрать";
        actionBtn.onclick = () => importWorldFromPath(w.path);

        card.appendChild(info);
        card.appendChild(actionBtn);
        container.appendChild(card);
      });
    }).catch(err => {
      container.innerHTML = `<div class="empty-state" style="color: var(--red);">Ошибка: ${escapeHtml(String(err))}</div>`;
    });
  }
}

function importWorldFromPath(path) {
  if (window.pywebview && window.pywebview.api) {
    window.pywebview.api.import_world_from_path(path).then(async res => {
      if (res && res.ok) {
        appendLog(`Мир "${res.world_name}" успешно загружен и установлен!`, "notice");
        closeImportWorldModal();
        loadWorldsList();
        await showCustomAlert(`Мир "${res.world_name}" успешно загружен и установлен на сервер!`, "Мир загружен");
      } else {
        await showCustomAlert(res.error || "Не удалось загрузить мир", "Ошибка загрузки");
      }
    });
  }
}

function browseDiskWorld() {
  if (window.pywebview && window.pywebview.api) {
    window.pywebview.api.browse_and_import_world().then(async res => {
      if (res && res.ok) {
        appendLog(`Мир "${res.world_name}" успешно импортирован!`, "notice");
        closeImportWorldModal();
        loadWorldsList();
        await showCustomAlert(`Мир "${res.world_name}" успешно импортирован на сервер!`, "Мир загружен");
      } else if (res && res.error) {
        await showCustomAlert(res.error, "Ошибка импорта");
      }
    });
  }
}

async function applyWorldMode() {
  const select = document.getElementById("mode-select");
  const mode = select.value;
  const ok = await showCustomConfirm(`Изменить режим сложности мира на "${mode}"? Перед сменой будет создана резервная копия.`, "Смена сложности");
  if (!ok) return;

  if (window.pywebview && window.pywebview.api) {
    window.pywebview.api.change_world_mode(mode).then(async res => {
      if (res.ok) {
        appendLog(`Режим мира изменён на: ${mode}`, "notice");
        loadWorldsList();
        await showCustomAlert(`Сложность мира успешно переключена на: ${mode}`, "Режим мира");
      } else {
        await showCustomAlert(res.error || "Не удалось изменить режим мира", "Ошибка смены режима");
      }
    });
  }
}

// --- Real-Time Top World Generation Progress Banner ---
let genBannerTimeout = null;

function updateWorldGenProgress(data) {
  if (!data) return;
  const banner = document.getElementById("top-gen-banner");
  if (!banner) return;

  const titleEl = document.getElementById("top-gen-title");
  const stageEl = document.getElementById("top-gen-stage");
  const pctEl = document.getElementById("top-gen-pct");
  const fillEl = document.getElementById("top-gen-bar-fill");
  const spinnerEl = document.getElementById("top-gen-spinner");

  if (genBannerTimeout) {
    clearTimeout(genBannerTimeout);
    genBannerTimeout = null;
  }

  if (data.active) {
    banner.style.display = "flex";
    banner.style.borderColor = "var(--border-focus)";
    if (titleEl) titleEl.textContent = `Создание мира "${data.world_name || "Мир"}"`;
    if (stageEl) stageEl.textContent = `— ${data.stage || "Генерация ландшафта..."}`;
    const pct = Math.min(100, Math.max(0, data.percent || 0));
    if (pctEl) pctEl.textContent = `${pct}%`;
    if (fillEl) fillEl.style.width = `${pct}%`;
    if (spinnerEl) spinnerEl.style.display = "inline-block";
  } else if (data.done) {
    banner.style.display = "flex";
    banner.style.borderColor = "var(--neon)";
    if (titleEl) titleEl.textContent = `✓ Мир "${data.world_name || "Мир"}" успешно создан!`;
    if (stageEl) stageEl.textContent = "— Готов к игре";
    if (pctEl) pctEl.textContent = "100%";
    if (fillEl) fillEl.style.width = "100%";
    if (spinnerEl) spinnerEl.style.display = "none";

    // Refresh worlds dropdown so the new world appears immediately!
    loadWorldsList();
    if (window.pywebview && window.pywebview.api && window.pywebview.api.get_ui_state) {
      window.pywebview.api.get_ui_state().then(st => updateServerState(st));
    }
    appendLog(`Мир "${data.world_name}" успешно создан и выбран!`, "notice");

    // Auto-hide after 4.5 seconds
    genBannerTimeout = setTimeout(() => {
      banner.style.display = "none";
    }, 4500);
  } else if (data.error) {
    banner.style.display = "flex";
    banner.style.borderColor = "var(--red)";
    if (titleEl) titleEl.textContent = `Ошибка создания мира "${data.world_name || ""}"`;
    if (stageEl) stageEl.textContent = `— ${data.error}`;
    if (spinnerEl) spinnerEl.style.display = "none";
    if (pctEl) pctEl.textContent = "Ошибка";

    appendLog(`Ошибка создания мира: ${data.error}`, "error");

    genBannerTimeout = setTimeout(() => {
      banner.style.display = "none";
    }, 6000);
  }
}

let currentRenamingFilename = "";

function openRenameWorldModal() {
  const select = document.getElementById("worlds-select");
  if (!select) return;
  const filename = select.value;
  if (!filename) {
    showCustomAlert("Сначала выберите мир из списка для переименования.", "Переименование мира");
    return;
  }
  if (currentServerRunning) {
    const activeWorld = document.getElementById("card-world-name") ? document.getElementById("card-world-name").textContent : "";
    if (activeWorld.includes(filename) || filename.includes(activeWorld)) {
      showCustomAlert("Нельзя переименовать активный мир во время работы сервера. Сначала остановите сервер!", "Защита сервера");
      return;
    }
  }

  currentRenamingFilename = filename;
  const cleanName = filename.replace(/\.wld$/i, "");
  document.getElementById("rename-world-old").value = filename;
  const newInp = document.getElementById("rename-world-new");
  newInp.value = cleanName;
  const errEl = document.getElementById("rename-world-error");
  if (errEl) { errEl.textContent = ""; errEl.style.display = "none"; }
  document.getElementById("modal-rename-world").classList.add("open");
  setTimeout(() => { newInp.focus(); newInp.select(); }, 100);
}

function closeRenameWorldModal() {
  document.getElementById("modal-rename-world").classList.remove("open");
  currentRenamingFilename = "";
}

async function submitRenameWorld() {
  const newName = document.getElementById("rename-world-new").value.trim();
  const errEl = document.getElementById("rename-world-error");
  if (!newName) {
    if (errEl) { errEl.textContent = "Укажите новое название мира"; errEl.style.display = "block"; }
    return;
  }

  const btn = document.getElementById("btn-submit-rename-world");
  if (btn) btn.disabled = true;

  if (window.pywebview && window.pywebview.api && window.pywebview.api.rename_world) {
    try {
      const res = await window.pywebview.api.rename_world(currentRenamingFilename, newName);
      if (res.ok) {
        closeRenameWorldModal();
        appendLog(`Мир успешно переименован в «${res.new_filename}»`, "notice");
        loadWorldsList();
        await showCustomAlert(`Мир успешно переименован:\n«${res.new_filename}»`, "Переименование мира");
      } else {
        if (errEl) { errEl.textContent = res.error || "Ошибка при переименовании"; errEl.style.display = "block"; }
      }
    } catch (e) {
      if (errEl) { errEl.textContent = String(e); errEl.style.display = "block"; }
    } finally {
      if (btn) btn.disabled = false;
    }
  }
}

// Background World Generation Modal
function openCreateWorldModal() {
  document.getElementById("modal-create-world").classList.add("open");
  document.getElementById("gen-world-name").focus();
}

function closeCreateWorldModal() {
  document.getElementById("modal-create-world").classList.remove("open");
}

async function submitCreateWorld() {
  const name = document.getElementById("gen-world-name").value.trim();
  const size = parseInt(document.getElementById("gen-world-size").value) || 2;
  const mode = parseInt(document.getElementById("gen-world-mode").value) || 0;
  const seed = document.getElementById("gen-world-seed").value.trim();

  if (!name) {
    await showCustomAlert("Укажи имя для нового мира.", "Имя мира");
    return;
  }

  // Close modal immediately so the user can freely use the panel
  closeCreateWorldModal();

  // Show top banner immediately at 0%
  const banner = document.getElementById("top-gen-banner");
  if (banner) {
    banner.style.display = "flex";
    banner.style.borderColor = "var(--border-focus)";
    document.getElementById("top-gen-title").textContent = `Создание мира "${name}"`;
    document.getElementById("top-gen-stage").textContent = "— Запуск генератора...";
    document.getElementById("top-gen-pct").textContent = "0%";
    document.getElementById("top-gen-bar-fill").style.width = "0%";
    const sp = document.getElementById("top-gen-spinner");
    if (sp) sp.style.display = "inline-block";
  }

  appendLog(`Запущена генерация нового мира "${name}". Прогресс отображается в верхней панели.`, "notice");

  if (window.pywebview && window.pywebview.api) {
    window.pywebview.api.create_world_background(name, size, mode, seed).then(async res => {
      if (!res.ok) {
        await showCustomAlert("Ошибка создания мира: " + res.error, "Ошибка генерации");
        if (banner) banner.style.display = "none";
      }
    });
  }
}

// Settings & Profiles Management
function loadSettingsData() {
  if (window.pywebview && window.pywebview.api) {
    window.pywebview.api.get_profiles_data().then(data => {
      const select = document.getElementById("profiles-select");
      if (!select) return;
      select.innerHTML = "";

      (data.profiles || []).forEach(p => {
        const opt = document.createElement("option");
        opt.value = p.id;
        opt.textContent = p.name;
        if (p.id === data.active_id) opt.selected = true;
        select.appendChild(opt);
      });

      refreshCustomDropdown(select);

      document.getElementById("cfg-server-pass").value = data.settings.password || "";
      document.getElementById("cfg-max-slots").value = data.settings.max_slots || 8;
      
      const autoSel = document.getElementById("cfg-autosave");
      if (autoSel) {
        autoSel.value = String(data.settings.autosave !== false);
        refreshCustomDropdown(autoSel);
      }
    });
  }
}

function switchProfileSelect() {
  const select = document.getElementById("profiles-select");
  const pid = select.value;
  if (window.pywebview && window.pywebview.api) {
    window.pywebview.api.switch_profile(pid).then(async res => {
      if (res.ok) {
        appendLog(`Переключено на профиль "${res.profile_name}"`, "notice");
        loadSettingsData();
      } else {
        await showCustomAlert(res.error || "Не удалось переключить профиль", "Ошибка профиля");
        loadSettingsData();
      }
    });
  }
}

async function deleteCurrentProfile() {
  const ok = await showCustomConfirm("Удалить текущий сервер навсегда?\nЕго папка, аккаунты TShock и отдельный мир будут удалены.\n(Общий мир останется).", "Удаление сервера");
  if (!ok) return;

  if (window.pywebview && window.pywebview.api) {
    window.pywebview.api.delete_current_profile().then(async res => {
      if (res.ok) {
        appendLog(res.message || "Сервер удалён.", "notice");
        loadSettingsData();
      } else {
        await showCustomAlert(res.error || "Не удалось удалить профиль", "Ошибка удаления");
      }
    });
  }
}

function copyServerPassword() {
  const pass = document.getElementById("cfg-server-pass").value;
  navigator.clipboard.writeText(pass).then(async () => {
    appendLog("Пароль сервера скопирован в буфер обмена.", "notice");
    await showCustomAlert("Пароль сервера скопирован: " + (pass || "(без пароля)"), "Пароль скопирован");
  });
}

function generateRandomPassword() {
  const chars = "abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  let pass = "";
  for (let i = 0; i < 9; i++) {
    pass += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  document.getElementById("cfg-server-pass").value = pass;
}

function saveServerSettings() {
  const pass = document.getElementById("cfg-server-pass").value.trim();
  const maxSlots = parseInt(document.getElementById("cfg-max-slots").value) || 8;
  const autosave = document.getElementById("cfg-autosave").value === "true";

  if (window.pywebview && window.pywebview.api) {
    window.pywebview.api.save_server_settings(pass, maxSlots, autosave).then(async res => {
      if (res.ok) {
        appendLog("Настройки сервера успешно сохранены.", "notice");
        if (res.ui_state) {
          updateServerState(res.ui_state);
        }
        await showCustomAlert("Настройки сохранены. Применятся при следующем запуске сервера.", "Настройки");
      } else {
        await showCustomAlert(res.error || "Ошибка сохранения настроек", "Ошибка сохранения");
      }
    });
  }
}

// Single-Window Server Wizard (Centered modal, No askstring!)
function openCreateServerModal() {
  document.getElementById("modal-create-server").classList.add("open");
  document.getElementById("wiz-server-name").value = "";

  // Populate existing worlds
  if (window.pywebview && window.pywebview.api) {
    window.pywebview.api.get_worlds_list().then(data => {
      const select = document.getElementById("wiz-select-existing");
      select.innerHTML = "";
      (data.worlds || []).forEach(w => {
        const opt = document.createElement("option");
        opt.value = w.filename;
        opt.textContent = `${w.name} (${w.filename})`;
        select.appendChild(opt);
      });
      refreshCustomDropdown(select);
    });
  }
}

function closeCreateServerModal() {
  document.getElementById("modal-create-server").classList.remove("open");
}

function toggleWizardWorldMode() {
  const mode = document.querySelector('input[name="wiz-world-type"]:checked').value;
  document.getElementById("wiz-choice-existing").style.display = mode === "existing" ? "block" : "none";
  document.getElementById("wiz-choice-new").style.display = mode === "new" ? "flex" : "none";
}

async function submitCreateServer() {
  const name = document.getElementById("wiz-server-name").value.trim();
  if (!name) {
    await showCustomAlert("Укажи название для нового сервера.", "Новый сервер");
    return;
  }

  const worldType = document.querySelector('input[name="wiz-world-type"]:checked').value;
  let params = { name: name, world_type: worldType };

  if (worldType === "existing") {
    params.world_file = document.getElementById("wiz-select-existing").value;
  } else {
    params.world_size = parseInt(document.getElementById("wiz-gen-size").value) || 2;
    params.world_mode = parseInt(document.getElementById("wiz-gen-mode").value) || 0;
    params.world_seed = document.getElementById("wiz-gen-seed").value.trim();
  }

  if (window.pywebview && window.pywebview.api) {
    window.pywebview.api.create_profile_wizard(params).then(async res => {
      if (res.ok) {
        appendLog(`Новый профиль "${name}" успешно создан!`, "notice");
        closeCreateServerModal();
        loadSettingsData();
        await showCustomAlert(`Сервер "${name}" успешно создан и выбран!`, "Сервер создан");
      } else {
        await showCustomAlert("Ошибка создания сервера: " + res.error, "Ошибка создания");
      }
    });
  }
}

// Metrics Updates
let metricsTimer = null;

function updateMetrics(data) {
  if (!data) return;

  const cpuVal = document.getElementById("metric-cpu-val");
  const cpuFill = document.getElementById("metric-cpu-fill");
  const cpuDesc = document.getElementById("metric-cpu-desc");

  const ramVal = document.getElementById("metric-ram-val");
  const ramFill = document.getElementById("metric-ram-fill");
  const ramDesc = document.getElementById("metric-ram-desc");

  if (!data.running || !data.pid) {
    if (cpuVal) cpuVal.textContent = "0.0 %";
    if (cpuFill) cpuFill.style.width = "0%";
    if (cpuDesc) cpuDesc.textContent = "Сервер выключен (процесс TShock не запущен)";

    if (ramVal) ramVal.textContent = "0 МБ";
    if (ramFill) ramFill.style.width = "0%";
    if (ramDesc) ramDesc.textContent = "Сервер выключен (процесс TShock не запущен)";
    return;
  }

  const cpuPct = Number(data.cpu ?? data.cpu_percent ?? 0);
  if (cpuVal) cpuVal.textContent = cpuPct.toFixed(1) + " %";
  if (cpuFill) cpuFill.style.width = Math.min(100, Math.max(0, cpuPct)) + "%";
  if (cpuDesc) cpuDesc.textContent = `Загрузка ядер процессом сервера TShock (PID: ${data.pid})`;

  const ramMb = Number(data.ram_mb ?? data.memory_mb ?? 0);
  const ramPct = Number(data.ram_percent ?? data.memory_percent ?? 0);

  if (ramVal) ramVal.textContent = Math.round(ramMb) + " МБ";
  if (ramFill) ramFill.style.width = Math.min(100, Math.max(0, ramPct)) + "%";
  if (ramDesc) ramDesc.textContent = `Рабочая память процесса • ${Math.round(ramMb)} МБ (${ramPct.toFixed(1)}% установленной ОЗУ)`;
}

function requestMetricsUpdate() {
  if (window.pywebview && window.pywebview.api && window.pywebview.api.get_metrics_now) {
    window.pywebview.api.get_metrics_now().then(data => {
      updateMetrics(data);
    });
  }
}

// Admin Management
let currentAccounts = [];
let selectedAccountIndex = -1;

function formatGroupLabel(group) {
  if (group === "admin") return "[Админ] admin";
  if (group === "default") return "[Игрок] default";
  if (group === "guest") return "[Гость] guest";
  return group;
}

function loadAdminData(btn) {
  if (btn) {
    if (btn.disabled) return;
    btn.disabled = true;
    spinButtonIcon(btn);
    setTimeout(() => { if (btn) btn.disabled = false; }, 800);
  }
  if (window.pywebview && window.pywebview.api) {
    window.pywebview.api.get_admin_data().then(data => {
      // Setup code
      const codeEl = document.getElementById("setup-code-val");
      if (codeEl) {
        codeEl.textContent = data.setup_code ? `/setup ${data.setup_code}` : "Сервер уже настроен или код отсутствует.";
      }

      // Accounts
      currentAccounts = data.accounts || [];
      renderAccounts(currentAccounts);

      // Groups dropdowns
      if (Array.isArray(data.groups) && data.groups.length > 0) {
        const assignSel = document.getElementById("assign-group-select");
        const inspectSel = document.getElementById("inspect-group-select");
        const currInspect = inspectSel ? inspectSel.value : "";

        const primaryOrder = ["admin", "default", "guest"];
        const sortedGroups = [...data.groups].sort((a, b) => {
          const ia = primaryOrder.indexOf(a);
          const ib = primaryOrder.indexOf(b);
          if (ia !== -1 && ib !== -1) return ia - ib;
          if (ia !== -1) return -1;
          if (ib !== -1) return 1;
          return a.localeCompare(b);
        });

        if (assignSel) {
          assignSel.innerHTML = "";
          sortedGroups.forEach(g => {
            if (g === "guest") return; // Registered accounts are players or admins, not unlogged guests
            const opt = document.createElement("option");
            opt.value = g;
            opt.textContent = formatGroupLabel(g);
            assignSel.appendChild(opt);
          });
          refreshCustomDropdown(assignSel);
        }
        if (inspectSel) {
          inspectSel.innerHTML = "";
          sortedGroups.forEach(g => {
            const opt = document.createElement("option");
            opt.value = g;
            opt.textContent = formatGroupLabel(g);
            if (g === currInspect) opt.selected = true;
            inspectSel.appendChild(opt);
          });
          refreshCustomDropdown(inspectSel);
        }
      }

      // Load perms for currently inspected group
      onInspectGroupChanged();
    });
  }
}

function renderAccounts(accounts) {
  const tbody = document.getElementById("accounts-tbody");
  if (!tbody) return;

  if (!accounts || accounts.length === 0) {
    tbody.innerHTML = '<tr><td colspan="2" class="empty-state">Нет зарегистрированных аккаунтов.</td></tr>';
    selectedAccountIndex = -1;
    return;
  }

  let html = "";
  accounts.forEach((acc, idx) => {
    const isSel = idx === selectedAccountIndex ? "selected" : "";
    const name = escapeHtml(acc.name || acc.username || "—");
    const group = escapeHtml(acc.group || "default");

    let groupBadge = `<span style="color: var(--neon);">${group}</span>`;
    if (group === "admin") {
      groupBadge = `<span style="color: #ff3c5a; font-weight: 700; background: rgba(255, 60, 90, 0.15); padding: 2px 8px; border-radius: 4px; border: 1px solid #ff3c5a;">[Админ] admin</span>`;
    } else if (group === "default") {
      groupBadge = `<span style="color: #32e17d; font-weight: 700; background: rgba(50, 225, 125, 0.15); padding: 2px 8px; border-radius: 4px; border: 1px solid #32e17d;">[Игрок] default</span>`;
    } else if (group === "guest") {
      groupBadge = `<span style="color: #a0a0a0; font-weight: 700; background: rgba(160, 160, 160, 0.15); padding: 2px 8px; border-radius: 4px; border: 1px solid #a0a0a0;">[Гость] guest</span>`;
    }

    html += `<tr class="${isSel}" onclick="selectAccountRow(${idx})">
      <td><strong>${name}</strong></td>
      <td>${groupBadge}</td>
    </tr>`;
  });
  tbody.innerHTML = html;
}

function selectAccountRow(index) {
  selectedAccountIndex = index;
  renderAccounts(currentAccounts);
}

async function assignSelectedAccountGroup() {
  if (selectedAccountIndex < 0 || selectedAccountIndex >= currentAccounts.length) {
    await showCustomAlert("Сначала выбери аккаунт в таблице.", "Выбор аккаунта");
    return;
  }
  const acc = currentAccounts[selectedAccountIndex];
  const name = acc.name || acc.username;
  const group = document.getElementById("assign-group-select").value;

  const ok = await showCustomConfirm(`Назначить аккаунту "${name}" группу "${group}"?`, "Группа TShock");
  if (!ok) return;

  if (window.pywebview && window.pywebview.api) {
    window.pywebview.api.assign_account_group(name, group).then(async res => {
      if (res.ok) {
        appendLog(`Аккаунту "${name}" назначена группа "${group}".`, "notice");
        loadAdminData();
        await showCustomAlert(`Аккаунту "${name}" успешно выдана группа "${group}"!`, "Группа изменена");
      } else {
        await showCustomAlert(res.error || "Не удалось назначить группу", "Ошибка группы");
      }
    });
  }
}

function onInspectGroupChanged() {
  const group = document.getElementById("inspect-group-select").value;
  if (!group) return;

  if (window.pywebview && window.pywebview.api) {
    window.pywebview.api.get_group_permissions(group).then(perms => {
      renderPermissions(perms, group);
    });
  }
}

function renderPermissions(perms, groupName) {
  const tbody = document.getElementById("perms-tbody");
  if (!tbody) return;

  if (!perms || perms.length === 0) {
    tbody.innerHTML = `<tr><td colspan="2" class="empty-state">У группы "${escapeHtml(groupName)}" нет особых разрешений.</td></tr>`;
    return;
  }

  let html = "";
  perms.forEach(p => {
    const permEsc = escapeHtml(p);
    html += `<tr>
      <td style="font-family: 'Cascadia Mono', Consolas, monospace; font-size: 11px; word-break: break-all; overflow-wrap: anywhere; padding: 8px 10px;">${permEsc}</td>
      <td style="text-align: center; width: 44px; padding: 8px 4px;">
        <button class="btn btn-danger btn-small" style="padding: 2px 8px; font-size: 11px;" onclick="removePermission('${permEsc}')">
          ✕
        </button>
      </td>
    </tr>`;
  });
  tbody.innerHTML = html;
}

function addCustomPermission(allow) {
  const input = document.getElementById("custom-perm-input");
  const perm = input.value.trim();
  const group = document.getElementById("inspect-group-select").value;

  if (!perm) return;

  if (window.pywebview && window.pywebview.api) {
    window.pywebview.api.change_group_permission(group, perm, allow).then(async res => {
      if (res.ok) {
        input.value = "";
        appendLog(`Группе "${group}" ${allow ? "добавлено" : "запрещено"} право: ${perm}`, "notice");
        onInspectGroupChanged();
      } else {
        await showCustomAlert(res.error || "Не удалось изменить право", "Ошибка права");
      }
    });
  }
}

async function removePermission(perm) {
  const group = document.getElementById("inspect-group-select").value;
  const ok = await showCustomConfirm(`Удалить право "${perm}" у группы "${group}"?`, "Удаление права");
  if (!ok) return;

  if (window.pywebview && window.pywebview.api) {
    window.pywebview.api.change_group_permission(group, perm, false).then(async res => {
      if (res.ok) {
        appendLog(`У группы "${group}" удалено право: ${perm}`, "notice");
        onInspectGroupChanged();
      } else {
        await showCustomAlert(res.error || "Не удалось удалить право", "Ошибка");
      }
    });
  }
}

async function copySetupCode() {
  const text = document.getElementById("setup-code-val").textContent.trim();
  if (!text || text.includes("отсутствует") || text.includes("после первого")) {
    await showCustomAlert("Код /setup не найден. Возможно, сервер уже настроен или ещё не запускался.", "Код /setup");
    return;
  }
  navigator.clipboard.writeText(text).then(async () => {
    appendLog("Команда скопирована: " + text, "notice");
    await showCustomAlert("Команда скопирована в буфер обмена: " + text, "Код скопирован");
  });
}

function escapeHtml(str) {
  return String(str).replace(/[&<>"']/g, m => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[m]);
}

// Gameplay & TShock Rules
function loadGameplayData() {
  if (!window.pywebview || !window.pywebview.api || !window.pywebview.api.get_tshock_gameplay_settings) return;

  window.pywebview.api.get_tshock_gameplay_settings().then(res => {
    if (!res || !res.ok) return;

    const s = res.settings || {};
    // Toggles
    const setCheck = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.checked = Boolean(val);
    };
    const setVal = (id, val) => {
      const el = document.getElementById(id);
      if (el && val !== undefined) el.value = val;
    };

    setCheck("gp-remember-pos", s.RememberLeavePos !== undefined ? s.RememberLeavePos : true);
    setCheck("gp-require-login", s.RequireLogin !== undefined ? s.RequireLogin : true);
    setCheck("gp-auto-uuid", s.DisableUUIDLogin !== undefined ? !s.DisableUUIDLogin : true);
    setCheck("gp-login-before-join", s.DisableLoginBeforeJoin !== undefined ? s.DisableLoginBeforeJoin : false);
    setVal("gp-min-pass", s.MinimumPasswordLength || 4);
    setVal("gp-max-slots", s.MaxSlots || 8);

    setCheck("gp-spawn-protect", s.SpawnProtection !== undefined ? s.SpawnProtection : false);
    setVal("gp-spawn-radius", s.SpawnProtectionRadius || 10);
    setCheck("gp-disable-build", s.DisableBuild !== undefined ? s.DisableBuild : false);
    setCheck("gp-protect-chests", s.RegionProtectChests !== undefined ? s.RegionProtectChests : false);
    setCheck("gp-disable-clown", s.DisableClownBombs !== undefined ? s.DisableClownBombs : false);
    setCheck("gp-disable-prime", s.DisablePrimeBombs !== undefined ? s.DisablePrimeBombs : false);
    setCheck("gp-prevent-dead", s.PreventDeadModification !== undefined ? s.PreventDeadModification : true);
    setCheck("gp-allow-corruption", s.AllowCorruptionCreep !== undefined ? s.AllowCorruptionCreep : true);
    setCheck("gp-allow-hallow", s.AllowHallowCreep !== undefined ? s.AllowHallowCreep : true);
    setCheck("gp-disable-tombstones", s.DisableTombstones !== undefined ? s.DisableTombstones : false);
    setCheck("gp-force-halloween", s.ForceHalloween !== undefined ? s.ForceHalloween : false);
    setCheck("gp-force-xmas", s.ForceXmas !== undefined ? s.ForceXmas : false);
    setCheck("gp-infinite-invasion", s.InfiniteInvasion !== undefined ? s.InfiniteInvasion : false);
    setCheck("gp-give-directly", s.GiveItemsDirectly !== undefined ? s.GiveItemsDirectly : false);
    setCheck("gp-anon-boss", s.AnonymousBossInvasions !== undefined ? s.AnonymousBossInvasions : true);

    setVal("gp-spawn-rate", s.DefaultSpawnRate || 600);
    setVal("gp-max-spawns", s.DefaultMaximumSpawns || 5);
    setVal("gp-invasion-mult", s.InvasionMultiplier || 1);
    setVal("gp-respawn-sec", s.RespawnSeconds !== undefined ? s.RespawnSeconds : 0);
    setVal("gp-respawn-boss-sec", s.RespawnBossSeconds !== undefined ? s.RespawnBossSeconds : 0);

    // Group prefixes
    if (Array.isArray(res.groups)) {
      res.groups.forEach(g => {
        if (g.name === "guest" && document.getElementById("role-prefix-guest")) {
          document.getElementById("role-prefix-guest").value = g.prefix || "[Гость] ";
        } else if (g.name === "default" && document.getElementById("role-prefix-default")) {
          document.getElementById("role-prefix-default").value = g.prefix || "[Игрок] ";
        } else if (g.name === "admin" && document.getElementById("role-prefix-admin")) {
          document.getElementById("role-prefix-admin").value = g.prefix || "[Админ] ";
        }
      });
    }
  });
}

async function saveGameplaySettings() {
  if (!window.pywebview || !window.pywebview.api || !window.pywebview.api.save_tshock_gameplay_settings) {
    await showCustomAlert("API панели недоступно", "Ошибка");
    return;
  }

  const payload = {
    settings: {
      RememberLeavePos: document.getElementById("gp-remember-pos")?.checked ?? true,
      RequireLogin: document.getElementById("gp-require-login")?.checked ?? true,
      DisableUUIDLogin: !(document.getElementById("gp-auto-uuid")?.checked ?? true),
      DisableLoginBeforeJoin: document.getElementById("gp-login-before-join")?.checked ?? false,
      MinimumPasswordLength: parseInt(document.getElementById("gp-min-pass")?.value, 10) || 4,
      MaxSlots: parseInt(document.getElementById("gp-max-slots")?.value, 10) || 8,
      SpawnProtection: document.getElementById("gp-spawn-protect")?.checked ?? false,
      SpawnProtectionRadius: parseInt(document.getElementById("gp-spawn-radius")?.value, 10) || 10,
      DisableBuild: document.getElementById("gp-disable-build")?.checked ?? false,
      RegionProtectChests: document.getElementById("gp-protect-chests")?.checked ?? false,
      DisableClownBombs: document.getElementById("gp-disable-clown")?.checked ?? false,
      DisablePrimeBombs: document.getElementById("gp-disable-prime")?.checked ?? false,
      PreventDeadModification: document.getElementById("gp-prevent-dead")?.checked ?? true,
      AllowCorruptionCreep: document.getElementById("gp-allow-corruption")?.checked ?? true,
      AllowCrimsonCreep: document.getElementById("gp-allow-corruption")?.checked ?? true,
      AllowHallowCreep: document.getElementById("gp-allow-hallow")?.checked ?? true,
      ForceHalloween: document.getElementById("gp-force-halloween")?.checked ?? false,
      ForceXmas: document.getElementById("gp-force-xmas")?.checked ?? false,
      DisableTombstones: document.getElementById("gp-disable-tombstones")?.checked ?? false,
      InfiniteInvasion: document.getElementById("gp-infinite-invasion")?.checked ?? false,
      GiveItemsDirectly: document.getElementById("gp-give-directly")?.checked ?? false,
      AnonymousBossInvasions: document.getElementById("gp-anon-boss")?.checked ?? true,
      DefaultSpawnRate: parseInt(document.getElementById("gp-spawn-rate")?.value, 10) || 600,
      DefaultMaximumSpawns: parseInt(document.getElementById("gp-max-spawns")?.value, 10) || 5,
      InvasionMultiplier: parseInt(document.getElementById("gp-invasion-mult")?.value, 10) || 1,
      RespawnSeconds: parseInt(document.getElementById("gp-respawn-sec")?.value, 10) || 0,
      RespawnBossSeconds: parseInt(document.getElementById("gp-respawn-boss-sec")?.value, 10) || 0
    },
    roles: [
      { name: "guest", prefix: document.getElementById("role-prefix-guest")?.value || "[Гость] " },
      { name: "default", prefix: document.getElementById("role-prefix-default")?.value || "[Игрок] " },
      { name: "admin", prefix: document.getElementById("role-prefix-admin")?.value || "[Админ] " }
    ]
  };

  try {
    const res = await window.pywebview.api.save_tshock_gameplay_settings(payload);
    if (res && res.ok) {
      if (res.reloaded) {
        await showCustomAlert("Параметры успешно сохранены и применены на сервере в реальном времени (/reload)!", "Геймплей и Защита");
      } else {
        await showCustomAlert("Параметры успешно сохранены в файл конфигурации!", "Геймплей и Защита");
      }
    } else {
      await showCustomAlert((res && res.error) || "Не удалось сохранить параметры", "Ошибка");
    }
  } catch (e) {
    await showCustomAlert(String(e), "Ошибка сохранения");
  }
}

async function runQuickGameplayAction(action) {
  if (!window.pywebview || !window.pywebview.api || !window.pywebview.api.execute_gameplay_action) {
    await showCustomAlert("API панели недоступно", "Ошибка");
    return;
  }
  try {
    const res = await window.pywebview.api.execute_gameplay_action(action);
    if (res && res.ok) {
      appendLog(res.message, "notice");
      await showCustomAlert(res.message, "Действие TShock");
    } else {
      await showCustomAlert((res && res.error) || "Не удалось выполнить команду", "Ошибка действия");
    }
  } catch (e) {
    await showCustomAlert(String(e), "Ошибка действия");
  }
}
