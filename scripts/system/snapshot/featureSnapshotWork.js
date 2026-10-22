// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
"use strict";

// Observe actual closure state on its real VM. No timer, capture, permission,
// upload or UI mutation is introduced by this helper.
function observer(sourceUrl, read) {
    if (typeof Test === "undefined" || typeof Test.featureIOSSnapshotEvent !== "function") {
        return { enabled: false, call: function (_name, callback) { return callback(); } };
    }
    var sequence = 0;
    function report(event, name, call) {
        Test.featureIOSSnapshotEvent({ snapshotWorkEventVersion: 1, role: "snapshot",
            sourceUrl: sourceUrl, event: event, closure: name, call: call, state: read() });
    }
    function sample() { report("snapshot", "", 0); }
    sample();
    Script.update.connect(sample);
    function ending() {
        Script.update.disconnect(sample);
        report("ending", "", 0);
    }
    return { enabled: true, ending: ending, call: function (name, callback) {
        var call = ++sequence;
        report("entry", name, call);
        try {
            var result = callback();
            report("returned", name, call);
            return result;
        } finally { report("finally", name, call); }
    } };
}
module.exports = { observer: observer };
