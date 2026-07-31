// Left navigation: renders the endpoint catalog grouped by category.
import { clear, el } from "./dom.js";

const CATEGORY_LABELS = {
  navigables: "Navigables",
  hierarchy: "Hierarchy",
  prompts: "Prompts",
};

export class CatalogNav {
  /**
   * @param {HTMLElement} container
   * @param {(endpointId:string)=>void} onSelect
   */
  constructor(container, onSelect) {
    this.container = container;
    this.onSelect = onSelect;
    /** @type {import("./types.js").Catalog} */
    this.catalog = { categories: [], endpoints: [] };
    this.filter = "";
    this.activeId = null;
  }

  /** @param {import("./types.js").Catalog} catalog */
  setCatalog(catalog) {
    this.catalog = catalog;
    this.render();
  }

  setFilter(text) {
    this.filter = text.trim().toLowerCase();
    this.render();
  }

  setActive(endpointId) {
    this.activeId = endpointId;
    this.container.querySelectorAll(".endpoint-item").forEach((node) => {
      node.classList.toggle("active", node.dataset.id === endpointId);
      node.setAttribute("aria-selected", node.dataset.id === endpointId ? "true" : "false");
    });
  }

  _matches(ep) {
    if (!this.filter) return true;
    return (
      ep.id.toLowerCase().includes(this.filter) ||
      ep.path.toLowerCase().includes(this.filter) ||
      ep.summary.toLowerCase().includes(this.filter)
    );
  }

  render() {
    clear(this.container);
    const { categories, endpoints } = this.catalog;
    let shown = 0;
    for (const category of categories) {
      const items = endpoints.filter((e) => e.category === category && this._matches(e));
      if (items.length === 0) continue;
      shown += items.length;
      const group = el("div", { class: "category-group" }, [
        el("div", { class: "category-title" }, [CATEGORY_LABELS[category] || category]),
        ...items.map((ep) => this._item(ep)),
      ]);
      this.container.append(group);
    }
    if (shown === 0) {
      this.container.append(el("div", { class: "empty-hint" }, ["No endpoints match your filter."]));
    } else if (this.activeId) {
      this.setActive(this.activeId);
    }
  }

  /** @param {import("./types.js").Endpoint} ep */
  _item(ep) {
    const item = el("button", {
      class: "endpoint-item",
      type: "button",
      role: "option",
      dataset: { id: ep.id },
      onClick: () => this.onSelect(ep.id),
    }, [
      el("div", { class: "endpoint-row" }, [
        el("span", { class: "method-badge" }, [ep.method]),
        el("span", { class: "endpoint-path", title: ep.path }, [ep.path]),
      ]),
      el("div", { class: "endpoint-desc" }, [ep.summary || ep.description || ""]),
    ]);
    return item;
  }
}
