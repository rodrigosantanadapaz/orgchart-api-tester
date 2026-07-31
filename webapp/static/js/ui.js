// Shared UI utilities: toasts and the loading overlay.
import { $, el } from "./dom.js";

let overlayCount = 0;
const VISIBLE_CLASS = "is-visible";

export function showLoading() {
  overlayCount += 1;
  const node = $("#loading");
  node.classList.add(VISIBLE_CLASS);
  node.setAttribute("aria-hidden", "false");
}

export function hideLoading() {
  overlayCount = Math.max(0, overlayCount - 1);
  if (overlayCount === 0) {
    const node = $("#loading");
    node.classList.remove(VISIBLE_CLASS);
    node.setAttribute("aria-hidden", "true");
  }
}

/**
 * @param {string} message
 * @param {"info"|"error"|"success"} [kind]
 */
export function toast(message, kind = "info") {
  const host = $("#toast-host");
  const node = el("div", { class: `toast ${kind}` }, [message]);
  host.append(node);
  setTimeout(() => {
    node.style.opacity = "0";
    setTimeout(() => node.remove(), 200);
  }, 3800);
}
