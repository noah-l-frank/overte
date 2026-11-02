"use strict";
// SPDX-License-Identifier: Apache-2.0
// Execute the full shipped module; only the native XMLHttpRequest is substituted.
const assert = require("node:assert/strict");
const path = require("node:path");
const test = require("node:test");
const { runProductionScript } = require("../support");

function start() {
    const requests = [];
    class NativeRequestBoundary {
        constructor() { this.headers = {}; this.readyState = 0; requests.push(this); }
        setRequestHeader(key, value) { this.headers[key] = value; }
        open(method, url, asynchronous) { this.opened = { method, url, asynchronous }; }
        send(body) { this.sent = body; }
        getResponseHeader(key) { assert.equal(key, "content-type"); return this.contentType; }
        complete(status = 200, text = "ok", contentType = "text/plain", statusText = "OK") {
            Object.assign(this, { readyState: 4, status, responseText: text, contentType, statusText });
            if (this.onreadystatechange) this.onreadystatechange();
        }
    }
    const module = { exports: {} };
    runProductionScript(path.resolve(__dirname, "../../../scripts/modules/request.js"), {
        module, XMLHttpRequest: NativeRequestBoundary, print() {}
    });
    return { request: module.exports.request, requests };
}

test("real connection polling GET serializes node IDs without an existing query", () => {
    const h = start(), received = [];
    const options = { uri: "https://example.invalid/api/v1/user/connection_request", method: "GET",
        body: { node_id: "self-node", proposed_node_id: "peer-node" } };
    h.request(options, (...args) => received.push(args));
    const xhr = h.requests[0];
    assert.deepEqual(xhr.opened, { method: "GET", asynchronous: true,
        url: "https://example.invalid/api/v1/user/connection_request?node_id=self-node&proposed_node_id=peer-node" });
    assert.equal(xhr.sent, null);
    assert.equal(Object.hasOwn(options, "body"), false);
    xhr.complete(200, '{"status":"pending"}', "application/json; charset=utf-8");
    assert.equal(received[0][0], false);
    assert.equal(received[0][1].status, "pending");
});

test("GET appends to an existing query and preserves already encoded input", () => {
    const h = start();
    h.request({ url: "https://example.invalid/poll?existing=one%20two", method: "GET",
        body: { "key%20name": "a%26b%3Dc", node_id: "uuid-123" } }, () => {});
    assert.equal(h.requests[0].opened.url,
        "https://example.invalid/poll?existing=one%20two&key%20name=a%26b%3Dc&node_id=uuid-123");
    assert.equal(h.requests[0].sent, null);
});

test("default GET includes only own body fields and preserves headers and callback context", () => {
    const h = start(), received = [], token = { caller: "connection poll" };
    const body = Object.assign(Object.create({ inherited: "omit" }), { node_id: "self" });
    const result = h.request({ uri: "https://example.invalid/poll", body,
        headers: { Authorization: "Bearer fixture-token", "X-Caller": "fixture" } },
    (...args) => received.push(args), token);
    assert.equal(result, undefined);
    assert.equal(h.requests[0].opened.url, "https://example.invalid/poll?node_id=self");
    assert.deepEqual(h.requests[0].headers,
        { Authorization: "Bearer fixture-token", "X-Caller": "fixture" });
    h.requests[0].complete();
    assert.deepEqual(received, [[false, "ok", token]]);
    assert.equal(h.requests[0].onreadystatechange, null);
});

test("string options keep ordinary GET and asynchronous dispatch", () => {
    const h = start();
    h.request("https://example.invalid/plain", () => {});
    assert.deepEqual(h.requests[0].opened,
        { method: "GET", url: "https://example.invalid/plain", asynchronous: true });
    assert.equal(h.requests[0].sent, null);
});

test("connection POST JSON retains method, body, headers and successful response parsing", () => {
    const h = start(), received = [], body = { user_connection_request: { node_id: "self", proposed_node_id: "peer" } };
    h.request({ uri: "https://example.invalid/connection_request", method: "POST", json: true, body,
        headers: { Authorization: "Bearer fixture-token" } }, (...args) => received.push(args));
    const xhr = h.requests[0];
    assert.equal(xhr.opened.method, "POST");
    assert.equal(xhr.opened.url, "https://example.invalid/connection_request");
    assert.equal(xhr.sent, JSON.stringify(body));
    assert.deepEqual(xhr.headers, { Authorization: "Bearer fixture-token", "Content-type": "application/json" });
    xhr.complete(200, '{"status":"success"}', "application/json");
    assert.equal(received[0][1].status, "success");
});

test("DELETE and failed responses preserve error/status and release the callback", () => {
    const h = start(), received = [];
    h.request({ uri: "https://example.invalid/connection_request", method: "DELETE" },
        (...args) => received.push(args));
    const xhr = h.requests[0];
    assert.equal(xhr.opened.method, "DELETE");
    xhr.complete(403, "private server detail", "text/plain", "Forbidden");
    assert.equal(received[0][0], "403:Forbidden");
    assert.equal(received[0][1].statusCode, 403);
    xhr.complete(200);
    assert.equal(received.length, 1);
});

test("native cancellation/transport failure and malformed JSON retain terminal callback semantics", () => {
    for (const jsonError of [false, true]) {
        const h = start(), received = [];
        h.request("https://example.invalid/plain", (...args) => received.push(args));
        const xhr = h.requests[0];
        if (jsonError) xhr.complete(200, "{broken", "application/json");
        else xhr.complete(0, "", "text/plain", "Aborted");
        assert.ok(received[0][0]);
        assert.equal(received[0][1].statusCode, jsonError ? 200 : 0);
        assert.equal(xhr.onreadystatechange, null);
        xhr.complete();
        assert.equal(received.length, 1);
    }
});
