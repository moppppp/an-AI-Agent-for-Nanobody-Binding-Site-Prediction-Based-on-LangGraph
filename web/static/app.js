(function () {
  const ROUTE_LABELS = {
    retrieve_knowledge: "检索知识库",
    knowledge_base_rag: "知识库 RAG",
    direct_llm: "直接问答",
    nanokgat_predict: "结合位点预测",
    nanokgat_predict_visualization: "预测 + 可视化",
    repeat_query_cache: "重复问题缓存",
    domain_tools: "领域工具",
    domain_tools_disabled: "领域工具（未启用）",
  };

  const INTENT_LABELS = {
    definition: "定义",
    comparison: "对比",
    prediction: "预测",
    visualization: "可视化",
    domain_tools: "领域数据/计算",
    unknown: "未知",
  };

  const el = {
    shell: document.querySelector(".shell"),
    welcome: document.getElementById("welcome"),
    messageList: document.getElementById("messageList"),
    chatScroll: document.getElementById("chatScroll"),
    form: document.getElementById("chatForm"),
    input: document.getElementById("queryInput"),
    sendBtn: document.getElementById("sendBtn"),
    statusBadge: document.getElementById("statusBadge"),
    statusText: document.getElementById("statusText"),
    newChatBtn: document.getElementById("newChatBtn"),
    scrollBottomBtn: document.getElementById("scrollBottomBtn"),
    toggleInsight: document.getElementById("toggleInsight"),
    closeInsight: document.getElementById("closeInsight"),
    insightPanel: document.getElementById("insightPanel"),
    overlay: document.getElementById("overlay"),
    insightEmpty: document.getElementById("insightEmpty"),
    insightContent: document.getElementById("insightContent"),
    chatHistoryList: document.getElementById("chatHistoryList"),
  };

  const SESSION_KEY = "nanobody_session_id";
  const CHATS_KEY = "nanobody_chat_history";
  const MAX_CHATS = 40;
  let ready = false;
  let busy = false;
  let turnCount = 0;
  let chatMessages = [];
  let lastInsightData = null;

  function getSessionId() {
    var id = localStorage.getItem(SESSION_KEY);
    if (!id) {
      id =
        typeof crypto !== "undefined" && crypto.randomUUID
          ? crypto.randomUUID()
          : "s-" + Date.now() + "-" + Math.random().toString(16).slice(2);
      localStorage.setItem(SESSION_KEY, id);
    }
    return id;
  }

  function resetSessionId() {
    var id =
      typeof crypto !== "undefined" && crypto.randomUUID
        ? crypto.randomUUID()
        : "s-" + Date.now() + "-" + Math.random().toString(16).slice(2);
    localStorage.setItem(SESSION_KEY, id);
    return id;
  }

  var sessionId = getSessionId();
  var pdbId = null;
  var pdbStatus = document.getElementById("pdbStatus");

  function loadAllChats() {
    try {
      var raw = localStorage.getItem(CHATS_KEY);
      var list = raw ? JSON.parse(raw) : [];
      return Array.isArray(list) ? list : [];
    } catch (e) {
      return [];
    }
  }

  function saveAllChats(chats) {
    localStorage.setItem(CHATS_KEY, JSON.stringify(chats.slice(0, MAX_CHATS)));
  }

  function chatTitleFromMessages(msgs) {
    if (!msgs || !msgs.length) return "新对话";
    for (var i = 0; i < msgs.length; i++) {
      if (msgs[i].role === "user" && msgs[i].text) {
        var t = msgs[i].text.trim();
        return t.length > 28 ? t.slice(0, 28) + "…" : t;
      }
    }
    return "新对话";
  }

  function persistCurrentChat() {
    if (!sessionId) return;
    var chats = loadAllChats();
    var idx = -1;
    for (var i = 0; i < chats.length; i++) {
      if (chats[i].id === sessionId) {
        idx = i;
        break;
      }
    }
    var record = {
      id: sessionId,
      title: chatTitleFromMessages(chatMessages),
      updatedAt: Date.now(),
      messages: chatMessages.slice(),
      lastInsight: lastInsightData,
      pdbId: pdbId,
    };
    if (idx >= 0) {
      chats[idx] = record;
    } else if (chatMessages.length > 0) {
      chats.unshift(record);
    } else {
      return;
    }
    chats.sort(function (a, b) {
      return (b.updatedAt || 0) - (a.updatedAt || 0);
    });
    saveAllChats(chats);
    renderChatHistory();
  }

  function renderChatHistory() {
    if (!el.chatHistoryList) return;
    var chats = loadAllChats();
    el.chatHistoryList.innerHTML = "";
    if (!chats.length) {
      var empty = document.createElement("p");
      empty.className = "sidebar-note";
      empty.style.margin = "0 0.25rem";
      empty.textContent = "暂无历史，发送消息后会出现在这里";
      el.chatHistoryList.appendChild(empty);
      return;
    }
    chats.forEach(function (chat) {
      var wrap = document.createElement("div");
      wrap.style.display = "flex";
      wrap.style.alignItems = "center";
      wrap.style.gap = "0.25rem";

      var btn = document.createElement("button");
      btn.type = "button";
      btn.className =
        "chat-history-item" + (chat.id === sessionId ? " active" : "");
      var title = document.createElement("span");
      title.className = "chat-title";
      title.textContent = chat.title || "新对话";
      title.title = chat.title || "";
      btn.appendChild(title);
      btn.addEventListener("click", function () {
        switchToChat(chat.id);
      });

      var del = document.createElement("button");
      del.type = "button";
      del.className = "chat-del";
      del.textContent = "×";
      del.title = "从列表移除（服务端记忆仍保留）";
      del.addEventListener("click", function (ev) {
        ev.stopPropagation();
        deleteChatFromHistory(chat.id);
      });

      wrap.appendChild(btn);
      wrap.appendChild(del);
      el.chatHistoryList.appendChild(wrap);
    });
  }

  function deleteChatFromHistory(id) {
    var chats = loadAllChats().filter(function (c) {
      return c.id !== id;
    });
    saveAllChats(chats);
    if (id === sessionId) {
      startNewChat(true);
    } else {
      renderChatHistory();
    }
  }

  function renderMessagesFromSnapshot() {
    el.messageList.innerHTML = "";
    turnCount = 0;
    chatMessages.forEach(function (m) {
      if (m.role === "user") {
        turnCount++;
        var um = createMessageRow("user");
        um.bubble.innerHTML = "<p>" + escapeHtml(m.text) + "</p>";
        el.messageList.appendChild(um.row);
      } else if (m.role === "assistant") {
        turnCount++;
        var tag =
          m.meta && m.meta.route ? ROUTE_LABELS[m.meta.route] || m.meta.route : null;
        var am = createMessageRow("assistant", { tag: tag });
        am.bubble.innerHTML = formatMarkdown(m.text || "");
        el.messageList.appendChild(am.row);
      }
    });
    hideWelcome();
    scrollToBottom(false);
  }

  function resetInsightPanel() {
    el.insightContent.classList.add("hidden");
    el.insightEmpty.classList.remove("hidden");
    el.shell.classList.remove("has-insight");
    lastInsightData = null;
  }

  function switchToChat(id) {
    if (!id || (id === sessionId && chatMessages.length)) return;
    if (busy) return;
    persistCurrentChat();
    var chats = loadAllChats();
    var chat = null;
    for (var i = 0; i < chats.length; i++) {
      if (chats[i].id === id) {
        chat = chats[i];
        break;
      }
    }
    if (!chat) return;
    sessionId = chat.id;
    localStorage.setItem(SESSION_KEY, sessionId);
    chatMessages = (chat.messages || []).slice();
    pdbId = chat.pdbId || null;
    if (pdbStatus) {
      pdbStatus.textContent = pdbId ? "已绑定 PDB" : "";
    }
    renderMessagesFromSnapshot();
    if (chat.lastInsight) {
      lastInsightData = chat.lastInsight;
      updateInsight(chat.lastInsight);
    } else {
      resetInsightPanel();
    }
    renderChatHistory();
    el.input.focus();
  }

  function startNewChat(skipPersist) {
    if (!skipPersist) persistCurrentChat();
    sessionId = resetSessionId();
    chatMessages = [];
    pdbId = null;
    lastInsightData = null;
    if (pdbStatus) pdbStatus.textContent = "";
    var pdbFileEl = document.getElementById("pdbFile");
    if (pdbFileEl) pdbFileEl.value = "";
    el.messageList.innerHTML = "";
    turnCount = 0;
    hideWelcome();
    resetInsightPanel();
    renderChatHistory();
    el.input.focus();
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function formatMarkdown(text) {
    let html = escapeHtml(text);
    html = html.replace(/```([\s\S]*?)```/g, function (_, code) {
      return "<pre><code>" + code.trim() + "</code></pre>";
    });
    html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
    html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    html = html.replace(/\n/g, "<br>");
    html = html.replace(/(<br>){3,}/g, "<br><br>");
    html = html.replace(/\[(\d+)\]/g, '<a href="#cite-$1" class="citation-ref">[$1]</a>');
    return html;
  }

  function nowTime() {
    return new Date().toLocaleTimeString("zh-CN", {
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  function hideWelcome() {
    if (turnCount > 0) el.welcome.classList.add("hidden");
    else el.welcome.classList.remove("hidden");
  }

  function scrollToBottom(smooth) {
    el.chatScroll.scrollTo({
      top: el.chatScroll.scrollHeight,
      behavior: smooth ? "smooth" : "auto",
    });
  }

  function createMessageRow(role, options) {
    options = options || {};
    const row = document.createElement("div");
    row.className = "msg-row " + role + (options.extraClass ? " " + options.extraClass : "");

    const avatar = document.createElement("div");
    avatar.className = "msg-avatar";
    avatar.textContent = role === "user" ? "你" : "AI";

    const content = document.createElement("div");
    content.className = "msg-content";

    const meta = document.createElement("div");
    meta.className = "msg-meta";
    const name = document.createElement("span");
    name.className = "msg-name";
    name.textContent = role === "user" ? "你" : "纳米抗体助手";
    const time = document.createElement("span");
    time.textContent = nowTime();
    meta.appendChild(name);
    if (options.tag) {
      const tag = document.createElement("span");
      tag.className = "msg-tag";
      tag.textContent = options.tag;
      meta.appendChild(tag);
    }
    meta.appendChild(time);

    const bubble = document.createElement("div");
    bubble.className = "msg-bubble";

    content.appendChild(meta);
    content.appendChild(bubble);

    if (role === "assistant" && !options.loading) {
      const actions = document.createElement("div");
      actions.className = "msg-actions";
      const copyBtn = document.createElement("button");
      copyBtn.type = "button";
      copyBtn.className = "msg-action-btn";
      copyBtn.textContent = "复制";
      copyBtn.addEventListener("click", function () {
        const t = bubble.innerText || "";
        navigator.clipboard.writeText(t).then(function () {
          copyBtn.textContent = "已复制";
          setTimeout(function () { copyBtn.textContent = "复制"; }, 1500);
        });
      });
      actions.appendChild(copyBtn);
      content.appendChild(actions);
    }

    row.appendChild(avatar);
    row.appendChild(content);
    return { row: row, bubble: bubble, meta: meta };
  }

  function appendUserMessage(text) {
    turnCount++;
    hideWelcome();
    chatMessages.push({ role: "user", text: text, ts: Date.now() });
    persistCurrentChat();
    const m = createMessageRow("user");
    m.bubble.innerHTML = "<p>" + escapeHtml(text) + "</p>";
    el.messageList.appendChild(m.row);
    scrollToBottom(true);
    return m.row;
  }

  function appendTypingIndicator() {
    const m = createMessageRow("assistant", { loading: true, extraClass: "msg-loading" });
    m.bubble.innerHTML =
      '<span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span>';
    el.messageList.appendChild(m.row);
    scrollToBottom(true);
    return m.row;
  }

  function appendAssistantMessage(text, meta) {
    meta = meta || null;
    chatMessages.push({ role: "assistant", text: text, meta: meta, ts: Date.now() });
    persistCurrentChat();
    const tag = meta && meta.route ? ROUTE_LABELS[meta.route] || meta.route : null;
    const m = createMessageRow("assistant", { tag: tag });
    m.bubble.innerHTML = formatMarkdown(text);
    el.messageList.appendChild(m.row);
    scrollToBottom(true);
    return m.row;
  }

  function appendErrorMessage(text) {
    chatMessages.push({ role: "assistant", text: text, meta: { route: "error" }, ts: Date.now() });
    persistCurrentChat();
    const m = createMessageRow("assistant", { extraClass: "msg-error" });
    m.bubble.innerHTML = "<p>" + escapeHtml(text) + "</p>";
    el.messageList.appendChild(m.row);
    scrollToBottom(true);
  }

  function setStatus(state, text) {
    el.statusBadge.className = "status-pill status-" + state;
    el.statusText.textContent = text;
  }

  function pollHealth() {
    fetch("/api/health")
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.error) {
          setStatus("error", "加载失败");
          el.sendBtn.disabled = true;
          return;
        }
        if (data.ready) {
          ready = true;
          setStatus("ready", "就绪，可以对话");
          el.sendBtn.disabled = false;
          return;
        }
        if (data.loading) {
          setStatus("loading", data.hint || "正在加载知识库…");
        }
        setTimeout(pollHealth, 2000);
      })
      .catch(function () {
        setStatus("error", "无法连接服务");
        setTimeout(pollHealth, 3000);
      });
  }

  function updateInsight(data) {
    lastInsightData = data;
    persistCurrentChat();
    el.insightEmpty.classList.add("hidden");
    el.insightContent.classList.remove("hidden");

    var routeLabel = ROUTE_LABELS[data.route] || data.route || "—";
    if (data.cache_hit) {
      routeLabel += "（Redis 缓存命中）";
    }
    document.getElementById("metaRoute").textContent = routeLabel;
    document.getElementById("metaIntent").textContent =
      INTENT_LABELS[data.intent] || data.intent || "—";

    var rel = typeof data.relevance === "number" ? data.relevance : 0;
    document.getElementById("metaRelevance").textContent = rel.toFixed(3);
    document.getElementById("relevanceBar").style.width = Math.min(100, rel * 100) + "%";

    var memTurns = typeof data.memory_turns === "number" ? data.memory_turns : 0;
    var repeatN = typeof data.repeat_count === "number" ? data.repeat_count : 0;
    var repeatTotal = typeof data.repeat_total === "number" ? data.repeat_total : 0;
    var memLabel =
      memTurns +
      " 轮" +
      (data.memory_has_summary ? " · 含历史摘要" : "") +
      (repeatTotal >= 2
        ? " · 相同问题累计 " + repeatTotal + " 次" +
          (repeatN > 1 ? "（连续 " + repeatN + "）" : "（含间断）")
        : repeatN > 0
          ? " · 连续相同 " + repeatN + " 次"
          : "");
    document.getElementById("metaMemory").textContent = memLabel;

    var memoryBlock = document.getElementById("memoryBlock");
    var summaryEl = document.getElementById("memorySummary");
    var contextEl = document.getElementById("memoryContext");
    var memoryMeta = document.getElementById("memoryMeta");
    var hasMem =
      (data.memory_summary && data.memory_summary.length) ||
      (data.memory_context_preview && data.memory_context_preview.length) ||
      memTurns > 0;
    if (hasMem) {
      memoryBlock.classList.remove("hidden");
      memoryMeta.textContent =
        memLabel + (data.session_id ? " · 会话 " + data.session_id.slice(0, 8) + "…" : "");
      summaryEl.textContent =
        data.memory_summary && data.memory_summary.length
          ? data.memory_summary
          : "（尚未生成摘要；继续对话超过窗口轮数后会出现）";
      contextEl.textContent =
        data.memory_context_preview && data.memory_context_preview.length
          ? data.memory_context_preview
          : "（本轮无历史上下文，这是会话的第一条消息）";
    } else {
      memoryBlock.classList.add("hidden");
    }

    var citeBlock = document.getElementById("citationBlock");
    var citeList = document.getElementById("citationList");
    citeList.innerHTML = "";
    if (data.citations && data.citations.length) {
      citeBlock.classList.remove("hidden");
      data.citations.forEach(function (c) {
        var div = document.createElement("div");
        div.className = "snippet-item";
        div.id = "cite-" + c.id;
        div.textContent = "[" + c.id + "] " + (c.preview || c.text || "");
        citeList.appendChild(div);
      });
    } else {
      citeBlock.classList.add("hidden");
    }

    var snippetBlock = document.getElementById("snippetBlock");
    var snippetList = document.getElementById("snippetList");
    snippetList.innerHTML = "";
    if (data.snippets && data.snippets.length) {
      snippetBlock.classList.remove("hidden");
      data.snippets.forEach(function (s, i) {
        var div = document.createElement("div");
        div.className = "snippet-item";
        div.textContent = (i + 1) + ". " + (s.length > 280 ? s.slice(0, 280) + "…" : s);
        snippetList.appendChild(div);
      });
    } else {
      snippetBlock.classList.add("hidden");
    }

    var toolBlock = document.getElementById("toolBlock");
    if (data.tool_results && data.tool_results.length) {
      toolBlock.classList.remove("hidden");
      document.getElementById("toolResultsJson").textContent = JSON.stringify(
        data.tool_results,
        null,
        2
      );
    } else {
      toolBlock.classList.add("hidden");
    }

    var predBlock = document.getElementById("predictionBlock");
    if (data.prediction && Object.keys(data.prediction).length) {
      predBlock.classList.remove("hidden");
      document.getElementById("predictionJson").textContent = JSON.stringify(
        data.prediction, null, 2
      );
    } else {
      predBlock.classList.add("hidden");
    }

    var pymol = document.getElementById("pymolLink");
    if (data.pymol_link) {
      pymol.href = data.pymol_link;
      pymol.classList.remove("hidden");
    } else {
      pymol.classList.add("hidden");
    }

    if (window.innerWidth >= 961) {
      el.shell.classList.add("has-insight");
    }
  }

  function openInsightMobile() {
    el.insightPanel.classList.add("open");
    el.overlay.classList.remove("hidden");
    el.overlay.classList.add("visible");
    el.overlay.setAttribute("aria-hidden", "false");
  }

  function closeInsightMobile() {
    el.insightPanel.classList.remove("open");
    el.overlay.classList.add("hidden");
    el.overlay.classList.remove("visible");
    el.overlay.setAttribute("aria-hidden", "true");
  }

  function sendQuery(q) {
    if (!ready || busy || !q.trim()) return;
    busy = true;
    el.sendBtn.disabled = true;

    appendUserMessage(q.trim());
    var loadingRow = appendTypingIndicator();

    fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query: q.trim(),
        session_id: sessionId,
        pdb_id: pdbId,
      }),
    })
      .then(function (res) {
        return res.json().then(function (data) {
          return { ok: res.ok, data: data };
        });
      })
      .then(function (r) {
        loadingRow.remove();
        if (!r.ok) {
          var detail = typeof r.data.detail === "string" ? r.data.detail : "请求失败";
          appendErrorMessage(detail);
          return;
        }
        if (r.data.session_id) {
          sessionId = r.data.session_id;
          localStorage.setItem(SESSION_KEY, sessionId);
        }
        appendAssistantMessage(r.data.answer || "(无回答)", r.data);
        updateInsight(r.data);
      })
      .catch(function (e) {
        loadingRow.remove();
        appendErrorMessage(String(e));
      })
      .finally(function () {
        busy = false;
        el.sendBtn.disabled = !ready;
        el.input.focus();
      });
  }

  function clearChat() {
    startNewChat(false);
  }

  function restoreSessionOnLoad() {
    var chats = loadAllChats();
    var found = null;
    for (var i = 0; i < chats.length; i++) {
      if (chats[i].id === sessionId) {
        found = chats[i];
        break;
      }
    }
    if (found && found.messages && found.messages.length) {
      chatMessages = found.messages.slice();
      pdbId = found.pdbId || null;
      renderMessagesFromSnapshot();
      if (found.lastInsight) {
        lastInsightData = found.lastInsight;
        updateInsight(found.lastInsight);
      }
    }
    renderChatHistory();
  }

  function bindQuickAsk(selector) {
    document.querySelectorAll(selector).forEach(function (btn) {
      btn.addEventListener("click", function () {
        var q = btn.getAttribute("data-q");
        if (!q) return;
        el.input.value = q;
        if (ready && !busy) sendQuery(q);
        else el.input.focus();
      });
    });
  }

  el.form.addEventListener("submit", function (e) {
    e.preventDefault();
    var q = el.input.value;
    el.input.value = "";
    autoResizeInput();
    sendQuery(q);
  });

  el.input.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      el.form.requestSubmit();
    }
  });

  function autoResizeInput() {
    el.input.style.height = "auto";
    el.input.style.height = Math.min(el.input.scrollHeight, 160) + "px";
  }
  el.input.addEventListener("input", autoResizeInput);

  el.newChatBtn.addEventListener("click", clearChat);

  el.chatScroll.addEventListener("scroll", function () {
    var nearBottom =
      el.chatScroll.scrollHeight - el.chatScroll.scrollTop - el.chatScroll.clientHeight < 80;
    el.scrollBottomBtn.classList.toggle("hidden", nearBottom);
  });

  el.scrollBottomBtn.addEventListener("click", function () {
    scrollToBottom(true);
  });

  el.toggleInsight.addEventListener("click", function () {
    if (window.innerWidth < 961) openInsightMobile();
    else {
      el.shell.classList.toggle("has-insight");
      el.toggleInsight.setAttribute(
        "aria-expanded",
        el.shell.classList.contains("has-insight")
      );
    }
  });

  el.closeInsight.addEventListener("click", closeInsightMobile);
  el.overlay.addEventListener("click", closeInsightMobile);

  bindQuickAsk(".nav-item, .chip");

  var pdbFile = document.getElementById("pdbFile");
  restoreSessionOnLoad();
  if (pdbFile) {
    pdbFile.addEventListener("change", function () {
      var f = pdbFile.files && pdbFile.files[0];
      if (!f) return;
      var fd = new FormData();
      fd.append("file", f);
      pdbStatus.textContent = "上传中…";
      fetch("/api/upload/pdb", { method: "POST", body: fd })
        .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
        .then(function (r) {
          if (!r.ok) {
            pdbStatus.textContent = "上传失败";
            pdbId = null;
            return;
          }
          pdbId = r.d.pdb_id;
          pdbStatus.textContent = "已绑定 PDB (" + r.d.residue_count + " 残基)";
        })
        .catch(function () {
          pdbStatus.textContent = "上传失败";
          pdbId = null;
        });
    });
  }

  pollHealth();
  autoResizeInput();
})();
