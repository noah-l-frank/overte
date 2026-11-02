// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Loaded only through ordinary Running Scripts. Native controls never invoke
// this function or manufacture its execution observations.
(function () {
    "use strict";
    var session = OVERTE_SCRIPT_MANAGEMENT_SESSION;
    Script.include(Script.resolvePath("companion.js"));
    var proof = typeof OVERTE_SCRIPT_MANAGEMENT_COMPANION === "string"
        ? OVERTE_SCRIPT_MANAGEMENT_COMPANION : "";
    var instance = String(Uuid.generate()).replace(/[{}-]/g, "").toLowerCase();
    var sequence = 0;
    var pending = null;
    var ending = false;
    function send() {
        if (ending || pending) { return; }
        var request = new XMLHttpRequest();
        pending = request;
        request.onreadystatechange = function () {
            if (request.readyState !== 4 || ending) { return; }
            if (request.status === 200) { sequence += 1; }
            pending = null;
        };
        request.timeout = 3000;
        request.ontimeout = function () { pending = null; };
        try {
            request.open("POST", session.eventsUrl, true);
            request.setRequestHeader("Content-Type", "application/json");
            request.send(JSON.stringify({ token: session.receiptToken,
                instance: instance, sequence: sequence,
                kind: sequence === 0 ? "start" : "tick", companionProof: proof }));
        } catch (_error) { pending = null; }
    }
    var timer = Script.setInterval(send, 250);
    Script.scriptEnding.connect(function () {
        ending = true;
        Script.clearInterval(timer);
        if (pending) { pending.abort(); pending = null; }
    });
    send();
}());
