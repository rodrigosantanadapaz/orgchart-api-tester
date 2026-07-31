// Shared JSDoc type definitions (strong typing without a build step).

/**
 * @typedef {Object} Param
 * @property {string} name
 * @property {"path"|"query"} location
 * @property {boolean} required
 * @property {boolean} repeatable
 * @property {string} description
 * @property {string} example
 */

/**
 * @typedef {Object} Endpoint
 * @property {string} id
 * @property {string} method
 * @property {string} path
 * @property {string} category
 * @property {string} summary
 * @property {string} description
 * @property {Param[]} params
 * @property {?Object} request_body
 * @property {string} response_type
 */

/**
 * @typedef {Object} Catalog
 * @property {string[]} categories
 * @property {Endpoint[]} endpoints
 */

/**
 * @typedef {Object} ExecuteResult
 * @property {string} timestamp
 * @property {string} endpointId
 * @property {?string} persona
 * @property {number} status upstream Skylab HTTP status (legacy alias)
 * @property {number} upstreamStatus
 * @property {number} proxyHttpStatus local POST /api/execute HTTP status
 * @property {boolean} upstreamOk
 * @property {number} durationMs
 * @property {string} method
 * @property {string} url
 * @property {Object<string,string>} requestHeaders
 * @property {Object<string,string>} responseHeaders
 * @property {Array<[string,string]>} query
 * @property {*} body
 */

/**
 * @typedef {Object} HistoryEntry
 * @property {string} id
 * @property {string} endpointId
 * @property {Object<string,*>} parameters
 * @property {?string} persona
 * @property {ExecuteResult} result
 */

export {};
