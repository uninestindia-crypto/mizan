/**
 * QuantOS Copilot — In-Platform AI Assistant Controller
 * Provides interactive chat, action proposal execution, and journey navigation.
 */
(function () {
  "use strict";

  let csrfToken = null;
  let isDrawerOpen = false;

  async function fetchCsrfToken() {
    try {
      const res = await fetch("/api/v1/auth/csrf");
      if (res.ok) {
        const data = await res.json();
        csrfToken = data.csrf_token || data.token;
      }
    } catch (err) {
      console.warn("[Copilot] Unable to pre-fetch CSRF token:", err);
    }
  }

  function getActiveTabId() {
    const activeBtn = document.querySelector(".tab-btn.active");
    return activeBtn ? activeBtn.getAttribute("data-tab") : "tab-ingestion";
  }

  function toggleDrawer() {
    const drawer = document.getElementById("copilot-drawer");
    const backdrop = document.getElementById("copilot-backdrop");
    if (!drawer) return;

    isDrawerOpen = !isDrawerOpen;
    if (isDrawerOpen) {
      drawer.classList.add("open");
      if (backdrop) backdrop.classList.add("open");
      document.getElementById("copilot-input")?.focus();
    } else {
      drawer.classList.remove("open");
      if (backdrop) backdrop.classList.remove("open");
    }
  }

  function appendMessage(role, text, proposals, result) {
    const container = document.getElementById("copilot-messages");
    if (!container) return;

    const msgEl = document.createElement("div");
    msgEl.className = `copilot-msg copilot-msg-${role}`;

    const contentEl = document.createElement("div");
    contentEl.className = "copilot-msg-content";
    contentEl.innerHTML = formatMarkdown(text);
    msgEl.appendChild(contentEl);

    // Render Action Proposals if present
    if (proposals && proposals.length > 0) {
      const actionsContainer = document.createElement("div");
      actionsContainer.className = "copilot-action-cards";

      proposals.forEach((prop) => {
        const card = document.createElement("div");
        card.className = "copilot-action-card";

        const title = document.createElement("strong");
        title.innerText = prop.title;

        const desc = document.createElement("p");
        desc.innerText = prop.description;

        const btn = document.createElement("button");
        btn.className = "btn-action-exec";
        btn.innerText = prop.title;
        btn.onclick = () => executeAction(prop);

        card.appendChild(title);
        card.appendChild(desc);
        card.appendChild(btn);
        actionsContainer.appendChild(card);
      });
      msgEl.appendChild(actionsContainer);
    }

    container.appendChild(msgEl);
    container.scrollTop = container.scrollHeight;
  }

  function formatMarkdown(text) {
    if (!text) return "";
    return text
      .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
      .replace(/\*(.*?)\*/g, "<em>$1</em>")
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/\n\n/g, "<br><br>")
      .replace(/\n/g, "<br>");
  }

  async function executeAction(proposal) {
    if (!csrfToken) await fetchCsrfToken();

    appendMessage("user", `Execute: ${proposal.title}`);

    try {
      const res = await fetch("/api/v1/assistant/execute-action", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": csrfToken || "",
        },
        body: JSON.stringify({
          action_id: proposal.action_id,
          action_type: proposal.action_type,
          parameters: proposal.parameters || {},
        }),
      });

      const data = await res.json();
      if (data.success) {
        appendMessage("assistant", data.message || "Action executed successfully.");
        if (data.navigate_to) {
          switchToTab(data.navigate_to);
        }
      } else {
        appendMessage("assistant", `❌ Action failed: ${data.message}`);
      }
    } catch (err) {
      appendMessage("assistant", `❌ Error executing action: ${err.message}`);
    }
  }

  function switchToTab(tabId) {
    const targetBtn = document.querySelector(`.tab-btn[data-tab="${tabId}"]`);
    if (targetBtn) {
      targetBtn.click();
    }
  }

  async function sendUserPrompt(promptText) {
    if (!promptText || !promptText.trim()) return;

    appendMessage("user", promptText);
    const inputEl = document.getElementById("copilot-input");
    if (inputEl) inputEl.value = "";

    const loadingId = "copilot-loading-indicator";
    const container = document.getElementById("copilot-messages");
    const loadingEl = document.createElement("div");
    loadingEl.id = loadingId;
    loadingEl.className = "copilot-msg copilot-msg-assistant copilot-loading";
    loadingEl.innerText = "QuantOS Copilot is thinking...";
    container.appendChild(loadingEl);
    container.scrollTop = container.scrollHeight;

    try {
      const res = await fetch("/api/v1/assistant/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": csrfToken || "",
        },
        body: JSON.stringify({
          prompt: promptText,
          current_tab: getActiveTabId(),
          history: [],
        }),
      });

      loadingEl.remove();
      if (res.ok) {
        const data = await res.json();
        appendMessage("assistant", data.message, data.action_proposals);
        renderPromptChips(data.suggested_prompts || []);
      } else {
        appendMessage("assistant", "⚠️ Server returned an error processing your query.");
      }
    } catch (err) {
      loadingEl.remove();
      appendMessage("assistant", `⚠️ Network error: ${err.message}`);
    }
  }

  function renderPromptChips(prompts) {
    const chipsContainer = document.getElementById("copilot-chips");
    if (!chipsContainer) return;
    chipsContainer.innerHTML = "";

    prompts.slice(0, 4).forEach((p) => {
      const chip = document.createElement("button");
      chip.className = "copilot-chip";
      chip.innerText = p;
      chip.onclick = () => sendUserPrompt(p);
      chipsContainer.appendChild(chip);
    });
  }

  // Initialize UI event listeners on DOM ready
  document.addEventListener("DOMContentLoaded", () => {
    fetchCsrfToken();

    const triggerBtn = document.getElementById("copilot-trigger-btn");
    const closeBtn = document.getElementById("copilot-close-btn");
    const backdrop = document.getElementById("copilot-backdrop");
    const sendBtn = document.getElementById("copilot-send-btn");
    const inputEl = document.getElementById("copilot-input");

    if (triggerBtn) triggerBtn.addEventListener("click", toggleDrawer);
    if (closeBtn) closeBtn.addEventListener("click", toggleDrawer);
    if (backdrop) backdrop.addEventListener("click", toggleDrawer);

    if (sendBtn && inputEl) {
      sendBtn.addEventListener("click", () => sendUserPrompt(inputEl.value));
      inputEl.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          sendUserPrompt(inputEl.value);
        }
      });
    }

    // Default welcome prompt chips
    renderPromptChips([
      "Audit Model & Strategy Profitability",
      "Run System Diagnostics",
      "Calculate Greeks for 24500 CE",
      "Inspect Risk Limits",
      "Explain Deflated Sharpe Ratio",
    ]);
  });
})();
