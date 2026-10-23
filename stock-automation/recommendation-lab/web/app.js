(function () {
  "use strict";
  const el = (id) => document.getElementById(id);
  const csrf = document.querySelector('meta[name="recommendation-csrf"]').content;
  const money = (value) => Number(value).toLocaleString("ko-KR") + "원";
  let busy = false, controller = null, serial = 0, expiryTimer = null;

  function node(tag, text, className) {
    const result = document.createElement(tag); result.textContent = text;
    if (className) result.className = className;
    return result;
  }
  function clear() {
    clearTimeout(expiryTimer); expiryTimer = null;
    el("cards").replaceChildren(); el("summary").textContent = ""; el("meta").textContent = "";
  }
  function setBusy(value) {
    busy = value; el("run").disabled = value; el("cancel").hidden = !value;
    el("result").setAttribute("aria-busy", String(value));
  }
  function validResult(data) {
    if (!data || data.purpose !== "RESEARCH_ONLY" || data.order_submission !== false || data.ledger_mutation !== false
        || typeof data.is_sample !== "boolean" || typeof data.rule_version !== "string"
        || !["CANDIDATES", "NO_TRADE"].includes(data.status) || !Array.isArray(data.candidates)
        || data.candidates.length > 3 || !Number.isFinite(Date.parse(data.data_cutoff_at))
        || !Number.isFinite(Date.parse(data.expires_at)) || Date.parse(data.expires_at) <= Date.now()
        || (data.status === "NO_TRADE" && data.candidates.length !== 0)
        || (data.status === "CANDIDATES" && data.candidates.length === 0)) return false;
    for (const key of ["research_capital_krw", "allocated_krw", "remaining_cash_krw"]) {
      if (!Number.isSafeInteger(data[key]) || data[key] < 0) return false;
    }
    if (data.research_capital_krw !== data.allocated_krw + data.remaining_cash_krw) return false;
    return data.candidates.every((candidate) => {
      if (!["code", "name", "venue", "session", "observed_at"].every((key) => typeof candidate[key] === "string")) return false;
      if (!["reasons", "risks", "sources"].every((key) => Array.isArray(candidate[key]) && candidate[key].every((item) => typeof item === "string"))) return false;
      if (!["reference_price", "entry_low", "entry_high", "suggested_quantity", "allocation_krw", "stop_price", "emergency_stop", "target1", "target2"]
        .every((key) => Number.isSafeInteger(candidate[key]) && candidate[key] > 0)) return false;
      return candidate.emergency_stop < candidate.stop_price && candidate.stop_price < candidate.entry_low
        && candidate.entry_low <= candidate.reference_price && candidate.reference_price <= candidate.entry_high
        && candidate.entry_high < candidate.target1 && candidate.target1 < candidate.target2
        && candidate.allocation_krw === candidate.entry_high * candidate.suggested_quantity
        && ["KRX", "NXT"].includes(candidate.venue) && candidate.stop_mode === "5M_CONFIRMED"
        && candidate.emergency_stop_mode === "IMMEDIATE";
    });
  }
  function card(candidate, sample) {
    const result = node("article", "", "card");
    result.append(node("span", sample ? "가상 연구 자료" : "독립 검증 전 연구 결과", "tag"),
      node("h3", candidate.name + " · " + candidate.code),
      node("p", candidate.venue + " / " + candidate.session + " / 기준 " + candidate.observed_at, "small"));
    const levels = node("dl", "");
    for (const [key, value] of [
      ["진입 범위", money(candidate.entry_low) + " ~ " + money(candidate.entry_high)],
      ["배정 제안 · 체결 아님", candidate.suggested_quantity + "주 / " + money(candidate.allocation_krw)],
      ["확인 손절", money(candidate.stop_price) + " / " + candidate.stop_mode],
      ["비상 하한", money(candidate.emergency_stop) + " / " + candidate.emergency_stop_mode],
      ["1차 목표", money(candidate.target1)], ["2차 목표", money(candidate.target2)],
    ]) {
      const row = node("div", ""); row.append(node("dt", key), node("dd", value)); levels.append(row);
    }
    result.append(levels);
    for (const reason of candidate.reasons) result.append(node("p", "근거 · " + reason));
    for (const risk of candidate.risks) result.append(node("p", "위험 · " + risk, "risk"));
    result.append(node("p", "출처 · " + candidate.sources.join(" / "), "small"));
    return result;
  }
  el("run").addEventListener("click", async function () {
    if (busy) return;
    const token = ++serial;
    clear(); setBusy(true);
    el("result-heading").textContent = "분석 중";
    el("status").textContent = "서버에서 지정한 자료를 검증합니다. 자동매매는 실행하지 않습니다.";
    controller = new AbortController();
    const activeController = controller;
    const timeout = setTimeout(() => activeController.abort(), 12000);
    try {
      const response = await fetch("/api/recommendations", {
        method: "POST", cache: "no-store", credentials: "same-origin", signal: activeController.signal,
        headers: { "Content-Type": "application/json", "X-Recommendation-CSRF": csrf },
        body: JSON.stringify({ request_id: crypto.randomUUID() }),
      });
      const data = await response.json();
      if (token !== serial) return;
      if (!response.ok) {
        el("result-heading").textContent = "추천 불가 · " + data.status;
        el("status").textContent = data.reason + (data.retry_after_seconds ? " / " + data.retry_after_seconds + "초 후 직접 다시 요청하세요." : "");
        return;
      }
      const until = Date.parse(data.expires_at);
      if (!validResult(data)) throw new Error("Invalid result");
      el("result-heading").textContent = data.status === "NO_TRADE" ? "매수 없음 · NO_TRADE" : "연구 후보 " + data.candidates.length + "종목";
      el("status").textContent = data.is_sample ? "가상 데이터입니다. 실제 추천이나 체결이 아닙니다." : "실험적 분석 결과입니다. 수익성·자료 수집의 독립 검증은 완료되지 않았습니다.";
      el("meta").textContent = "자료 기준 " + data.data_cutoff_at + " / 유효기한 " + data.expires_at + " / " + data.rule_version;
      el("summary").textContent = "가정 자금 " + money(data.research_capital_krw) + " · 제안 배정 " + money(data.allocated_krw) + " · 현금 " + money(data.remaining_cash_krw) + " · 계좌 잔액 아님";
      el("cards").append(...data.candidates.map((candidate) => card(candidate, data.is_sample)));
      expiryTimer = setTimeout(function () {
        if (token !== serial) return;
        clear(); el("result-heading").textContent = "결과 만료 · 다시 요청 필요";
        el("status").textContent = "자동 재조회하지 않습니다. 이전 후보는 숨겼습니다.";
      }, Math.max(0, until - Date.now()));
    } catch (error) {
      if (token !== serial) return;
      clear(); el("result-heading").textContent = "결과 없음";
      el("status").textContent = error.name === "AbortError" ? "화면 대기 시간이 초과됐습니다. 서버 작업 취소를 의미하지 않습니다." : "결과 확인 실패. 자동 재시도하지 않습니다.";
    } finally {
      clearTimeout(timeout);
      if (token === serial) { setBusy(false); controller = null; }
    }
  });
  el("cancel").addEventListener("click", function () {
    if (!busy) return;
    ++serial; controller?.abort(); controller = null; clear(); setBusy(false);
    el("result-heading").textContent = "화면 대기 취소";
    el("status").textContent = "이 브라우저의 대기만 취소했습니다. 서버 작업이나 기존 매매의 중지가 아닙니다.";
  });
}());
