// Bottom panel: in-memory session history. Clicking an entry reloads its
// request + response via the provided callback.
import { clear, el } from "./dom.js";

export class History {
  /**
   * @param {HTMLElement} tbody
   * @param {HTMLElement} countLabel
   * @param {(entry:import("./types.js").HistoryEntry)=>void} onReload
   */
  constructor(tbody, countLabel, onReload) {
    this.tbody = tbody;
    this.countLabel = countLabel;
    this.onReload = onReload;
    /** @type {import("./types.js").HistoryEntry[]} */
    this.entries = [];
  }

  /**
   * @param {string} endpointId
   * @param {Object<string,*>} parameters
   * @param {import("./types.js").ExecuteResult} result
   */
  add(endpointId, parameters, result) {
    /** @type {import("./types.js").HistoryEntry} */
    const entry = {
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      endpointId,
      parameters,
      persona: result.persona,
      result,
    };
    this.entries.unshift(entry);
    this.render();
  }

  clearAll() {
    this.entries = [];
    this.render();
  }

  render() {
    clear(this.tbody);
    this.countLabel.textContent = this.entries.length ? `(${this.entries.length})` : "";
    if (this.entries.length === 0) {
      this.tbody.append(
        el("tr", { class: "empty-row" }, [el("td", { colSpan: 5 }, ["No requests yet this session."])]),
      );
      return;
    }
    for (const entry of this.entries) {
      const t = new Date(entry.result.timestamp);
      const time = isNaN(t.getTime()) ? entry.result.timestamp : t.toLocaleTimeString();
      const upstream = entry.result.upstreamStatus ?? entry.result.status;
      const ok = typeof entry.result.upstreamOk === "boolean"
        ? entry.result.upstreamOk
        : upstream >= 200 && upstream < 300;
      const statusCls = ok ? "status-2xx" : "status-4xx";
      const row = el("tr", { class: "history-row", onClick: () => this.onReload(entry) }, [
        el("td", { class: "mono" }, [time]),
        el("td", { class: "mono" }, [entry.endpointId]),
        el("td", {}, [entry.persona || "—"]),
        el("td", { class: `mono ${statusCls}` }, [String(upstream)]),
        el("td", { class: "mono" }, [`${entry.result.durationMs.toFixed(1)} ms`]),
      ]);
      this.tbody.append(row);
    }
  }
}
