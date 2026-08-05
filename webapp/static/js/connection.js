// Top panel: connection form + status (mock or live execution).
import { $ } from "./dom.js";
import * as api from "./api.js";
import { ApiError } from "./api.js";
import { toast } from "./ui.js";
import { extractSubFromPasswordField } from "./jwt.js?v=11";

export class Connection {
  /** @param {(connected:boolean)=>void} onChange */
  constructor(onChange) {
    this.onChange = onChange;
    this.form = $("#connection-form");
    this.statusDot = this.form.querySelector(".status-dot");
    this.statusText = this.form.querySelector(".status-text");
    this.connectBtn = $("#conn-button");
    this.probeBtn = /** @type {HTMLButtonElement} */ ($("#probe-button"));
    this.disconnectBtn = $("#disconnect-button");
    this.modeSelect = /** @type {HTMLSelectElement} */ ($("#execution-mode"));
    this.modeBadge = $("#mode-badge");
    this.oauthPanel = /** @type {HTMLElement} */ ($("#oauth-panel"));
    this.getTokenBtn = /** @type {HTMLButtonElement} */ ($("#get-token-button"));
    this.oauthGetTokenBtn = /** @type {HTMLButtonElement} */ ($("#oauth-get-token-button"));
    this.usernameInput = /** @type {HTMLInputElement} */ ($("#conn-username"));
    this.usernameField = /** @type {HTMLElement} */ ($("#conn-username-field"));
    this.userBadge = /** @type {HTMLElement} */ ($("#user-identity-badge"));
    /** @type {?{host:string,tenant:string,username:string,mode:string,oauthOnly?:boolean,identity?:string|null,userSub?:string|null,userLogin?:string|null}} */
    this.state = null;

    this.form.addEventListener("submit", (e) => { e.preventDefault(); this.connect(); });
    this.disconnectBtn.addEventListener("click", () => this.disconnect());
    this.probeBtn.addEventListener("click", () => this.probe());
    this.modeSelect.addEventListener("change", () => {
      this._updateOAuthPanel();
      this.onModeChange();
    });
    $("#conn-host").addEventListener("input", () => this._updateOAuthPanel());
    $("#conn-tenant").addEventListener("input", () => this._updateOAuthPanel());
    this.getTokenBtn.addEventListener("click", () => this.getToken());
    this.oauthGetTokenBtn.addEventListener("click", () => this.getToken());
    this._updateOAuthPanel();
  }

  get username() { return this.state?.username || null; }

  _usesSkylabOAuth() {
    const host = this._normalizeHost($("#conn-host").value);
    return this.modeSelect.value === "live" && this._isSkylabHost(host);
  }

  _connectionStatusLabel(host, tenant, username, oauthOnly, identity, userSub) {
    if (oauthOnly) {
      if (identity && userSub) {
        return `Connected · ${identity} @ ${host} (${tenant})`;
      }
      if (userSub) {
        return `Connected · sub ${userSub} @ ${host} (${tenant})`;
      }
      return `Connected · OAuth → ${tenant}@${host}`;
    }
    return `Connected · ${username}@${host}`;
  }

  _renderUserBadge(identity, userSub) {
    if (!userSub && !identity) {
      this.userBadge.hidden = true;
      this.userBadge.textContent = "";
      return;
    }
    this.userBadge.hidden = false;
    const name = identity || "(name pending)";
    const subLine = userSub ? `sub: ${userSub}` : "";
    this.userBadge.innerHTML = [
      `<span class="user-name">${this._escapeHtml(name)}</span>`,
      subLine ? `<span class="user-sub">${this._escapeHtml(subLine)}</span>` : "",
    ].join("");
  }

  /** @param {string} text */
  _escapeHtml(text) {
    return text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  _statusTitle(oauthOnly, identity, userSub, userLogin) {
    if (!oauthOnly) return "";
    const parts = [];
    if (identity) parts.push(`User: ${identity}`);
    if (userLogin) parts.push(`Login: ${userLogin}`);
    if (userSub) parts.push(`sub: ${userSub}`);
    return parts.join(" · ");
  }

  async _enrichWithUserProfile(summary) {
    if (!summary.oauthOnly) return summary;
    try {
      const me = await api.getMe();
      if (me.connected) {
        return {
          ...summary,
          identity: me.label ?? me.displayName ?? summary.identity,
          userSub: me.sub ?? summary.userSub ?? null,
          userLogin: me.login ?? summary.userLogin ?? null,
        };
      }
    } catch { /* keep server connect/config summary */ }
    return summary;
  }
  get isConnected() { return this.state != null; }

  async loadConfig() {
    const cfg = await api.getConfig();
    this._applyMode(cfg.mode);
    this.modeSelect.value = cfg.mode;
    if (cfg.connected && cfg.host && cfg.tenant && cfg.username) {
      const summary = await this._enrichWithUserProfile({
        host: cfg.host,
        tenant: cfg.tenant,
        username: cfg.username,
        mode: cfg.mode,
        identity: cfg.identity ?? null,
        userSub: cfg.userSub ?? null,
        userLogin: cfg.userLogin ?? null,
        oauthOnly: cfg.oauthOnly ?? false,
      });
      this._restoreConnectedState(summary);
    } else {
      this._clearConnectedState();
    }
    this._updateOAuthPanel();
  }

  _restoreConnectedState(summary) {
    $("#conn-host").value = summary.host;
    $("#conn-tenant").value = summary.tenant;
    const oauthOnly = summary.oauthOnly ?? (
      summary.mode === "live" && this._isSkylabHost(summary.host)
    );
    const identity = summary.identity ?? null;
    if (oauthOnly && identity) {
      this.usernameInput.value = identity;
    } else if (oauthOnly && summary.userSub) {
      this.usernameInput.value = summary.userSub;
    } else {
      this.usernameInput.value = oauthOnly ? "" : summary.username;
    }
    this.state = {
      ...summary,
      oauthOnly,
      identity,
      userSub: summary.userSub ?? null,
      userLogin: summary.userLogin ?? null,
    };
    this._applyMode(summary.mode);
    this.modeSelect.value = summary.mode;
    this._setModeLocked(true);
    const statusText = this._connectionStatusLabel(
      summary.host,
      summary.tenant,
      summary.username,
      oauthOnly,
      identity,
      summary.userSub ?? null,
    );
    this._setStatus("connected", statusText);
    this.statusText.title = this._statusTitle(
      oauthOnly,
      identity,
      summary.userSub ?? null,
      summary.userLogin ?? null,
    );
    this._renderUserBadge(identity, summary.userSub ?? null);
    this.connectBtn.hidden = true;
    this.probeBtn.hidden = false;
    this.disconnectBtn.hidden = false;
    this.onChange(true);
  }

  _clearConnectedState() {
    if (this.state) return;
    this._setModeLocked(false);
    this.connectBtn.hidden = false;
    this.probeBtn.hidden = true;
    this.disconnectBtn.hidden = true;
    this._setStatus("disconnected", "Disconnected");
  }

  _applyMode(mode) {
    this.modeBadge.textContent = mode;
    this.modeBadge.dataset.mode = mode;
    this.modeBadge.title = mode === "live"
      ? "Live HTTP via HttpxTransport (credentials in memory only)"
      : "Mock transport — no network I/O";
  }

  async onModeChange() {
    if (this.isConnected) {
      this.modeSelect.value = this.state?.mode || "mock";
      toast("Disconnect before changing execution mode.", "error");
      return;
    }
    const mode = this.modeSelect.value;
    try {
      const cfg = await api.setMode(mode);
      this._applyMode(cfg.mode);
      this._updateOAuthPanel();
      toast(`Execution mode set to ${cfg.mode}.`, "info");
    } catch (err) {
      const e = /** @type {ApiError} */ (err);
      if (e.status === 409) {
        await this.loadConfig();
        if (this.isConnected) {
          this.modeSelect.value = this.state?.mode || "mock";
          toast("Still connected on the server — click Disconnect, then change mode.", "error");
          return;
        }
      }
      toast(e.message || "Could not change mode.", "error");
      await this.loadConfig();
    }
  }

  _setModeLocked(locked) {
    this.modeSelect.disabled = locked;
  }

  _isSkylabHost(host) {
    const h = (host || "").toLowerCase();
    return h.includes("skylab") || h.endsWith(".inday.io");
  }

  _normalizeHost(raw) {
    let host = (raw || "").trim();
    for (const scheme of ["https://", "http://"]) {
      if (host.toLowerCase().startsWith(scheme)) host = host.slice(scheme.length);
    }
    host = host.split("/")[0].split("?")[0];
    return host.replace(/\/+$/, "");
  }

  _setConnectedUi(connected) {
    this.form.classList.toggle("is-connected", connected);
  }

  _updateOAuthPanel() {
    const host = this._normalizeHost($("#conn-host").value);
    const mode = this.modeSelect.value;
    const pw = $("#conn-password");
    const skylabOAuth = mode === "live" && this._isSkylabHost(host);
    this._setConnectedUi(this.isConnected);
    this.oauthPanel.hidden = !(skylabOAuth && !this.isConnected);
    if (skylabOAuth) {
      this.usernameInput.disabled = true;
      this.usernameField.classList.add("is-inactive");
      if (!this.isConnected) {
        this.usernameInput.value = "";
        this.usernameInput.placeholder = "Not used — identity is in the Bearer token";
      } else if (this.state?.identity) {
        this.usernameInput.value = this.state.identity;
        this.usernameInput.placeholder = "Logged-in user (from Bearer token)";
      }
      this.usernameInput.title = "SkyLab Live uses OAuth Bearer only. User identity is read from the token.";
      pw.placeholder = "Bearer <OAuth access token>";
      pw.title = "Click Get token, or paste Bearer … manually.";
    } else {
      this.usernameInput.disabled = this.isConnected;
      this.usernameField.classList.remove("is-inactive");
      this.usernameInput.placeholder = "persona / user";
      this.usernameInput.title = "";
      pw.placeholder = "SUV password";
      pw.title = "";
    }
  }

  async getToken() {
    const host = this._normalizeHost($("#conn-host").value);
    if (host !== $("#conn-host").value.trim()) {
      $("#conn-host").value = host;
    }
    const payload = {
      host,
      tenant: $("#conn-tenant").value.trim(),
      client_id: $("#oauth-client-id").value.trim(),
      client_secret: $("#oauth-client-secret").value,
      refresh_token: $("#oauth-refresh-token").value,
    };
    if (!payload.host || !payload.tenant) {
      toast("Enter host and tenant first.", "error");
      return;
    }
    if (this.oauthPanel.hidden) {
      this.oauthPanel.hidden = false;
      this._updateOAuthPanel();
    }
    if (!payload.client_id || !payload.client_secret || !payload.refresh_token) {
      toast("Fill in OAuth client ID, secret, and refresh token below.", "error");
      return;
    }
    this.getTokenBtn.disabled = true;
    this.oauthGetTokenBtn.disabled = true;
    try {
      const res = await api.getToken(payload);
      $("#conn-password").value = res.authorization;
      $("#oauth-client-secret").value = "";
      $("#oauth-refresh-token").value = "";
      toast(res.message, "success");
    } catch (err) {
      const e = /** @type {ApiError} */ (err);
      toast(e.message || "Token exchange failed.", "error");
    } finally {
      this.getTokenBtn.disabled = false;
      this.oauthGetTokenBtn.disabled = false;
    }
  }

  async probe() {
    this.probeBtn.disabled = true;
    try {
      const res = await api.probeUpstream();
      const lines = res.probes
        .map((p) => {
          const hint = p.errorHint ? ` — ${p.errorHint}` : "";
          return `${p.name}: HTTP ${p.status}${hint}`;
        })
        .join(" · ");
      toast(`${res.summary} (${lines})`, "info");
    } catch (err) {
      const e = /** @type {ApiError} */ (err);
      toast(e.message || "Probe failed.", "error");
    } finally {
      this.probeBtn.disabled = false;
    }
  }

  _setStatus(stateName, text) {
    this.statusDot.dataset.state = stateName;
    this.statusText.textContent = text;
  }

  async connect() {
    const host = this._normalizeHost($("#conn-host").value);
    if (host !== $("#conn-host").value.trim()) {
      $("#conn-host").value = host;
    }
    const skylabOAuth = this._usesSkylabOAuth();
    const payload = {
      host,
      tenant: $("#conn-tenant").value.trim(),
      username: skylabOAuth ? "oauth" : this.usernameInput.value.trim(),
      password: $("#conn-password").value,
    };
    if (!payload.host || !payload.tenant || !payload.password) {
      toast("Please fill in host, tenant, and password (Bearer on SkyLab).", "error");
      return;
    }
    if (!skylabOAuth && !payload.username) {
      toast("Please fill in username for SUV login.", "error");
      return;
    }
    if (skylabOAuth) {
      const previewSub = extractSubFromPasswordField(payload.password);
      if (!previewSub) {
        toast("Could not read user ID (sub) from Bearer token — paste a valid JWT.", "error");
        return;
      }
    }
    this._setStatus("connecting", "Connecting…");
    this.connectBtn.disabled = true;
    this._setModeLocked(true);
    try {
      const res = await api.connect(payload);
      const summary = await this._enrichWithUserProfile({
        host: res.host,
        tenant: res.tenant,
        username: res.username,
        mode: res.mode,
        oauthOnly: skylabOAuth,
        identity: res.identity ?? null,
        userSub: res.userSub ?? null,
        userLogin: res.userLogin ?? null,
      });
      this.state = summary;
      this._applyMode(res.mode);
      this.modeSelect.value = res.mode;
      const statusText = this._connectionStatusLabel(
        res.host,
        res.tenant,
        res.username,
        skylabOAuth,
        summary.identity ?? null,
        summary.userSub ?? null,
      );
      this._setStatus("connected", statusText);
      this.statusText.title = this._statusTitle(
        skylabOAuth,
        summary.identity ?? null,
        summary.userSub ?? null,
        summary.userLogin ?? null,
      );
      this._renderUserBadge(summary.identity ?? null, summary.userSub ?? null);
      this.connectBtn.hidden = true;
      this.probeBtn.hidden = false;
      this.disconnectBtn.hidden = false;
      $("#conn-password").value = "";
      toast(res.message, "success");
      this.onChange(true);
      this._updateOAuthPanel();
    } catch (err) {
      const e = /** @type {ApiError} */ (err);
      this._setStatus("disconnected", "Disconnected");
      toast(e.message || "Connection failed.", "error");
    } finally {
      this.connectBtn.disabled = false;
      if (!this.isConnected) this._setModeLocked(false);
    }
  }

  async disconnect() {
    try { await api.disconnect(); } catch { /* best effort */ }
    this.state = null;
    this._setStatus("disconnected", "Disconnected");
    this.connectBtn.hidden = false;
    this.probeBtn.hidden = true;
    this.disconnectBtn.hidden = true;
    this._setModeLocked(false);
    this.userBadge.hidden = true;
    this.userBadge.textContent = "";
    this.onChange(false);
    this._updateOAuthPanel();
  }
}
