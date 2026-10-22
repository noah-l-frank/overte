// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Ordinary test application: all navigation uses the documented Tablet API.
(function () {
    "use strict";
    var tablet = Tablet.getTablet("com.highfidelity.interface.tablet.system");
    var page = Script.resolvePath("index.html"), injected = Script.resolvePath("injected.js");
    var current = Script.resolvePath("../../current"), stopped = false, pending = false;
    var web = tablet.addButton({text: "WEB TEST", sortOrder: 200});
    var inline = tablet.addButton({text: "INLINE TEST", sortOrder: 201});
    function get(url, next) {
        var request = new XMLHttpRequest();request.open("GET", url);
        request.onreadystatechange = function () {
            if (request.readyState !== request.DONE || stopped) return;
            if (request.status !== 200) { pending = false;return; }
            try { next(JSON.parse(request.responseText)); } catch (_) { pending = false; }
        };
        request.send();
    }
    function openWeb() { if (!stopped) tablet.gotoWebScreen(page, injected); }
    function openInline() {
        if (stopped || pending) return;pending = true;
        // The server supplies ordinary immutable app INPUT, never observations.
        get(current, function (phase) {
            if (!phase || typeof phase.ticket !== "string" || !/^[0-9a-f]{32}$/.test(phase.ticket)) { pending = false;return; }
            get(Script.resolvePath("../" + phase.ticket + "/inline-input.json"), function (input) {
                if (!input || typeof input.dataUrl !== "string" || input.dataUrl.indexOf("data:text/html;charset=utf-8;base64,") !== 0) { pending = false;return; }
                pending = false;tablet.gotoWebScreen(input.dataUrl, injected);
            });
        });
    }
    function echo(message) {
        if (stopped || typeof message !== "string" || message.length > 4096) return;
        var packet;try { packet = JSON.parse(message); } catch (_) { return; }
        if (!packet || packet.contract !== "overte-web-parity-v1" || packet.action !== "echo" ||
                typeof packet.sequence !== "number" || !isFinite(packet.sequence) || packet.sequence < 1 ||
                packet.sequence > 1000000 || Math.floor(packet.sequence) !== packet.sequence) return;
        // No cooperative origin filtering: actual native authority must reject it.
        tablet.emitScriptEvent(JSON.stringify({contract: packet.contract, action: "echo", sequence: packet.sequence, surface: "tablet"}));
    }
    web.clicked.connect(openWeb);inline.clicked.connect(openInline);tablet.webEventReceived.connect(echo);
    Script.scriptEnding.connect(function () {
        stopped = true;web.clicked.disconnect(openWeb);inline.clicked.disconnect(openInline);
        tablet.webEventReceived.disconnect(echo);tablet.gotoHomeScreen();tablet.removeButton(inline);tablet.removeButton(web);
    });
}());
