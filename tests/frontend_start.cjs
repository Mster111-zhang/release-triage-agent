const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const assert = require("node:assert/strict");

class Element {
  constructor(value = "") {
    this.value = value;
    this.textContent = "";
    this.hidden = false;
    this.disabled = false;
    this.children = [];
    this.listeners = {};
    this.files = [];
    this.classList = {toggle() {}};
  }
  addEventListener(event, callback) { this.listeners[event] = callback; }
  setAttribute() {}
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) {
    this.children = children;
    if (this.isSelect) this.value = children[0]?.value || "";
  }
}

async function check() {
  const ids = ["investigate", "case", "alert", "mode", "evidence-file", "status", "submit",
    "report-empty", "report-body", "conclusion", "reason", "action", "verdict", "citations",
    "call-count", "trace", "evidence-count", "evidence", "upload-panel", "dataset-label",
    "file-status", "online-note"];
  const nodes = Object.fromEntries(ids.map((id) => [id, new Element()]));
  nodes.case.isSelect = true;
  nodes.mode.value = "local";
  nodes.mode.options = [new Element(), new Element()];
  nodes["report-body"].hidden = nodes.verdict.hidden = true;
  const requests = [];
  const nextTick = () => new Promise((resolve) => setImmediate(resolve));
  const context = {
    document: {getElementById: (id) => nodes[id], createElement: () => new Element()},
    Option: function(label, value) {
      const option = new Element(value);
      option.textContent = label;
      return option;
    },
    fetch: async (url, options) => {
      requests.push({url, options});
      const response = options ? {
        category: "dependency_latency", title: "支付服务自身变慢", reason: "指标显示下游延迟。",
        action: "核对支付服务。", citations: [], trace: [], evidence: [],
      } : {cases: [
        {id: "case-02", label: "支付请求积压", alert: "支付很慢"},
        {id: "case-04", label: "缺失证据", alert: "证据不足"},
      ], bailian_ready: true};
      return {ok: true, json: async () => response};
    },
  };
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(path.join(__dirname, "../release_triage/web/app.js"), "utf8"), context);
  await nextTick();
  assert.equal(requests.length, 1, "opening the page should only load scenarios");
  assert.equal(nodes.case.value, "");
  assert.equal(nodes.submit.disabled, true);
  assert.equal(nodes["report-body"].hidden, true);
  nodes.case.value = "case-02";
  nodes.case.listeners.change();
  assert.equal(requests.length, 1, "selecting a scenario must not run the investigation");
  assert.equal(nodes.submit.disabled, false);
  nodes.investigate.listeners.submit({preventDefault() {}});
  await nextTick();
  assert.equal(requests.filter((item) => item.options).length, 1);
  assert.equal(nodes["report-body"].hidden, false);
  assert.equal(nodes.conclusion.textContent, "支付服务自身变慢");
  nodes.case.value = "case-04";
  nodes.case.listeners.change();
  assert.equal(nodes["report-body"].hidden, true);
  assert.equal(nodes.conclusion.textContent, "");
  assert.equal(nodes.evidence.children.length, 0);
  assert.equal(nodes.trace.children.length, 0);
  console.log("Manual investigation and stale-report regression passed.");
}
check().catch((error) => { console.error(error); process.exit(1); });
