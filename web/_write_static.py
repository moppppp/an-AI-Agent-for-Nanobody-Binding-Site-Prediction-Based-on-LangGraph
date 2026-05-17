"""One-off helper to write UTF-8 static assets."""
from pathlib import Path

STATIC = Path(__file__).parent / "static"

INDEX = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>纳米抗体智能体</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet" />
  <link rel="stylesheet" href="/static/app.css" />
</head>
<body>
  <div class="app">
    <header class="header">
      <motion class="brand">
        <span class="logo" aria-hidden="true">Nb</span>
        <div>
          <h1>纳米抗体智能体</h1>
          <p class="tagline">知识库 RAG · 结合位点预测 · LangGraph 路由</p>
        </div>
      </div>
      <span id="statusBadge" class="badge badge-loading">加载中…</span>
    </header>
    <main class="main">
      <section class="chat-panel">
        <div id="messages" class="messages" role="log" aria-live="polite">
          <article class="msg msg-assistant welcome">
            <div class="msg-body">
              <p>你好，我是纳米抗体研究助手。你可以问我：</p>
              <ul>
                <li>纳米抗体的定义与特点</li>
                <li>与常规抗体的对比</li>
                <li>结合位点预测（NanoKGAT）</li>
              </ul>
            </div>
          </article>
        </div>
        <motion class="chips" id="chips">
          <button type="button" class="chip" data-q="什么是纳米抗体？">什么是纳米抗体？</button>
          <button type="button" class="chip" data-q="纳米抗体与传统抗体相比有什么优势？">与传统抗体对比</button>
          <button type="button" class="chip" data-q="请预测该纳米抗体的结合位点">结合位点预测</button>
        </div>
        <form id="chatForm" class="composer">
          <textarea id="queryInput" rows="2" placeholder="输入问题，Enter 发送，Shift+Enter 换行" maxlength="8000" required></textarea>
          <button type="submit" id="sendBtn" disabled>发送</button>
        </form>
      </section>
      <aside class="meta-panel" aria-label="推理详情">
        <h2>推理详情</h2>
        <p class="meta-hint">发送问题后显示路由、相关度与检索片段。</p>
        <dl id="metaList" class="meta-list hidden">
          <div><dt>路由</dt><dd id="metaRoute">—</dd></div>
          <div><dt>意图</dt><dd id="metaIntent">—</dd></div>
          <div><dt>知识库相关度</dt><dd id="metaRelevance">—</dd></div>
        </dl>
        <section id="snippetBlock" class="snippet-block hidden">
          <h3>检索片段</h3>
          <ol id="snippetList"></ol>
        </section>
        <section id="predictionBlock" class="prediction-block hidden">
          <h3>预测结果</h3>
          <pre id="predictionJson"></pre>
        </section>
        <a id="pymolLink" class="pymol-link hidden" href="#" target="_blank" rel="noopener">在 PyMOL 查看结构</a>
      </aside>
    </main>
  </div>
  <script src="/static/app.js"></script>
</body>
</html>
""".replace("<motion ", "<div ").replace('class="chips"', 'class="chips"')

JS = open(__file__).read().split("JS_START")[1].split("JS_END")[0] if False else ""
