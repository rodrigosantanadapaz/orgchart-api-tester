// Entry point: loads the catalog and wires the panels together.
import * as api from "./api.js";
import { ApiError } from "./api.js";
import { $ } from "./dom.js";
import { showLoading, hideLoading, toast } from "./ui.js";
import { CatalogNav } from "./catalog.js";
import { RequestForm } from "./form.js";
import { ResponseView } from "./response.js";
import { History } from "./history.js";
import { Connection } from "./connection.js";

class App {
  constructor() {
    /** @type {import("./types.js").Catalog} */
    this.catalog = { categories: [], endpoints: [] };
    this.byId = new Map();
    this.currentId = null;

    this.nav = new CatalogNav($("#endpoint-list"), (id) => this.selectEndpoint(id));
    this.form = new RequestForm($("#form-container"));
    this.response = new ResponseView($("#response-container"), $("#copy-button"));
    this.history = new History($("#history-body"), $("#history-count"), (e) => this.reload(e));
    this.connection = new Connection((connected) => this.onConnectionChange(connected));

    this.formActions = $("#form-actions");
    this.endpointTag = $("#form-endpoint-tag");
    this.sendBtn = $("#send-button");
    this.resetBtn = $("#reset-button");

    this.sendBtn.addEventListener("click", () => this.send());
    this.resetBtn.addEventListener("click", () => this.form.reset());
    $("#clear-history").addEventListener("click", () => this.history.clearAll());
    $("#endpoint-filter").addEventListener("input", (e) => this.nav.setFilter(e.target.value));

    document.addEventListener("keydown", (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter") { e.preventDefault(); this.send(); }
    });
  }

  async init() {
    showLoading();
    try {
      const [, catalog] = await Promise.all([
        this.connection.loadConfig(),
        api.getCatalog(),
      ]);
      this.catalog = catalog;
      this.byId = new Map(this.catalog.endpoints.map((e) => [e.id, e]));
      this.nav.setCatalog(this.catalog);
    } catch (err) {
      toast(/** @type {ApiError} */ (err).message || "Failed to load catalog.", "error");
    } finally {
      hideLoading();
    }
  }

  onConnectionChange(connected) {
    this._updateSendState();
    if (!connected) toast("Disconnected.", "info");
  }

  _updateSendState() {
    const ready = this.connection.isConnected && this.currentId != null;
    this.sendBtn.disabled = !ready;
    this.sendBtn.title = this.connection.isConnected ? "" : "Connect first";
  }

  /** @param {string} id @param {Object<string,*>} [values] */
  selectEndpoint(id, values = {}) {
    const ep = this.byId.get(id);
    if (!ep) return;
    this.currentId = id;
    this.nav.setActive(id);
    this.form.render(ep, values);
    this.endpointTag.hidden = false;
    this.endpointTag.textContent = `${ep.method} ${ep.path}`;
    this.formActions.hidden = false;
    this._updateSendState();
  }

  async send() {
    if (!this.currentId) { toast("Select an endpoint first.", "error"); return; }
    if (!this.connection.isConnected) { toast("Connect to a host first.", "error"); return; }
    const errors = this.form.validate();
    if (errors.length) { toast(errors[0], "error"); return; }

    const parameters = this.form.collect();
    showLoading();
    try {
      const result = await api.execute({
        endpoint_id: this.currentId,
        parameters,
        persona: this.connection.state?.oauthOnly
          ? "OAuth token"
          : this.connection.username,
      });
      this.response.render(result);
      this.history.add(this.currentId, parameters, result);
      const upstream = result.upstreamStatus ?? result.status;
      if (upstream < 200 || upstream >= 300) {
        toast(`Skylab returned HTTP ${upstream} — upstream call failed.`, "error");
      }
    } catch (err) {
      const e = /** @type {ApiError} */ (err);
      this.response.renderError(e);
      toast(e.message || "Request failed.", "error");
    } finally {
      hideLoading();
    }
  }

  /** @param {import("./types.js").HistoryEntry} entry */
  reload(entry) {
    this.selectEndpoint(entry.endpointId, entry.parameters);
    this.response.render(entry.result);
    toast("Reloaded request from history.", "info");
  }
}

const app = new App();
app.init();
