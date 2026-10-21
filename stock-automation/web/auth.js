/* Browser-only authorization code + PKCE. No passwords or AWS credentials here. */
(() => {
  "use strict";
  const cfg = window.SABU_CONFIG;
  const key = "sabu-pkce";
  let accessToken = "";
  let expiresAt = 0;
  let loginPending = false;
  let resolveReady;
  const ready = new Promise((resolve) => { resolveReady = resolve; });
  const b64 = (bytes) => btoa(String.fromCharCode(...bytes)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  const random = () => b64(crypto.getRandomValues(new Uint8Array(32)));
  const root = new URL("/", location.origin).href;

  function validateConfig() {
    if (!cfg || ![cfg.authOrigin, cfg.apiOrigin].every((value) => new URL(value).protocol === "https:")) {
      throw new Error("Invalid deployment configuration");
    }
  }

  function showSignIn(message = "모의 원장을 보려면 로그인해 주세요.") {
    let gate = document.getElementById("sign-in-gate");
    if (!gate) {
      gate = document.createElement("section"); gate.id = "sign-in-gate";
      gate.className = "auth-gate"; gate.setAttribute("aria-label", "대시보드 로그인");
      const card = document.createElement("div"); card.className = "auth-card";
      const title = document.createElement("h1"); title.textContent = "SABU Trading Console";
      const detail = document.createElement("p"); detail.id = "sign-in-message";
      const button = document.createElement("button"); button.type = "button";
      button.textContent = "로그인"; button.className = "refresh-button";
      button.addEventListener("click", () => { signIn().catch(() => {
        loginPending = false; showSignIn("로그인을 시작하지 못했습니다. 다시 시도해 주세요.");
      }); });
      card.append(title, detail, button); gate.append(card); document.body.append(gate);
    }
    document.getElementById("sign-in-message").textContent = message;
    gate.hidden = false;
  }

  async function signIn() {
    validateConfig();
    if (loginPending) return;
    loginPending = true;
    const verifier = random(); const state = random();
    const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier));
    sessionStorage.setItem(key, JSON.stringify({ verifier, state, created: Date.now() }));
    const url = new URL("/oauth2/authorize", cfg.authOrigin);
    url.search = new URLSearchParams({ response_type: "code", client_id: cfg.clientId,
      redirect_uri: root, scope: "openid", state, code_challenge: b64(new Uint8Array(digest)),
      code_challenge_method: "S256" }).toString();
    location.assign(url.href);
  }

  async function initialize() {
    validateConfig();
    const params = new URLSearchParams(location.search);
    const code = params.get("code"); const state = params.get("state");
    if (params.size) history.replaceState(null, "", location.pathname);
    if (!code) { showSignIn(params.has("error") ? "로그인이 완료되지 않았습니다. 다시 시도해 주세요." : undefined); return; }
    const stored = sessionStorage.getItem(key); sessionStorage.removeItem(key);
    const attempt = stored ? JSON.parse(stored) : null;
    if (!attempt || !state || state !== attempt.state || Date.now() - attempt.created > 600000
        || attempt.created > Date.now()) throw new Error("Invalid sign-in state");
    const response = await fetch(new URL("/oauth2/token", cfg.authOrigin), {
      method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ grant_type: "authorization_code", client_id: cfg.clientId,
        code, redirect_uri: root, code_verifier: attempt.verifier })
    });
    if (!response.ok) throw new Error("Sign-in failed");
    const tokens = await response.json();
    if (typeof tokens.access_token !== "string" || tokens.token_type?.toLowerCase() !== "bearer"
        || !(Number(tokens.expires_in) > 0)) throw new Error("Invalid token response");
    // Keep only the short-lived access token in memory. Never persist token sets.
    accessToken = tokens.access_token; expiresAt = Date.now() + Number(tokens.expires_in) * 1000;
    document.getElementById("sign-in-gate")?.remove(); resolveReady();
    const logout = document.createElement("button"); logout.type = "button";
    logout.className = "refresh-button"; logout.textContent = "로그아웃";
    logout.addEventListener("click", () => {
      accessToken = ""; expiresAt = 0; sessionStorage.removeItem(key);
      showSignIn("로그아웃되었습니다.");
      const url = new URL("/logout", cfg.authOrigin);
      url.search = new URLSearchParams({ client_id: cfg.clientId, logout_uri: root }).toString();
      location.replace(url.href);
    });
    document.querySelector(".top-actions").append(logout);
  }

  window.sabuDashboardFetch = async () => {
    await ready;
    if (!accessToken || Date.now() >= expiresAt - 15000) {
      showSignIn("로그인 시간이 만료되었습니다. 다시 로그인해 주세요.");
      throw new Error("Sign-in expired");
    }
    const response = await fetch(new URL("/api/dashboard", cfg.apiOrigin), {
      cache: "no-store", headers: { Authorization: `Bearer ${accessToken}` }
    });
    if (response.status === 401 || response.status === 403) {
      accessToken = ""; expiresAt = 0; showSignIn("로그인이 필요합니다.");
    }
    return response;
  };
  initialize().catch(() => { accessToken = ""; showSignIn("로그인을 확인하지 못했습니다. 다시 시도해 주세요."); });
})();
