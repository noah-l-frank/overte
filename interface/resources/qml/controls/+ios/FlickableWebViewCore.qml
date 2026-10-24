// Copyright 2026 Overte e.V.
// SPDX-License-Identifier: Apache-2.0
import QtQuick 2.15
import QtQuick.Controls 2.15 as QuickControls
import controls 1.0 as SharedControls

SharedControls.NativeFlickableWebViewCore {
    id: flick

    // World input deliberately admits stationary taps rather than turning a
    // camera/virtual-pad drag into a page click. Give those taps explicit page
    // scrolling, and expose the existing same-document native presentation for
    // native media controls, nested scrolling and accessibility.
    function scrollWorldPage(direction) {
        if (surface !== "world-entity" || !visible || !enabled || !interactive ||
                webViewCore.loading || webViewCore.error.length ||
                (direction !== -1 && direction !== 1)) { return; }
        var distance = Math.max(48, Math.round(webViewCore.height * 0.8)) * direction;
        webViewCore.runJavaScript("window.scrollBy(0," + distance + ");");
    }

    Binding {
        target: flick.webViewCore
        property: "anchors.topMargin"
        value: worldControls.visible ? worldControls.height : 0
    }
    Row {
        id: worldControls
        objectName: "IOSWorldWebControls"
        y: 48
        width: parent.width
        height: 48
        spacing: 4
        visible: flick.surface === "world-entity"
        enabled: flick.enabled && flick.interactive && flick.url.length > 0
        QuickControls.Button {
            objectName: "IOSWorldWebScrollUp"
            width: (worldControls.width - 8) / 3
            height: worldControls.height
            text: qsTr("Scroll up")
            enabled: !flick.webViewCore.loading && !flick.webViewCore.error.length
            Accessible.name: text
            onClicked: flick.scrollWorldPage(-1)
        }
        QuickControls.Button {
            objectName: "IOSWorldWebScrollDown"
            width: (worldControls.width - 8) / 3
            height: worldControls.height
            text: qsTr("Scroll down")
            enabled: !flick.webViewCore.loading && !flick.webViewCore.error.length
            Accessible.name: text
            onClicked: flick.scrollWorldPage(1)
        }
        QuickControls.Button {
            objectName: "IOSWorldWebOpenBrowser"
            width: (worldControls.width - 8) / 3
            height: worldControls.height
            text: qsTr("Open browser")
            Accessible.name: qsTr("Open this world page in the native browser")
            onClicked: flick.openNative()
        }
    }
}
