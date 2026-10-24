// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Only UIKit/WK is substituted. All selected world/shared QML runs unchanged.
import QtQuick 2.15
import "../../../tests/device/contracts/web/qml" as Boundary
Boundary.FakeEmbeddedWebBackend {
    property var scripts: []
    function runJavaScript(source, callback) {
        scripts.push(source);
        if (callback) { callback("native-result"); }
    }
}
