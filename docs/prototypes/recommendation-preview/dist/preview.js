/* Offline UI demonstration only. No broker, AI, ledger, storage or network client. */
(function () {
  "use strict";

  const byId = (id) => document.getElementById(id);
  const ui = Object.fromEntries([
    "run", "cancel", "scenario", "progress", "state-badge", "result-panel",
    "result-title", "result-count", "status", "viewed-at", "summary", "cards", "empty",
  ].map((id) => [id, byId(id)]));
  const sampleCandidates = [
    {
      name: "가상 A기업", code: "DEMO_A", theme: "가상 인프라",
      reason: "화면 예시: 거래대금 확대와 지지 확인 근거가 이 자리에 표시됩니다.",
      levels: [
        ["진입 범위 · 가상", "12,300~12,500원"], ["배정 · 가상 60만원 기준", "최대 10주 / 125,000원 (20.8%)"],
        ["확인 손절 · 가상", "12,100원 / 5M_CONFIRMED"], ["비상 하한 · 가상", "11,900원 / IMMEDIATE"],
        ["1차 목표 · 가상", "13,000원"], ["2차 목표 · 가상", "13,500원"],
      ],
      risk: "가상 위험: 지지가 깨지거나 촉매가 무효화되면 추천을 철회하는 형태입니다.",
    },
    {
      name: "가상 B기업", code: "DEMO_B", theme: "가상 소비재",
      reason: "화면 예시: 다른 테마에서 조건을 충족한 후보의 근거를 표시합니다.",
      levels: [
        ["진입 범위 · 가상", "28,400~28,600원"], ["배정 · 가상 60만원 기준", "최대 3주 / 85,800원 (14.3%)"],
        ["확인 손절 · 가상", "28,000원 / 5M_CONFIRMED"], ["비상 하한 · 가상", "27,700원 / IMMEDIATE"],
        ["1차 목표 · 가상", "29,500원"], ["2차 목표 · 가상", "30,500원"],
      ],
      risk: "가상 위험: 시장 충격이나 유동성 악화 시 계획한 가격보다 손실이 커질 수 있습니다.",
    },
  ];
  const outcomes = {
    candidates: { title: "가상 후보 2종목", message: "화면 시연 결과입니다. 실제 종목·시세·추천이 아닙니다.", badge: "시연 완료" },
    no_trade: { title: "매수 없음 · NO_TRADE", message: "가상 예시: 조건을 충족한 후보가 없어 신규 투자금 0원, 현금 100%를 표시합니다.", badge: "매수 없음" },
    stale: { title: "자료 만료 · 추천 차단", message: "가상 예시: 필수 자료가 오래되어 추천을 표시하지 않습니다. 이전 후보를 최신 결과로 대신하지 않습니다.", badge: "자료 확인 필요" },
    timeout: { title: "시간 초과 · 결과 없음", message: "가상 예시: 제한 시간 안에 자료를 확인하지 못했습니다. 자동 재시도하지 않습니다.", badge: "시간 초과" },
    error: { title: "조회 실패 · 결과 없음", message: "가상 예시: 자료 조회가 실패했습니다. NO_TRADE 분석 성공이나 후보 없음으로 바꾸지 않습니다.", badge: "조회 실패" },
  };
  let busy = false;
  let timer = null;
  let generation = 0;

  function element(tag, text, className) {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
  }

  function setBusy(value) {
    busy = value;
    ui.run.disabled = value;
    ui.scenario.disabled = value;
    ui.cancel.hidden = !value;
    ui.progress.hidden = !value;
    ui["result-panel"].setAttribute("aria-busy", String(value));
    ui.run.textContent = value ? "샘플 화면 준비 중…" : "종목 추천 · 샘플 실행 ↗";
  }

  function clearResults() {
    ui.cards.replaceChildren();
    ui.summary.replaceChildren();
    ui.summary.hidden = true;
    ui.empty.hidden = true;
    ui["result-count"].textContent = "0종목";
    ui["viewed-at"].textContent = "시연 실행 시각 없음 · 실제 시세 기준 시각 없음";
  }

  function addSummary(invested, cash) {
    ui.summary.replaceChildren();
    for (const [label, value] of [["가상 배정 합계", invested], ["가상 잔여 현금", cash]]) {
      const item = element("div");
      item.append(element("span", label), element("strong", value));
      ui.summary.append(item);
    }
    ui.summary.hidden = false;
  }

  function candidateCard(candidate) {
    const card = element("article", undefined, "candidate");
    const heading = element("div", undefined, "candidate-heading");
    heading.append(element("h3", candidate.name), element("span", "가상 데이터", "pill"));
    const levels = element("dl", undefined, "levels");
    for (const [label, value] of candidate.levels) {
      const row = element("div");
      row.append(element("dt", label), element("dd", value));
      levels.append(row);
    }
    const detail = element("details");
    detail.append(
      element("summary", "손절 해석과 자료 상태 보기"),
      element("p", "5M_CONFIRMED: 5분봉이 확인 손절선 아래에서 마감하고 다음 봉도 회복하지 못하는 경우입니다. 비상 하한은 별도이며 무기한 기다리지 않습니다."),
      element("p", "실제 시세 기준 시각 없음 / 거래소·세션·NXT 자격·호가·기관·프로그램 수급·뉴스 출처: 미연결. 실제 기능에서는 필수 검증 누락 시 추천을 차단해야 합니다."),
    );
    card.append(heading, element("p", candidate.code + " · " + candidate.theme + " · 실제 상장종목 아님", "caption"),
      element("p", candidate.reason, "reason"), levels, element("p", candidate.risk, "risk"), detail);
    return card;
  }

  function finish(scenario, token) {
    if (!busy || generation !== token) return;
    timer = null;
    setBusy(false);
    const result = outcomes[scenario] || outcomes.error;
    ui["state-badge"].textContent = result.badge;
    ui["result-title"].textContent = result.title;
    ui.status.textContent = result.message;
    ui["viewed-at"].textContent = "시연 완료 시각 " + new Intl.DateTimeFormat("ko-KR", {
      timeZone: "Asia/Seoul", hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false,
    }).format(new Date()) + " KST · 실제 시세 기준 시각 없음";
    if (scenario === "candidates") {
      ui["result-count"].textContent = "가상 2종목";
      addSummary("210,800원 · 35.1%", "389,200원 · 64.9%");
      ui.cards.append(...sampleCandidates.map(candidateCard));
    } else if (scenario === "no_trade") {
      addSummary("0원 · 0%", "600,000원 · 100%");
      ui.empty.hidden = false;
    }
  }

  ui.run.addEventListener("click", function () {
    if (busy) return;
    const scenario = ui.scenario.value;
    const token = ++generation;
    clearResults();
    setBusy(true);
    ui["state-badge"].textContent = "샘플 실행 중";
    ui["result-title"].textContent = "가상 결과 준비 중";
    ui.status.textContent = "실제 API를 호출하지 않고 선택한 화면 시나리오만 재생합니다.";
    timer = setTimeout(function () { finish(scenario, token); }, 1100);
  });

  ui.cancel.addEventListener("click", function () {
    if (!busy) return;
    ++generation;
    clearTimeout(timer);
    timer = null;
    setBusy(false);
    clearResults();
    ui["state-badge"].textContent = "시연 중단";
    ui["result-title"].textContent = "중단됨 · 결과 없음";
    ui.status.textContent = "샘플 화면 시연을 중단했습니다. 운영 중인 작업이나 매매를 중지하는 버튼이 아닙니다.";
  });
}());
