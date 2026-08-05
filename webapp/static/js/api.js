// Typed wrappers around the backend API. The UI never builds Org Chart URLs;
// it only calls these endpoints, which delegate to the frozen engine.

/** Error carrying a friendly message plus optional detail lines. */
export class ApiError extends Error {
  /** @param {string} message @param {string[]} [detail] @param {number} [status] */
  constructor(message, detail = [], status = 0) {
    super(message);
    this.name = "ApiError";
    this.detail = detail;
    this.status = status;
  }
}

/**
 * @param {string} url
 * @param {RequestInit} [options]
 * @returns {Promise<any>}
 */
async function request(url, options = {}) {
  let resp;
  try {
    resp = await fetch(url, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
  } catch (networkErr) {
    throw new ApiError("Could not reach the server.", [String(networkErr)]);
  }
  const text = await resp.text();
  const data = text ? JSON.parse(text) : {};
  if (!resp.ok) {
    const message = data.error || `Request failed (${resp.status}).`;
    throw new ApiError(message, data.detail || [], resp.status);
  }
  return data;
}

/** @returns {Promise<import("./types.js").Catalog>} */
export function getCatalog() {
  return request("/api/catalog");
}

/** @returns {Promise<{mode:string,modes:string[],connected?:boolean,identity?:string,userSub?:string,userLogin?:string,oauthOnly?:boolean}>} */
export function getConfig() {
  return request("/api/config");
}

/** @returns {Promise<{connected:boolean,sub?:string,displayName?:string,login?:string,label?:string}>} */
export function getMe() {
  return request("/api/me");
}

/** @param {"mock"|"live"} mode */
export function setMode(mode) {
  return request("/api/mode", { method: "POST", body: JSON.stringify({ mode }) });
}

/** @param {{host:string,tenant:string,username:string,password:string}} payload */
export function connect(payload) {
  return request("/api/connect", { method: "POST", body: JSON.stringify(payload) });
}

export function disconnect() {
  return request("/api/disconnect", { method: "POST" });
}

/**
 * @param {{host:string,tenant:string,client_id:string,client_secret:string,refresh_token:string}} payload
 * @returns {Promise<{authorization:string,expiresIn:?number,message:string}>}
 */
export function getToken(payload) {
  return request("/api/token", { method: "POST", body: JSON.stringify(payload) });
}

/** @returns {Promise<{host:string,tenant:string,probes:Array,summary:string}>} */
export function probeUpstream() {
  return request("/api/probe", { method: "POST" });
}

/**
 * @param {{endpoint_id:string, parameters:Object<string,*>, persona:?string}} payload
 * @returns {Promise<import("./types.js").ExecuteResult>}
 */
export function execute(payload) {
  return request("/api/execute", { method: "POST", body: JSON.stringify(payload) });
}
