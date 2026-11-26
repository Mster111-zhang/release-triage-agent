"use strict";

const byId = (name) => document.getElementById(name);
const form = byId("investigate");
const select = byId("case");
const alertBox = byId("alert");
const mode = byId("mode");
const upload = byId("evidence-file");
const status = byId("status");
const submit = byId("submit");
const sourceNames = { releases: "发布变更", logs: "错误日志", metrics: "服务指标" };
let scenarios = [];
let imported = null;

function element(tag, text, className) {
  const node = document.createElement(tag);
  node.textContent = text;
  if (className) node.className = className;
  return node;
}

function showReport(report) {
  byId("report-empty").hidden = true;
  byId("report-body").hidden = false;
  byId("conclusion").textContent = report.title;
  byId("reason").textContent = report.reason;
  byId("action").textContent = report.action;

  const verdict = byId("verdict");
  verdict.hidden = false;
  verdict.classList.toggle("warn", report.category === "insufficient");
  verdict.textContent = report.category === "insufficient" ? "待补充证据" : "已核对证据";

  byId("citations").replaceChildren(...report.citations.map((id) => {
    const link = element("a", id);
    link.href = "#" + id;
    link.setAttribute("aria-label", "查看证据 " + id);
    return link;
  }));
  byId("call-count").textContent = report.trace.length + " 次查询";
  byId("trace").replaceChildren(...report.trace.map((step) => {
    const row = document.createElement("li");
    row.append(element("strong", step.label), element("p", step.reason));
    const window = step.arguments;
    const duration = window.start + "–" + window.end + " UTC";
    row.append(element("div", step.planner + " · " + duration + " · " + step.ids.length + " 条记录 · 查询 " + step.query_ms + " ms", "small"));
    return row;
  }));
  byId("evidence-count").textContent = report.evidence.length + " 条记录";
  byId("evidence").replaceChildren(...report.evidence.map((record) => {
    const row = document.createElement("article");
    row.className = "evidence-row";
    row.id = record.id;
    const meta = document.createElement("div");
    meta.className = "meta";
    meta.append(element("span", record.id, "row-id"));
    meta.append(element("span", sourceNames[record.source] + " · " + record.at + " UTC", "small"));
    row.append(meta, element("p", record.description));
    return row;
  }));
}

function setAlert() {
  const custom = select.value === "upload";
  byId("upload-panel").hidden = !custom;
  byId("dataset-label").textContent = custom ? "导入证据" : "模拟事故数据";
  alertBox.value = custom ? imported?.alert || "" : scenarios.find((item) => item.id === select.value)?.alert || "";
  submit.disabled = custom && !imported;
  status.textContent = "";
}

async function investigate() {
  const body = {scenario: select.value, alert: alertBox.value, mode: mode.value};
  if (body.scenario === "upload") {
    if (!imported) return;
    body.evidence = imported.records;
  }
  const controls = [submit, select, upload, alertBox, mode];
  for (const control of controls) control.disabled = true;
  status.textContent = "正在查询事故证据…";
  try {
    const response = await fetch("/api/investigate", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(body),
    });
    const report = await response.json();
    if (!response.ok) {
      const location = report.detail?.[0]?.loc;
      const recordIndex = location?.[2];
      const message = Number.isInteger(recordIndex)
        ? "第 " + (recordIndex + 1) + " 条证据的来源、时间或数值格式不符合要求。"
        : "请检查告警和证据包设置。";
      throw new Error(typeof report.detail === "string" ? report.detail : message);
    }
    showReport(report);
    status.textContent = "排查完成";
  } catch (error) {
    status.textContent = error.message || "排查失败，请重试。";
  } finally {
    for (const control of controls) control.disabled = false;
  }
}

select.addEventListener("change", setAlert);
mode.addEventListener("change", () => {
  byId("online-note").hidden = mode.value !== "bailian";
});
upload.addEventListener("change", async () => {
  const file = upload.files[0];
  const fileStatus = byId("file-status");
  imported = null;
  setAlert();
  if (!file) {
    fileStatus.textContent = "最多 100 条记录";
    return;
  }
  try {
    if (file.size > 128 * 1024) throw new Error("证据文件不能超过 128 KB。");
    const data = JSON.parse(await file.text());
    if (file !== upload.files[0]) return;
    if (typeof data?.alert !== "string" || !Array.isArray(data.records) || !data.records.length || data.records.length > 100) {
      throw new Error("文件需要告警描述和 1 至 100 条 records。");
    }
    imported = data;
    fileStatus.textContent = "已导入 " + data.records.length + " 条记录";
    if (select.value === "upload") setAlert();
  } catch (error) {
    if (file === upload.files[0]) {
      fileStatus.textContent = error instanceof SyntaxError ? "文件不是可读取的 JSON。" : error.message;
    }
  }
});
form.addEventListener("submit", (event) => {
  event.preventDefault();
  investigate();
});

async function initialize() {
  try {
    const response = await fetch("/api/scenarios");
    if (!response.ok) throw new Error();
    const data = await response.json();
    scenarios = data.cases;
    select.replaceChildren(
      ...scenarios.map((item) => new Option(item.label, item.id)),
      new Option("导入自定义证据", "upload"),
    );
    const bailian = mode.options[1];
    if (data.bailian_ready) {
      bailian.disabled = false;
      bailian.textContent = "百炼模型 · 在线查询策略";
    }
    select.disabled = false;
    setAlert();
    await investigate();
  } catch {
    status.textContent = "无法加载演示场景，请刷新页面。";
  }
}

initialize();
