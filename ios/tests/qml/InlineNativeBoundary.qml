// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
import QtQuick 2.15
import IOSInlineProperties 1.0

// Actual native property bodies and Qt item/context, with an explicit unopened
// WK boundary. This fixture never pretends to load HTML, initialize a bridge or
// play video successfully.
NativeProperties {
    property string userAgent: ""
    property string eventBridgeJavaScript: ""
    property bool useBackground: true
    readonly property string currentUrl: url
    readonly property bool loading: false
    readonly property bool canGoBack: false
    readonly property bool canGoForward: false
    readonly property string error: "Native WK boundary not executed"
    readonly property bool bridgeAvailable: false
    signal webEventReceived(var message)
    signal nativeClosed()
    function emitScriptEvent(message) {}
    function runJavaScript(code, callback) { return false; }
    function openNative() { return false; }
    function goBack() { return false; }
    function goForward() { return false; }
    function reload() { return false; }
    function reloadAndBypassCache() { return false; }
    function stop() {}
    function unfocus() {}
}
