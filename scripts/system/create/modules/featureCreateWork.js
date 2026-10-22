// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
"use strict";

// Passive instrumentation exists only in an E2E process exposing this native
// method. The observer reads real closure state; it cannot cancel or finish it.
function observer(role, sourceUrl, read) {
    if (typeof Test === "undefined" || typeof Test.featureIOSCreateEvent !== "function") {
        return { enabled: false, call: function (_name, callback) { return callback(); } };
    }
    var sequence = 0;
    function report(event, name, call) {
        Test.featureIOSCreateEvent({ createWorkEventVersion: 1, role: role,
            sourceUrl: sourceUrl, event: event, closure: name, call: call,
            state: read() });
    }
    function sample() { report("snapshot", "", 0); }
    sample();
    Script.update.connect(sample);
    Script.scriptEnding.connect(function () {
        Script.update.disconnect(sample);
        report("ending", "", 0);
    });
    return { enabled: true, call: function (name, callback) {
        var call = ++sequence;
        report("entry", name, call);
        try {
            var value = callback();
            report("returned", name, call);
            return value;
        } finally { report("finally", name, call); }
    } };
}
module.exports = { observer: observer };
