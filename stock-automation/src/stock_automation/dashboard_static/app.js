const won = new Intl.NumberFormat("ko-KR", { style: "currency", currency: "KRW", maximumFractionDigits: 0 });
const number = new Intl.NumberFormat("ko-KR");
const byId = (id) => document.getElementById(id);
let equityHistory = { PAPER: [], LIVE: [] };
let activeEquityMode = "PAPER";

function setClock() {
  byId("clock").textContent = new Intl.DateTimeFormat("ko-KR", {
    timeZone: "Asia/Seoul", hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false,
  }).format(new Date());
}

function formatTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return new Intl.DateTimeFormat("ko-KR", {
    timeZone: "Asia/Seoul", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false,
  }).format(date);
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = text;
  return node;
}

function empty(title, detail) {
  const node = el("div", "empty");
  node.append(el("strong", "", title), document.createTextNode(detail));
  return node;
}

function metric(id, value, signed = false) {
  const node = byId(id);
  node.textContent = won.format(value || 0);
  node.classList.remove("positive", "negative");
  if (signed && value > 0) node.classList.add("positive");
  if (signed && value < 0) node.classList.add("negative");
}

function renderPositions(rows) {
  const root = byId("positions"); root.replaceChildren();
  byId("position-count").textContent = String(rows.length);
  if (!rows.length) { root.append(empty("열린 포지션 없음", "현재 전략은 현금 상태입니다.")); return; }
  rows.forEach((row) => {
    const card = el("article", "position-card");
    const name = el("div", "position-name");
    name.append(el("span", "", `${row.strategy} · ${row.code || "-"}`), el("strong", "", row.name || "확인 불가"));
    const stats = [
      ["진입가", won.format(row.entry_price || 0)],
      ["잔여수량", `${number.format(row.remaining_quantity || 0)}주`],
      ["확인 손절", won.format(row.stop_price || 0)],
      ["목표 1 / 2", `${number.format(row.target1 || 0)} / ${number.format(row.target2 || 0)}`],
    ];
    card.append(name);
    stats.forEach(([label, value]) => { const stat = el("div", "position-stat"); stat.append(el("span", "", label), el("strong", "", value)); card.append(stat); });
    root.append(card);
  });
}

function svgEl(tag, attributes = {}) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
  Object.entries(attributes).forEach(([key, value]) => node.setAttribute(key, String(value)));
  return node;
}

function renderEquityChart() {
  const rows = equityHistory[activeEquityMode] || [];
  const root = byId("equity-chart"); root.replaceChildren();
  document.querySelectorAll(".equity-mode").forEach((button) => {
    button.classList.toggle("active", button.dataset.equityMode === activeEquityMode);
  });
  if (!rows.length) {
    byId("equity-current").textContent = "-"; byId("equity-change").textContent = "-";
    root.append(empty("기록 없음", `${activeEquityMode === "PAPER" ? "모의" : "실거래"} 일별 총금액이 아직 없습니다.`));
    return;
  }
  const values = rows.map((row) => Number(row.total_assets));
  const first = values[0]; const latest = values[values.length - 1]; const change = latest - first;
  byId("equity-current").textContent = won.format(latest);
  const changeNode = byId("equity-change");
  changeNode.textContent = `${change >= 0 ? "+" : ""}${won.format(change)}`;
  changeNode.className = change > 0 ? "positive" : change < 0 ? "negative" : "";

  const width = 900; const height = 220; const left = 18; const right = 18; const top = 18; const bottom = 32;
  const minimum = Math.min(...values); const maximum = Math.max(...values); const span = Math.max(1, maximum - minimum);
  const points = rows.map((row, index) => ({
    x: left + (rows.length === 1 ? (width - left - right) / 2 : index * (width - left - right) / (rows.length - 1)),
    y: top + (maximum - Number(row.total_assets)) * (height - top - bottom) / span,
    row,
  }));
  const svg = svgEl("svg", { viewBox: `0 0 ${width} ${height}`, role: "img", "aria-label": "일별 총금액 선그래프" });
  [0, .5, 1].forEach((ratio) => {
    const y = top + ratio * (height - top - bottom);
    svg.append(svgEl("line", { x1: left, y1: y, x2: width - right, y2: y, class: "chart-grid" }));
  });
  const line = points.map((point, index) => `${index ? "L" : "M"}${point.x.toFixed(1)},${point.y.toFixed(1)}`).join(" ");
  const area = `${line} L${points.at(-1).x.toFixed(1)},${height - bottom} L${points[0].x.toFixed(1)},${height - bottom} Z`;
  svg.append(svgEl("path", { d: area, class: "equity-area" }), svgEl("path", { d: line, class: "equity-line" }));
  points.forEach((point, index) => {
    const dot = svgEl("circle", { cx: point.x, cy: point.y, r: index === points.length - 1 ? 5 : 3, class: "equity-dot" });
    const title = svgEl("title"); title.textContent = `${point.row.recorded_at.slice(0, 10)} · ${won.format(point.row.total_assets)}`; dot.append(title); svg.append(dot);
    const label = svgEl("text", { x: point.x, y: height - 10, class: "chart-date", "text-anchor": "middle" });
    label.textContent = point.row.recorded_at.slice(5, 10); svg.append(label);
  });
  root.append(svg);
}

function renderEvents(rows) {
  const root = byId("events"); root.replaceChildren();
  if (!rows.length) { const tr = el("tr"); const td = el("td"); td.colSpan = 7; td.append(empty("기록 없음", "첫 모의실행 이후 이력이 표시됩니다.")); tr.append(td); root.append(tr); return; }
  rows.forEach((row) => {
    const tr = el("tr");
    const time = el("td", "", formatTime(row.occurred_at)); time.dataset.label = "시각";
    const type = el("td"); type.dataset.label = "구분"; type.append(el("span", "event-pill", row.type));
    const stock = el("td"); stock.dataset.label = "종목"; stock.append(el("strong", "", row.stock || "-"));
    const decision = el("td", "", row.decision || "-"); decision.dataset.label = "결정";
    const price = el("td", "", row.price ? won.format(row.price) : "-"); price.dataset.label = "가격";
    const pnl = el("td", row.pnl > 0 ? "positive" : row.pnl < 0 ? "negative" : "", row.pnl === null || row.pnl === undefined ? "-" : won.format(row.pnl)); pnl.dataset.label = "손익";
    const reasons = el("td", "reason-cell");
    reasons.dataset.label = "매매 이유";
    if (row.reasons?.length) row.reasons.forEach((reason) => reasons.append(el("span", "reason-chip", reason)));
    else reasons.textContent = "기록 없음";
    tr.append(time, type, stock, decision, price, pnl, reasons); root.append(tr);
  });
}

function renderLiveSafety(summary, orders) {
  summary = summary || {};
  const tone = summary.overall || "blocked";
  const badge = byId("live-safety-badge");
  badge.className = `badge ${tone}`; badge.textContent = summary.title || "확인 불가";
  byId("live-active-orders").textContent = `${number.format(summary.active_orders || 0)}건`;
  const ambiguous = summary.ambiguous_orders || 0;
  const ambiguousNode = byId("live-ambiguous-orders");
  ambiguousNode.textContent = `${number.format(ambiguous)}건`;
  ambiguousNode.className = ambiguous ? "negative" : "positive";
  byId("live-last-reconciled").textContent = formatTime(summary.last_reconciled_at);

  const gates = byId("live-gates"); gates.replaceChildren();
  (summary.gates || []).forEach((gate) => {
    const row = el("div", `live-gate ${gate.state || "blocked"}`);
    const copy = el("div"); copy.append(el("span", "", gate.label), el("strong", "", gate.detail));
    row.append(el("i", "gate-icon"), copy); gates.append(row);
  });
  if (!(summary.gates || []).length) gates.append(empty("안전정보 없음", "DynamoDB 안전 레코드를 확인하세요."));

  const root = byId("live-orders"); root.replaceChildren();
  if (!orders?.length) {
    root.append(empty("실주문 이력 없음", "현재 실주문이 실행되지 않았거나 안전 원장이 연결되지 않았습니다."));
    return;
  }
  orders.forEach((order) => {
    const card = el("article", `live-order-card ${order.tone || "neutral"}`);
    const header = el("div", "live-order-header");
    const identity = el("div", "live-order-identity");
    identity.append(
      el("span", "", `${order.strategy || "전략 확인 불가"} · ${order.side || "-"}`),
      el("strong", "", `${order.name || "확인 불가"} ${order.code ? `(${order.code})` : ""}`),
    );
    header.append(identity, el("span", `order-state ${order.tone || "neutral"}`, order.state_label || order.state));
    const figures = el("div", "live-order-figures");
    [["주문", `${number.format(order.quantity || 0)}주`], ["체결", `${number.format(order.filled_quantity || 0)}주`], ["미체결", `${number.format(order.remaining_quantity || 0)}주`], ["지정가", order.limit_price ? won.format(order.limit_price) : "-"]].forEach(([label, value]) => {
      const figure = el("div"); figure.append(el("span", "", label), el("strong", "", value)); figures.append(figure);
    });
    const steps = el("div", "order-steps");
    (order.steps || []).forEach((step) => {
      const node = el("div", `order-step ${step.state}`);
      node.append(el("i"), el("span", "", step.label)); steps.append(node);
    });
    const meta = el("div", "live-order-meta");
    meta.append(
      el("span", "", `갱신 ${formatTime(order.updated_at)}`),
      el("span", "", order.broker_order_no ? `주문번호 ${order.broker_order_no}` : "주문번호 대기"),
    );
    card.append(header, figures, steps, meta);
    if (order.uncertainty_reason) card.append(el("p", "order-warning", order.uncertainty_reason));
    root.append(card);
  });
}

function renderSafety(rows) {
  const root = byId("safety"); root.replaceChildren();
  rows.forEach((row) => {
    const item = el("div", "safety-row"); const name = el("div", "safety-name");
    name.append(el("strong", "", row.label), el("small", "", row.detail));
    item.append(name, el("span", `state-dot ${row.state}`)); root.append(item);
  });
}

function renderStrategyModes(rows) {
  const root = byId("strategy-modes"); root.replaceChildren();
  rows.forEach((row) => {
    const item = el("div", "strategy-mode-row");
    const heading = el("div", "strategy-mode-heading");
    heading.append(el("strong", "", row.label), el("small", "", row.detail));
    const choices = el("div", "mode-choices");
    [["paper_selected", "모의"], ["live_selected", "실거래"]].forEach(([field, label]) => {
      const choice = el("label", `mode-choice ${field === "live_selected" ? "live" : "paper"}`);
      const input = document.createElement("input"); input.type = "checkbox";
      input.checked = Boolean(row[field]); input.disabled = Boolean(row.controls_locked);
      choice.append(input, el("span", "", label)); choices.append(choice);
    });
    item.append(heading, choices); root.append(item);
  });
}

function renderWallets(rows) {
  const root = byId("wallets"); root.replaceChildren();
  if (!rows.length) { root.append(empty("지갑 대기 중", "AWS 모의작업 후 자동 생성됩니다.")); return; }
  rows.forEach((row) => {
    const item = el("div", "wallet-row"); const name = el("div", "wallet-name"); const value = el("div", "wallet-value");
    name.append(el("strong", "", row.strategy), el("small", "", `실현 ${won.format(row.realized_pnl || 0)}`));
    value.append(el("strong", "", won.format(row.available_cash || 0)), el("small", "", `투자 ${won.format(row.invested_principal || 0)}`));
    item.append(name, value); root.append(item);
  });
}

function renderSchedules(rows) {
  const root = byId("schedules"); root.replaceChildren();
  rows.forEach((row) => {
    const item = el("div", "timeline-row"); const label = el("div", "timeline-label");
    label.append(el("strong", "", row.label), el("small", "", `${row.strategy} · 구성됨`));
    item.append(el("div", "timeline-time", row.time), el("div", "timeline-marker"), label); root.append(item);
  });
}

function renderWarnings(rows) {
  const section = byId("warnings-section"); const root = byId("warnings"); root.replaceChildren();
  if (!rows.length) { section.classList.add("hidden"); return; }
  rows.forEach((warning) => root.append(el("p", "", warning))); section.classList.remove("hidden");
}

function render(data) {
  const dangerous = data.mode !== "LIVE_LOCKED";
  const badge = byId("mode-badge"); badge.textContent = dangerous ? "LIVE FLAG DETECTED" : "LIVE LOCKED"; badge.className = `badge ${dangerous ? "danger" : "safe"}`;
  byId("generated-at").textContent = formatTime(data.generated_at);
  byId("live-lock-reason").textContent = data.live_transition.reason;
  metric("available-cash", data.metrics.available_cash);
  metric("invested-principal", data.metrics.invested_principal);
  metric("realized-pnl", data.metrics.realized_pnl, true);
  byId("fees-taxes").textContent = `비용 ${won.format(data.metrics.fees_taxes || 0)}`;
  byId("open-positions").textContent = `${number.format(data.metrics.open_positions || 0)}개`;
  byId("pending-alerts").textContent = `알림 대기 ${number.format(data.metrics.pending_notifications || 0)}건`;
  equityHistory = data.equity_history || { PAPER: [], LIVE: [] }; renderEquityChart();
  renderLiveSafety(data.live_safety, data.live_orders || []);
  renderPositions(data.positions); renderEvents(data.recent_events); renderSafety(data.safety);
  renderStrategyModes(data.strategy_modes || []); renderWallets(data.wallets);
  renderSchedules(data.schedules); renderWarnings(data.warnings);
}

let toastTimer;
function toast(message) { const node = byId("toast"); node.textContent = message; node.classList.add("show"); clearTimeout(toastTimer); toastTimer = setTimeout(() => node.classList.remove("show"), 2500); }

async function load(manual = false) {
  const button = byId("refresh"); button.classList.add("loading"); button.disabled = true;
  try {
    const response = await fetch("/api/dashboard", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    render(await response.json()); if (manual) toast("최신 원장으로 갱신했습니다.");
  } catch (error) {
    renderWarnings(["대시보드 데이터를 불러오지 못했습니다. 서버와 AWS 권한을 확인하세요."]);
    toast("데이터 연결 실패");
  } finally { button.classList.remove("loading"); button.disabled = false; }
}

byId("refresh").addEventListener("click", () => load(true));
document.querySelectorAll(".equity-mode").forEach((button) => button.addEventListener("click", () => {
  activeEquityMode = button.dataset.equityMode; renderEquityChart();
}));
setClock(); setInterval(setClock, 1000); load(); setInterval(() => load(false), 60000);
