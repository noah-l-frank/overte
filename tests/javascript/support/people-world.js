// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { FakeSignal } = require("../support/signal");
const root = path.resolve(__dirname, "../../..");
const protocol = require(path.join(root, "scripts/system/libraries/peopleConnection.js"));
const A = "11111111-1111-4111-8111-111111111111", B = "22222222-2222-4222-8222-222222222222";
const C = "33333333-3333-4333-8333-333333333333", DOMAIN = "44444444-4444-4444-8444-444444444444";
const braced = id => "{" + id + "}";

// Both complete Pal engines, the production state helper and unmodified request
// serializer execute. Native account/AvatarList/AppUi and the HTTP server are
// boundaries. The service below models reciprocal server matching, not a live
// directory or authentication claim.
function world() {
    let now = 0, next = 0;
    const clients = [], timers = new Map(), intervals = new Map(), messages = [], http = [], proposals = new Map(), held = [], heldProfiles = [];
    let holdProfiles = false;
    let responseMode = "normal";
    function later(fn, ms) { const id = ++next; timers.set(id, { fn, at: now + ms }); return id; }
    function advance(ms = 0) {
        const end = now + ms;
        for (let count = 0; count < 10000; ++count) {
            const ordered = [...timers].filter(([, value]) => value.at <= end).sort((a, b) => a[1].at - b[1].at);
            if (!ordered.length) { now = end; return; }
            const [id, value] = ordered[0]; timers.delete(id); now = value.at; value.fn();
        }
        throw new Error("Timer loop did not settle");
    }
    function deliver() {
        for (let count = 0; messages.length && count < 1000; ++count) {
            const message = messages.shift();
            clients.forEach(client => client.Messages.messageReceived.emit(message.channel, message.body, braced(message.sender)));
        }
        assert.equal(messages.length, 0);
        advance();
    }
    function client(id, touch = true) {
        let nonce = 0, ui;
        const peerData = new Map();
        const native = { id, domain: DOMAIN, endpoint: "https://directory.invalid", loggedIn: true, username: "fixture" };
        const Messages = { messageReceived: new FakeSignal(), subscribed: new Set(),
            subscribe(channel) { this.subscribed.add(channel); }, unsubscribe(channel) { this.subscribed.delete(channel); },
            sendMessage(channel, body) { messages.push({ sender: native.id, channel, body }); } };
        class HttpBoundary {
            constructor() { this.headers = {}; }
            setRequestHeader(key, value) { this.headers[key] = value; }
            getResponseHeader() { return "application/json"; }
            open(method, url) { this.method = method; this.url = url; }
            send(body) {
                this.body = body; http.push({ owner: id, method: this.method, url: this.url, body, headers: this.headers });
                later(() => {
                    let status = 200, value = { status: "success", data: { users: [], total_pages: 1, current_page: 1 } };
                    const url = new URL(this.url);
                    if (holdProfiles && url.pathname === "/api/v1/users" && url.searchParams.has("search")) {
                        heldProfiles.push(() => {
                            this.status = 200; this.statusText = "OK"; this.readyState = 4;
                            this.responseText = JSON.stringify({ status: "success", data: { users: [{ username: "confirmed-peer",
                                connection: "connection", images: {}, location: { node_id: id === A ? B : A } }] } });
                            this.onreadystatechange();
                        });
                        return;
                    }
                    if (url.pathname.endsWith("/user/connection_request")) {
                        if (responseMode === "hold") {
                            held.push(() => {
                                this.status = 200; this.statusText = "OK"; this.readyState = 4;
                                this.responseText = JSON.stringify({ status: "success", connection: { username: "held-peer", new_connection: true } });
                                this.onreadystatechange();
                            });
                            return;
                        }
                        if (responseMode === "401") { status = 401; value = {}; }
                        else if (responseMode === "network") { status = 0; value = {}; }
                        else if (responseMode === "malformed") { value = { status: "success" }; }
                        else {
                            const pair = this.method === "POST" ? JSON.parse(body).user_connection_request : Object.fromEntries(url.searchParams);
                            if (this.method === "POST") { proposals.set(pair.node_id, pair.proposed_node_id); }
                            value = proposals.get(pair.proposed_node_id) === pair.node_id
                                ? { status: "success", connection: { username: "confirmed-peer", new_connection: true } }
                                : { status: "success", connection: "pending" };
                        }
                    }
                    this.status = status; this.statusText = status === 200 ? "OK" : "Unavailable";
                    this.responseText = JSON.stringify(value); this.readyState = 4; this.onreadystatechange();
                }, 0);
            }
        }
        const transport = { module: { exports: {} }, XMLHttpRequest: HttpBoundary, print() {} };
        vm.runInNewContext(fs.readFileSync(path.join(root, "scripts/modules/request.js"), "utf8"), transport);
        const ending = new FakeSignal(), Window = { domainChanged: new FakeSignal(), domainConnectionRefused: new FakeSignal() };
        const Users = { requestsDomainListData: false, canKick: false, avatarDisconnected: new FakeSignal(),
            usernameFromIDReply: new FakeSignal(), getIgnoreStatus(peer) { return !!peerData.get(protocol.session(peer))?.ignored; },
            getPersonalMuteStatus() { return false; }, requestUsernameFromID() {} };
        const AvatarList = { avatarAddedEvent: new FakeSignal(), avatarRemovedEvent: new FakeSignal(), avatarSessionChangedEvent: new FakeSignal(),
            getAvatarIdentifiers() { return [...peerData.keys()].map(braced); },
            getAvatar(peer) { const found = peerData.get(protocol.session(peer)); return found ? {
                sessionUUID: braced(protocol.session(peer)), displayName: found.name, isReplicated: found.replicated === true } : null; },
            getPalData() { return { data: [] }; } };
        const mapping = { from() { return this; }, peek() { return this; }, to() { return this; }, enable() {}, disable() {} };
        class AppUi {
            constructor(options) { this.options = options; this.isOpen = false; this.states = []; this.sent = []; ui = this;
                this.tablet = { tabletShown: true, tabletShownChanged: new FakeSignal() }; }
            open() { this.options.onOpened(); this.isOpen = true; this.options.onMessage({ method: "connectionReady" }); }
            close() { this.options.onClosed(); this.isOpen = false; }
            sendMessage(message) { this.sent.push(message); if (message.method === "connectionState") { this.states.push(message.params); } }
            messagesWaiting() {}
            message(message) { this.options.onMessage(message); }
            get state() { return this.states.at(-1) || { phase: "idle" }; }
        }
        const api = { ANDROID_PHONE_INTERFACE: touch, Script: { require(name) {
            if (name === "request") { return transport.module.exports; }
            if (name === "appUi") { return AppUi; }
            const local = path.resolve(root, "scripts/system", name);
            assert.equal(local, path.join(root, "scripts/system/libraries/peopleConnection.js"));
            return require(local);
        }, include() {}, resolvePath(value) { return path.join(root, "scripts/system", value); },
            setTimeout: later, clearTimeout(value) { timers.delete(value); },
            setInterval(fn, ms) { const value = ++next; intervals.set(value, { fn, ms }); return value; },
            clearInterval(value) { intervals.delete(value); }, scriptEnding: ending },
            Uuid: { generate() { return "aaaaaaaa-aaaa-4aaa-8aaa-" + String(++nonce).padStart(12, "0"); } },
            Account: { get metaverseServerURL() { return native.endpoint; }, get username() { return native.username; }, isLoggedIn() { return native.loggedIn; },
                myUsernameChanged: new FakeSignal(), loggedInChanged: new FakeSignal(), connected: new FakeSignal(), disconnected: new FakeSignal() },
            MyAvatar: { get sessionUUID() { return braced(native.id); } },
            location: { get domainID() { return braced(native.domain); } },
            Messages, Users, AvatarList, Window, HMD: { active: !touch }, Settings: { getValue() { return false; }, setValue() {} },
            Controller: { Standard: {}, newMapping() { return mapping; }, mousePressEvent: new FakeSignal(), mouseMoveEvent: new FakeSignal() },
            Entities: { deleteEntity() {}, addEntity() { return "fixture-overlay"; }, editEntity() {} },
            Vec3: {}, Quat: {}, Camera: {}, Overlays: {}, UserActivityLogger: { palAction() {} }, print() {},
            Date: { now() { return now; } } };
        vm.runInNewContext(fs.readFileSync(path.join(root, "scripts/system/pal.js"), "utf8"), api, { filename: "scripts/system/pal.js" });
        const result = { native, ui, peerData, Messages, Users, Window, ending, AvatarList, Account: api.Account,
            stop() { ending.emit(); }, request(peer) { ui.message({ method: "connectionRequest", params: peer }); },
            respond(accept) { ui.message({ method: "connectionRespond", params: accept }); } };
        clients.push(result); return result;
    }
    function pair() {
        const a = client(A), b = client(B, false);
        a.peerData.set(B, { name: "Actual B" }); b.peerData.set(A, { name: "Actual A" });
        return { a, b };
    }
    function inject(to, from, fields) {
        to.Messages.messageReceived.emit(protocol.channel, JSON.stringify({ version: 1, type: "invite", to: to.native.id,
            requestId: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb", domain: DOMAIN, endpoint: to.native.endpoint, ...fields }), braced(from));
    }
    return { client, pair, deliver, advance, inject, http, messages, timers, intervals,
        release() { held.splice(0).forEach(callback => callback()); },
        holdProfiles() { holdProfiles = true; },
        releaseProfiles() { heldProfiles.splice(0).forEach(callback => callback()); },
        mode(value) { responseMode = value; }, posts() { return http.filter(row => row.method === "POST" && row.url.endsWith("/user/connection_request")); } };
}

module.exports = { world, A, B, C, DOMAIN, protocol, braced };
