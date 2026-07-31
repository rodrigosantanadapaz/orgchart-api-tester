// Center panel: builds a request form dynamically from endpoint metadata and
// collects/validates parameter values. Knows nothing about URLs.
import { clear, el } from "./dom.js";

export class RequestForm {
  /** @param {HTMLElement} container */
  constructor(container) {
    this.container = container;
    /** @type {?import("./types.js").Endpoint} */
    this.endpoint = null;
  }

  /**
   * @param {import("./types.js").Endpoint} endpoint
   * @param {Object<string,*>} [values] pre-filled values (history reload)
   */
  render(endpoint, values = {}) {
    this.endpoint = endpoint;
    clear(this.container);

    const pathParams = endpoint.params.filter((p) => p.location === "path");
    const queryParams = endpoint.params.filter((p) => p.location === "query");

    if (endpoint.description) {
      this.container.append(el("p", { class: "param-desc" }, [endpoint.description]));
    }
    if (endpoint.id === "list_navigables") {
      this.container.append(el("p", { class: "endpoint-advisory" }, [
        "On the SUV internal API surface, GET /navigables (no ID) often returns a "
        + "server error (S23). Use Prompt: organizations/workers to find IDs, then "
        + "GET /navigables/{ID} or /children instead.",
      ]));
    }
    if (pathParams.length) {
      this.container.append(
        el("div", { class: "param-group" }, [
          el("h3", {}, ["Path parameters"]),
          ...pathParams.map((p) => this._field(p, values[p.name])),
        ]),
      );
    }
    if (queryParams.length) {
      this.container.append(
        el("div", { class: "param-group" }, [
          el("h3", {}, ["Query parameters"]),
          ...queryParams.map((p) => this._field(p, values[p.name])),
        ]),
      );
    }
    if (!pathParams.length && !queryParams.length) {
      this.container.append(el("div", { class: "empty-hint" }, ["This endpoint takes no parameters."]));
    }
  }

  /** @param {import("./types.js").Param} param */
  _field(param, value) {
    const label = el("div", { class: "param-label" }, [
      el("span", { class: "param-name" }, [param.name]),
      param.required ? el("span", { class: "req-star", title: "required" }, ["*"]) : null,
      param.repeatable ? el("span", { class: "repeat-badge", title: "repeatable" }, ["repeat"]) : null,
    ]);
    const children = [label];
    if (param.description) children.push(el("div", { class: "param-desc" }, [param.description]));

    const wrap = el("div", { class: "param-field", dataset: { name: param.name, location: param.location, repeatable: String(param.repeatable) } }, children);

    if (param.repeatable) {
      const list = el("div", { class: "repeat-list" });
      const initial = Array.isArray(value) ? value : value != null ? [value] : [""];
      initial.forEach((v) => list.append(this._repeatRow(param, v)));
      wrap.append(list);
      wrap.append(el("button", {
        class: "btn btn-ghost btn-small add-repeat", type: "button",
        onClick: () => list.append(this._repeatRow(param, "")),
      }, ["+ Add value"]));
    } else {
      wrap.append(el("input", {
        class: "param-input", type: "text",
        value: value != null ? String(value) : "",
        placeholder: param.example || "",
        dataset: { input: "single" },
      }));
      wrap.append(el("div", { class: "field-error", hidden: true }));
    }
    return wrap;
  }

  _repeatRow(param, value) {
    const input = el("input", {
      class: "param-input", type: "text",
      value: value != null ? String(value) : "",
      placeholder: param.example || "",
      dataset: { input: "repeat" },
    });
    return el("div", { class: "repeat-row" }, [
      input,
      el("button", { class: "icon-btn", type: "button", title: "Remove",
        onClick: (e) => e.target.closest(".repeat-row").remove() }, ["\u2212"]),
    ]);
  }

  /**
   * Collect the current values into an engine-ready parameters object.
   * @returns {Object<string,*>}
   */
  collect() {
    /** @type {Object<string,*>} */
    const params = {};
    this.container.querySelectorAll(".param-field").forEach((field) => {
      const name = field.dataset.name;
      if (field.dataset.repeatable === "true") {
        const values = [...field.querySelectorAll('[data-input="repeat"]')]
          .map((i) => i.value.trim())
          .filter((v) => v !== "");
        if (values.length) params[name] = values;
      } else {
        const input = field.querySelector('[data-input="single"]');
        const val = input.value.trim();
        if (val !== "") params[name] = val;
      }
    });
    return params;
  }

  /**
   * Validate required params client-side. Returns list of error messages and
   * marks invalid inputs.
   * @returns {string[]}
   */
  validate() {
    const errors = [];
    this.container.querySelectorAll(".field-error").forEach((n) => { n.hidden = true; });
    this.container.querySelectorAll(".param-input").forEach((n) => n.classList.remove("invalid"));

    (this.endpoint?.params || []).forEach((param) => {
      if (!param.required) return;
      const field = this.container.querySelector(`.param-field[data-name="${param.name}"]`);
      if (!field) return;
      const input = field.querySelector(".param-input");
      const empty = param.repeatable
        ? [...field.querySelectorAll(".param-input")].every((i) => i.value.trim() === "")
        : input.value.trim() === "";
      if (empty) {
        errors.push(`"${param.name}" is required.`);
        input.classList.add("invalid");
        const err = field.querySelector(".field-error");
        if (err) { err.textContent = "Required."; err.hidden = false; }
      }
    });
    return errors;
  }

  reset() {
    if (this.endpoint) this.render(this.endpoint, {});
  }
}
