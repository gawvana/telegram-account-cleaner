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
  dashboardScore: 100,
};

const inFlightOps = new Set();

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

  let icon = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>';
  if (type === "success") icon = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#00E887" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>';
  if (type === "error") icon = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#FF5268" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>';
  if (type === "warning") icon = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#FFB547" stroke-width="2.5"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>';

  const iconSpan = document.createElement("span");
  iconSpan.style.display = "inline-flex";
  iconSpan.style.alignItems = "center";
  iconSpan.innerHTML = icon;
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
      updateAuthUI(true, loginStatus.phone, loginStatus.api_id_masked, loginStatus.api_hash_masked);
      await loadDashboardData();
    } else {
      updateAuthUI(false, "", loginStatus?.api_id_masked, loginStatus?.api_hash_masked);
    }
  } catch (err) {
    console.warn("Init status check notice:", err);
    updateAuthUI(false);
  }
}

function updateAuthUI(isAuth, phone = "", apiIdMasked = "", apiHashMasked = "") {
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
  const banner = document.getElementById("dashboardDisconnectedBanner");
  const credsCard = document.getElementById("settingsApiCredentialsCard");
  const apiIdDisplay = document.getElementById("settingsApiIdDisplay");
  const apiHashDisplay = document.getElementById("settingsApiHashDisplay");

  if (isAuth) {
    if (formBox) formBox.style.display = "none";
    if (banner) banner.style.display = "none";
    if (credsCard) credsCard.style.display = "block";
    if (apiIdDisplay) apiIdDisplay.textContent = apiIdMasked || "••••••••";
    if (apiHashDisplay) apiHashDisplay.textContent = apiHashMasked || "••••••••••";
    if (profileBadge) {
      profileBadge.className = "profile-status text-success";
      profileBadge.textContent = "● Сессия активна (MTProto)";
    }
    if (profilePhone) profilePhone.textContent = `Телефон: ${phone || "Скрыт"}`;
  } else {
    if (formBox) formBox.style.display = "block";
    if (banner) banner.style.display = "block";
    if (credsCard) credsCard.style.display = "none";
    if (profileBadge) {
      profileBadge.className = "profile-status text-danger";
      profileBadge.textContent = "○ Не подключён";
    }
    // Show Step 1 onboarding
    const stepCreds = document.getElementById("loginCredsStep");
    const stepPhone = document.getElementById("loginPhoneStep");
    const stepCode = document.getElementById("loginCodeStep");
    const step2fa = document.getElementById("login2faStep");
    if (stepCreds) stepCreds.style.display = "block";
    if (stepPhone) stepPhone.style.display = "none";
    if (stepCode) stepCode.style.display = "none";
    if (step2fa) step2fa.style.display = "none";
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

  // Close More Sheet if open with smooth animation
  const moreSheet = document.getElementById("mobileMoreSheet");
  if (moreSheet && (moreSheet.classList.contains("open") || moreSheet.style.display === "flex")) {
    moreSheet.classList.remove("open");
    setTimeout(() => { moreSheet.style.display = "none"; }, 280);
  }

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

  // Mobile More Button & Native Sheet
  const btnMobileMore = document.getElementById("btnMobileMore");
  const moreSheetEl = document.getElementById("mobileMoreSheet");
  if (btnMobileMore && moreSheetEl) {
    btnMobileMore.addEventListener("click", () => {
      moreSheetEl.style.display = "flex";
      setTimeout(() => moreSheetEl.classList.add("open"), 10);
    });
  }

  const btnCloseMoreSheet = document.getElementById("btnCloseMoreSheet");
  if (btnCloseMoreSheet && moreSheetEl) {
    btnCloseMoreSheet.addEventListener("click", () => {
      moreSheetEl.classList.remove("open");
      setTimeout(() => { moreSheetEl.style.display = "none"; }, 280);
    });
  }

  if (moreSheetEl) {
    moreSheetEl.addEventListener("click", (e) => {
      if (e.target === moreSheetEl) {
        moreSheetEl.classList.remove("open");
        setTimeout(() => { moreSheetEl.style.display = "none"; }, 280);
      }
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
  document.getElementById("btnRefreshDialogs")?.addEventListener("click", async () => {
    showToast("Обновление списка диалогов...", "info");
    await loadDialogs();
  });
  document.getElementById("btnGoToDialogs")?.addEventListener("click", () => navigateTo("dialogs"));
  document.getElementById("btnGoToSmartClean")?.addEventListener("click", () => navigateTo("smartclean"));
  document.getElementById("btnSelectAllRecs")?.addEventListener("click", () => {
    const checkboxes = document.querySelectorAll("#recommendationsList input[type='checkbox']");
    const allChecked = Array.from(checkboxes).every((cb) => cb.checked);
    checkboxes.forEach((cb) => (cb.checked = !allChecked));
    showToast(!allChecked ? "Все рекомендации выбраны" : "Выбор снят", "info");
  });

  // Smart Clean Batch Execution
  document.getElementById("btnExecuteSmartClean")?.addEventListener("click", async () => {
    const recs = state.dialogs.filter(
      (d) => !d.is_whitelisted && (d.recommended || (d.heuristics && d.heuristics.recommended_for_cleanup))
    );
    if (recs.length === 0) {
      showToast("Нет рекомендаций для очистки", "info");
      return;
    }

    if (!confirm(`Очистить все рекомендованные диалоги (${recs.length} шт.)?`)) return;

    const btn = document.getElementById("btnExecuteSmartClean");
    if (btn) btn.disabled = true;

    try {
      showToast(`Очистка ${recs.length} диалогов...`, "info");
      const res = await apiFetch("/cleanup/run", {
        method: "POST",
        body: JSON.stringify({
          target_chat_ids: recs.map((r) => Number(r.chat_id)),
          dry_run: false,
          is_smart_clean: true,
        }),
      });

      showToast(`Smart Clean завершён: обработано ${res.processed ?? recs.length} диалогов`, "success");
      const cleanedIds = new Set(recs.map((r) => Number(r.chat_id)));
      state.dialogs = state.dialogs.filter((d) => !cleanedIds.has(Number(d.chat_id)));

      renderDialogsList();
      loadSmartCleanRecommendations();
      await loadDashboardData();
    } catch (err) {
      showToast(err.message, "error");
    } finally {
      if (btn) btn.disabled = false;
    }
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
      const res = await apiFetch("/rejoin-manifest");
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

  // 3-Second Hold Logic (Hardened against duplicate mobile events)
  if (btnHoldDeepClean && holdProgressFill) {
    let isHolding = false;

    const startHold = (e) => {
      if (isHolding) return;
      isHolding = true;
      if (e && e.cancelable && e.type === "touchstart") e.preventDefault();

      state.holdStart = Date.now();
      clearInterval(state.holdTimer);
      state.holdTimer = setInterval(() => {
        const elapsed = Date.now() - state.holdStart;
        const pct = Math.min((elapsed / 3000) * 100, 100);
        holdProgressFill.style.width = `${pct}%`;

        if (elapsed >= 3000) {
          clearInterval(state.holdTimer);
          isHolding = false;
          deepCleanModal.style.display = "none";
          executeDeepClean();
        }
      }, 50);
    };

    const cancelHold = () => {
      if (!isHolding) return;
      isHolding = false;
      clearInterval(state.holdTimer);
      holdProgressFill.style.width = "0%";
    };

    btnHoldDeepClean.addEventListener("mousedown", startHold);
    btnHoldDeepClean.addEventListener("mouseup", cancelHold);
    btnHoldDeepClean.addEventListener("mouseleave", cancelHold);
    btnHoldDeepClean.addEventListener("touchstart", startHold, { passive: false });
    btnHoldDeepClean.addEventListener("touchend", cancelHold);
    btnHoldDeepClean.addEventListener("touchcancel", cancelHold);
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

  const btnSelDel = document.getElementById("btnSelectionDelete");
  btnSelDel?.addEventListener("click", async () => {
    if (state.selectedChatIds.size === 0) return;
    if (inFlightOps.has("batch_delete")) return;
    const count = state.selectedChatIds.size;
    if (!confirm(`Очистить выбранные диалоги (${count} шт.)?`)) return;

    inFlightOps.add("batch_delete");
    btnSelDel.disabled = true;
    btnSelDel.classList.add("is-loading");
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
      state.dialogs = []; // Invalidate stale cached dialogs
      await loadDialogs();
      await loadDashboardData();
    } catch (err) {
      showToast(err.message, "error");
    } finally {
      inFlightOps.delete("batch_delete");
      btnSelDel.disabled = false;
      btnSelDel.classList.remove("is-loading");
    }
  });

  // Whitelist Add & Export/Import
  document.getElementById("btnAddWlItem")?.addEventListener("click", async () => {
    const inputId = document.getElementById("inputWlChatId");
    const inputTitle = document.getElementById("inputWlTitle");
    const val = inputId.value.trim();
    if (!val) return;

    const num = parseInt(val, 10);
    if (isNaN(num)) {
      showToast("Введите числовой Chat ID (например: -1001234567890)", "warning");
      return;
    }

    const body = { chat_id: num, title: inputTitle.value.trim() || "" };

    try {
      await apiFetch("/whitelist", { method: "POST", body: JSON.stringify(body) });
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
      const res = await apiFetch("/whitelist/export");
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
        await apiFetch("/whitelist/import", {
          method: "POST",
          body: JSON.stringify({ items }),
        });
        showToast("Whitelist успешно импортирован", "success");
        await loadWhitelist();
      } catch (err) {
        showToast("Ошибка импорта Whitelist: " + err.message, "error");
      }
    });
  }

  // Backup Export / Import
  document.getElementById("btnExportFullBackup")?.addEventListener("click", async () => {
    try {
      const res = await apiFetch("/backup/export");
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
        await apiFetch("/backup/import", {
          method: "POST",
          body: JSON.stringify(json),
        });
        showToast("Резервная копия успешно восстановлена", "success");
      } catch (err) {
        showToast("Ошибка восстановления бэкапа", "error");
      }
    });
  }

  // Schedule Mode Warning Listener
  document.getElementById("scheduleModeSelect")?.addEventListener("change", (e) => {
    const warn = document.getElementById("scheduleModeWarning");
    if (warn) warn.style.display = e.target.value === "auto" ? "block" : "none";
  });

  // Schedule Save
  document.getElementById("btnSaveSchedule")?.addEventListener("click", async () => {
    const btn = document.getElementById("btnSaveSchedule");
    if (btn) btn.classList.add("is-loading");

    const enabled = document.getElementById("scheduleEnableToggle").checked;
    const freq = document.getElementById("scheduleFreqSelect").value;
    const scope = document.getElementById("scheduleScopeSelect").value;
    const mode = document.getElementById("scheduleModeSelect").value;

    const payload = {
      auto_clean_enabled: enabled ? 1 : 0,
      auto_clean_frequency: freq,
      auto_clean_scope: scope,
      auto_clean_mode: mode,
    };

    try {
      await apiFetch("/settings", {
        method: "POST",
        body: JSON.stringify(payload),
      });

      try {
        localStorage.setItem("clin_schedule_settings", JSON.stringify(payload));
      } catch (e) {}

      showToast("Расписание успешно сохранено", "success");
    } catch (err) {
      showToast(err.message, "error");
    } finally {
      if (btn) btn.classList.remove("is-loading");
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

  // Dashboard Connect Banner Trigger
  document.getElementById("btnGoToConnect")?.addEventListener("click", () => {
    navigateTo("settings");
    document.getElementById("loginFormContainer")?.scrollIntoView({ behavior: "smooth" });
  });

  // Password Visibility Toggles
  const eyeSvg = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>';
  const eyeOffSvg = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>';

  document.getElementById("btnToggleApiHash")?.addEventListener("click", () => {
    const input = document.getElementById("loginApiHashInput");
    const btn = document.getElementById("btnToggleApiHash");
    if (input && btn) {
      const isPwd = input.type === "password";
      input.type = isPwd ? "text" : "password";
      btn.innerHTML = isPwd ? eyeOffSvg : eyeSvg;
    }
  });

  document.getElementById("btnToggleChangeApiHash")?.addEventListener("click", () => {
    const input = document.getElementById("changeApiHashInput");
    const btn = document.getElementById("btnToggleChangeApiHash");
    if (input && btn) {
      const isPwd = input.type === "password";
      input.type = isPwd ? "text" : "password";
      btn.innerHTML = isPwd ? eyeOffSvg : eyeSvg;
    }
  });

  // API Guide Modal Triggers
  document.getElementById("btnOpenApiGuide")?.addEventListener("click", () => {
    const modal = document.getElementById("apiCredentialsGuideModal");
    if (modal) modal.style.display = "flex";
  });
  document.getElementById("btnCloseApiGuideModal")?.addEventListener("click", () => {
    const modal = document.getElementById("apiCredentialsGuideModal");
    if (modal) modal.style.display = "none";
  });
  document.getElementById("btnAckApiGuide")?.addEventListener("click", () => {
    const modal = document.getElementById("apiCredentialsGuideModal");
    if (modal) modal.style.display = "none";
  });

  // Onboarding Step 1 -> Step 2
  document.getElementById("btnProceedToPhone")?.addEventListener("click", () => {
    const apiIdVal = document.getElementById("loginApiIdInput")?.value.trim();
    const apiHashVal = document.getElementById("loginApiHashInput")?.value.trim();

    if (!apiIdVal || parseInt(apiIdVal, 10) <= 0) {
      showToast("Введите корректный числовой API ID", "warning");
      return;
    }
    if (!apiHashVal || apiHashVal.length < 8) {
      showToast("Введите корректный API Hash приложения (32 знака)", "warning");
      return;
    }

    const credsStep = document.getElementById("loginCredsStep");
    const phoneStep = document.getElementById("loginPhoneStep");
    if (credsStep) credsStep.style.display = "none";
    if (phoneStep) phoneStep.style.display = "block";
  });

  document.getElementById("btnBackToCreds")?.addEventListener("click", () => {
    const credsStep = document.getElementById("loginCredsStep");
    const phoneStep = document.getElementById("loginPhoneStep");
    if (phoneStep) phoneStep.style.display = "none";
    if (credsStep) credsStep.style.display = "block";
  });

  // Send Auth Code (Step 2)
  document.getElementById("btnSendAuthCode")?.addEventListener("click", async () => {
    const phone = document.getElementById("loginPhoneInput")?.value.trim();
    const apiIdVal = document.getElementById("loginApiIdInput")?.value.trim();
    const apiHashVal = document.getElementById("loginApiHashInput")?.value.trim();

    if (!phone) {
      showToast("Введите номер телефона", "warning");
      return;
    }

    const body = { phone };
    if (apiIdVal) body.api_id = parseInt(apiIdVal, 10);
    if (apiHashVal) body.api_hash = apiHashVal;

    const btn = document.getElementById("btnSendAuthCode");
    if (btn) btn.disabled = true;

    try {
      showToast("Отправка запроса в Telegram...", "info");
      await apiFetch("/login/send-code", {
        method: "POST",
        body: JSON.stringify(body),
      });
      document.getElementById("loginPhoneStep").style.display = "none";
      document.getElementById("loginCodeStep").style.display = "block";
      showToast("Код подтверждения отправлен в ваш Telegram", "success");
    } catch (err) {
      showToast(err.message, "error");
    } finally {
      if (btn) btn.disabled = false;
    }
  });

  // Verify Auth Code (Step 3)
  document.getElementById("btnVerifyAuthCode")?.addEventListener("click", async () => {
    const code = document.getElementById("loginCodeInput")?.value.trim();
    if (!code) return;

    const btn = document.getElementById("btnVerifyAuthCode");
    if (btn) btn.disabled = true;

    try {
      const res = await apiFetch("/login/verify-code", {
        method: "POST",
        body: JSON.stringify({ code }),
      });
      if (res.step === "2FA") {
        document.getElementById("loginCodeStep").style.display = "none";
        document.getElementById("login2faStep").style.display = "block";
        showToast("Требуется 2FA облачный пароль", "info");
      } else if (res.is_authorized) {
        showToast("Аккаунт Telegram успешно подключён!", "success");
        // Clear transient inputs
        if (document.getElementById("loginApiHashInput")) document.getElementById("loginApiHashInput").value = "";
        if (document.getElementById("loginPhoneInput")) document.getElementById("loginPhoneInput").value = "";
        if (document.getElementById("loginCodeInput")) document.getElementById("loginCodeInput").value = "";
        await checkConsentAndAuth();
      }
    } catch (err) {
      showToast(err.message, "error");
    } finally {
      if (btn) btn.disabled = false;
    }
  });

  // Verify 2FA Password (Step 4)
  document.getElementById("btnVerify2fa")?.addEventListener("click", async () => {
    const password = document.getElementById("login2faInput")?.value;
    if (!password) return;

    const btn = document.getElementById("btnVerify2fa");
    if (btn) btn.disabled = true;

    try {
      const res = await apiFetch("/login/verify-2fa", {
        method: "POST",
        body: JSON.stringify({ password }),
      });
      if (res.is_authorized) {
        showToast("Аккаунт Telegram успешно подключён!", "success");
        if (document.getElementById("loginApiHashInput")) document.getElementById("loginApiHashInput").value = "";
        if (document.getElementById("login2faInput")) document.getElementById("login2faInput").value = "";
        await checkConsentAndAuth();
      }
    } catch (err) {
      showToast(err.message, "error");
    } finally {
      if (btn) btn.disabled = false;
    }
  });

  // Change Credentials Modal & Save
  document.getElementById("btnOpenChangeCredsModal")?.addEventListener("click", () => {
    document.getElementById("changeCredentialsModal").style.display = "flex";
  });
  document.getElementById("btnCloseChangeCredsModal")?.addEventListener("click", () => {
    document.getElementById("changeCredentialsModal").style.display = "none";
  });
  document.getElementById("btnCancelChangeCreds")?.addEventListener("click", () => {
    document.getElementById("changeCredentialsModal").style.display = "none";
  });
  document.getElementById("btnSaveChangeCreds")?.addEventListener("click", async () => {
    const apiIdVal = document.getElementById("changeApiIdInput")?.value.trim();
    const apiHashVal = document.getElementById("changeApiHashInput")?.value.trim();

    if (!apiIdVal || parseInt(apiIdVal, 10) <= 0) {
      showToast("Введите корректный числовой API ID", "warning");
      return;
    }
    if (!apiHashVal || apiHashVal.length < 8) {
      showToast("Введите корректный API Hash (32 знака)", "warning");
      return;
    }

    const btn = document.getElementById("btnSaveChangeCreds");
    if (btn) btn.disabled = true;

    try {
      await apiFetch("/settings/credentials", {
        method: "POST",
        body: JSON.stringify({
          api_id: parseInt(apiIdVal, 10),
          api_hash: apiHashVal,
        }),
      });
      showToast("Данные Telegram API обновлены", "success");
      document.getElementById("changeCredentialsModal").style.display = "none";
      if (document.getElementById("changeApiHashInput")) document.getElementById("changeApiHashInput").value = "";
      await checkConsentAndAuth();
    } catch (err) {
      showToast(err.message, "error");
    } finally {
      if (btn) btn.disabled = false;
    }
  });

  // System Diagnostics Modal Triggers
  document.getElementById("btnOpenDiagnosticsModal")?.addEventListener("click", openDiagnosticsModal);
  document.getElementById("btnCloseDiagnosticsModal")?.addEventListener("click", () => {
    document.getElementById("diagnosticsModal").style.display = "none";
  });
  document.getElementById("btnCloseDiagnosticsBtn")?.addEventListener("click", () => {
    document.getElementById("diagnosticsModal").style.display = "none";
  });
  document.getElementById("btnRefreshDiagnostics")?.addEventListener("click", loadDiagnostics);

  // Hygiene Breakdown Modal Triggers
  document.getElementById("btnWhyScore")?.addEventListener("click", openHygieneBreakdownModal);
  document.getElementById("btnCloseHygieneModal")?.addEventListener("click", () => {
    document.getElementById("hygieneBreakdownModal").style.display = "none";
  });
  document.getElementById("btnAckHygieneModal")?.addEventListener("click", () => {
    document.getElementById("hygieneBreakdownModal").style.display = "none";
  });

  // Initialize Desktop Command Palette (Ctrl+K)
  initCommandPalette();
}

// ----------------------------------------------------
// SCREEN CONTROLLERS
// ----------------------------------------------------

// 1. Dashboard
async function loadDashboardData() {
  try {
    const res = await apiFetch("/hygiene-score");
    const score = res.current ? res.current.score : 92;
    state.dashboardScore = score;
    document.getElementById("dashboardScoreValue").textContent = score;

    // Update Circular Gauge
    const circle = document.getElementById("scoreCircleFill");
    if (circle) {
      const circumference = 2 * Math.PI * 50; // ~314.15
      const offset = circumference - (score / 100) * circumference;
      circle.style.strokeDashoffset = offset;
    }

    if (res.current) {
      if (state.dialogs && state.dialogs.length > 0) {
        document.getElementById("statPrivate").textContent = state.dialogs.filter((d) => d.chat_type === "private").length;
        document.getElementById("statBots").textContent = state.dialogs.filter((d) => d.chat_type === "bot").length;
        document.getElementById("statGroups").textContent = state.dialogs.filter((d) => d.chat_type === "group" || d.chat_type === "supergroup").length;
        document.getElementById("statChannels").textContent = state.dialogs.filter((d) => d.chat_type === "channel").length;
      } else {
        document.getElementById("statPrivate").textContent = res.current.private_count ?? res.current.total_dialogs ?? "--";
        document.getElementById("statBots").textContent = res.current.bots_count ?? "--";
        document.getElementById("statGroups").textContent = res.current.groups_count ?? "--";
        document.getElementById("statChannels").textContent = res.current.channels_count ?? "--";
      }
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
              <span class="ticket-number-badge">CLIN-JOB-${escapeHtml(j.id)}</span>
              <strong style="margin-left: 8px;">${escapeHtml(j.job_type)}</strong>
            </div>
            <div style="font-size: 12px; color: var(--clin-text-muted);">
              ${isSuccess ? '<span style="color: var(--clin-green); font-weight: 600;">Успешно</span>' : '<span style="color: var(--clin-danger); font-weight: 600;">' + escapeHtml(j.status) + '</span>'} (${Number(j.processed_items) || 0} обработано)
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
  const btnScan = document.getElementById("btnExecuteScan");

  const optPrivate = document.getElementById("scanOptPrivate")?.checked ?? true;
  const optBots = document.getElementById("scanOptBots")?.checked ?? true;
  const optGroups = document.getElementById("scanOptGroups")?.checked ?? true;
  const optChannels = document.getElementById("scanOptChannels")?.checked ?? true;
  const isDryRun = document.getElementById("scanDryRunSwitch")?.checked ?? true;

  if (btnScan) btnScan.disabled = true;
  pCard.style.display = "block";
  rCard.style.display = "none";
  pFill.style.width = "10%";
  pPct.textContent = "10%";
  pStatus.textContent = isDryRun ? "Симуляция сканирования MTProto..." : "Подключение к Telegram MTProto...";

  try {
    pFill.style.width = "40%";
    pPct.textContent = "40%";
    pStatus.textContent = "Считывание диалогов и каналов...";

    const res = await apiFetch("/scan");
    let items = res.items || [];
    if (!optPrivate) items = items.filter((i) => i.chat_type !== "private");
    if (!optBots) items = items.filter((i) => i.chat_type !== "bot");
    if (!optGroups) items = items.filter((i) => i.chat_type !== "group" && i.chat_type !== "supergroup");
    if (!optChannels) items = items.filter((i) => i.chat_type !== "channel");

    state.dialogs = items;

    pFill.style.width = "100%";
    pPct.textContent = "100%";
    pStatus.textContent = isDryRun ? "Симуляция завершена!" : "Сканирование завершено!";
    pCounts.textContent = `Обработано: ${state.dialogs.length} / ${state.dialogs.length}`;

    setTimeout(() => {
      pCard.style.display = "none";
      rCard.style.display = "block";
      document.getElementById("scanResultTotalTitle").textContent = `Найдено: ${state.dialogs.length} диалогов`;

      const s = res.summary || res || {};
      const breakdown = document.getElementById("scanResultsBreakdown");
      breakdown.innerHTML = `
        <div class="stat-card"><strong>Личные:</strong> ${s.private_chats ?? s.private_count ?? 0}</div>
        <div class="stat-card"><strong>Боты:</strong> ${s.bot_chats ?? s.bots_count ?? 0}</div>
        <div class="stat-card"><strong>Группы:</strong> ${s.group_chats ?? s.groups_count ?? 0}</div>
        <div class="stat-card"><strong>Каналы:</strong> ${s.channel_chats ?? s.channels_count ?? 0}</div>
        <div class="stat-card"><strong>В Whitelist:</strong> ${s.whitelisted_count ?? 0}</div>
        <div class="stat-card"><strong>Рекомендовано:</strong> ${s.recommended_count ?? 0}</div>
      `;
      loadDashboardData();
      showToast(`Найдено ${state.dialogs.length} диалогов`, "success");
    }, 600);
  } catch (err) {
    pCard.style.display = "none";
    showToast(err.message, "error");
  } finally {
    if (btnScan) btnScan.disabled = false;
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
    const filterUpper = String(state.activeFilter || "").toUpperCase();
    if (filterUpper === "INACTIVE") {
      filtered = filtered.filter((d) => (d.inactive_days ?? d.heuristics?.inactive_days ?? 0) >= 60);
    } else if (filterUpper === "GROUP") {
      filtered = filtered.filter((d) => {
        const type = String(d.chat_type || "").toUpperCase();
        return type === "GROUP" || type === "SUPERGROUP";
      });
    } else {
      filtered = filtered.filter((d) => String(d.chat_type || "").toUpperCase() === filterUpper);
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
      const inactive = d.inactive_days ?? d.heuristics?.inactive_days ?? 0;
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
            ${isWl ? '<span class="badge-wl" style="display: inline-flex; align-items: center; gap: 4px;"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg><span>Whitelist</span></span>' : ""}
            ${inactive > 0 ? `<span>Неактивен: ${inactive} дн.</span>` : ""}
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

// 4. Smart Clean Recommendations & Single Clean
async function cleanSingleChat(chatId) {
  const numericChatId = Number(chatId);
  const opKey = `clean_${numericChatId}`;
  if (inFlightOps.has(opKey)) return;

  const target = state.dialogs.find((d) => Number(d.chat_id) === numericChatId);
  const chatName = target ? target.title : `ID ${numericChatId}`;

  if (!confirm(`Очистить и покинуть диалог "${chatName}"?`)) return;

  inFlightOps.add(opKey);
  try {
    showToast(`Очистка "${chatName}"...`, "info");
    const res = await apiFetch("/cleanup/run", {
      method: "POST",
      body: JSON.stringify({
        target_chat_ids: [numericChatId],
        dry_run: false,
      }),
    });

    showToast(`Успешно очищено (${res.processed ?? 1} диалог)`, "success");

    state.dialogs = state.dialogs.filter((d) => Number(d.chat_id) !== numericChatId);
    state.selectedChatIds.delete(numericChatId);

    renderDialogsList();
    loadSmartCleanRecommendations();
    await loadDashboardData();
  } catch (err) {
    showToast(err.message, "error");
  } finally {
    inFlightOps.delete(opKey);
  }
}
window.cleanSingleChat = cleanSingleChat;

async function loadSmartCleanRecommendations() {
  if (state.dialogs.length === 0) {
    await loadDialogs();
  }

  const recs = state.dialogs.filter(
    (d) => !d.is_whitelisted && (d.recommended || (d.heuristics && d.heuristics.recommended_for_cleanup))
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
      const tags = d.tags || (d.heuristics && d.heuristics.tags) || [];
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
    const res = await apiFetch("/whitelist");
    const container = document.getElementById("whitelistContainer");
    if (!container) return;

    const items = Array.isArray(res) ? res : (res.whitelist || []);
    if (items.length === 0) {
      container.innerHTML = '<div style="padding: 16px; color: var(--clin-text-muted);">Белый список пуст.</div>';
      return;
    }

    container.innerHTML = items
      .map(
        (i) => `
      <div class="table-row">
        <span>${escapeHtml(i.title || i.username || "Chat")}</span>
        <span class="font-mono">${escapeHtml(i.chat_id)}</span>
        <span>${escapeHtml(i.added_at ? i.added_at.slice(0, 10) : "--")}</span>
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
  const numericChatId = Number(chatId);
  const opKey = `rm_wl_${numericChatId}`;
  if (inFlightOps.has(opKey)) return;

  inFlightOps.add(opKey);
  try {
    await apiFetch(`/whitelist/${numericChatId}`, { method: "DELETE" });
    showToast("Удалено из белого списка", "info");
    await loadWhitelist();
  } catch (err) {
    showToast(err.message, "error");
  } finally {
    inFlightOps.delete(opKey);
  }
}
window.removeWlItem = removeWlItem;

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
              <span class="ticket-number-badge">CLIN-JOB-${escapeHtml(j.id)}</span>
              <strong style="margin-left: 8px;">${escapeHtml(j.job_type)}</strong>
            </div>
            <div style="font-size: 12px; color: var(--clin-text-muted);">
              ${j.status === "COMPLETED" ? '<span style="color: var(--clin-green); font-weight: 600;">Успешно</span>' : '<span style="color: var(--clin-danger); font-weight: 600;">' + escapeHtml(j.status) + '</span>'} | ${Number(j.processed_items) || 0} обработано
            </div>
          </div>
        `
          )
          .join("");
      }
    }

    // Initialize Chart.js for Hygiene History
    const scoreData = await apiFetch("/hygiene-score").catch(() => null);
    const canvas = document.getElementById("hygieneHistoryChart");
    if (canvas && scoreData && Array.isArray(scoreData.history) && scoreData.history.length > 0 && typeof Chart !== "undefined") {
      const labels = scoreData.history.map((h) => (h.recorded_at ? h.recorded_at.slice(5, 16).replace("T", " ") : ""));
      const dataPoints = scoreData.history.map((h) => h.score);

      if (state.chartInstance) {
        state.chartInstance.destroy();
      }

      state.chartInstance = new Chart(canvas, {
        type: "line",
        data: {
          labels,
          datasets: [{
            label: "Hygiene Score",
            data: dataPoints,
            borderColor: "#00E887",
            backgroundColor: "rgba(0, 232, 135, 0.12)",
            tension: 0.35,
            fill: true,
            pointBackgroundColor: "#00E887",
            pointRadius: 4,
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            y: { min: 0, max: 100, grid: { color: "rgba(255,255,255,0.06)" }, ticks: { color: "#9BA3AA" } },
            x: { grid: { display: false }, ticks: { color: "#9BA3AA" } },
          },
          plugins: {
            legend: { display: false },
            tooltip: {
              backgroundColor: "#191D20",
              titleColor: "#F5F7F8",
              bodyColor: "#00E887",
              borderColor: "rgba(255,255,255,0.1)",
              borderWidth: 1,
            },
          },
        },
      });
    }

    // Load Cryptographic Audit Timeline
    await loadAuditTimeline();
  } catch (err) {
    console.warn("Could not load history:", err);
  }
}

// 7. Schedule
async function loadSchedule() {
  try {
    const res = await apiFetch("/settings");
    let s = res.settings || res || {};

    try {
      const cached = JSON.parse(localStorage.getItem("clin_schedule_settings") || "{}");
      if (cached && typeof cached === "object") {
        s = { ...cached, ...s };
      }
    } catch (e) {}

    document.getElementById("scheduleEnableToggle").checked = Boolean(s.auto_clean_enabled);
    if (s.auto_clean_frequency) document.getElementById("scheduleFreqSelect").value = s.auto_clean_frequency;
    if (s.auto_clean_scope) document.getElementById("scheduleScopeSelect").value = s.auto_clean_scope;
    if (s.auto_clean_mode) {
      document.getElementById("scheduleModeSelect").value = s.auto_clean_mode;
      const warn = document.getElementById("scheduleModeWarning");
      if (warn) warn.style.display = s.auto_clean_mode === "auto" ? "block" : "none";
    }
  } catch (err) {
    console.warn("Could not load schedule:", err);
    try {
      const cached = JSON.parse(localStorage.getItem("clin_schedule_settings") || "{}");
      if (cached && typeof cached === "object") {
        document.getElementById("scheduleEnableToggle").checked = Boolean(cached.auto_clean_enabled);
        if (cached.auto_clean_frequency) document.getElementById("scheduleFreqSelect").value = cached.auto_clean_frequency;
        if (cached.auto_clean_scope) document.getElementById("scheduleScopeSelect").value = cached.auto_clean_scope;
        if (cached.auto_clean_mode) document.getElementById("scheduleModeSelect").value = cached.auto_clean_mode;
      }
    } catch (e) {}
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
    const res = await apiFetch("/rejoin-manifest");
    const box = document.getElementById("manifestPreviewBox");
    if (box) {
      const items = Array.isArray(res) ? res : (res.manifest || []);
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

// ========================================================
// CLIN 2.0 ADVANCED CONTROLLERS & PRODUCT CAPABILITIES
// ========================================================

// 1. Desktop Command Palette (Ctrl+K / Cmd+K)
function initCommandPalette() {
  const modal = document.getElementById("commandPaletteModal");
  const input = document.getElementById("commandPaletteInput");
  const resultsContainer = document.getElementById("commandPaletteResults");
  if (!modal || !input || !resultsContainer) return;

  const commands = [
    { title: "Дашборд", desc: "Сводка состояния и гигиена профиля", action: () => navigateTo("dashboard"), shortcut: "D" },
    { title: "Сканирование", desc: "Запустить анализ аккаунта", action: () => { navigateTo("scan"); executeScan(); }, shortcut: "S" },
    { title: "Диалоги", desc: "Список чатов, каналов и ботов", action: () => navigateTo("dialogs"), shortcut: "C" },
    { title: "Smart Clean", desc: "Умная очистка неактивных диалогов", action: () => navigateTo("smartclean"), shortcut: "M" },
    { title: "Белый список", desc: "Управление защищёнными чатами", action: () => navigateTo("whitelist"), shortcut: "W" },
    { title: "История операций", desc: "Журнал очисток и крипто-таймлайн", action: () => navigateTo("history"), shortcut: "H" },
    { title: "Расписание", desc: "Автоматическая регулярная очистка", action: () => navigateTo("schedule"), shortcut: "R" },
    { title: "Центр поддержки", desc: "Создать обращение или тикет", action: () => navigateTo("support"), shortcut: "T" },
    { title: "Настройки", desc: "Telegram API, безопасность и бэкапы", action: () => navigateTo("settings"), shortcut: "N" },
    { title: "Системная диагностика", desc: "Проверить статус ядра CLIN и БД", action: () => openDiagnosticsModal(), shortcut: "DG" },
    { title: "Индекс гигиены", desc: "Посмотреть факторы и расчёт баллов", action: () => openHygieneBreakdownModal(), shortcut: "SC" },
    { title: "Экспорт архива", desc: "Выгрузить настройки и белый список в JSON", action: () => document.getElementById("btnExportFullBackup")?.click(), shortcut: "EX" },
  ];

  let selectedIndex = 0;
  let filteredCommands = [...commands];

  function renderPalette() {
    resultsContainer.innerHTML = "";
    if (filteredCommands.length === 0) {
      resultsContainer.innerHTML = '<div style="padding: 14px; text-align: center; color: var(--clin-text-muted); font-size: 13px;">Команды не найдены</div>';
      return;
    }

    filteredCommands.forEach((cmd, idx) => {
      const btn = document.createElement("button");
      btn.className = `palette-item ${idx === selectedIndex ? "active" : ""}`;
      btn.innerHTML = `
        <div class="palette-item-left">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg>
          <div>
            <div style="font-weight: 600;">${escapeHtml(cmd.title)}</div>
            <div style="font-size: 11px; color: var(--clin-text-muted);">${escapeHtml(cmd.desc)}</div>
          </div>
        </div>
        <span class="palette-shortcut-badge">${escapeHtml(cmd.shortcut)}</span>
      `;
      btn.addEventListener("click", () => {
        closePalette();
        cmd.action();
      });
      resultsContainer.appendChild(btn);
    });
  }

  function openPalette() {
    modal.style.display = "flex";
    setTimeout(() => {
      modal.classList.add("open");
      input.value = "";
      filteredCommands = [...commands];
      selectedIndex = 0;
      renderPalette();
      input.focus();
    }, 10);
  }

  function closePalette() {
    modal.classList.remove("open");
    setTimeout(() => { modal.style.display = "none"; }, 180);
  }

  window.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
      e.preventDefault();
      if (modal.classList.contains("open")) {
        closePalette();
      } else {
        openPalette();
      }
    } else if (e.key === "Escape" && modal.classList.contains("open")) {
      closePalette();
    }
  });

  input.addEventListener("input", () => {
    const q = input.value.trim().toLowerCase();
    filteredCommands = commands.filter((c) => c.title.toLowerCase().includes(q) || c.desc.toLowerCase().includes(q));
    selectedIndex = 0;
    renderPalette();
  });

  input.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      selectedIndex = (selectedIndex + 1) % (filteredCommands.length || 1);
      renderPalette();
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      selectedIndex = (selectedIndex - 1 + (filteredCommands.length || 1)) % (filteredCommands.length || 1);
      renderPalette();
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (filteredCommands[selectedIndex]) {
        closePalette();
        filteredCommands[selectedIndex].action();
      }
    }
  });

  modal.addEventListener("click", (e) => {
    if (e.target === modal) closePalette();
  });
}

// 2. Non-Destructive System Diagnostics Modal
async function openDiagnosticsModal() {
  const modal = document.getElementById("diagnosticsModal");
  if (!modal) return;
  modal.style.display = "flex";
  await loadDiagnostics();
}

async function loadDiagnostics() {
  const grid = document.getElementById("diagnosticsGrid");
  const tsLabel = document.getElementById("diagnosticsTimestamp");
  if (!grid) return;

  grid.innerHTML = '<div class="diag-card"><span style="color: var(--clin-text-muted); font-size: 12px;">Опрос подсистем...</span></div>';

  try {
    const data = await apiFetch("/diagnostics");
    if (tsLabel && data.timestamp) {
      tsLabel.textContent = `Обновлено: ${data.timestamp.replace("T", " ").slice(0, 19)}`;
    }

    grid.innerHTML = `
      <div class="diag-card">
        <div class="diag-card-header">
          <span class="diag-title">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>
            <span>FastAPI Ядро</span>
          </span>
          <span class="diag-status-pill ${data.backend?.status === 'ok' ? 'ok' : 'warn'}">${data.backend?.status || 'OK'}</span>
        </div>
        <div class="diag-row"><span>Версия:</span> <strong>${escapeHtml(data.backend?.app_version || '2.1.0')}</strong></div>
        <div class="diag-row"><span>Аптайм:</span> <strong>${Math.round(data.backend?.uptime_seconds || 0)} сек</strong></div>
        <div class="diag-row"><span>Режим:</span> <strong>${data.backend?.serverless_mode ? 'Serverless' : 'Daemon'}</strong></div>
      </div>

      <div class="diag-card">
        <div class="diag-card-header">
          <span class="diag-title">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg>
            <span>SQLite База Данных</span>
          </span>
          <span class="diag-status-pill ${data.database?.status === 'ok' ? 'ok' : 'warn'}">${data.database?.status || 'OK'}</span>
        </div>
        <div class="diag-row"><span>Целостность:</span> <strong>${escapeHtml(data.database?.integrity_check || 'ok')}</strong></div>
        <div class="diag-row"><span>Журнал:</span> <strong>${escapeHtml(data.database?.journal_mode || 'WAL')}</strong></div>
        <div class="diag-row"><span>Задержка:</span> <strong>${(data.database?.latency_ms || 0).toFixed(2)} ms</strong></div>
      </div>

      <div class="diag-card">
        <div class="diag-card-header">
          <span class="diag-title">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
            <span>Сессионное хранилище</span>
          </span>
          <span class="diag-status-pill ${data.sessions?.status === 'ok' ? 'ok' : 'warn'}">${data.sessions?.status || 'OK'}</span>
        </div>
        <div class="diag-row"><span>Шифрование:</span> <strong>${data.sessions?.master_key_configured ? 'Fernet AES' : 'Локально'}</strong></div>
        <div class="diag-row"><span>Активные сессии:</span> <strong>${data.sessions?.active_sessions_count || 0}</strong></div>
        <div class="diag-row"><span>Права записи:</span> <strong>${data.sessions?.is_writable ? 'Разрешено' : 'Нет'}</strong></div>
      </div>

      <div class="diag-card">
        <div class="diag-card-header">
          <span class="diag-title">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
            <span>Планировщик и диск</span>
          </span>
          <span class="diag-status-pill ${data.scheduler?.status === 'ok' ? 'ok' : 'warn'}">${data.scheduler?.status || 'OK'}</span>
        </div>
        <div class="diag-row"><span>Планировщик:</span> <strong>${data.scheduler?.enabled ? 'Активен' : 'Отключён'}</strong></div>
        <div class="diag-row"><span>Задач в очереди:</span> <strong>${data.scheduler?.registered_jobs_count || 0}</strong></div>
        <div class="diag-row"><span>Размер БД:</span> <strong>${Math.round((data.storage?.db_size_bytes || 0) / 1024)} KB</strong></div>
      </div>
    `;
  } catch (err) {
    grid.innerHTML = `<div style="color: var(--clin-danger); padding: 14px; font-size: 13px;">Ошибка диагностики: ${escapeHtml(err.message)}</div>`;
  }
}

// 3. Hygiene Score Breakdown Modal
async function openHygieneBreakdownModal() {
  const modal = document.getElementById("hygieneBreakdownModal");
  if (!modal) return;
  modal.style.display = "flex";

  const gradeEl = document.getElementById("modalHygieneGrade");
  const scoreValEl = document.getElementById("modalHygieneScoreVal");
  const descEl = document.getElementById("modalHygieneScoreDesc");
  const listEl = document.getElementById("modalDeductionsList");

  if (listEl) {
    listEl.innerHTML = '<div style="color: var(--clin-text-muted); font-size: 12px; padding: 8px;">Загрузка расчёта индекса...</div>';
  }

  try {
    const res = await apiFetch("/settings/hygiene-score/breakdown");
    if (gradeEl) gradeEl.textContent = res.grade || "A";
    if (scoreValEl) scoreValEl.textContent = `${res.score || 100} / 100`;

    if (descEl) {
      if (res.score >= 90) descEl.textContent = "Превосходный уровень гигиены аккаунта";
      else if (res.score >= 75) descEl.textContent = "Хороший уровень: рекомендуется очистить неактивные подписки";
      else if (res.score >= 50) descEl.textContent = "Умеренный уровень: накопились забытые каналы и боты";
      else descEl.textContent = "Критический уровень: требуется проведение глубокой очистки";
    }

    if (listEl) {
      const deductions = res.deductions || [];
      if (deductions.length === 0) {
        listEl.innerHTML = '<div style="color: var(--clin-green); font-size: 12.5px; padding: 10px;">Штрафные баллы отсутствуют. Ваш аккаунт полностью оптимизирован!</div>';
      } else {
        listEl.innerHTML = deductions.map((d) => `
          <div class="deduction-item">
            <div class="deduction-details">
              <span class="deduction-name">${escapeHtml(d.category)}</span>
              <span class="deduction-advice">${escapeHtml(d.advice)}</span>
            </div>
            <div class="deduction-penalty">${d.total_deduction > 0 ? `-${d.total_deduction}` : "0"} б.</div>
          </div>
        `).join("");
      }
    }
  } catch (err) {
    if (listEl) {
      listEl.innerHTML = `<div style="color: var(--clin-warning); font-size: 12px; padding: 8px;">Информация временно рассчитывается локально: текущий индекс ${state.dashboardScore || 100}/100.</div>`;
    }
  }
}

// 4. Cryptographic Audit Timeline Loader
async function loadAuditTimeline() {
  const container = document.getElementById("auditTimelineContainer");
  if (!container) return;
  try {
    const entries = await apiFetch("/history/audit-timeline");
    if (!Array.isArray(entries) || entries.length === 0) {
      container.innerHTML = '<div style="color: var(--clin-text-muted); font-size: 12px; padding: 8px;">Журнал аудита чист.</div>';
      return;
    }
    container.innerHTML = entries.map((e) => `
      <div style="display: flex; justify-content: space-between; align-items: center; padding: 6px 0; border-bottom: 1px solid var(--clin-border-subtle); font-size: 11.5px;">
        <div>
          <span style="font-weight: 600; color: var(--clin-text);">${escapeHtml(e.action)}</span>
          <span style="color: var(--clin-text-muted); margin-left: 6px;">Чат: ${escapeHtml(e.chat_id)}</span>
        </div>
        <div style="display: flex; align-items: center; gap: 6px;">
          <span style="font-family: var(--font-mono); color: var(--clin-text-muted);">${e.timestamp?.slice(11, 19) || ''}</span>
          ${e.is_tamper_evident_valid ? '<span style="color: var(--clin-green); font-size: 10px; border: 1px solid rgba(0,232,135,0.3); padding: 1px 4px; border-radius: 3px;">SHA-256 OK</span>' : '<span style="color: var(--clin-danger); font-size: 10px;">INVALID</span>'}
        </div>
      </div>
    `).join("");
  } catch (err) {
    console.warn("Could not load audit timeline:", err);
  }
}

