// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
"use strict";
const assert = require("node:assert/strict");
const test = require("node:test");
const { world, A, B, C, DOMAIN, protocol, braced } = require("../support/people-world");

test("normal touch People requests and actual Pico Pal opens an explicit consent prompt before any server mutation", () => {
    const w = world(), { a, b } = w.pair();
    a.ui.open(); a.request(braced(B)); w.deliver();
    assert.equal(a.ui.state.phase, "outgoing"); assert.equal(b.ui.isOpen, true);
    assert.equal(b.ui.state.phase, "incoming"); assert.equal(b.ui.state.peerName, "Actual A");
    assert.equal(w.posts().length, 0);
    b.respond(false); w.deliver();
    assert.equal(a.ui.state.phase, "declined"); assert.equal(b.ui.state.phase, "declined");
    assert.equal(w.posts().length, 0);
    assert.equal(a.Messages.subscribed.has(protocol.channel), true);
    a.stop(); b.stop(); assert.equal(w.timers.size, 0);
});

test("two real Pal engines submit reciprocal authenticated protocol bytes and poll through the actual request serializer", () => {
    const w = world(), { a, b } = w.pair(); a.ui.open(); a.request(B); w.deliver(); b.respond(true); w.deliver();
    assert.equal(w.posts().length, 2);
    for (const row of w.posts()) {
        assert.equal(row.headers["Content-type"], "application/json");
        assert.deepEqual(JSON.parse(row.body), { user_connection_request: { node_id: row.owner, proposed_node_id: row.owner === A ? B : A } });
    }
    w.advance(200);
    assert.equal(a.ui.state.phase, "success"); assert.equal(b.ui.state.phase, "success");
    const poll = w.http.find(row => row.method === "GET" && row.url.includes("/user/connection_request?"));
    assert.ok(poll); assert.equal(poll.body, null); assert.equal(poll.headers["Content-type"], undefined);
    assert.ok(a.ui.sent.some(row => row.method === "refreshConnections"));
    assert.ok(b.ui.sent.some(row => row.method === "refreshConnections"));
    a.stop(); b.stop(); assert.equal(w.timers.size, 0);
});

test("self, invalid, offline, ignored, replicated and anonymous local requests cannot submit or invite", () => {
    for (const target of [A, "not-a-session", C]) {
        const w = world(), { a } = w.pair(); a.request(target); assert.equal(a.ui.state.phase, "error"); assert.equal(w.messages.length, 0); a.stop();
    }
    for (const flag of ["ignored", "replicated"]) {
        const w = world(), { a } = w.pair(); a.peerData.get(B)[flag] = true; a.request(B);
        assert.equal(a.ui.state.phase, "error"); assert.equal(w.messages.length, 0); a.stop();
    }
    const w = world(), { a } = w.pair(); a.native.loggedIn = false; a.request(B);
    assert.match(a.ui.state.message, /Sign in/); assert.equal(w.posts().length, 0); a.stop();
});

test("unknown sender, foreign endpoint/domain/target, malformed and self messages cannot open a prompt", () => {
    const w = world(), { a } = w.pair();
    w.inject(a, C, {}); w.inject(a, A, {});
    for (const fields of [{ domain: C }, { endpoint: "https://foreign.invalid" }, { to: C }, { requestId: "bad" }, { version: 2 }]) { w.inject(a, B, fields); }
    a.Messages.messageReceived.emit(protocol.channel, "{broken", braced(B));
    assert.equal(a.ui.isOpen, false); assert.equal(a.ui.state.phase, "idle");
    a.native.loggedIn = false; w.inject(a, B, {}); assert.equal(a.ui.isOpen, false); a.stop();
});

test("only the matching actual sender and consent state can accept; replay cannot reopen a declined request", () => {
    const w = world(), { a, b } = w.pair(); a.peerData.set(C, { name: "Actual C" });
    a.request(B); const invitation = JSON.parse(w.messages[0].body); w.deliver();
    w.inject(a, C, { ...invitation, to: A, type: "accept" });
    w.inject(a, B, { ...invitation, to: A, type: "ready" });
    assert.equal(w.posts().length, 0); assert.equal(a.ui.state.phase, "outgoing");
    b.respond(false); w.deliver();
    w.inject(b, A, invitation); assert.equal(b.ui.state.phase, "declined");
    b.respond(true); assert.equal(w.posts().length, 0); a.stop(); b.stop();
});

test("cancel, page close, tablet hide and script stop revoke the real Pal request and its peer prompt", () => {
    for (const action of [a => a.ui.message({ method: "connectionCancel" }), a => a.ui.close(),
        a => { a.ui.tablet.tabletShown = false; a.ui.tablet.tabletShownChanged.emit(); }, a => a.stop()]) {
        const w = world(), { a, b } = w.pair(); a.ui.open(); a.request(B); w.deliver(); action(a); w.deliver();
        assert.equal(b.ui.state.phase, "cancelled"); assert.equal(w.posts().length, 0);
        a.stop(); b.stop(); assert.equal(w.timers.size, 0); assert.equal(w.intervals.size, 0);
    }
});

test("peer loss, account/session/domain/endpoint changes and invitation timeout retire pending consent", () => {
    for (const mutate of [a => a.peerData.delete(B), a => { a.native.loggedIn = false; },
        a => { a.native.id = C; }, a => { a.native.username = "other-account"; }, a => { a.native.domain = C; }, a => { a.native.endpoint = "https://other.invalid"; }]) {
        const w = world(), { a, b } = w.pair(); a.request(B); w.deliver(); mutate(a); w.advance(250);
        assert.equal(a.ui.state.phase, "error"); assert.equal(w.posts().length, 0); a.stop(); b.stop(); assert.equal(w.timers.size, 0);
    }
    const w = world(), { a, b } = w.pair(); a.request(B); w.deliver(); w.advance(30000); w.deliver();
    assert.match(a.ui.state.message, /expired/); assert.equal(w.posts().length, 0); a.stop(); b.stop();
});

test("real request transport errors and malformed service replies never manufacture a connection", () => {
    for (const mode of ["401", "network", "malformed"]) {
        const w = world(), { a, b } = w.pair(); w.mode(mode); a.request(B); w.deliver(); b.respond(true); w.deliver();
        assert.equal(a.ui.state.phase, "error"); assert.equal(b.ui.state.phase, "error");
        if (mode === "401") { assert.match(a.ui.state.message, /signed in/); }
        assert.equal(a.ui.sent.some(row => row.method === "refreshConnections"), false); a.stop(); b.stop();
    }
});

test("in-flight cancellation and no-response deadline are honest and late server replies cannot revive the UI", () => {
    const w = world(), { a, b } = w.pair(); w.mode("hold"); a.request(B); w.deliver(); b.respond(true); w.deliver();
    assert.equal(a.ui.state.phase, "submitting"); a.ui.message({ method: "connectionCancel" });
    assert.match(a.ui.state.message, /may still complete/); w.advance(12000);
    assert.equal(b.ui.state.phase, "error"); assert.match(b.ui.state.message, /did not confirm/);
    const phases = [a.ui.state.phase, b.ui.state.phase]; w.release();
    assert.deepEqual([a.ui.state.phase, b.ui.state.phase], phases);
    assert.equal(a.ui.sent.some(row => row.method === "refreshConnections"), false);
    a.stop(); b.stop(); assert.equal(w.timers.size, 0);
});


test("actual Pal account signal leases reject held successes after account switch or same-account logout/login", () => {
    for (const change of [a => { a.native.username = "new-account"; a.Account.myUsernameChanged.emit("new-account"); },
        a => { a.Account.disconnected.emit("logout"); a.Account.connected.emit(); },
        a => { a.Account.loggedInChanged.emit(false); a.Account.loggedInChanged.emit(true); },
        a => { a.Account.connected.emit(); }]) {
        const w = world(), { a, b } = w.pair(); w.mode("hold"); a.request(B); w.deliver(); b.respond(true); w.deliver();
        change(a); assert.equal(a.ui.state.phase, "cancelled");
        w.release(); w.advance(); assert.equal(a.ui.state.phase, "cancelled");
        assert.equal(a.ui.sent.some(row => row.method === "refreshConnections"), false);
        a.stop(); b.stop(); assert.equal(w.timers.size, 0);
        for (const signal of [a.Account.myUsernameChanged, a.Account.loggedInChanged, a.Account.connected, a.Account.disconnected]) { assert.equal(signal.listenerCount, 0); }
    }
});

test("native domain invalidation rejects held responses and cannot retain an old incoming dialog", () => {
    const w = world(), { a, b } = w.pair(); w.mode("hold"); a.ui.open(); a.request(B); w.deliver(); b.respond(true); w.deliver();
    a.Window.domainChanged.emit(); assert.equal(a.ui.isOpen, false); w.release(); w.advance();
    assert.equal(a.ui.sent.some(row => row.method === "refreshConnections"), false);
    a.stop(); b.stop(); assert.equal(w.timers.size, 0);
});


test("new connection profile refresh uses the current endpoint and rejects a later account/session lease", () => {
    const w = world(), { a, b } = w.pair(); w.holdProfiles();
    a.native.endpoint = b.native.endpoint = "https://current-directory.invalid";
    a.request(B); w.deliver(); b.respond(true); w.deliver(); w.advance(200);
    assert.equal(a.ui.state.phase, "success");
    const profile = w.http.find(row => row.url.includes("search=confirmed-peer"));
    assert.ok(profile.url.startsWith("https://current-directory.invalid/"));
    a.native.username = "other-account"; a.Account.myUsernameChanged.emit("other-account");
    assert.equal(a.ui.state.phase, "idle");
    w.releaseProfiles(); w.advance();
    assert.equal(a.ui.sent.some(row => row.method === "updateUsername"), false);
    a.stop(); b.stop(); assert.equal(w.timers.size, 0);
});


test("concurrent invitations cannot replace consent and users can cancel and retry normally", () => {
    const w = world(), { a, b } = w.pair(); a.request(B); b.request(A); w.deliver();
    assert.equal(a.ui.state.phase, "outgoing"); assert.equal(b.ui.state.phase, "outgoing");
    assert.equal(w.posts().length, 0);
    a.ui.message({ method: "connectionCancel" }); b.ui.message({ method: "connectionCancel" }); w.deliver();
    a.request(B); w.deliver(); assert.equal(b.ui.state.phase, "incoming");
    b.respond(true); w.deliver(); w.advance(200);
    assert.equal(a.ui.state.phase, "success"); assert.equal(b.ui.state.phase, "success");
    a.stop(); b.stop(); assert.equal(w.timers.size, 0);
});
