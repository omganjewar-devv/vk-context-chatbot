// State Management
let currentConversationId = localStorage.getItem("active_conversation_id") || null;
let currentStrategy = localStorage.getItem("active_strategy") || "truncation";
let conversations = [];
let isGenerating = false;
let latestContextMeta = null;

// DOM Elements
const messagesContainer = document.getElementById("messages-container");
const chatForm = document.getElementById("chat-form");
const userInput = document.getElementById("user-input");
const sendBtn = document.getElementById("send-btn");
const typingIndicator = document.getElementById("typing-indicator");
const conversationList = document.getElementById("conversation-list");
const newChatBtn = document.getElementById("new-chat-btn");
const strategySelector = document.getElementById("strategy-selector");
const providerNameEl = document.getElementById("provider-name");
const apiStatusBanner = document.getElementById("api-status-banner");
const apiStatusMessage = document.getElementById("api-status-message");
const toggleInspectorBtn = document.getElementById("toggle-inspector-btn");
const inspectorDrawer = document.getElementById("context-inspector-drawer");

// Inspector Elements
const inspectorTotalTurns = document.getElementById("inspector-total-turns");
const inspectorActiveTurns = document.getElementById("inspector-active-turns");
const inspectorPrunedTurns = document.getElementById("inspector-pruned-turns");
const inspectorEstTokens = document.getElementById("inspector-est-tokens");
const inspectorStrategyName = document.getElementById("inspector-strategy-name");
const inspectorStrategyDesc = document.getElementById("inspector-strategy-desc");
const inspectorSummarySection = document.getElementById("inspector-summary-section");
const inspectorSummaryContent = document.getElementById("inspector-summary-content");
const inspectorSummaryLen = document.getElementById("inspector-summary-len");
const inspectorSystemPrompt = document.getElementById("inspector-system-prompt");
const statSessionsCount = document.getElementById("stat-sessions-count");
const statCurrentTurns = document.getElementById("stat-current-turns");

// Initialize Marked Options
if (window.marked) {
  marked.setOptions({
    highlight: function(code, lang) {
      if (lang && hljs.getLanguage(lang)) {
        try {
          return hljs.highlight(code, { language: lang }).value;
        } catch (e) {}
      }
      return hljs.highlightAuto(code).value;
    },
    breaks: true
  });
}

// Auto-resize input textarea
userInput.addEventListener("input", function() {
  this.style.height = "auto";
  this.style.height = (this.scrollHeight) + "px";
});

// Submit on Enter (Shift+Enter for newline)
userInput.addEventListener("keydown", function(e) {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    chatForm.dispatchEvent(new Event("submit"));
  }
});

// Toggle Context Inspector Drawer (Desktop / Mobile)
toggleInspectorBtn.addEventListener("click", () => {
  inspectorDrawer.classList.toggle("hidden");
});

// Strategy Selector Change
strategySelector.value = currentStrategy;
strategySelector.addEventListener("change", (e) => {
  currentStrategy = e.target.value;
  localStorage.setItem("active_strategy", currentStrategy);
  updateInspectorStrategyInfo(currentStrategy);
});

// New Chat Button
newChatBtn.addEventListener("click", () => {
  startNewConversation();
});

// Prompt Chips Handler
document.querySelectorAll(".prompt-chip").forEach(chip => {
  chip.addEventListener("click", () => {
    userInput.value = chip.getAttribute("data-text");
    userInput.focus();
    userInput.style.height = "auto";
    userInput.style.height = (userInput.scrollHeight) + "px";
  });
});

// Handle Chat Submission
chatForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const message = userInput.value.trim();
  if (!message || isGenerating) return;

  // Clear input
  userInput.value = "";
  userInput.style.height = "auto";

  // Hide starter prompts once user engages
  const promptsEl = document.getElementById("suggested-prompts");
  if (promptsEl) promptsEl.classList.add("hidden");

  // Render User Message immediately
  appendMessage("user", message);

  // Set Generating State
  setGenerating(true);

  try {
    const payload = {
      message: message,
      conversation_id: currentConversationId,
      strategy: currentStrategy
    };

    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      const errMsg = errData.detail || `Server returned error status ${res.status}`;
      appendErrorMessage(`Error: ${errMsg}`);
      return;
    }

    const data = await res.json();

    // Update conversation ID if newly assigned
    if (data.conversation_id) {
      currentConversationId = data.conversation_id;
      localStorage.setItem("active_conversation_id", currentConversationId);
    }

    // Render Assistant Reply with Metadata chip
    appendMessage("assistant", data.reply, data.metadata);

    // Update Context Inspector
    if (data.metadata) {
      latestContextMeta = data.metadata;
      updateContextInspector(data.metadata);
    }

    // Refresh Sidebar Conversations
    loadConversations();

  } catch (err) {
    console.error("Chat error:", err);
    appendErrorMessage(`Network Error: Unable to communicate with backend server. Check your connection.`);
  } finally {
    setGenerating(false);
  }
});

function setGenerating(generating) {
  isGenerating = generating;
  sendBtn.disabled = generating;
  if (generating) {
    typingIndicator.classList.remove("hidden");
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
  } else {
    typingIndicator.classList.add("hidden");
  }
}

function appendMessage(role, text, metadata = null) {
  const msgWrapper = document.createElement("div");
  msgWrapper.className = `flex flex-col message-animate ${role === "user" ? "items-end" : "items-start"}`;

  const innerContainer = document.createElement("div");
  innerContainer.className = `flex items-start space-x-2.5 max-w-[85%] sm:max-w-[75%] ${role === "user" ? "flex-row-reverse space-x-reverse" : "flex-row"}`;

  // Avatar
  const avatar = document.createElement("div");
  if (role === "user") {
    avatar.className = "w-7 h-7 rounded-full bg-slate-700 flex items-center justify-center shrink-0 text-slate-200 text-xs mt-1 shadow";
    avatar.innerHTML = `<i class="fa-solid fa-user"></i>`;
  } else {
    avatar.className = "w-7 h-7 rounded-full bg-gradient-to-tr from-cyan-500 to-indigo-600 flex items-center justify-center shrink-0 text-white text-xs mt-1 shadow-md shadow-indigo-500/20";
    avatar.innerHTML = `<i class="fa-solid fa-brain"></i>`;
  }

  // Bubble
  const bubble = document.createElement("div");
  bubble.className = `px-4 py-3 rounded-2xl ${role === "user" ? "user-bubble text-white text-sm" : "assistant-bubble text-slate-200 prose-chat"}`;

  if (role === "assistant") {
    bubble.innerHTML = window.marked ? marked.parse(text) : text;
  } else {
    bubble.textContent = text;
  }

  innerContainer.appendChild(avatar);
  innerContainer.appendChild(bubble);
  msgWrapper.appendChild(innerContainer);

  // If assistant returned context metadata, append small pill
  if (role === "assistant" && metadata) {
    const metaChip = document.createElement("div");
    metaChip.className = "text-[10px] text-slate-500 mt-1 ml-10 flex items-center space-x-2";
    
    const stratName = metadata.strategy === "summarization" ? "Running Summary" : "Sliding Window";
    let summaryTag = metadata.has_summary ? ` | <span class="text-indigo-400 font-medium">Summary Active</span>` : "";
    let prunedTag = metadata.pruned_count > 0 ? ` | <span class="text-amber-400 font-medium">Pruned ${metadata.pruned_count}</span>` : "";

    metaChip.innerHTML = `
      <span>Strategy: <strong class="text-slate-400">${stratName}</strong></span>
      <span>|</span>
      <span>Active Turns: <strong class="text-slate-400">${metadata.active_context_count}</strong>/${metadata.total_history_count}</span>
      ${prunedTag}
      ${summaryTag}
      <span>|</span>
      <span>~${metadata.estimated_tokens} tokens</span>
    `;
    msgWrapper.appendChild(metaChip);
  }

  messagesContainer.appendChild(msgWrapper);
  messagesContainer.scrollTop = messagesContainer.scrollHeight;

  // Highlight any code blocks in message
  if (role === "assistant" && window.hljs) {
    bubble.querySelectorAll("pre code").forEach((block) => {
      hljs.highlightElement(block);
    });
  }
}

function appendErrorMessage(errorText) {
  const errBox = document.createElement("div");
  errBox.className = "p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-start space-x-2.5 max-w-[85%] message-animate";
  errBox.innerHTML = `
    <i class="fa-solid fa-circle-exclamation text-rose-400 mt-0.5 shrink-0"></i>
    <div class="leading-relaxed">
      <strong>Request Alert:</strong> ${errorText}
    </div>
  `;
  messagesContainer.appendChild(errBox);
  messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

// Context Inspector Updates
function updateInspectorStrategyInfo(strategy) {
  if (strategy === "summarization") {
    inspectorStrategyName.textContent = "Running Summarization";
    inspectorStrategyDesc.textContent = "Older turns are periodically compressed into a concise running summary and prepended to context.";
    inspectorSummarySection.classList.remove("hidden");
  } else {
    inspectorStrategyName.textContent = "Sliding Window Truncation";
    inspectorStrategyDesc.textContent = "Only the last 6 messages are forwarded to the model. Older turns are pruned to cap token consumption.";
    inspectorSummarySection.classList.add("hidden");
  }
}

function updateContextInspector(meta) {
  if (!meta) return;

  inspectorTotalTurns.textContent = meta.total_history_count;
  inspectorActiveTurns.textContent = meta.active_context_count;
  inspectorPrunedTurns.textContent = meta.pruned_count;
  inspectorEstTokens.textContent = meta.estimated_tokens;
  statCurrentTurns.textContent = meta.total_history_count;

  updateInspectorStrategyInfo(meta.strategy);

  if (meta.strategy === "summarization") {
    inspectorSummarySection.classList.remove("hidden");
    if (meta.summary) {
      inspectorSummaryContent.textContent = meta.summary;
      inspectorSummaryLen.textContent = `${meta.summary.length} chars`;
    } else {
      inspectorSummaryContent.textContent = "(No summary generated yet; triggers after threshold turns)";
      inspectorSummaryLen.textContent = "0 chars";
    }
  } else {
    inspectorSummarySection.classList.add("hidden");
  }
}

// Conversation Management
async function loadConversations() {
  try {
    const res = await fetch("/api/conversations");
    if (!res.ok) return;
    conversations = await res.json();

    statSessionsCount.textContent = conversations.length;
    renderConversationList();

    // If no active conversation, create or select first
    if (!currentConversationId && conversations.length > 0) {
      selectConversation(conversations[0].conversation_id);
    }
  } catch (e) {
    console.error("Failed to load conversations:", e);
  }
}

function renderConversationList() {
  conversationList.innerHTML = "";
  if (conversations.length === 0) {
    conversationList.innerHTML = `<div class="text-[11px] text-slate-500 p-2 text-center">No active chats</div>`;
    return;
  }

  conversations.forEach((conv) => {
    const isActive = conv.conversation_id === currentConversationId;
    const item = document.createElement("div");
    item.className = `p-2.5 rounded-lg cursor-pointer transition flex items-center justify-between group ${isActive ? "bg-slate-800 text-cyan-300 font-medium" : "hover:bg-slate-800/50 text-slate-400 hover:text-slate-200"}`;

    const info = document.createElement("div");
    info.className = "flex-1 min-w-0 pr-2";
    
    const preview = conv.last_message_preview || "New conversation";
    info.innerHTML = `
      <div class="truncate text-xs">${preview}</div>
      <div class="text-[10px] text-slate-500 flex items-center space-x-1.5 mt-0.5">
        <span>${conv.message_count} turns</span>
        <span>•</span>
        <span class="capitalize">${conv.strategy}</span>
      </div>
    `;

    info.addEventListener("click", () => {
      selectConversation(conv.conversation_id);
    });

    const delBtn = document.createElement("button");
    delBtn.className = "opacity-0 group-hover:opacity-100 text-slate-500 hover:text-rose-400 p-1 text-xs transition";
    delBtn.innerHTML = `<i class="fa-solid fa-trash"></i>`;
    delBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      deleteConversation(conv.conversation_id);
    });

    item.appendChild(info);
    item.appendChild(delBtn);
    conversationList.appendChild(item);
  });
}

async function selectConversation(convId) {
  currentConversationId = convId;
  localStorage.setItem("active_conversation_id", currentConversationId);
  renderConversationList();

  try {
    const res = await fetch(`/api/conversations/${convId}`);
    if (!res.ok) {
      startNewConversation();
      return;
    }
    const data = await res.json();
    currentStrategy = data.strategy;
    strategySelector.value = currentStrategy;
    updateInspectorStrategyInfo(currentStrategy);

    // Replay messages in UI
    messagesContainer.innerHTML = "";
    if (data.messages && data.messages.length > 0) {
      const promptsEl = document.getElementById("suggested-prompts");
      if (promptsEl) promptsEl.classList.add("hidden");

      data.messages.forEach(m => {
        appendMessage(m.role, m.content);
      });
    }

    statCurrentTurns.textContent = data.message_count;
    inspectorTotalTurns.textContent = data.message_count;
    
    // Update summary in inspector if present
    if (data.running_summary) {
      inspectorSummaryContent.textContent = data.running_summary;
      inspectorSummaryLen.textContent = `${data.running_summary.length} chars`;
    }

  } catch (e) {
    console.error("Error loading conversation detail:", e);
  }
}

function startNewConversation() {
  currentConversationId = null;
  localStorage.removeItem("active_conversation_id");
  messagesContainer.innerHTML = "";
  
  // Show starter prompt chips
  const promptsEl = document.getElementById("suggested-prompts");
  if (promptsEl) promptsEl.classList.remove("hidden");

  statCurrentTurns.textContent = "0";
  inspectorTotalTurns.textContent = "0";
  inspectorActiveTurns.textContent = "0";
  inspectorPrunedTurns.textContent = "0";
  inspectorEstTokens.textContent = "0";
  inspectorSummaryContent.textContent = "(No summary generated yet)";

  renderConversationList();
}

async function deleteConversation(convId) {
  try {
    await fetch(`/api/conversations/${convId}`, { method: "DELETE" });
    if (currentConversationId === convId) {
      startNewConversation();
    }
    loadConversations();
  } catch (e) {
    console.error("Error deleting conversation:", e);
  }
}

// Initial System Health & Status Check
async function checkHealth() {
  try {
    const res = await fetch("/api/health");
    if (!res.ok) return;
    const health = await res.json();

    document.getElementById("header-bot-name").textContent = health.bot_name;
    document.getElementById("header-bot-badge").textContent = health.bot_role.split("&")[0].trim();
    providerNameEl.textContent = `${health.provider.toUpperCase()} (${health.model})`;

    if (!health.has_valid_key) {
      apiStatusBanner.classList.remove("hidden");
    } else {
      apiStatusBanner.classList.add("hidden");
    }

    inspectorSystemPrompt.textContent = `Persona: ${health.bot_name} (${health.bot_role})\nFocus: Distributed Systems, High-Concurrency, Architecture Trade-offs, Robust Code Standards.`;

  } catch (e) {
    console.error("Health check error:", e);
  }
}

// Bootstrap
(async function init() {
  updateInspectorStrategyInfo(currentStrategy);
  await checkHealth();
  await loadConversations();
  if (currentConversationId) {
    selectConversation(currentConversationId);
  }
})();
