// State Management
const state = {
  tg: window.Telegram ? window.Telegram.WebApp : null,
  initData: "",
  userId: null,
  dialogs: [],
  selectedChatIds: new Set(),
  activeFilter: "all",
  searchQuery: "",
  chartInstance: null,
  holdTimer: null,
  holdProgress: 0,
  sseSource: null,
};

// Initialize App
document.addEventListener("DOMContentLoaded", async () => {
  if (state.tg) {
    state.tg.ready();
    state.tg.expand();
    state.initData = state.tg.initData || "";
  }

  // Fallback for standalone browser testing if initData is empty
  if (!state.initData) {
    // Generate dev fallback header
    console.warn("Running outside Telegram WebApp. Using development fallback.");
  }

  setupEventListeners();
  await checkAuthAndLoad();
});

// API Fetch Helper
async function apiFetch(endpoint, options = {}) {
  const headers = options.headers || {};
  if (state.initData) {
    headers["Authorization"] = `tma ${state.initData}`;
  }
  headers["Content-Type"] = "application/json";

  const res = await fetch(`/api${endpoint}`, {
    ...options,
    headers,
  });

  if (res.status === 401) {
    switchTab("login");
    throw new Error("Требуется авторизация");
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Network error" }));
    throw new Error(err.detail || "Произошла ошибка при обращении к серверу");
  }

  return res.json();
}

// Check Auth & Initial Load
async function checkAuthAndLoad() {
  try {
    const authStatus = await apiFetch("/login/status");
    if (!authStatus.is_authorized) {
      document.getElementById("accountPhoneLabel").textContent = "Не подключён";
      switchTab("login");
      return;
    }

    document.getElementById("accountPhoneLabel").textContent = "Подключён";
    await loadHygieneScore();
    await loadHistory();
  } catch (err) {
    console.error("Auth check failed:", err);
    switchTab("login");
  }
}

// Navigation Tabs
function switchTab(tabId) {
  document.querySelectorAll(".tab-pane").forEach((el) => el.classList.remove("active"));
  document.querySelectorAll(".nav-btn").forEach((el) => el.classList.remove("active"));

  const targetPane = document.getElementById(`tab-${tabId}`);
  const targetBtn = document.querySelector(`.nav-btn[data-tab="${tabId}"]`);

  if (targetPane) targetPane.classList.add("active");
  if (targetBtn) targetBtn.classList.add("active");

  if (tabId === "whitelist") loadWhitelist();
  if (tabId === "history") loadHistory();
  if (tabId === "schedule") loadSchedule();
}

// Hygiene Score & Dashboard
async function loadHygieneScore() {
  try {
    const res = await apiFetch("/hygiene-score");
    const score = res.current.score ?? 0;

    document.getElementById("scoreText").textContent = score;
    document.getElementById("gaugeValue").textContent = `${score}%`;

    // Render Chart
    renderHygieneChart(res.history);
  } catch (err) {
    console.error("Failed to load hygiene score:", err);
  }
}

// Scan Dialogs
async function startScan() {
  triggerHaptic("medium");
  const btn = document.getElementById("btnScanNow");
  btn.disabled = true;
  btn.textContent = "⏳ Сканирование аккаунта...";

  try {
    const res = await apiFetch("/scan");
    state.dialogs = res.items || [];

    // Update Dashboard counts
    document.getElementById("statPrivate").textContent = res.summary.private_chats;
    document.getElementById("statBots").textContent = res.summary.bot_chats;
    document.getElementById("statGroups").textContent = res.summary.group_chats;
    document.getElementById("statChannels").textContent = res.summary.channel_chats;

    renderDialogsList();
    switchTab("preview");
  } catch (err) {
    alert(err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "🔍 Сканировать аккаунт";
  }
}

// Render Dialogs
function renderDialogsList() {
  const container = document.getElementById("dialogsContainer");
  container.innerHTML = "";

  const filtered = state.dialogs.filter((d) => {
    // Filter pill
    if (state.activeFilter === "recommended" && !d.recommended) return false;
    if (state.activeFilter !== "all" && state.activeFilter !== "recommended" && d.chat_type !== state.activeFilter) return false;

    // Search query
    if (state.searchQuery) {
      const q = state.searchQuery.toLowerCase();
      const matchTitle = (d.title || "").toLowerCase().includes(q);
      const matchUser = (d.username || "").toLowerCase().includes(q);
      if (!matchTitle && !matchUser) return false;
    }
    return true;
  });

  if (filtered.length === 0) {
    container.innerHTML = '<div class="empty-state">Диалоги не найдены.</div>';
    return;
  }

  filtered.forEach((item) => {
    const el = document.createElement("div");
    el.className = `dialog-item ${item.is_whitelisted ? "whitelisted" : ""}`;

    const isChecked = state.selectedChatIds.has(item.chat_id);

    const typeLabel = {
      CHANNEL: "Канал",
      GROUP: "Группа",
      BOT: "Бот",
      PRIVATE: "Личный",
    }[item.chat_type] || item.chat_type;

    el.innerHTML = `
      <input type="checkbox" class="dialog-checkbox" data-id="${item.chat_id}" ${isChecked ? "checked" : ""} ${item.is_whitelisted ? "disabled" : ""} />
      <div class="dialog-info">
        <div class="dialog-title">${escapeHtml(item.title)}</div>
        <div class="dialog-meta">
          <span class="badge badge-tag">${typeLabel}</span>
          ${item.username ? `<span>@${item.username}</span>` : ""}
          ${item.tags && item.tags.length ? `<span class="badge badge-tag">${escapeHtml(item.tags[0])}</span>` : ""}
          ${item.is_whitelisted ? `<span class="badge badge-wl">Whitelist</span>` : ""}
        </div>
      </div>
    `;

    const checkbox = el.querySelector(".dialog-checkbox");
    checkbox.addEventListener("change", (e) => {
      if (e.target.checked) {
        state.selectedChatIds.add(item.chat_id);
      } else {
        state.selectedChatIds.delete(item.chat_id);
      }
      updateFloatingBar();
    });

    container.appendChild(el);
  });

  updateFloatingBar();
}

function updateFloatingBar() {
  const count = state.selectedChatIds.size;
  const bar = document.getElementById("floatingBar");
  document.getElementById("selectedCountBadge").textContent = `Выбрано: ${count}`;

  if (count > 0) {
    bar.style.display = "flex";
    document.getElementById("floatingSelectedText").textContent = `Выбрано диалогов: ${count}`;
  } else {
    bar.style.display = "none";
  }
}

// Hold To Confirm Button Logic
function setupHoldButton() {
  const btn = document.getElementById("btnMaxCleanHold");
  const progressEl = document.getElementById("holdProgress");
  let interval = null;

  const startHold = () => {
    state.holdProgress = 0;
    progressEl.style.width = "0%";
    triggerHaptic("light");

    interval = setInterval(() => {
      state.holdProgress += 4; // 25 ticks = 100% (approx 2.5s)
      progressEl.style.width = `${state.holdProgress}%`;

      if (state.holdProgress >= 100) {
        clearInterval(interval);
        triggerHaptic("heavy");
        triggerMaxClean();
        state.holdProgress = 0;
        progressEl.style.width = "0%";
      }
    }, 100);
  };

  const cancelHold = () => {
    if (interval) clearInterval(interval);
    state.holdProgress = 0;
    progressEl.style.width = "0%";
  };

  btn.addEventListener("mousedown", startHold);
  btn.addEventListener("touchstart", startHold);
  btn.addEventListener("mouseup", cancelHold);
  btn.addEventListener("mouseleave", cancelHold);
  btn.addEventListener("touchend", cancelHold);
}

// Cleanup Operations
async function triggerMaxClean() {
  try {
    await apiFetch("/cleanup/start", {
      method: "POST",
      body: JSON.stringify({ is_max_clean: true }),
    });
    showProgressModal("⚡ Выполняется MAX CLEAN");
  } catch (err) {
    alert(err.message);
  }
}

async function triggerSmartClean() {
  triggerHaptic("medium");
  try {
    await apiFetch("/cleanup/start", {
      method: "POST",
      body: JSON.stringify({ is_smart_clean: true }),
    });
    showProgressModal("🧠 Выполняется Smart Clean");
  } catch (err) {
    alert(err.message);
  }
}

async function cleanSelectedDialogs() {
  const ids = Array.from(state.selectedChatIds);
  if (ids.length === 0) return;

  if (!confirm(`Очистить выбранные диалоги (${ids.length} шт.)?`)) return;

  try {
    await apiFetch("/cleanup/start", {
      method: "POST",
      body: JSON.stringify({ target_chat_ids: ids }),
    });
    state.selectedChatIds.clear();
    updateFloatingBar();
    showProgressModal("Очистка выбранных диалогов");
  } catch (err) {
    alert(err.message);
  }
}

// SSE Live Progress Modal
function showProgressModal(title) {
  document.getElementById("progressTitle").textContent = title;
  document.getElementById("progressModal").style.display = "flex";
  document.getElementById("progressBarFill").style.width = "0%";
  document.getElementById("progressPercent").textContent = "0%";

  if (state.sseSource) {
    state.sseSource.close();
  }

  state.sseSource = new EventSource("/api/cleanup/stream");

  state.sseSource.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (!data.is_active && data.processed === undefined) {
      closeProgressModal();
      return;
    }

    const pct = data.percentage || 0;
    document.getElementById("progressBarFill").style.width = `${pct}%`;
    document.getElementById("progressPercent").textContent = `${pct}%`;
    document.getElementById("progressCounts").textContent = `${data.processed || 0} / ${data.total || 0}`;
    document.getElementById("progressCurrentItem").textContent = data.current_item || "Обработка...";

    if (data.is_finished) {
      setTimeout(() => {
        closeProgressModal();
        loadHygieneScore();
        alert("✅ Очистка успешно завершена!");
      }, 1000);
    }
  };

  state.sseSource.onerror = () => {
    closeProgressModal();
  };
}

function closeProgressModal() {
  if (state.sseSource) {
    state.sseSource.close();
    state.sseSource = null;
  }
  document.getElementById("progressModal").style.display = "none";
}

async function stopProgress() {
  triggerHaptic("heavy");
  try {
    await apiFetch("/cleanup/stop", { method: "POST" });
    closeProgressModal();
    alert("🛑 Операция остановлена");
  } catch (err) {
    alert(err.message);
  }
}

// Whitelist Management
async function loadWhitelist() {
  const container = document.getElementById("whitelistContainer");
  try {
    const items = await apiFetch("/whitelist");
    if (items.length === 0) {
      container.innerHTML = '<div class="empty-state">Белый список пуст.</div>';
      return;
    }
    container.innerHTML = "";
    items.forEach((it) => {
      const div = document.createElement("div");
      div.className = "dialog-item";
      div.innerHTML = `
        <div class="dialog-info">
          <div class="dialog-title">${escapeHtml(it.title || "Без названия")}</div>
          <div class="dialog-meta">
            <span>ID: ${it.chat_id}</span>
            ${it.username ? `<span>@${it.username}</span>` : ""}
          </div>
        </div>
        <button class="btn btn-outline btn-sm btn-danger" onclick="removeFromWhitelist(${it.chat_id})">Удалить</button>
      `;
      container.appendChild(div);
    });
  } catch (err) {
    console.error("Error loading whitelist:", err);
  }
}

async function addToWhitelist() {
  const chatId = document.getElementById("wlChatId").value.trim();
  const title = document.getElementById("wlTitle").value.trim();
  if (!chatId) return alert("Введите Chat ID");

  try {
    await apiFetch("/whitelist", {
      method: "POST",
      body: JSON.stringify({ chat_id: parseInt(chatId), title }),
    });
    document.getElementById("wlChatId").value = "";
    document.getElementById("wlTitle").value = "";
    loadWhitelist();
    triggerHaptic("light");
  } catch (err) {
    alert(err.message);
  }
}

async function removeFromWhitelist(chatId) {
  try {
    await apiFetch(`/whitelist/${chatId}`, { method: "DELETE" });
    loadWhitelist();
    triggerHaptic("light");
  } catch (err) {
    alert(err.message);
  }
}

// History & Chart.js
async function loadHistory() {
  try {
    const res = await apiFetch("/history");
    const tbody = document.getElementById("historyTbody");
    tbody.innerHTML = "";

    const jobs = res.recent_jobs || [];
    if (jobs.length === 0) {
      tbody.innerHTML = '<tr><td colspan="4" class="text-center">Задач пока не было.</td></tr>';
      return;
    }

    jobs.forEach((j) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${j.job_type}</td>
        <td><span class="badge ${j.status === "COMPLETED" ? "badge-wl" : "badge-tag"}">${j.status}</span></td>
        <td>${j.processed_items - j.error_items - j.skipped_items} / ${j.total_items}</td>
        <td>${(j.started_at || "").slice(0, 16).replace("T", " ")}</td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error("Error loading history:", err);
  }
}

function renderHygieneChart(historyData = []) {
  const ctx = document.getElementById("hygieneChart");
  if (!ctx) return;

  const labels = historyData.map((d, i) => `#${i + 1}`);
  const scores = historyData.map((d) => d.score);

  if (state.chartInstance) {
    state.chartInstance.destroy();
  }

  state.chartInstance = new Chart(ctx, {
    type: "line",
    data: {
      labels: labels.length ? labels : ["Сейчас"],
      datasets: [
        {
          label: "Score",
          data: scores.length ? scores : [100],
          borderColor: "#2f80ed",
          backgroundColor: "rgba(47, 128, 237, 0.1)",
          fill: true,
          tension: 0.3,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        y: { min: 0, max: 100, ticks: { color: "#708499" } },
        x: { ticks: { color: "#708499" } },
      },
    },
  });
}

// Schedule Settings
async function loadSchedule() {
  try {
    const s = await apiFetch("/settings");
    document.getElementById("schedEnabled").checked = Boolean(s.auto_clean_enabled);
    if (s.auto_clean_frequency) document.getElementById("schedFrequency").value = s.auto_clean_frequency;
    if (s.auto_clean_scope) document.getElementById("schedScope").value = s.auto_clean_scope;
    if (s.auto_clean_mode) document.getElementById("schedMode").value = s.auto_clean_mode;
  } catch (err) {
    console.error("Error loading settings:", err);
  }
}

async function saveSchedule() {
  try {
    await apiFetch("/settings", {
      method: "POST",
      body: JSON.stringify({
        auto_clean_enabled: document.getElementById("schedEnabled").checked ? 1 : 0,
        auto_clean_frequency: document.getElementById("schedFrequency").value,
        auto_clean_scope: document.getElementById("schedScope").value,
        auto_clean_mode: document.getElementById("schedMode").value,
      }),
    });
    triggerHaptic("medium");
    alert("Расписание сохранено!");
  } catch (err) {
    alert(err.message);
  }
}

// Rejoin Manifest
async function viewRejoinManifest() {
  try {
    const manifest = await apiFetch("/rejoin-manifest");
    if (manifest.length === 0) {
      alert("Rejoin Manifest пуст. Публичные чаты пока не покидались.");
      return;
    }

    let report = "📎 REJOIN MANIFEST (Ссылки для возврата):\n\n";
    manifest.forEach((m, idx) => {
      report += `${idx + 1}. ${m.title} (${m.chat_type})\n`;
      if (m.invite_link) report += `   🔗 ${m.invite_link}\n`;
      else if (m.username) report += `   🔗 https://t.me/${m.username}\n`;
    });

    alert(report);
  } catch (err) {
    alert(err.message);
  }
}

// Backup Export/Import
async function exportFullBackup() {
  try {
    const data = await apiFetch("/backup/export");
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `cleaner_backup_${Date.now()}.json`;
    a.click();
  } catch (err) {
    alert(err.message);
  }
}

// Secure Login Flow
async function requestLoginCode() {
  const phone = document.getElementById("loginPhoneInput").value.trim();
  if (!phone) return alert("Введите номер телефона");

  const customApiId = document.getElementById("customApiIdInput") ? document.getElementById("customApiIdInput").value.trim() : null;
  const customApiHash = document.getElementById("customApiHashInput") ? document.getElementById("customApiHashInput").value.trim() : null;

  const payload = { phone };
  if (customApiId && !isNaN(parseInt(customApiId))) {
    payload.api_id = parseInt(customApiId);
  }
  if (customApiHash) {
    payload.api_hash = customApiHash;
  }

  try {
    const res = await apiFetch("/login/request-code", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    alert(res.message);
    document.getElementById("loginStepPhone").style.display = "none";
    document.getElementById("loginStepCode").style.display = "block";
  } catch (err) {
    alert(err.message);
  }
}

async function submitLoginCode() {
  const code = document.getElementById("loginCodeInput").value.trim();
  if (!code) return alert("Введите код");

  try {
    const res = await apiFetch("/login/submit-code", {
      method: "POST",
      body: JSON.stringify({ code }),
    });

    if (res.is_authorized) {
      alert("🟢 Аккаунт успешно подключён!");
      window.location.reload();
    } else if (res.step === "2FA") {
      document.getElementById("loginStepCode").style.display = "none";
      document.getElementById("loginStep2FA").style.display = "block";
    }
  } catch (err) {
    alert(err.message);
  }
}

async function submit2FA() {
  const password = document.getElementById("login2FAPasswordInput").value;
  if (!password) return alert("Введите пароль");

  try {
    const res = await apiFetch("/login/submit-2fa", {
      method: "POST",
      body: JSON.stringify({ password }),
    });
    if (res.is_authorized) {
      alert("🟢 Аккаунт успешно подключён!");
      window.location.reload();
    }
  } catch (err) {
    alert(err.message);
  }
}

// Helpers
function triggerHaptic(style = "medium") {
  if (state.tg && state.tg.HapticFeedback) {
    try {
      state.tg.HapticFeedback.impactOccurred(style);
    } catch (e) {}
  }
}

function escapeHtml(str) {
  return (str || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

// Setup Event Listeners
function setupEventListeners() {
  // Tabs
  document.querySelectorAll(".nav-btn").forEach((btn) => {
    btn.addEventListener("click", () => switchTab(btn.dataset.tab));
  });

  // Buttons
  document.getElementById("btnScanNow")?.addEventListener("click", startScan);
  document.getElementById("btnSmartClean")?.addEventListener("click", triggerSmartClean);
  document.getElementById("btnCleanSelected")?.addEventListener("click", cleanSelectedDialogs);
  document.getElementById("btnStopProgress")?.addEventListener("click", stopProgress);
  document.getElementById("btnAddToWhitelist")?.addEventListener("click", addToWhitelist);
  document.getElementById("btnSaveSchedule")?.addEventListener("click", saveSchedule);
  document.getElementById("btnViewRejoinManifest")?.addEventListener("click", viewRejoinManifest);
  document.getElementById("btnExportFullBackup")?.addEventListener("click", exportFullBackup);
  document.getElementById("btnExportHistoryCsv")?.addEventListener("click", () => {
    window.location.href = "/api/history/export/csv";
  });

  // Login
  document.getElementById("btnRequestLoginCode")?.addEventListener("click", requestLoginCode);
  document.getElementById("btnSubmitLoginCode")?.addEventListener("click", submitLoginCode);
  document.getElementById("btnSubmit2FA")?.addEventListener("click", submit2FA);
  document.getElementById("btnLogoutSession")?.addEventListener("click", async () => {
    if (confirm("Вы действительно хотите завершить сессию?")) {
      await apiFetch("/login/logout", { method: "POST" });
      window.location.reload();
    }
  });

  // Search & Filter
  document.getElementById("dialogSearchInput")?.addEventListener("input", (e) => {
    state.searchQuery = e.target.value;
    renderDialogsList();
  });

  document.querySelectorAll(".pill").forEach((pill) => {
    pill.addEventListener("click", () => {
      document.querySelectorAll(".pill").forEach((p) => p.classList.remove("active"));
      pill.classList.add("active");
      state.activeFilter = pill.dataset.filter;
      renderDialogsList();
    });
  });

  document.getElementById("selectAllCheckbox")?.addEventListener("change", (e) => {
    const isChecked = e.target.checked;
    state.dialogs.forEach((d) => {
      if (!d.is_whitelisted) {
        if (isChecked) state.selectedChatIds.add(d.chat_id);
        else state.selectedChatIds.delete(d.chat_id);
      }
    });
    renderDialogsList();
  });

  setupHoldButton();
}
