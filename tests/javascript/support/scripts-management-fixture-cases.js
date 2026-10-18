"use strict";
const assert = require("node:assert/strict");
const path = require("node:path");
const test = require("node:test");
const {createScriptApi, runProductionScript} = require("../support");
const source = path.resolve(__dirname, "../../device/fixture/script_management/client.js");

function start({companion = "owned-proof", throws = false} = {}) {
    const Script = createScriptApi(), requests = [], includes = [];
    const config = {eventsUrl: "http://fixture.test/script-management/owned/events",
                    receiptToken: "synthetic-receipt"};
    Script.resolvePath = name => "http://fixture.test/script-management/owned/" + name;
    Script.include = name => { includes.push(name); };
    class XMLHttpRequest {
        constructor() { requests.push(this); }
        open(method, url) { this.method = method; this.url = url; }
        setRequestHeader(name, value) { this.header = [name, value]; }
        send(body) { if (throws) throw new Error("transport unavailable"); this.body = JSON.parse(body); }
        abort() { this.aborted = true; }
        complete(status = 200) { this.status = status; this.readyState = 4; this.onreadystatechange(); }
    }
    runProductionScript(source, {Script, XMLHttpRequest,
        Uuid: {generate: () => "{01234567-89ab-cdef-0123-456789abcdef}"},
        OVERTE_SCRIPT_MANAGEMENT_SESSION: config,
        OVERTE_SCRIPT_MANAGEMENT_COMPANION: companion});
    return {Script, requests, includes, config, tick: () => Script.runTimer([...Script.timers.keys()][0])};
}

test("actual script includes its ordinary companion and emits only its execution event", () => {
    const s = start(), first = s.requests[0];
    assert.deepEqual(s.includes, ["http://fixture.test/script-management/owned/companion.js"]);
    assert.equal(first.method, "POST");
    assert.equal(first.url, s.config.eventsUrl);
    assert.equal(first.timeout, 3000);
    assert.deepEqual(first.header, ["Content-Type", "application/json"]);
    assert.deepEqual(first.body, {token: "synthetic-receipt", instance: "0123456789abcdef0123456789abcdef",
        sequence: 0, kind: "start", companionProof: "owned-proof"});
    first.complete();
    s.tick();
    assert.equal(s.requests[1].body.sequence, 1);
    assert.equal(s.requests[1].body.kind, "tick");
    s.Script.end();
});

test("in-flight requests are serialized and rejected acknowledgments cannot advance execution", () => {
    const s = start();
    s.tick(); s.tick();
    assert.equal(s.requests.length, 1);
    s.requests[0].complete(400);
    s.tick();
    assert.equal(s.requests[1].body.sequence, 0);
    s.requests[1].complete();
    s.tick();
    assert.equal(s.requests[2].body.sequence, 1);
    s.Script.end();
});

test("engine ending clears the owned timer and aborts its pending real request endpoint", () => {
    const s = start(), callback = [...s.Script.timers.values()][0].callback;
    s.Script.end();
    assert.equal(s.Script.timers.size, 0);
    assert.equal(s.requests[0].aborted, true);
    s.requests[0].complete();
    callback();
    assert.equal(s.requests.length, 1);
});

test("transport exceptions do not invent successful events or leak pending state", () => {
    const s = start({throws: true});
    s.tick();
    assert.equal(s.requests.length, 2);
    assert.equal(s.requests[1].body, undefined);
    s.Script.end();
});
