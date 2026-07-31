// Tiny DOM helpers.

/**
 * Create an element with props and children.
 * @param {string} tag
 * @param {Object} [props]
 * @param {(Node|string)[]} [children]
 * @returns {HTMLElement}
 */
export function el(tag, props = {}, children = []) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (value == null) continue;
    if (key === "class") node.className = value;
    else if (key === "dataset") Object.assign(node.dataset, value);
    else if (key === "hidden") node.hidden = Boolean(value);
    else if (key.startsWith("on") && typeof value === "function") {
      node.addEventListener(key.slice(2).toLowerCase(), value);
    } else if (key in node) {
      // @ts-ignore - permissive assignment
      node[key] = value;
    } else {
      node.setAttribute(key, String(value));
    }
  }
  for (const child of [].concat(children)) {
    if (child == null) continue;
    node.append(child.nodeType ? child : document.createTextNode(String(child)));
  }
  return node;
}

/** @param {string} sel @returns {HTMLElement} */
export function $(sel) {
  const node = document.querySelector(sel);
  if (!node) throw new Error(`element not found: ${sel}`);
  return /** @type {HTMLElement} */ (node);
}

export function clear(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
}
