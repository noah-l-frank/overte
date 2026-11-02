"use strict";
const assert = require("node:assert/strict");
const path = require("node:path");
const test = require("node:test");
const {createScriptApi, runProductionScript} = require("./index");
const source = path.resolve(__dirname, "../../device/fixture/create_management/observer.js");
const prefix = "OVERTE_E2E_CREATE_" + "c".repeat(32) + "_";
const parentId = "1".repeat(32), childId = "2".repeat(32), foreignId = "3".repeat(32);
const me = "ab".repeat(16), self = "0".repeat(31) + "1";

function row(name, {parentID = null, owner = self} = {}) {
    return {name, type: "Box", shape: "Cube", entityHostType: "avatar",
        owningAvatarID: owner, parentID,
        dimensions: {x: .5, y: .6, z: .7}, color: {red: 35, green: 125, blue: 220}};
}

function start({queryIds} = {}) {
    const Script = createScriptApi(), requests = [], reads = [], writes = [];
    const entities = new Map([
        [parentId, row(prefix + "import-parent", {parentID: self})],
        [childId, row(prefix + "import-child", {parentID: parentId, owner: me})],
        [foreignId, row("unrelated-private-name", {owner: "d".repeat(32)})]
    ]);
    const Entities = {
        findEntities(position, radius) {
            reads.push({position, radius}); return queryIds || [...entities.keys()];
        },
        getEntityProperties(id, fields) {
            reads.push({id, fields: Array.from(fields)});
            return entities.get(id) || {};
        },
        addEntity() { writes.push("add"); throw new Error("read-only observer wrote an entity"); },
        editEntity() { writes.push("edit"); throw new Error("read-only observer wrote an entity"); },
        deleteEntity() { writes.push("delete"); throw new Error("read-only observer wrote an entity"); }
    };
    class XMLHttpRequest {
        constructor() { requests.push(this); }
        open(method, url) { this.method = method; this.url = url; }
        setRequestHeader() {}
        send(body) { this.body = JSON.parse(body); }
        complete(status = 200) { this.status = status; this.readyState = 4; this.onreadystatechange(); }
        abort() { this.aborted = true; }
    }
    runProductionScript(source, {Script, Entities, XMLHttpRequest,
        MyAvatar: {position: {x: 0, y: 0, z: 4}, sessionUUID: me, SELF_ID: self},
        Uuid: {generate: () => "fedcba9876543210fedcba9876543210"},
        OVERTE_CREATE_SESSION: {prefix, receiptToken: "synthetic-receipt",
            eventsUrl: "http://fixture.test/create/session/events"}});
    return {Script, requests, entities, reads, writes,
        tick: () => Script.runTimer([...Script.timers.keys()][0])};
}

test("Create observer reads actual owned state, handles SELF_ID and hides unrelated identities", () => {
    const s = start(), body = s.requests[0].body;
    assert.equal(body.complete, true);
    assert.equal(body.queriedEntityCount, 3);
    assert.equal(body.entities.length, 2);
    const parent = body.entities.find(value => value.id === parentId);
    const child = body.entities.find(value => value.id === childId);
    assert.equal(parent.ownedByCurrentAvatar, true);
    assert.equal(child.ownedByCurrentAvatar, true);
    assert.equal(parent.parentId, null);
    assert.equal(parent.hasExternalParent, true);
    assert.equal(child.parentId, parentId);
    assert.equal(child.hasExternalParent, false);
    assert.deepEqual(parent.color, s.entities.get(parentId).color);
    for (const secret of [me, self, "unrelated-private-name"]) {
        assert.equal(JSON.stringify(body).includes(secret), false);
    }
    assert.deepEqual(s.writes, []);
    assert.equal(s.reads[0].radius, 64);
    s.Script.end();
});

test("Create observer samples changed native properties only after an earlier receipt is acknowledged", () => {
    const s = start(), first = s.requests[0].body;
    s.entities.get(parentId).color = {red: 240, green: 10, blue: 80};
    s.tick();
    assert.equal(s.requests.length, 1);
    s.requests[0].complete(400);
    s.tick();
    assert.deepEqual(s.requests[1].body, first);
    s.requests[1].complete();
    s.tick();
    assert.equal(s.requests[2].body.sequence, 1);
    assert.deepEqual(s.requests[2].body.entities.find(value => value.id === parentId).color,
                     {red: 240, green: 10, blue: 80});
    assert.deepEqual(s.writes, []);
    s.Script.end();
});

test("Create observer query overflow is explicit incomplete evidence", () => {
    const s = start({queryIds: Array(4097).fill(parentId)});
    assert.equal(s.requests[0].body.complete, false);
    assert.equal(s.requests[0].body.error, "query-budget");
    assert.deepEqual(s.requests[0].body.entities, []);
    s.Script.end();
});

test("Create observer failed native reads do not become a successful empty snapshot", () => {
    const s = start();
    s.requests[0].complete();
    s.entities.set(parentId, {name: prefix + "import-parent"});
    s.tick();
    assert.equal(s.requests[1].body.complete, false);
    assert.equal(s.requests[1].body.error, "entity-read-error");
    assert.deepEqual(s.requests[1].body.entities, []);
    s.Script.end();
});

test("Create observer ending clears timers and prevents further reads or requests", () => {
    const s = start(), callback = [...s.Script.timers.values()][0].callback;
    const reads = s.reads.length;
    s.Script.end();
    assert.equal(s.Script.timers.size, 0);
    assert.equal(s.requests[0].aborted, true);
    callback();
    assert.equal(s.reads.length, reads);
    assert.equal(s.requests.length, 1);
    assert.deepEqual(s.writes, []);
});
