// ========================================================
// CLIN — Telegram Account Cleaner Frontend Application
// Functional-First, Zero AI Slop Architecture
// ========================================================

const state = {
  tg: window.Telegram ? window.Telegram.WebApp : null,
  initData: "",
  userId: null,
  isAuthorized: false,
  hasConsent: false,
  activeScreen: "dashboard",
  dialogs: [],
  selectedChatIds: new Set(),
  activeFilter: "all",
  searchQuery: "",
  chartInstance: null,
  holdTimer: null,
  holdStart: null,
};

// HTML Escaper for XSS Prevention
function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

// Strict URL Sanitizer to prevent javascript: and data: XSS vectors
function sanitizeUrl(url) {
  if (!url || typeof url !== "string") return "#";
  const trimmed = url.trim();
  try {
    const parsed = new URL(trimmed, window.location.origin);
    if (parsed.protocol === "https:" || parsed.protocol === "http:" || parsed.protocol === "tg:") {
      return trimmed;
    }
  } catch (e) {
    if (trimmed.startsWith("tg://") || trimmed.startsWith("https://") || trimmed.startsWith("http://")) {
      return trimmed;
    }
  }
  return "#";
}

// Toast Notifications System
function showToast(message, type = "info", duration = 3500) {
  const container = document.getElementById("toastContainer");
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = `toast ${type}`;

  let icon = "ℹ️";
  if (type === "success") icon = "✓";
  if (type === "error") icon = "✕";
  if (type === "warning") icon = "⚠";

  const iconSpan = document.createElement("span");
  iconSpan.textContent = icon;
  const msgSpan = document.createElement("span");
  msgSpan.textContent = String(message || "");

  toast.appendChild(iconSpan);
  toast.appendChild(msgSpan);
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateY(8px)";
    setTimeout(() => toast.remove(), 250);
  }, duration);
}

// API Helper
async function apiFetch(endpoint, options = {}) {
  const headers = options.headers || {};
  if (state.initData) {
    headers["Authorization"] = `tma ${state.initData}`;
  }
  headers["Content-Type"] = "application/json";

  try {
    const res = await fetch(`/api${endpoint}`, { ...options, headers });
    const data = await res.json().catch(() => ({}));

    if (res.status === 401) {
      updateAuthUI(false);
      throw new Error("Требуется авторизация");
    }

    if (!res.ok) {
      const errMsg = (data.error && data.error.message) || data.detail || "Ошибка сервера";
      throw new Error(errMsg);
    }

    return data;
  } catch (err) {
    throw err;
  }
}

// App Initialization
document.addEventListener("DOMContentLoaded", async () => {
  if (state.tg) {
    state.tg.ready();
    state.tg.expand();
    state.initData = state.tg.initData || "";
    try {
      state.tg.setHeaderColor("#111417");
      state.tg.setBackgroundColor("#090B0D");
    } catch (e) {}
  }

  setupEventListeners();
  await checkConsentAndAuth();
});

// Check Consent & Auth
async function checkConsentAndAuth() {
  try {
    // 1. Check Consent
    const consentRes = await apiFetch("/consent/status").catch(() => null);
    if (consentRes && consentRes.data) {
      state.hasConsent = consentRes.data.has_consent;
      document.getElementById("settingsConsentVer").textContent = `v${consentRes.data.required_agreement_version}.0`;
      document.getElementById("settingsConsentDate").textContent = consentRes.data.accepted_at || "Не принято";

      if (!state.hasConsent) {
        document.getElementById("consentModal").style.display = "flex";
      }
    }

    // 2. Check Auth Status
    const loginStatus = await apiFetch("/login/status").catch(() => null);
    if (loginStatus && loginStatus.is_authorized) {
      updateAuthUI(true, loginStatus.phone);
      await loadDashboardData();
    } else {
      updateAuthUI(false);
    }
  } catch (err) {
    console.warn("Init status check notice:", err);
    updateAuthUI(false);
  }
}

function updateAuthUI(isAuth, phone = "") {
  state.isAuthorized = isAuth;
  const dots = [document.getElementById("sidebarStatusDot"), document.getElementById("mobileStatusDot")];
  const labels = [document.getElementById("sidebarStatusText"), document.getElementById("mobileStatusText")];

  dots.forEach((dot) => {
    if (dot) {
      dot.className = `status-dot ${isAuth ? "online" : "disconnected"}`;
    }
  });

  const text = isAuth ? (phone ? `+${phone}` : "Подключён") : "Не подключён";
  labels.forEach((lbl) => {
    if (lbl) lbl.textContent = text;
  });

  const formBox = document.getElementById("loginFormContainer");
  const profileBadge = document.getElementById("settingsConnectionBadge");
  const profilePhone = document.getElementById("settingsUserPhone");

  if (isAuth) {
    if (formBox) formBox.style.display = "none";
    if (profileBadge) {
      profileBadge.className = "profile-status text-success";
      profileBadge.textContent = "● Сессия активна (MTProto)";
    }
    if (profilePhone) profilePhone.textContent = `Телефон: ${phone || "Скрыт"}`;
  } else {
    if (formBox) formBox.style.display = "block";
    if (profileBadge) {
      profileBadge.className = "profile-status text-danger";
      profileBadge.textContent = "○ Не подключён";
    }
  }
}

// Navigation Handler
function navigateTo(screenId) {
  state.activeScreen = screenId;

  // Toggle Screen Panes
  document.querySelectorAll(".screen-pane").forEach((pane) => {
    pane.classList.toggle("active", pane.id === `screen-${screenId}`);
  });

  // Toggle Sidebar Items
  document.querySelectorAll(".sidebar-nav .nav-item").forEach((btn) => {
    btn.classList.toggle("active", btn.getAttribute("data-screen") === screenId);
  });

  // Toggle Mobile Bottom Nav
  document.querySelectorAll(".mobile-bottom-nav .mobile-nav-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.getAttribute("data-screen") === screenId);
  });

  // Close More Sheet if open
  const moreSheet = document.getElementById("mobileMoreSheet");
  if (moreSheet) moreSheet.style.display = "none";

  // Lazy screen loading
  if (screenId === "dashboard") loadDashboardData();
  if (screenId === "dialogs") loadDialogs();
  if (screenId === "smartclean") loadSmartCleanRecommendations();
  if (screenId === "whitelist") loadWhitelist();
  if (screenId === "history") loadHistory();
  if (screenId === "schedule") loadSchedule();
  if (screenId === "support") loadSupportData();
  if (screenId === "settings") loadSettingsData();
}

// Event Listeners Setup
function setupEventListeners() {
  // Navigation: Desktop Sidebar
  document.querySelectorAll(".sidebar-nav .nav-item").forEach((btn) => {
    btn.addEventListener("click", () => {
      const screen = btn.getAttribute("data-screen");
      if (screen) navigateTo(screen);
    });
  });

  // Navigation: Mobile Bottom Nav
  document.querySelectorAll(".mobile-bottom-nav .mobile-nav-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const screen = btn.getAttribute("data-screen");
      if (screen) navigateTo(screen);
    });
  });

  // Mobile More Button
  const btnMobileMore = document.getElementById("btnMobileMore");
  if (btnMobileMore) {
    btnMobileMore.addEventListener("click", () => {
      document.getElementById("mobileMoreSheet").style.display = "flex";
    });
  }

  const btnCloseMoreSheet = document.getElementById("btnCloseMoreSheet");
  if (btnCloseMoreSheet) {
    btnCloseMoreSheet.addEventListener("click", () => {
      document.getElementById("mobileMoreSheet").style.display = "none";
    });
  }

  // Mobile More Sheet Items
  document.querySelectorAll(".sheet-item").forEach((btn) => {
    btn.addEventListener("click", () => {
      const screen = btn.getAttribute("data-screen");
      if (screen) navigateTo(screen);
    });
  });

  // Consent Acceptance
  const btnAcceptConsent = document.getElementById("btnAcceptConsent");
  if (btnAcceptConsent) {
    btnAcceptConsent.addEventListener("click", async () => {
      try {
        await apiFetch("/consent/accept", { method: "POST" });
        state.hasConsent = true;
        document.getElementById("consentModal").style.display = "none";
        showToast("Согласие принято! Добро пожаловать в CLIN.", "success");
        await checkConsentAndAuth();
      } catch (err) {
        showToast(err.message, "error");
      }
    });
  }

  // Consent Withdrawal
  const btnWithdrawConsent = document.getElementById("btnWithdrawConsent");
  if (btnWithdrawConsent) {
    btnWithdrawConsent.addEventListener("click", async () => {
      if (!confirm("Вы уверены, что хотите отозвать согласие? Ваша сессия на сервере будет немедленно перезаписана нулями и удалена.")) return;
      try {
        await apiFetch("/consent/withdraw", { method: "POST" });
        showToast("Согласие отозвано. Сессия стёрта.", "warning");
        state.hasConsent = false;
        state.isAuthorized = false;
        updateAuthUI(false);
        document.getElementById("consentModal").style.display = "flex";
      } catch (err) {
        showToast(err.message, "error");
      }
    });
  }

  // Dashboard Quick Action Triggers
  document.getElementById("btnActionScan")?.addEventListener("click", () => navigateTo("scan"));
  document.getElementById("btnQuickScanTop")?.addEventListener("click", () => navigateTo("scan"));
  document.getElementById("btnActionSmartClean")?.addEventListener("click", () => navigateTo("smartclean"));
  document.getElementById("btnViewAllHistory")?.addEventListener("click", () => navigateTo("history"));
  document.getElementById("btnStartScanFromDialogs")?.addEventListener("click", () => navigateTo("scan"));

  // Additional Action Buttons
  document.getElementById("btnWhyScore")?.addEventListener("click", () => {
    showToast("Индекс чистоты рассчитывается от 0 до 100 на основе активности: базовые 100 баллов за вычетом спам-ботов, неактивных каналов и с учётом защиты Whitelist.", "info", 6000);
  });
  document.getElementById("btnRefreshDialogs")?.addEventListener("click", async () => {
    showToast("Обновление списка диалогов...", "info");
    await loadDialogs();
  });
  document.getElementById("btnGoToDialogs")?.addEventListener("click", () => navigateTo("dialogs"));
  document.getElementById("btnGoToSmartClean")?.addEventListener("click", () => navigateTo("smartclean"));
  document.getElementById("btnSelectAllRecs")?.addEventListener("click", () => {
    const checkboxes = document.querySelectorAll("#smartCleanList input[type='checkbox']");
    const allChecked = Array.from(checkboxes).every((cb) => cb.checked);
    checkboxes.forEach((cb) => (cb.checked = !allChecked));
    showToast(!allChecked ? "Все рекомендации выбраны" : "Выбор снят", "info");
  });
  document.getElementById("btnExportCsv")?.addEventListener("click", async () => {
    try {
      const headers = {};
      if (state.initData) headers["Authorization"] = `tma ${state.initData}`;
      const res = await fetch("/api/history/export/csv", { headers });
      if (!res.ok) throw new Error("Ошибка скачивания CSV");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `clin_history_${Date.now()}.csv`;
      a.click();
      URL.revokeObjectURL(url);
      showToast("История экспортирована в CSV", "success");
    } catch (err) {
      showToast(err.message, "error");
    }
  });
  document.getElementById("btnExportManifest")?.addEventListener("click", async () => {
    try {
      const res = await apiFetch("/settings/rejoin-manifest");
      const blob = new Blob([JSON.stringify(res, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `clin_rejoin_manifest_${Date.now()}.json`;
      a.click();
      URL.revokeObjectURL(url);
      showToast("Rejoin Manifest сохранён", "success");
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  // Deep Clean Modal & Hold-to-Confirm
  const btnActionDeepClean = document.getElementById("btnActionDeepClean");
  const deepCleanModal = document.getElementById("deepCleanModal");
  const btnCancelDeepClean = document.getElementById("btnCancelDeepClean");
  const btnHoldDeepClean = document.getElementById("btnHoldDeepClean");
  const holdProgressFill = document.getElementById("holdProgressFill");

  if (btnActionDeepClean && deepCleanModal) {
    btnActionDeepClean.addEventListener("click", () => {
      deepCleanModal.style.display = "flex";
      if (holdProgressFill) holdProgressFill.style.width = "0%";
    });
  }

  if (btnCancelDeepClean && deepCleanModal) {
    btnCancelDeepClean.addEventListener("click", () => {
      deepCleanModal.style.display = "none";
      clearInterval(state.holdTimer);
    });
  }

  // 3-Second Hold Logic
  if (btnHoldDeepClean && holdProgressFill) {
    const startHold = () => {
      state.holdStart = Date.now();
      state.holdTimer = setInterval(() => {
        const elapsed = Date.now() - state.holdStart;
        const pct = Math.min((elapsed / 3000) * 100, 100);
        holdProgressFill.style.width = `${pct}%`;

        if (elapsed >= 3000) {
          clearInterval(state.holdTimer);
          deepCleanModal.style.display = "none";
          executeDeepClean();
        }
      }, 50);
    };

    const cancelHold = () => {
      clearInterval(state.holdTimer);
      holdProgressFill.style.width = "0%";
    };

    btnHoldDeepClean.addEventListener("mousedown", startHold);
    btnHoldDeepClean.addEventListener("mouseup", cancelHold);
    btnHoldDeepClean.addEventListener("mouseleave", cancelHold);
    btnHoldDeepClean.addEventListener("touchstart", startHold);
    btnHoldDeepClean.addEventListener("touchend", cancelHold);
  }

  // Scan Execution
  document.getElementById("btnExecuteScan")?.addEventListener("click", executeScan);

  // Dialogs Filter Chips
  document.querySelectorAll(".filter-chips .chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      document.querySelectorAll(".filter-chips .chip").forEach((c) => c.classList.remove("active"));
      chip.classList.add("active");
      state.activeFilter = chip.getAttribute("data-filter") || "all";
      renderDialogsList();
    });
  });

  // Dialogs Search Input
  const searchInput = document.getElementById("dialogSearchInput");
  const clearBtn = document.getElementById("btnSearchClear");
  if (searchInput && clearBtn) {
    searchInput.addEventListener("input", (e) => {
      state.searchQuery = e.target.value.trim().toLowerCase();
      clearBtn.style.display = state.searchQuery ? "block" : "none";
      renderDialogsList();
    });
    clearBtn.addEventListener("click", () => {
      searchInput.value = "";
      state.searchQuery = "";
      clearBtn.style.display = "none";
      renderDialogsList();
    });
  }

  // Dialogs Selection Actions
  document.getElementById("btnSelectionClear")?.addEventListener("click", () => {
    state.selectedChatIds.clear();
    updateSelectionBar();
    renderDialogsList();
  });

  document.getElementById("btnSelectionWhitelist")?.addEventListener("click", async () => {
    if (state.selectedChatIds.size === 0) return;
    try {
      for (const chatId of state.selectedChatIds) {
        await apiFetch("/settings/whitelist", {
          method: "POST",
          body: JSON.stringify({ chat_id: chatId }),
        });
      }
      showToast(`Добавлено ${state.selectedChatIds.size} диалогов в Whitelist`, "success");
      state.selectedChatIds.clear();
      updateSelectionBar();
      await loadDialogs();
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  document.getElementById("btnSelectionDelete")?.addEventListener("click", async () => {
    if (state.selectedChatIds.size === 0) return;
    const count = state.selectedChatIds.size;
    if (!confirm(`Очистить выбранные диалоги (${count} шт.)?`)) return;

    try {
      const res = await apiFetch("/cleanup/run", {
        method: "POST",
        body: JSON.stringify({
          target_chat_ids: Array.from(state.selectedChatIds),
          dry_run: false,
        }),
      });
      showToast(`Очистка завершена: обработано ${res.processed}`, "success");
      state.selectedChatIds.clear();
      updateSelectionBar();
      await loadDialogs();
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  // Whitelist Add & Export/Import
  document.getElementById("btnAddWlItem")?.addEventListener("click", async () => {
    const inputId = document.getElementById("inputWlChatId");
    const inputTitle = document.getElementById("inputWlTitle");
    const val = inputId.value.trim();
    if (!val) return;

    const num = parseInt(val, 10);
    const body = isNaN(num) ? { username: val.replace("@", "") } : { chat_id: num };
    if (inputTitle.value.trim()) body.title = inputTitle.value.trim();

    try {
      await apiFetch("/settings/whitelist", { method: "POST", body: JSON.stringify(body) });
      inputId.value = "";
      inputTitle.value = "";
      showToast("Добавлено в Белый список", "success");
      await loadWhitelist();
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  document.getElementById("btnExportWl")?.addEventListener("click", async () => {
    try {
      const res = await apiFetch("/settings/whitelist");
      const blob = new Blob([JSON.stringify(res, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "clin_whitelist.json";
      a.click();
      URL.revokeObjectURL(url);
      showToast("Whitelist экспортирован", "success");
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  const btnImportWl = document.getElementById("btnImportWl");
  const wlFileInput = document.getElementById("wlFileInput");
  if (btnImportWl && wlFileInput) {
    btnImportWl.addEventListener("click", () => wlFileInput.click());
    wlFileInput.addEventListener("change", async (e) => {
      const file = e.target.files[0];
      if (!file) return;
      try {
        const text = await file.text();
        const json = JSON.parse(text);
        const items = Array.isArray(json) ? json : json.items || [];
        for (const item of items) {
          if (item.chat_id) {
            await apiFetch("/settings/whitelist", {
              method: "POST",
              body: JSON.stringify({ chat_id: item.chat_id, title: item.title }),
            });
          }
        }
        showToast("Whitelist успешно импортирован", "success");
        await loadWhitelist();
      } catch (err) {
        showToast("Ошибка чтения файла Whitelist", "error");
      }
    });
  }

  // Backup Export / Import
  document.getElementById("btnExportFullBackup")?.addEventListener("click", async () => {
    try {
      const res = await apiFetch("/settings/backup/export");
      const blob = new Blob([JSON.stringify(res, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "clin_full_backup.json";
      a.click();
      URL.revokeObjectURL(url);
      showToast("Резервная копия сохранена", "success");
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  const btnImportBackup = document.getElementById("btnImportFullBackup");
  const backupFileInput = document.getElementById("backupFileInput");
  if (btnImportBackup && backupFileInput) {
    btnImportBackup.addEventListener("click", () => backupFileInput.click());
    backupFileInput.addEventListener("change", async (e) => {
      const file = e.target.files[0];
      if (!file) return;
      try {
        const text = await file.text();
        const json = JSON.parse(text);
        await apiFetch("/settings/backup/import", {
          method: "POST",
          body: JSON.stringify(json),
        });
        showToast("Резервная копия успешно восстановлена", "success");
      } catch (err) {
        showToast("Ошибка восстановления бэкапа", "error");
      }
    });
  }

  // Schedule Save
  document.getElementById("btnSaveSchedule")?.addEventListener("click", async () => {
    const enabled = document.getElementById("scheduleEnableToggle").checked;
    const freq = document.getElementById("scheduleFreqSelect").value;
    const scope = document.getElementById("scheduleScopeSelect").value;
    const mode = document.getElementById("scheduleModeSelect").value;

    try {
      await apiFetch("/settings/schedule", {
        method: "POST",
        body: JSON.stringify({
          auto_clean_enabled: enabled,
          auto_clean_frequency: freq,
          auto_clean_scope: scope,
          auto_clean_mode: mode,
        }),
      });
      showToast("Расписание обновлено", "success");
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  // Support: Modal Open & Submit
  document.getElementById("btnOpenCreateTicketModal")?.addEventListener("click", () => {
    document.getElementById("createTicketModal").style.display = "flex";
  });

  document.getElementById("btnCancelCreateTicket")?.addEventListener("click", () => {
    document.getElementById("createTicketModal").style.display = "none";
  });

  document.getElementById("btnSubmitCreateTicket")?.addEventListener("click", async () => {
    const category = document.getElementById("ticketCategorySelect").value;
    const subject = document.getElementById("ticketSubjectInput").value.trim();
    const description = document.getElementById("ticketDescriptionInput").value.trim();

    if (!subject || !description) {
      showToast("Заполните тему и описание тикета", "warning");
      return;
    }

    try {
      const res = await apiFetch("/support/tickets", {
        method: "POST",
        body: JSON.stringify({ category, subject, description }),
      });
      document.getElementById("createTicketModal").style.display = "none";
      document.getElementById("ticketSubjectInput").value = "";
      document.getElementById("ticketDescriptionInput").value = "";
      showToast(`Тикет ${res.data.ticket_number} создан`, "success");
      await loadSupportData();
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  document.getElementById("btnCloseThreadModal")?.addEventListener("click", () => {
    document.getElementById("ticketDetailModal").style.display = "none";
  });

  // Logout
  document.getElementById("btnLogoutSession")?.addEventListener("click", async () => {
    if (!confirm("Завершить сессию Telegram на этом устройстве?")) return;
    try {
      await apiFetch("/login/logout", { method: "POST" });
      updateAuthUI(false);
      showToast("Сессия завершена", "info");
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  // Phone Auth Triggers
  document.getElementById("btnSendAuthCode")?.addEventListener("click", async () => {
    const phone = document.getElementById("loginPhoneInput").value.trim();
    if (!phone) return;
    try {
      await apiFetch("/login/send-code", {
        method: "POST",
        body: JSON.stringify({ phone }),
      });
      document.getElementById("loginCodeStep").style.display = "block";
      showToast("Код отправлен в Telegram", "success");
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  document.getElementById("btnVerifyAuthCode")?.addEventListener("click", async () => {
    const code = document.getElementById("loginCodeInput").value.trim();
    if (!code) return;
    try {
      const res = await apiFetch("/login/verify-code", {
        method: "POST",
        body: JSON.stringify({ code }),
      });
      if (res.step === "2FA") {
        document.getElementById("login2faStep").style.display = "block";
        showToast("Требуется 2FA пароль", "info");
      } else if (res.is_authorized) {
        showToast("Успешный вход в аккаунт!", "success");
        await checkConsentAndAuth();
      }
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  document.getElementById("btnVerify2fa")?.addEventListener("click", async () => {
    const password = document.getElementById("login2faInput").value;
    if (!password) return;
    try {
      const res = await apiFetch("/login/verify-2fa", {
        method: "POST",
        body: JSON.stringify({ password }),
      });
      if (res.is_authorized) {
        showToast("Успешный вход в аккаунт!", "success");
        await checkConsentAndAuth();
      }
    } catch (err) {
      showToast(err.message, "error");
    }
  });
}

// ----------------------------------------------------
// SCREEN CONTROLLERS
// ----------------------------------------------------

// 1. Dashboard
async function loadDashboardData() {
  try {
    const res = await apiFetch("/hygiene-score");
    const score = res.current ? res.current.score : 92;
    document.getElementById("dashboardScoreValue").textContent = score;

    // Update Circular Gauge
    const circle = document.getElementById("scoreCircleFill");
    if (circle) {
      const circumference = 2 * Math.PI * 50; // ~314.15
      const offset = circumference - (score / 100) * circumference;
      circle.style.strokeDashoffset = offset;
    }

    if (res.current) {
      document.getElementById("statPrivate").textContent = res.current.private_count ?? "--";
      document.getElementById("statBots").textContent = res.current.bots_count ?? "--";
      document.getElementById("statGroups").textContent = res.current.groups_count ?? "--";
      document.getElementById("statChannels").textContent = res.current.channels_count ?? "--";
    }

    // Load recent activity from history
    const histRes = await apiFetch("/history");
    const list = document.getElementById("dashboardActivityList");
    if (list && histRes.recent_jobs && histRes.recent_jobs.length > 0) {
      list.innerHTML = histRes.recent_jobs
        .slice(0, 4)
        .map((j) => {
          const isSuccess = j.status === "COMPLETED";
          return `
          <div class="ticket-item">
            <div>
              <span class="ticket-number-badge">CLIN-JOB-${j.id}</span>
              <strong style="margin-left: 8px;">${escapeHtml(j.job_type)}</strong>
            </div>
            <div style="font-size: 12px; color: var(--clin-text-muted);">
              ${isSuccess ? "✅ Успешно" : "❌ Ошибка"} (${j.processed_items || 0} обработано)
            </div>
          </div>
        `;
        })
        .join("");
    }
  } catch (err) {
    console.warn("Could not load dashboard data:", err);
  }
}

// 2. Scan Execution
async function executeScan() {
  const pCard = document.getElementById("scanProgressCard");
  const rCard = document.getElementById("scanResultsCard");
  const pStatus = document.getElementById("scanProgressStatus");
  const pPct = document.getElementById("scanProgressPercent");
  const pFill = document.getElementById("scanProgressBarFill");
  const pCounts = document.getElementById("scanProgressCounts");

  pCard.style.display = "block";
  rCard.style.display = "none";
  pFill.style.width = "10%";
  pPct.textContent = "10%";
  pStatus.textContent = "Подключение к Telegram MTProto...";

  try {
    pFill.style.width = "40%";
    pPct.textContent = "40%";
    pStatus.textContent = "Считывание диалогов и каналов...";

    const res = await apiFetch("/scan");
    state.dialogs = res.items || [];

    pFill.style.width = "100%";
    pPct.textContent = "100%";
    pStatus.textContent = "Сканирование завершено!";
    pCounts.textContent = `Обработано: ${state.dialogs.length} / ${state.dialogs.length}`;

    setTimeout(() => {
      pCard.style.display = "none";
      rCard.style.display = "block";
      document.getElementById("scanResultTotalTitle").textContent = `Найдено: ${state.dialogs.length} диалогов`;

      const breakdown = document.getElementById("scanResultsBreakdown");
      breakdown.innerHTML = `
        <div class="stat-card"><strong>Личные:</strong> ${res.private_chats || 0}</div>
        <div class="stat-card"><strong>Боты:</strong> ${res.bot_chats || 0}</div>
        <div class="stat-card"><strong>Группы:</strong> ${res.group_chats || 0}</div>
        <div class="stat-card"><strong>Каналы:</strong> ${res.channel_chats || 0}</div>
        <div class="stat-card"><strong>В Whitelist:</strong> ${res.whitelisted_count || 0}</div>
        <div class="stat-card"><strong>Рекомендовано:</strong> ${res.recommended_count || 0}</div>
      `;
      showToast(`Найдено ${state.dialogs.length} диалогов`, "success");
    }, 600);
  } catch (err) {
    pCard.style.display = "none";
    showToast(err.message, "error");
  }
}

// 3. Dialogs
async function loadDialogs() {
  if (state.dialogs.length === 0) {
    try {
      const res = await apiFetch("/scan");
      state.dialogs = res.items || [];
    } catch (e) {}
  }
  renderDialogsList();
}

function renderDialogsList() {
  const container = document.getElementById("dialogsListContainer");
  if (!container) return;

  let filtered = state.dialogs;

  // Filter Chip Logic
  if (state.activeFilter !== "all") {
    if (state.activeFilter === "INACTIVE") {
      filtered = filtered.filter((d) => d.heuristics && d.heuristics.inactive_days >= 60);
    } else {
      filtered = filtered.filter((d) => d.chat_type === state.activeFilter);
    }
  }

  // Search Logic
  if (state.searchQuery) {
    filtered = filtered.filter((d) => {
      const title = (d.title || "").toLowerCase();
      const username = (d.username || "").toLowerCase();
      return title.includes(state.searchQuery) || username.includes(state.searchQuery);
    });
  }

  if (filtered.length === 0) {
    container.innerHTML = `
      <div class="empty-state-card">
        <h4>Диалоги не найдены</h4>
        <p>По выбранному фильтру или запросу ничего не найдено.</p>
      </div>
    `;
    return;
  }

  container.innerHTML = filtered
    .slice(0, 100) // render up to 100 for high performance
    .map((d) => {
      const isChecked = state.selectedChatIds.has(d.chat_id);
      const initial = (d.title || "?").charAt(0).toUpperCase();
      const isWl = d.is_whitelisted;
      return `
      <div class="dialog-item-row ${isChecked ? "selected" : ""}" data-chat-id="${d.chat_id}">
        <input type="checkbox" class="dialog-chk" data-chat-id="${d.chat_id}" ${isChecked ? "checked" : ""} />
        <div class="dialog-avatar">${escapeHtml(initial)}</div>
        <div class="dialog-details">
          <div class="dialog-top-line">
            <span class="dialog-title">${escapeHtml(d.title)}</span>
            <span class="badge-type">${escapeHtml(d.chat_type)}</span>
          </div>
          <div class="dialog-meta-line">
            ${d.username ? `<span>@${escapeHtml(d.username)}</span>` : ""}
            ${isWl ? '<span class="badge-wl">⭐ Whitelist</span>' : ""}
            ${d.heuristics && d.heuristics.inactive_days ? `<span>Неактивен: ${d.heuristics.inactive_days} дн.</span>` : ""}
          </div>
        </div>
      </div>
    `;
    })
    .join("");

  // Attach Checkbox Handlers
  container.querySelectorAll(".dialog-chk").forEach((chk) => {
    chk.addEventListener("change", (e) => {
      const chatId = parseInt(e.target.getAttribute("data-chat-id"), 10);
      if (e.target.checked) {
        state.selectedChatIds.add(chatId);
      } else {
        state.selectedChatIds.delete(chatId);
      }
      updateSelectionBar();
    });
  });
}

function updateSelectionBar() {
  const bar = document.getElementById("selectionActionBar");
  const countLabel = document.getElementById("selectedCountLabel");
  const count = state.selectedChatIds.size;

  if (bar && countLabel) {
    countLabel.textContent = count;
    bar.style.display = count > 0 ? "flex" : "none";
  }
}

// 4. Smart Clean Recommendations
async function loadSmartCleanRecommendations() {
  if (state.dialogs.length === 0) {
    await loadDialogs();
  }

  const recs = state.dialogs.filter(
    (d) => !d.is_whitelisted && d.heuristics && d.heuristics.recommended_for_cleanup
  );

  const container = document.getElementById("recommendationsList");
  const countLabel = document.getElementById("recTotalCount");
  const executeBtn = document.getElementById("btnExecuteSmartClean");

  if (countLabel) countLabel.textContent = recs.length;
  if (executeBtn) {
    executeBtn.disabled = recs.length === 0;
    executeBtn.textContent = `Очистить рекомендованные (${recs.length})`;
  }

  if (!container) return;

  if (recs.length === 0) {
    container.innerHTML = `
      <div class="empty-state-card">
        <h4>Все диалоги в порядке!</h4>
        <p>Мёртвых каналов, спам-ботов или неактивных чатов не обнаружено.</p>
      </div>
    `;
    return;
  }

  container.innerHTML = recs
    .map((d) => {
      const tags = d.heuristics.tags || [];
      return `
      <div class="rec-item-card">
        <div class="rec-info">
          <div class="rec-name">${escapeHtml(d.title)}</div>
          <div class="rec-tags">
            ${tags.map((t) => `<span class="tag-badge risk-med">${escapeHtml(t)}</span>`).join("")}
          </div>
        </div>
        <button class="btn btn-secondary btn-sm" onclick="cleanSingleChat(${d.chat_id})">Очистить</button>
      </div>
    `;
    })
    .join("");
}

// 5. Whitelist
async function loadWhitelist() {
  try {
    const res = await apiFetch("/settings/whitelist");
    const container = document.getElementById("whitelistContainer");
    if (!container) return;

    const items = res.whitelist || [];
    if (items.length === 0) {
      container.innerHTML = '<div style="padding: 16px; color: var(--clin-text-muted);">Белый список пуст.</div>';
      return;
    }

    container.innerHTML = items
      .map(
        (i) => `
      <div class="table-row">
        <span>${escapeHtml(i.title || i.username || "Chat")}</span>
        <span class="font-mono">${i.chat_id}</span>
        <span>${i.added_at ? i.added_at.slice(0, 10) : "--"}</span>
        <button class="btn btn-ghost btn-sm text-danger" onclick="removeWlItem(${i.chat_id})">Удалить</button>
      </div>
    `
      )
      .join("");
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function removeWlItem(chatId) {
  try {
    await apiFetch(`/settings/whitelist/${chatId}`, { method: "DELETE" });
    showToast("Удалено из белого списка", "info");
    await loadWhitelist();
  } catch (err) {
    showToast(err.message, "error");
  }
}

// 6. History
async function loadHistory() {
  try {
    const res = await apiFetch("/history");
    const summary = res.summary || {};
    document.getElementById("histTotalJobs").textContent = summary.total_jobs || 0;
    document.getElementById("histCleanedCount").textContent = summary.total_processed || 0;
    document.getElementById("histSkippedCount").textContent = summary.total_skipped || 0;
    document.getElementById("histErrorsCount").textContent = summary.total_errors || 0;

    const list = document.getElementById("jobsListContainer");
    const jobs = res.recent_jobs || [];
    if (list) {
      if (jobs.length === 0) {
        list.innerHTML = '<div style="padding: 16px; color: var(--clin-text-muted);">Журнал операций пуст.</div>';
      } else {
        list.innerHTML = jobs
          .map(
            (j) => `
          <div class="ticket-item">
            <div>
              <span class="ticket-number-badge">CLIN-JOB-${j.id}</span>
              <strong style="margin-left: 8px;">${escapeHtml(j.job_type)}</strong>
            </div>
            <div style="font-size: 12px; color: var(--clin-text-muted);">
              ${j.status === "COMPLETED" ? "✅ Успешно" : "❌ " + j.status} | ${j.processed_items || 0} обработано
            </div>
          </div>
        `
          )
          .join("");
      }
    }
  } catch (err) {
    console.warn("Could not load history:", err);
  }
}

// 7. Schedule
async function loadSchedule() {
  try {
    const res = await apiFetch("/settings");
    const s = res.settings || {};
    document.getElementById("scheduleEnableToggle").checked = !!s.auto_clean_enabled;
    if (s.auto_clean_frequency) document.getElementById("scheduleFreqSelect").value = s.auto_clean_frequency;
    if (s.auto_clean_scope) document.getElementById("scheduleScopeSelect").value = s.auto_clean_scope;
    if (s.auto_clean_mode) document.getElementById("scheduleModeSelect").value = s.auto_clean_mode;
  } catch (err) {
    console.warn("Could not load schedule:", err);
  }
}

// 8. Support Center
async function loadSupportData() {
  // Load FAQ
  try {
    const faqRes = await apiFetch("/support/faq");
    const faqList = document.getElementById("faqAccordionContainer");
    if (faqList && faqRes.data) {
      faqList.innerHTML = faqRes.data
        .map(
          (item) => `
        <div class="faq-item">
          <button class="faq-question">
            <span>${escapeHtml(item.question)}</span>
            <span>+</span>
          </button>
          <div class="faq-answer">${escapeHtml(item.answer)}</div>
        </div>
      `
        )
        .join("");

      faqList.querySelectorAll(".faq-question").forEach((btn) => {
        btn.addEventListener("click", () => {
          btn.parentElement.classList.toggle("open");
        });
      });
    }

    // Load User Tickets
    const ticketRes = await apiFetch("/support/tickets");
    const ticketList = document.getElementById("supportTicketsList");
    if (ticketList && ticketRes.data) {
      ticketList.textContent = "";
      if (ticketRes.data.length === 0) {
        const emptyDiv = document.createElement("div");
        emptyDiv.style.cssText = "padding: 12px; color: var(--clin-text-muted);";
        emptyDiv.textContent = "У вас нет открытых обращений.";
        ticketList.appendChild(emptyDiv);
      } else {
        ticketRes.data.forEach((t) => {
          const item = document.createElement("div");
          item.className = "ticket-item";
          item.style.cursor = "pointer";
          item.addEventListener("click", () => openTicketDetail(t.ticket_number));

          const left = document.createElement("div");
          const badge = document.createElement("span");
          badge.className = "ticket-number-badge";
          badge.textContent = t.ticket_number;
          const strong = document.createElement("strong");
          strong.style.marginLeft = "8px";
          strong.textContent = t.subject;
          left.appendChild(badge);
          left.appendChild(strong);

          const right = document.createElement("div");
          right.className = "text-success";
          right.style.cssText = "font-size: 11px; text-transform: uppercase;";
          right.textContent = t.status;

          item.appendChild(left);
          item.appendChild(right);
          ticketList.appendChild(item);
        });
      }
    }
  } catch (err) {
    console.warn("Could not load support data:", err);
  }
}

async function openTicketDetail(ticketNumber) {
  try {
    const res = await apiFetch(`/support/tickets/${ticketNumber}`);
    const data = res.data;
    document.getElementById("threadTicketNumber").textContent = data.ticket.ticket_number;
    document.getElementById("threadTicketSubject").textContent = data.ticket.subject;

    const container = document.getElementById("threadMessagesContainer");
    container.textContent = "";
    (data.messages || []).forEach((m) => {
      const bubble = document.createElement("div");
      bubble.className = `message-bubble ${m.sender_type}`;
      const author = document.createElement("strong");
      author.textContent = (m.sender_type === "admin" ? "Поддержка CLIN" : "Вы") + ": ";
      const msgDiv = document.createElement("div");
      msgDiv.textContent = m.message;
      bubble.appendChild(author);
      bubble.appendChild(msgDiv);
      container.appendChild(bubble);
    });

    const sendBtn = document.getElementById("btnSendThreadReply");
    sendBtn.onclick = async () => {
      const input = document.getElementById("threadReplyInput");
      const text = input.value.trim();
      if (!text) return;
      try {
        await apiFetch(`/support/tickets/${ticketNumber}/reply`, {
          method: "POST",
          body: JSON.stringify({ message: text }),
        });
        input.value = "";
        await openTicketDetail(ticketNumber);
      } catch (err) {
        showToast(err.message, "error");
      }
    };

    document.getElementById("ticketDetailModal").style.display = "flex";
  } catch (err) {
    showToast(err.message, "error");
  }
}

// 9. Settings
async function loadSettingsData() {
  try {
    const res = await apiFetch("/settings/rejoin-manifest");
    const box = document.getElementById("manifestPreviewBox");
    if (box) {
      const items = res.manifest || [];
      box.textContent = "";
      if (items.length === 0) {
        box.textContent = "Манифест пуст. При выходе из публичных каналов ссылки появятся здесь.";
      } else {
        items.slice(0, 10).forEach((i) => {
          const row = document.createElement("div");
          row.style.marginBottom = "4px";
          row.textContent = `• ${i.title || "Канал"}: `;

          const rawLink = i.invite_link || (i.username ? `https://t.me/${i.username}` : "");
          if (rawLink) {
            const link = document.createElement("a");
            link.href = sanitizeUrl(rawLink);
            link.target = "_blank";
            link.rel = "noopener noreferrer";
            link.style.color = "var(--clin-green)";
            link.textContent = rawLink;
            row.appendChild(link);
          }
          box.appendChild(row);
        });
      }
    }
  } catch (e) {}
}

// Deep Clean Runner
async function executeDeepClean() {
  showToast("Запуск операции Deep Clean...", "info");
  try {
    const res = await apiFetch("/cleanup/run", {
      method: "POST",
      body: JSON.stringify({ is_max_clean: true, dry_run: false }),
    });
    showToast(`Deep Clean завершён: обработано ${res.processed} диалогов`, "success");
    await loadDashboardData();
  } catch (err) {
    showToast(err.message, "error");
  }
}
