// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
"use strict";
// Original complete Pal/protocol engines execute. This is an explicit native
// QML/token/SDK transport model, not a compiled QML or real pointer proof.
const assert = require("node:assert/strict");
const readline = require("node:readline");
const { world, A, B, braced } = require("../../../../../tests/javascript/support/people-world");
const primarySession = process.argv[2] || A, peerSession = process.argv[3] || B;
const w = world(), primary = w.client(primarySession, false), peer = w.client(peerSession, false);
primary.native.username = "primary-fixture"; peer.native.username = "peer-fixture";
primary.peerData.set(peerSession, { name: "Original peer" }); peer.peerData.set(primarySession, { name: "Original primary" });
const roles = { primary, peer }, controls = [], replies = [];
let stopped = false;
function command(value) {
    const client = roles[value.role];
    if (value.operation === "input") {
        controls.push({ role: value.role, control: value.control });
        if (value.control === "people.entry") { client.ui.open(); }
        else if (value.control === "people.RequestConnection") { client.request(braced(value.role === "primary" ? peerSession : primarySession)); }
        else if (value.control === "people.ConnectionDecline") { client.ui.message({ method: "connectionRespond", params: false }); }
        else if (value.control === "people.ConnectionCancel") { client.ui.message({ method: "connectionCancel" }); }
        else { assert.ok(value.control === "people.nearby" || value.control === "people.row.0"); }
        w.deliver();
    } else if (value.operation === "advance") { w.advance(value.ms); }
    else if (value.operation === "invalidate") {
        client.native.domain = "33333333-3333-4333-8333-333333333333"; client.Window.domainChanged.emit(); w.deliver();
    } else if (value.operation === "stop") {
        primary.stop(); peer.stop(); stopped = true;
    } else { assert.equal(value.operation, "capture"); }
    return { primary: { state: primary.ui.state, open: primary.ui.isOpen }, peer: { state: peer.ui.state, open: peer.ui.isOpen },
        controls, posts: w.posts(), queuedMessages: w.messages.length, timers: w.timers.size,
        subscriptions: { primary: [...primary.Messages.subscribed], peer: [...peer.Messages.subscribed] }, stopped };
}
readline.createInterface({ input: process.stdin }).on("line", line => {
    const value = JSON.parse(line), result = command(value); replies.push(result);
    process.stdout.write(JSON.stringify(result) + "\n");
    if (stopped) { process.exitCode = 0; process.stdin.destroy(); }
});
