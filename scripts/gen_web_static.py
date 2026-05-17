# -*- coding: utf-8 -*-
"""Generate web/static assets (UTF-8)."""
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "web" / "static"

INDEX_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>纳米抗体智能体</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600;1,9..40,400&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet" />
  <link rel="stylesheet" href="/static/app.css" />
</head>
<body>
  <div class="shell">
    <aside class="sidebar">
      <div class="sidebar-top">
        <div class="brand">
          <span class="brand-icon">Nb</span>
          <span class="brand-text">纳米抗体智能体</span>
        </div>
        <button type="button" id="newChatBtn" class="btn btn-primary btn-block" title="新建对话（保留历史，可切换回来）">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 5v14M5 12h14"/></svg>
          新对话
        </button>
      </div>
      <nav class="sidebar-chats" aria-label="对话历史">
        <p class="nav-label">历史对话</p>
        <div id="chatHistoryList" class="chat-history-list"></div>
      </nav>
      <nav class="sidebar-nav" aria-label="示例问题">
        <p class="nav-label">试试这些问题</p>
        <button type="button" class="nav-item" data-q="什么是纳米抗体？">什么是纳米抗体？</button>
        <button type="button" class="nav-item" data-q="纳米抗体与传统抗体相比有什么优势？">与传统抗体对比</button>
        <button type="button" class="nav-item" data-q="请预测该纳米抗体的结合位点">结合位点预测</button>
      </nav>
      <div class="sidebar-footer">
        <div id="statusBadge" class="status-pill status-loading">
          <span class="status-dot"></span>
          <span id="statusText">正在加载模型…</span>
        </div>
        <p class="sidebar-note">知识库 RAG · NanoKGAT · LangGraph</p>
      </div>
    </aside>

    <main class="chat-main">
      <header class="chat-header">
        <h1>对话</h1>
        <button type="button" id="toggleInsight" class="btn btn-ghost" aria-expanded="false">推理详情</button>
      </header>

      <div class="chat-body">
        <div id="chatScroll" class="chat-scroll">
          <div id="welcome" class="welcome-card">
            <div class="welcome-icon">🧬</div>
            <h2>开始一段对话</h2>
            <p>我可以基于知识库回答纳米抗体相关问题，或调用 NanoKGAT 预测结合位点。</p>
            <div class="welcome-chips">
              <button type="button" class="chip" data-q="什么是纳米抗体？">纳米抗体简介</button>
              <button type="button" class="chip" data-q="图神经网络在抗体结合位点预测中的应用">GNN 与结合位点</button>
              <button type="button" class="chip" data-q="请预测该纳米抗体的结合位点">预测结合位点</button>
            </div>
          </div>
          <div id="messageList" class="message-list" role="log" aria-live="polite"></div>
        </div>
        <button type="button" id="scrollBottomBtn" class="scroll-bottom hidden" aria-label="回到底部">↓</button>
      </div>

      <footer class="composer-wrap">
        <form id="chatForm" class="composer">
          <div class="composer-inner">
            <textarea
              id="queryInput"
              rows="1"
              placeholder="输入消息… Enter 发送，Shift+Enter 换行"
              maxlength="8000"
              autocomplete="off"
            ></textarea>
            <button type="submit" id="sendBtn" class="send-btn" disabled aria-label="发送">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M3.4 20.4 20.8 12 3.4 3.6l-.8 7.2 9.2 1.2-9.2 1.2.8 7.2z"/></svg>
            </button>
          </div>
          <div class="composer-tools">
            <label class="pdb-upload-label">
              <input type="file" id="pdbFile" accept=".pdb" hidden />
              上传 PDB
            </label>
            <span id="pdbStatus" class="pdb-status"></span>
          </div>
          <p class="composer-hint">支持多轮记忆 · 混合检索 · PDB 上传预测 · Redis 重复问缓存</p>
        </form>
      </footer>
    </main>

    <aside id="insightPanel" class="insight-panel" aria-label="推理详情">
      <header class="insight-header">
        <h2>推理详情</h2>
        <button type="button" id="closeInsight" class="btn btn-ghost btn-sm" aria-label="关闭">×</button>
      </header>
      <div class="insight-body">
        <p id="insightEmpty" class="insight-empty">发送消息后，将显示本次请求的路由与检索信息。</p>
        <div id="insightContent" class="insight-content hidden">
          <div class="insight-cards">
            <div class="insight-card">
              <span class="insight-label">路由</span>
              <span id="metaRoute" class="insight-value">—</span>
            </div>
            <div class="insight-card">
              <span class="insight-label">意图</span>
              <span id="metaIntent" class="insight-value">—</span>
            </div>
            <div class="insight-card">
              <span class="insight-label">相关度</span>
              <div class="relevance-bar-wrap">
                <div id="relevanceBar" class="relevance-bar" style="width:0%"></div>
              </div>
              <span id="metaRelevance" class="insight-value mono">0.000</span>
            </div>
            <div class="insight-card">
              <span class="insight-label">对话记忆</span>
              <span id="metaMemory" class="insight-value">—</span>
            </div>
          </div>
          <section id="memoryBlock" class="insight-section hidden">
            <h3>对话记忆</h3>
            <p id="memoryMeta" class="memory-meta">—</p>
            <h4 class="memory-subhead">历史摘要</h4>
            <pre id="memorySummary" class="code-block memory-text">（暂无）</pre>
            <h4 class="memory-subhead">送入模型的上下文预览</h4>
            <pre id="memoryContext" class="code-block memory-text">（暂无）</pre>
          </section>
          <section id="citationBlock" class="insight-section hidden">
            <h3>引用来源</h3>
            <div id="citationList" class="snippet-list"></div>
          </section>
          <section id="snippetBlock" class="insight-section hidden">
            <h3>检索片段</h3>
            <div id="snippetList" class="snippet-list"></div>
          </section>
          <section id="predictionBlock" class="insight-section hidden">
            <h3>预测结果</h3>
            <pre id="predictionJson" class="code-block"></pre>
          </section>
          <a id="pymolLink" class="pymol-link hidden" href="#" target="_blank" rel="noopener noreferrer">在 PyMOL 中查看结构 →</a>
        </div>
      </div>
    </aside>
  </div>

  <div id="overlay" class="overlay hidden" aria-hidden="true"></div>
  <script src="/static/app.js"></script>
</body>
</html>
"""

APP_CSS = """
:root {
  --bg: #0a0e14;
  --bg-elevated: #121820;
  --bg-hover: #1a222d;
  --border: #2a3544;
  --text: #e6edf5;
  --text-muted: #8b9cb3;
  --accent: #5eead4;
  --accent-soft: rgba(94, 234, 212, 0.12);
  --user: #2563eb;
  --user-bg: #1e3a5f;
  --assistant-bg: #161d28;
  --danger: #f87171;
  --radius: 14px;
  --radius-sm: 10px;
  --sidebar-w: 260px;
  --insight-w: 320px;
  --font: "DM Sans", "Segoe UI", system-ui, sans-serif;
  --mono: "JetBrains Mono", Consolas, monospace;
  --shadow: 0 8px 32px rgba(0, 0, 0, 0.35);
}

*, *::before, *::after { box-sizing: border-box; }

html, body {
  margin: 0;
  height: 100%;
  overflow: hidden;
  font-family: var(--font);
  background: var(--bg);
  color: var(--text);
  -webkit-font-smoothing: antialiased;
}

.shell {
  display: grid;
  grid-template-columns: var(--sidebar-w) 1fr;
  height: 100dvh;
  max-height: 100dvh;
  overflow: hidden;
  min-height: 0;
}

.shell > .sidebar,
.shell > .chat-main,
.shell > .insight-panel {
  min-height: 0;
  min-width: 0;
}

@media (max-width: 960px) {
  .shell {
    grid-template-columns: 1fr;
  }
  .sidebar { display: none; }
  .insight-panel {
    position: fixed;
    right: 0;
    top: 0;
    bottom: 0;
    z-index: 100;
    transform: translateX(100%);
    transition: transform 0.25s ease;
    box-shadow: var(--shadow);
  }
  .insight-panel.open { transform: translateX(0); }
  .overlay.visible {
    display: block;
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,0.5);
    z-index: 90;
  }
}

/* Sidebar */
.sidebar {
  display: flex;
  flex-direction: column;
  background: var(--bg-elevated);
  border-right: 1px solid var(--border);
  padding: 1rem;
}

.brand {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  margin-bottom: 1rem;
}

.brand-icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: linear-gradient(135deg, #2dd4bf, #0d9488);
  color: #042f2e;
  font-weight: 700;
  font-size: 0.85rem;
  display: flex;
  align-items: center;
  justify-content: center;
}

.brand-text {
  font-weight: 600;
  font-size: 0.95rem;
}

.btn {
  font: inherit;
  cursor: pointer;
  border: none;
  border-radius: var(--radius-sm);
  transition: background 0.15s, opacity 0.15s;
}

.btn-block { width: 100%; }

.btn-primary {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 0.65rem 1rem;
  background: var(--accent-soft);
  color: var(--accent);
  border: 1px solid rgba(94, 234, 212, 0.25);
}

.btn-primary:hover { background: rgba(94, 234, 212, 0.2); }

.btn-ghost {
  background: transparent;
  color: var(--text-muted);
  padding: 0.4rem 0.65rem;
}

.btn-ghost:hover { background: var(--bg-hover); color: var(--text); }

.btn-sm { font-size: 1.25rem; line-height: 1; padding: 0.2rem 0.5rem; }

.sidebar-chats {
  flex: 0 0 auto;
  max-height: 38vh;
  overflow-y: auto;
  margin-bottom: 0.75rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid var(--border);
}

.chat-history-list {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.chat-history-item {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  width: 100%;
  text-align: left;
  padding: 0.45rem 0.5rem;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--text);
  cursor: pointer;
  font-size: 0.82rem;
}

.chat-history-item:hover {
  background: var(--surface-2);
}

.chat-history-item.active {
  background: rgba(56, 189, 248, 0.15);
  color: var(--accent);
}

.chat-history-item .chat-title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chat-history-item .chat-del {
  flex: 0 0 auto;
  border: none;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 0.75rem;
  padding: 0 0.2rem;
}

.chat-history-item .chat-del:hover {
  color: #f87171;
}

.sidebar-nav { flex: 1; overflow-y: auto; min-height: 0; }

.nav-label {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-muted);
  margin: 0 0 0.5rem;
}

.nav-item {
  display: block;
  width: 100%;
  text-align: left;
  padding: 0.55rem 0.65rem;
  margin-bottom: 0.25rem;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--text);
  font: inherit;
  font-size: 0.85rem;
  cursor: pointer;
}

.nav-item:hover { background: var(--bg-hover); }

.sidebar-footer { margin-top: auto; padding-top: 1rem; }

.status-pill {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.8rem;
  padding: 0.45rem 0.65rem;
  border-radius: 999px;
  background: var(--bg-hover);
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #eab308;
  animation: pulse 1.5s ease infinite;
}

.status-ready .status-dot { background: var(--accent); animation: none; }
.status-error .status-dot { background: var(--danger); animation: none; }

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.sidebar-note {
  font-size: 0.72rem;
  color: var(--text-muted);
  margin: 0.5rem 0 0;
}

/* Chat main */
.chat-main {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  height: 100%;
  max-height: 100dvh;
  overflow: hidden;
  background: var(--bg);
}

.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.85rem 1.25rem;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.chat-header h1 {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
}

.chat-body {
  flex: 1 1 auto;
  position: relative;
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.chat-scroll {
  flex: 1 1 auto;
  min-height: 0;
  overflow-x: hidden;
  overflow-y: auto;
  overscroll-behavior: contain;
  -webkit-overflow-scrolling: touch;
  padding: 1.25rem;
  scroll-behavior: smooth;
}

.welcome-card {
  max-width: 520px;
  margin: 2rem auto 3rem;
  text-align: center;
  padding: 2rem 1.5rem;
}

.welcome-card.hidden { display: none; }

.welcome-icon { font-size: 2.5rem; margin-bottom: 0.75rem; }

.welcome-card h2 {
  margin: 0 0 0.5rem;
  font-size: 1.35rem;
}

.welcome-card p {
  color: var(--text-muted);
  margin: 0 0 1.25rem;
  font-size: 0.95rem;
}

.welcome-chips, .chip {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  justify-content: center;
}

.chip {
  font: inherit;
  font-size: 0.82rem;
  padding: 0.45rem 0.85rem;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: var(--bg-elevated);
  color: var(--text);
  cursor: pointer;
}

.chip:hover {
  border-color: var(--accent);
  color: var(--accent);
}

.message-list {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  max-width: 780px;
  margin: 0 auto;
  width: 100%;
}

.msg-row {
  display: flex;
  gap: 0.75rem;
  align-items: flex-start;
}

.msg-row.user { flex-direction: row-reverse; }

.msg-avatar {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.75rem;
  font-weight: 600;
}

.msg-row.user .msg-avatar {
  background: var(--user);
  color: #fff;
}

.msg-row.assistant .msg-avatar {
  background: var(--accent-soft);
  color: var(--accent);
  border: 1px solid rgba(94, 234, 212, 0.3);
}

.msg-content { flex: 1; min-width: 0; max-width: 85%; }

.msg-row.user .msg-content { display: flex; flex-direction: column; align-items: flex-end; }

.msg-meta {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.35rem;
  font-size: 0.75rem;
  color: var(--text-muted);
}

.msg-row.user .msg-meta { flex-direction: row-reverse; }

.msg-name { font-weight: 500; color: var(--text); }

.msg-tag {
  font-size: 0.68rem;
  padding: 0.15rem 0.45rem;
  border-radius: 4px;
  background: var(--accent-soft);
  color: var(--accent);
}

.msg-bubble {
  padding: 0.85rem 1rem;
  border-radius: var(--radius);
  font-size: 0.95rem;
  line-height: 1.6;
  word-break: break-word;
}

.msg-row.user .msg-bubble {
  background: var(--user-bg);
  border: 1px solid #2d4f7a;
  border-bottom-right-radius: 4px;
}

.msg-row.assistant .msg-bubble {
  background: var(--assistant-bg);
  border: 1px solid var(--border);
  border-bottom-left-radius: 4px;
}

.msg-bubble p { margin: 0 0 0.65rem; }
.msg-bubble p:last-child { margin-bottom: 0; }
.msg-bubble ul, .msg-bubble ol { margin: 0.5rem 0; padding-left: 1.25rem; }
.msg-bubble code {
  font-family: var(--mono);
  font-size: 0.85em;
  background: rgba(0,0,0,0.3);
  padding: 0.15em 0.35em;
  border-radius: 4px;
}
.msg-bubble pre {
  margin: 0.5rem 0;
  padding: 0.75rem;
  background: #0d1117;
  border-radius: 8px;
  overflow-x: auto;
  font-family: var(--mono);
  font-size: 0.8rem;
}

.msg-actions {
  display: flex;
  gap: 0.35rem;
  margin-top: 0.4rem;
}

.msg-row.user .msg-actions { justify-content: flex-end; }

.msg-action-btn {
  font: inherit;
  font-size: 0.72rem;
  padding: 0.2rem 0.5rem;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
}

.msg-action-btn:hover { color: var(--accent); background: var(--bg-hover); }

.msg-error .msg-bubble {
  border-color: var(--danger);
  color: #fecaca;
}

.msg-loading .msg-bubble {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  color: var(--text-muted);
}

.typing-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--text-muted);
  animation: typing 1.2s ease infinite;
}
.typing-dot:nth-child(2) { animation-delay: 0.15s; }
.typing-dot:nth-child(3) { animation-delay: 0.3s; }

@keyframes typing {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
  30% { transform: translateY(-4px); opacity: 1; }
}

.scroll-bottom {
  position: absolute;
  bottom: 1rem;
  left: 50%;
  transform: translateX(-50%);
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: 1px solid var(--border);
  background: var(--bg-elevated);
  color: var(--text);
  cursor: pointer;
  box-shadow: var(--shadow);
}
.scroll-bottom:hover { border-color: var(--accent); color: var(--accent); }
.scroll-bottom.hidden { display: none; }

.composer-wrap {
  flex: 0 0 auto;
  flex-shrink: 0;
  padding: 0.75rem 1.25rem 1rem;
  border-top: 1px solid var(--border);
  background: var(--bg-elevated);
}

.composer-inner {
  display: flex;
  align-items: flex-end;
  gap: 0.5rem;
  max-width: 780px;
  margin: 0 auto;
  padding: 0.5rem 0.5rem 0.5rem 1rem;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius);
}

.composer-inner:focus-within {
  border-color: rgba(94, 234, 212, 0.5);
  box-shadow: 0 0 0 2px var(--accent-soft);
}

.composer textarea {
  flex: 1;
  border: none;
  background: transparent;
  color: var(--text);
  font: inherit;
  font-size: 0.95rem;
  resize: none;
  max-height: 160px;
  line-height: 1.5;
  padding: 0.35rem 0;
}

.composer textarea:focus { outline: none; }

.send-btn {
  flex-shrink: 0;
  width: 40px;
  height: 40px;
  border: none;
  border-radius: 10px;
  background: var(--accent);
  color: #042f2e;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.send-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.send-btn:not(:disabled):hover {
  filter: brightness(1.08);
}

.composer-hint {
  max-width: 780px;
  margin: 0.4rem auto 0;
  font-size: 0.72rem;
  color: var(--text-muted);
  text-align: center;
}

/* Insight panel */
.shell.has-insight {
  grid-template-columns: var(--sidebar-w) 1fr var(--insight-w);
}

@media (min-width: 961px) {
  .insight-panel {
    border-left: 1px solid var(--border);
    background: var(--bg-elevated);
    display: flex;
    flex-direction: column;
    overflow: hidden;
    min-height: 0;
    max-height: 100dvh;
  }
}

.insight-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem;
  border-bottom: 1px solid var(--border);
}

.insight-header h2 {
  margin: 0;
  font-size: 0.9rem;
}

.insight-body {
  flex: 1 1 auto;
  min-height: 0;
  overflow-x: hidden;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  padding: 1rem;
}

.insight-empty {
  color: var(--text-muted);
  font-size: 0.85rem;
  margin: 0;
}

.insight-content.hidden { display: none; }

.insight-cards {
  display: grid;
  gap: 0.65rem;
  margin-bottom: 1rem;
}

.insight-card {
  padding: 0.65rem 0.75rem;
  background: var(--bg);
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
}

.insight-label {
  display: block;
  font-size: 0.7rem;
  color: var(--text-muted);
  margin-bottom: 0.25rem;
}

.insight-value {
  font-size: 0.85rem;
  font-weight: 500;
}

.insight-value.mono {
  font-family: var(--mono);
  font-size: 0.8rem;
}

.relevance-bar-wrap {
  height: 4px;
  background: var(--bg-hover);
  border-radius: 2px;
  margin: 0.35rem 0;
  overflow: hidden;
}

.relevance-bar {
  height: 100%;
  background: var(--accent);
  border-radius: 2px;
  transition: width 0.4s ease;
}

.insight-section {
  margin-top: 1rem;
}

.insight-section h3 {
  margin: 0 0 0.5rem;
  font-size: 0.8rem;
  color: var(--text-muted);
}

.snippet-item {
  padding: 0.65rem;
  margin-bottom: 0.5rem;
  background: var(--bg);
  border-radius: 8px;
  border: 1px solid var(--border);
  font-size: 0.78rem;
  color: var(--text-muted);
  line-height: 1.45;
}

.code-block {
  margin: 0;
  padding: 0.75rem;
  background: #0d1117;
  border-radius: 8px;
  font-family: var(--mono);
  font-size: 0.72rem;
  overflow-x: auto;
  white-space: pre-wrap;
}

.pymol-link {
  display: inline-block;
  margin-top: 0.75rem;
  color: var(--accent);
  font-size: 0.85rem;
  text-decoration: none;
}

.pymol-link:hover { text-decoration: underline; }

.overlay.hidden { display: none; }

.hidden { display: none !important; }

.composer-tools {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-top: 0.5rem;
  font-size: 0.8rem;
}

.pdb-upload-label {
  cursor: pointer;
  color: var(--accent);
  border: 1px dashed var(--border);
  padding: 0.25rem 0.6rem;
  border-radius: 6px;
}

.pdb-status { color: var(--text-muted); }

.citation-ref {
  color: var(--accent);
  font-weight: 600;
  cursor: pointer;
  text-decoration: none;
}

.citation-ref:hover { text-decoration: underline; }

.memory-meta {
  margin: 0 0 0.5rem;
  font-size: 0.8rem;
  color: var(--text-muted);
}

.memory-subhead {
  margin: 0.75rem 0 0.35rem;
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--text-muted);
}

.memory-text {
  max-height: 200px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-word;
}
"""

APP_JS = r"""
(function () {
  const ROUTE_LABELS = {
    retrieve_knowledge: "检索知识库",
    knowledge_base_rag: "知识库 RAG",
    direct_llm: "直接问答",
    nanokgat_predict: "结合位点预测",
    nanokgat_predict_visualization: "预测 + 可视化",
    repeat_query_cache: "重复问题缓存",
  };

  const INTENT_LABELS = {
    definition: "定义",
    comparison: "对比",
    prediction: "预测",
    visualization: "可视化",
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
"""


def _fix_motion_tags(text: str) -> str:
    """Replace accidental <motion> typos with <div>."""
    text = text.replace("<motion ", "<div ")
    text = text.replace("</motion>", "</div>")
    text = text.replace("🧬</motion>", "🧬</div>")
    return text


def _write_utf8(path: Path, content: str) -> None:
    path.write_bytes(content.encode("utf-8"))


def main() -> None:
    STATIC.mkdir(parents=True, exist_ok=True)
    html = _fix_motion_tags(INDEX_HTML)
    css = APP_CSS.strip() + "\n"
    js = _fix_motion_tags(APP_JS.strip()) + "\n"
    _write_utf8(STATIC / "index.html", html)
    _write_utf8(STATIC / "app.css", css)
    _write_utf8(STATIC / "app.js", js)
    print("Wrote", STATIC / "index.html", STATIC / "app.css", STATIC / "app.js")


if __name__ == "__main__":
    main()
