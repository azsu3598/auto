const won = new Intl.NumberFormat("ko-KR", { style: "currency", currency: "KRW", maximumFractionDigits: 0 });
const number = new Intl.NumberFormat("ko-KR");
const byId = (id) => document.getElementById(id);

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

function renderEvents(rows) {
  const root = byId("events"); root.replaceChildren();
  if (!rows.length) { const tr = el("tr"); const td = el("td"); td.colSpan = 6; td.append(empty("기록 없음", "첫 모의실행 이후 이력이 표시됩니다.")); tr.append(td); root.append(tr); return; }
  rows.forEach((row) => {
    const tr = el("tr");
    const time = el("td", "", formatTime(row.occurred_at));
    const type = el("td"); type.append(el("span", "event-pill", row.type));
    const stock = el("td"); stock.append(el("strong", "", row.stock || "-"));
    const decision = el("td", "", row.decision || "-");
    const price = el("td", "", row.price ? won.format(row.price) : "-");
    const pnl = el("td", row.pnl > 0 ? "positive" : row.pnl < 0 ? "negative" : "", row.pnl === null || row.pnl === undefined ? "-" : won.format(row.pnl));
    tr.append(time, type, stock, decision, price, pnl); root.append(tr);
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
  renderPositions(data.positions); renderEvents(data.recent_events); renderSafety(data.safety);
  renderWallets(data.wallets); renderSchedules(data.schedules); renderWarnings(data.warnings);
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
setClock(); setInterval(setClock, 1000); load(); setInterval(() => load(false), 60000);
