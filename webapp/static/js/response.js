// Right panel: renders the response (or a friendly error) and supports copy.
import { clear, el } from "./dom.js";

/** Escape + syntax-highlight a JSON value into HTML. */
function highlightJson(value) {
  const json = JSON.stringify(value, null, 2);
  const escaped = json
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  return escaped.replace(
    /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false)\b|\bnull\b|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)/g,
    (match) => {
      let cls = "tok-number";
      if (/^"/.test(match)) cls = /:$/.test(match) ? "tok-key" : "tok-string";
      else if (/true|false/.test(match)) cls = "tok-bool";
      else if (/null/.test(match)) cls = "tok-null";
      return `<span class="${cls}">${match}</span>`;
    },
  );
}

function statusClass(status) {
  if (status >= 200 && status < 300) return "status-2xx";
  if (status >= 400 && status < 500) return "status-4xx";
  if (status >= 500) return "status-5xx";
  return "";
}

function kvList(obj) {
  const rows = [];
  for (const [k, v] of Object.entries(obj || {})) {
    rows.push(el("span", { class: "kk" }, [k]));
    rows.push(el("span", { class: "vv" }, [String(v)]));
  }
  return el("div", { class: "kv-list" }, rows.length ? rows : [el("span", { class: "kk" }, ["(none)"])]);
}

function upstreamStatus(result) {
  return result.upstreamStatus ?? result.status;
}

function proxyStatus(result) {
  return result.proxyHttpStatus ?? 200;
}

function upstreamOk(result) {
  if (typeof result.upstreamOk === "boolean") return result.upstreamOk;
  const code = upstreamStatus(result);
  return code >= 200 && code < 300;
}

function diagnosticHints(result) {
  const hints = [];
  const upstream = upstreamStatus(result);
  const hdrs = Object.fromEntries(
    Object.entries(result.responseHeaders || {}).map(([k, v]) => [k.toLowerCase(), v]),
  );

  if (!upstreamOk(result)) {
    hints.push(
      `Skylab returned HTTP ${upstream}. POST /api/execute returned HTTP ${proxyStatus(result)} `
      + "only because the local tester proxy completed — that is not an upstream success.",
    );
  }

  if (upstream === 400 && !hdrs["wd-stat-request-id"]) {
    hints.push(
      "No wd-stat-request-id header — rejection likely at the API gateway before the orgchart service.",
    );
  }

  if (hdrs["wd-stat-request-id"]) {
    hints.push(`wd-stat-request-id: ${hdrs["wd-stat-request-id"]}`);
  }

  return hints;
}

export class ResponseView {
  /** @param {HTMLElement} container @param {HTMLElement} copyButton */
  constructor(container, copyButton) {
    this.container = container;
    this.copyButton = copyButton;
    this._lastBody = null;
    copyButton.addEventListener("click", () => this._copy());
  }

  /** @param {import("./types.js").ExecuteResult} result */
  render(result) {
    clear(this.container);
    this._lastBody = result.body;
    this.copyButton.hidden = false;

    const upstream = upstreamStatus(result);
    const ok = upstreamOk(result);
    const hints = diagnosticHints(result);

    const summary = el("div", { class: "resp-summary" }, [
      this._chip("Proxy (POST /api/execute)", String(proxyStatus(result)), statusClass(proxyStatus(result))),
      this._chip("Upstream (Skylab)", String(upstream), statusClass(upstream)),
      this._chip("Upstream result", ok ? "OK" : "FAILED", ok ? "status-2xx" : "status-4xx"),
      this._chip("Time", `${result.durationMs.toFixed(1)} ms`),
      this._chip("Method", result.method),
      this._chip("Persona", result.persona || "—"),
    ]);

    const nodes = [summary];

    if (!ok) {
      nodes.push(
        el("div", { class: "upstream-alert", role: "alert" }, [
          el("strong", {}, [`Upstream HTTP ${upstream} — not a successful Org Chart API call.`]),
          el("p", {}, [
            "The browser Network tab may show HTTP 200 for POST /api/execute. "
            + "That status is the local tester proxy only.",
          ]),
        ]),
      );
    }

    if (hints.length) {
      nodes.push(
        this._section(
          "Diagnostics",
          el("ul", { class: "diag-list" }, hints.map((h) => el("li", {}, [h]))),
        ),
      );
    }

    const queryText = (result.query || [])
      .map(([k, v]) => `${k}=${v}`)
      .join("&");

    nodes.push(
      this._section("Upstream URL", el("pre", { class: "code-block url-block" }, [result.url])),
      this._section(
        "Query string",
        el("pre", { class: "code-block" }, [queryText || "(none)"]),
      ),
      this._section("Request headers (safe)", kvList(result.requestHeaders)),
      this._section("Response headers", kvList(result.responseHeaders)),
      this._section(
        "Response body",
        el("pre", { class: "code-block", innerHTML: highlightJson(result.body) }),
      ),
    );

    this.container.append(...nodes);
  }

  /** @param {import("./api.js").ApiError} err */
  renderError(err) {
    clear(this.container);
    this.copyButton.hidden = true;
    const details = (err.detail || []).map((d) => el("li", {}, [d]));
    this.container.append(
      el("div", { class: "error-box" }, [
        el("div", { class: "title" }, [err.status ? `${err.message} (${err.status})` : err.message]),
        details.length ? el("ul", {}, details) : null,
      ]),
    );
  }

  _section(title, node) {
    return el("div", { class: "resp-section" }, [el("h4", {}, [title]), node]);
  }

  _chip(k, v, cls = "") {
    return el("div", { class: "resp-chip" }, [
      el("span", { class: "k" }, [k]),
      el("span", { class: `v ${cls}` }, [v]),
    ]);
  }

  async _copy() {
    if (this._lastBody == null) return;
    try {
      await navigator.clipboard.writeText(JSON.stringify(this._lastBody, null, 2));
      this.copyButton.textContent = "Copied!";
      setTimeout(() => { this.copyButton.textContent = "Copy response"; }, 1400);
    } catch {
      this.copyButton.textContent = "Copy failed";
      setTimeout(() => { this.copyButton.textContent = "Copy response"; }, 1400);
    }
  }
}
