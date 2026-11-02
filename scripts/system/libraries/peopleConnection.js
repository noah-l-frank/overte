// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
"use strict";

// Platform-neutral consent and directory protocol for the normal People app.
// The directory remains authoritative: peer messages never establish a connection.
var CHANNEL = "io.overte.people.connection.v1";
function session(value) {
    var text = String(value || "").toLowerCase();
    if (text.charAt(0) === "{" && text.charAt(text.length - 1) === "}") { text = text.slice(1, -1); }
    return /^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/.test(text)
        && text !== "00000000-0000-0000-0000-000000000000" ? text : "";
}

function create(context) {
    var active = null, disposed = false, revision = 0, timer = null, pollTimer = null;
    var recent = {}, recentKeys = [];
    var view = { phase: "idle", message: "", peerName: "", peer: "", requestId: "" };
    function identity() {
        var raw = context.identity();
        return { self: session(raw.self), domain: session(raw.domain),
            endpoint: String(raw.endpoint || "").replace(/\/+$/, ""), loggedIn: raw.loggedIn === true,
            account: String(raw.account || ""), accountGeneration: raw.accountGeneration };
    }
    function usable(id) { return id.self && id.domain && id.loggedIn && /^https:\/\/[^\s?#]+$/i.test(id.endpoint); }
    function peer(id) {
        var found = context.peer(id);
        return found && session(found.id) === id && found.present !== false && !found.ignored && !found.replicated ? found : null;
    }
    function sameIdentity(a, b) {
        return usable(b) && a.self === b.self && a.domain === b.domain && a.endpoint === b.endpoint
            && a.account === b.account && a.accountGeneration === b.accountGeneration;
    }
    function publish() { if (!disposed) { context.update(Object.assign({}, view)); } }
    function show(phase, message, record) {
        view = { phase: phase, message: message, peerName: record ? record.name : "",
            peer: record ? record.peer : "", requestId: record ? record.id : "" };
        publish();
    }
    function clearTimer() {
        if (timer !== null) { context.clearTimeout(timer); timer = null; }
        if (pollTimer !== null) { context.clearTimeout(pollTimer); pollTimer = null; }
    }
    function send(record, type) {
        context.send(CHANNEL, JSON.stringify({ version: 1, type: type, to: record.peer,
            requestId: record.id, domain: record.identity.domain, endpoint: record.identity.endpoint }));
    }
    function remember(key) {
        recent[key] = true; recentKeys.push(key);
        if (recentKeys.length > 128) { delete recent[recentKeys.shift()]; }
    }
    function finish(phase, message, notify) {
        var record = active;
        clearTimer(); active = null; ++revision;
        if (record && notify && sameIdentity(record.identity, identity())) { send(record, notify); }
        show(phase, message, record);
    }
    function current(record) {
        if (disposed || active !== record || record.revision !== revision) { return false; }
        if (!sameIdentity(record.identity, identity())) {
            finish("error", "Your account, location or connection service changed. Request a connection again."); return false;
        }
        if (!peer(record.peer)) { finish("error", "This person is no longer available. Request a connection when they return."); return false; }
        return true;
    }
    function watch(record) {
        clearTimer();
        timer = context.setTimeout(function tick() {
            timer = null;
            if (!current(record)) { return; }
            if (context.now() >= record.deadline) {
                finish("error", record.submitted
                    ? "The connection service did not confirm in time. Refresh Connections before trying again."
                    : "The connection request expired. You can send a new request.", record.submitted ? "" : "cancel");
                return;
            }
            timer = context.setTimeout(tick, 250);
        }, 250);
    }
    function recordFor(id, target, requestId, phase) {
        if (!target || target === id.self) { return null; }
        var found = peer(target);
        if (!found) { return null; }
        return { identity: id, peer: target, id: requestId,
            name: String(found.name || "Nearby person").slice(0, 128), phase: phase,
            revision: ++revision, deadline: context.now() + 30000, submitted: false, polls: 0 };
    }
    function failure(error, response) {
        if (response && response.statusCode === 401) { return "All participants must be signed in. Sign in and request a connection again."; }
        if (response && response.statusCode === 403) { return "The connection service refused this request. Check your account and try again."; }
        if (error) { return "The connection request failed. Check your network and try again."; }
        return "The connection service could not confirm this request. Refresh Connections and try again.";
    }
    function submit(record) {
        if (!current(record) || record.submitted) { return; }
        record.submitted = true; record.phase = "submitting";
        record.deadline = context.now() + 12000;
        show("submitting", "Both people agreed. Waiting for the connection service...", record);
        var body = { node_id: record.identity.self, proposed_node_id: record.peer };
        function completed(error, response) {
            if (!current(record)) { return; }
            if (!error && response && response.connection === "pending") {
                if (++record.polls > 10) { finish("error", "No matching signed-in partner was confirmed. Refresh Connections and try again."); return; }
                record.phase = "polling";
                show("polling", "Waiting for the other signed-in request to be confirmed...", record);
                pollTimer = context.setTimeout(function () {
                    pollTimer = null;
                    if (!current(record)) { return; }
                    try { context.request({ uri: record.identity.endpoint + "/api/v1/user/connection_request", body: body }, completed); }
                    catch (exception) { if (current(record)) { finish("error", "The connection request could not be sent. Try again."); } }
                }, 200);
            } else if (!error && response && response.status === "success" && response.connection
                    && typeof response.connection === "object" && typeof response.connection.username === "string"
                    && response.connection.username.length > 0) {
                var username = response.connection.username;
                finish("success", "The connection service confirmed your connection.");
                if (!disposed && sameIdentity(record.identity, identity())) { context.connected(username); }
            } else { finish("error", failure(error, response)); }
        }
        try { context.request({ uri: record.identity.endpoint + "/api/v1/user/connection_request",
            method: "POST", json: true, body: { user_connection_request: body } }, completed); }
        catch (exception) { if (current(record)) { finish("error", "The connection request could not be sent. Try again."); } }
    }
    function request(target) {
        if (disposed) { return; }
        if (active) { publish(); return; }
        var own = identity(), targetId = session(target);
        if (!own.loggedIn) { show("error", "Sign in before requesting a connection."); return; }
        if (!usable(own)) { show("error", "Join a domain and use an HTTPS connection service before requesting a connection."); return; }
        var id = session(context.requestId());
        var record = id && recordFor(own, targetId, id, "outgoing");
        if (!record) { show("error", "Select a different person who is currently available nearby."); return; }
        active = record; remember(record.peer + "/" + record.id);
        show("outgoing", "Waiting for this person to accept your connection request.", record);
        watch(record); send(record, "invite");
    }
    function receive(channel, raw, sender) {
        if (disposed || channel !== CHANNEL || typeof raw !== "string" || raw.length > 2048) { return; }
        var own = identity(), from = session(sender), message;
        if (!usable(own) || !from || from === own.self || !peer(from)) { return; }
        try { message = JSON.parse(raw); } catch (error) { return; }
        if (!message || message.version !== 1 || session(message.to) !== own.self
                || session(message.domain) !== own.domain || message.endpoint !== own.endpoint) { return; }
        var id = session(message.requestId);
        if (!id) { return; }
        if (message.type === "invite") {
            var key = from + "/" + id;
            if (recent[key]) { return; }
            remember(key);
            if (active) { return; } // Never replace an existing consent prompt or operation.
            var incoming = recordFor(own, from, id, "incoming");
            if (!incoming) { return; }
            active = incoming;
            show("incoming", "This person would like to connect with you. Accept only if you want to connect.", incoming);
            watch(incoming); return;
        }
        var record = active;
        if (!record || record.peer !== from || record.id !== id || !current(record)) { return; }
        if (message.type === "accept" && record.phase === "outgoing") {
            record.phase = "accepted"; send(record, "ready"); submit(record);
        } else if (message.type === "ready" && record.phase === "accepted") { submit(record); }
        else if (message.type === "decline" && !record.submitted) { finish("declined", "This person declined the connection request."); }
        else if (message.type === "cancel" && !record.submitted) { finish("cancelled", "The other person canceled the connection request."); }
    }
    function respond(accept) {
        var record = active;
        if (!record || record.phase !== "incoming" || !current(record)) { return; }
        if (!accept) { finish("declined", "Connection request declined.", "decline"); return; }
        record.phase = "accepted";
        show("accepted", "You accepted. Waiting for the requester...", record);
        send(record, "accept");
    }
    function cancel() {
        if (disposed) { return; }
        if (active) {
            finish("cancelled", active.submitted
                ? "Stopped waiting. A submitted server request may still complete; refresh Connections to check."
                : "Connection request canceled.", active.submitted ? "" : "cancel");
        } else { show("idle", ""); }
    }
    function invalidate(reason) {
        if (active) { finish("cancelled", reason === "account"
            ? "Connection request canceled because your account changed. Request a connection again."
            : "Connection request canceled because your location or session changed."); }
        else if (view.phase === "success") { show("idle", ""); }
    }
    function dispose() {
        if (active && !active.submitted && sameIdentity(active.identity, identity())) { send(active, "cancel"); }
        clearTimer(); active = null; ++revision; disposed = true;
    }
    return { request: request, receive: receive, respond: respond, cancel: cancel,
        invalidate: invalidate, dispose: dispose, publish: publish, snapshot: function () { return Object.assign({}, view); } };
}
module.exports = { create: create, channel: CHANNEL, session: session };
