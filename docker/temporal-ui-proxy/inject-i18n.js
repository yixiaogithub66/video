(() => {
  if (window.__TEMPORAL_I18N_INSTALLED__) {
    return;
  }
  window.__TEMPORAL_I18N_INSTALLED__ = true;

  const STORAGE_KEY = "temporal_ui_locale";
  const localeFromStorage = localStorage.getItem(STORAGE_KEY);
  let locale = localeFromStorage === "zh" ? "zh" : "en";

  const EN_TO_ZH = {
    "Start Workflow": "发起工作流",
    "Workflow ID": "工作流 ID",
    "Run ID": "运行 ID",
    "Open Workflows": "运行中工作流",
    "Closed Workflows": "已关闭工作流",
    "Temporal System Workflows": "Temporal 系统工作流",
    Workflows: "工作流",
    Schedules: "调度",
    Batch: "批处理",
    Archive: "归档",
    Namespaces: "命名空间",
    Import: "导入",
    Docs: "文档",
    Feedback: "反馈",
    Filter: "筛选",
    Status: "状态",
    Type: "类型",
    Start: "开始时间",
    Completed: "已完成",
    Running: "运行中",
    Failed: "失败",
    Canceled: "已取消",
    Terminated: "已终止",
    "Timed Out": "已超时",
    Namespace: "命名空间",
    Schedules: "调度",
    Search: "搜索",
    Advanced: "高级",
    Day: "天间模式",
    Night: "夜间模式",
  };

  const ZH_TO_EN = Object.fromEntries(Object.entries(EN_TO_ZH).map(([en, zh]) => [zh, en]));

  const REGEX_EN_TO_ZH = [
    [/\b(\d+)\s+Workflows\b/g, "$1 个工作流"],
    [/\b(\d+)\s+Completed\b/g, "$1 个已完成"],
  ];

  const REGEX_ZH_TO_EN = [
    [/(\d+)\s*个工作流/g, "$1 Workflows"],
    [/(\d+)\s*个已完成/g, "$1 Completed"],
  ];

  function replaceAllByMap(text, dictionary) {
    const entries = Object.entries(dictionary).sort((a, b) => b[0].length - a[0].length);
    let out = text;
    for (const [from, to] of entries) {
      out = out.split(from).join(to);
    }
    return out;
  }

  function translateText(text) {
    if (!text || !text.trim()) {
      return text;
    }

    let out = text;
    if (locale === "zh") {
      for (const [regex, replaceWith] of REGEX_EN_TO_ZH) {
        out = out.replace(regex, replaceWith);
      }
      out = replaceAllByMap(out, EN_TO_ZH);
      return out;
    }

    for (const [regex, replaceWith] of REGEX_ZH_TO_EN) {
      out = out.replace(regex, replaceWith);
    }
    out = replaceAllByMap(out, ZH_TO_EN);
    return out;
  }

  function isTranslatableNode(node) {
    if (!node || node.nodeType !== Node.TEXT_NODE) {
      return false;
    }
    const parent = node.parentElement;
    if (!parent) {
      return false;
    }
    const tag = parent.tagName;
    if (tag === "SCRIPT" || tag === "STYLE" || tag === "NOSCRIPT") {
      return false;
    }
    return true;
  }

  function translateDom(root = document.body) {
    if (!root) {
      return;
    }
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    let node = walker.nextNode();
    while (node) {
      if (isTranslatableNode(node)) {
        const original = node.nodeValue;
        const next = translateText(original);
        if (next !== original) {
          node.nodeValue = next;
        }
      }
      node = walker.nextNode();
    }
  }

  function applyLocaleToPage() {
    document.documentElement.lang = locale === "zh" ? "zh-CN" : "en";
    const nextTitle = translateText(document.title);
    if (nextTitle && nextTitle !== document.title) {
      document.title = nextTitle;
    }
    translateDom(document.body);
    const btn = document.getElementById("temporal-lang-toggle");
    if (btn) {
      btn.textContent = locale === "zh" ? "English" : "中文";
    }
  }

  function mountToggleButton() {
    const existing = document.getElementById("temporal-lang-toggle");
    if (existing) {
      return;
    }
    const btn = document.createElement("button");
    btn.id = "temporal-lang-toggle";
    btn.type = "button";
    btn.textContent = locale === "zh" ? "English" : "中文";
    btn.style.position = "fixed";
    btn.style.top = "56px";
    btn.style.right = "16px";
    btn.style.zIndex = "999999";
    btn.style.border = "0";
    btn.style.borderRadius = "8px";
    btn.style.padding = "6px 10px";
    btn.style.background = "#111827";
    btn.style.color = "#ffffff";
    btn.style.cursor = "pointer";
    btn.style.fontSize = "12px";
    btn.style.boxShadow = "0 2px 8px rgba(0,0,0,0.18)";
    btn.style.opacity = "0.96";
    btn.addEventListener("click", () => {
      locale = locale === "zh" ? "en" : "zh";
      localStorage.setItem(STORAGE_KEY, locale);
      applyLocaleToPage();
    });
    document.body.appendChild(btn);
  }

  function placeButton() {
    const btn = document.getElementById("temporal-lang-toggle");
    if (!btn) {
      return;
    }
    if (window.innerWidth < 1100) {
      btn.style.top = "52px";
      btn.style.right = "12px";
      btn.style.padding = "5px 9px";
      btn.style.fontSize = "11px";
    } else {
      btn.style.top = "56px";
      btn.style.right = "16px";
      btn.style.padding = "6px 10px";
      btn.style.fontSize = "12px";
    }
  }

  function installObserver() {
    const observer = new MutationObserver(() => {
      mountToggleButton();
      translateDom(document.body);
    });
    observer.observe(document.documentElement, { childList: true, subtree: true, characterData: true });
  }

  function start() {
    mountToggleButton();
    placeButton();
    applyLocaleToPage();
    installObserver();
    window.addEventListener("resize", placeButton);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
