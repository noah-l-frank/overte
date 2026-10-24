// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
import QtQuick 2.15
import controls 1.0 as SharedControls

SharedControls.FlickableWebViewCore {
    id: web
    surface: "world-entity"
    property alias scriptUrl: web.userScriptUrl
    function fromScript(message) { webViewCore.fromScript(message); }
}
