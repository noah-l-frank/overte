// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
import QtQuick 2.7
import QtQuick.Controls 2.2 as QuickControls
import controlsUit 1.0 as HiFiControls

Item {
    id: flick
    HiFiControls.TouchUiMetrics { id: touchMetrics }
    property alias touchProfile: touchMetrics.profile
    property alias url: webView.url
    property alias canGoBack: webView.canGoBack
    property alias canGoForward: webView.canGoForward
    property alias webViewCore: webView
    property alias useBackground: webView.useBackground
    property alias userAgent: webView.userAgent
    property alias userScriptUrl: webView.scriptUrl
    property alias surface: webView.surface
    property alias sourceIdentity: webView.sourceIdentity
    property alias inlineDocument: webView.inlineDocument
    property string urlTag: "noDownload=false"
    property bool interactive: true
    readonly property bool compactNavigation: touchMetrics.directTouch && flick.touchProfile.screenSpacePresentation
    property bool blurOnCtrlShift: true
    signal newViewRequestedCallback(var request)
    signal loadingChangedCallback(var loadRequest)
    signal nativeClosed()
    function stop() { webView.stop(); }
    function unfocus() { webView.unfocus(); }
    // Legacy callers cancel a pending unfocus timer when raising the keyboard.
    // Native surfaces have no such timer; dropping focus would close the editor.
    function stopUnfocus() {}
    function openNative() { return webView.openNative(); }
    function onLoadingChanged(loadRequest) {}
    Row {
        id: navigation
        width: parent.width
        // The phone surface already ends above the native IME. Reserve the
        // remaining height for the focused document; tablet navigation stays
        // available outside this browser toolbar.
        visible: !(touchMetrics.directTouch && touchMetrics.systemImeAvailable
            && flick.touchProfile.screenSpacePresentation && touchMetrics.keyboardVisible)
        height: visible ? (flick.compactNavigation
            ? Math.max(touchMetrics.adaptiveMinimumControlHeight, Math.ceil(26 * touchMetrics.textScale)) : 48) : 0
        spacing: 4
        QuickControls.Button {
            objectName: "EmbeddedWebBack"
            width: flick.compactNavigation
                ? Math.max(touchMetrics.adaptiveMinimumControlHeight,
                    Math.min(contentItem.implicitWidth + 16, (navigation.width - 12) / 4))
                : (touchMetrics.directTouch ? Math.min(implicitWidth + 24, (navigation.width - 12) / 4)
                    : (navigation.width - 12) / 4)
            height: navigation.height
            text: qsTr("Back")
            enabled: flick.interactive && webView.canGoBack
            focusPolicy: Qt.NoFocus
            onClicked: webView.goBack()
        }
        QuickControls.Button {
            objectName: "EmbeddedWebForward"
            width: flick.compactNavigation
                ? Math.max(touchMetrics.adaptiveMinimumControlHeight,
                    Math.min(contentItem.implicitWidth + 16, (navigation.width - 12) / 4))
                : (touchMetrics.directTouch ? Math.min(implicitWidth + 24, (navigation.width - 12) / 4)
                    : (navigation.width - 12) / 4)
            height: navigation.height
            text: qsTr("Forward")
            enabled: flick.interactive && webView.canGoForward
            focusPolicy: Qt.NoFocus
            onClicked: webView.goForward()
        }
        QuickControls.Button {
            objectName: "EmbeddedWebReload"
            width: flick.compactNavigation
                ? Math.max(touchMetrics.adaptiveMinimumControlHeight,
                    Math.min(contentItem.implicitWidth + 16, (navigation.width - 12) / 4))
                : (touchMetrics.directTouch ? Math.min(implicitWidth + 24, (navigation.width - 12) / 4)
                    : (navigation.width - 12) / 4)
            height: navigation.height
            text: qsTr("Reload")
            enabled: flick.interactive && webView.url.length > 0
            focusPolicy: Qt.NoFocus
            onClicked: webView.reload()
        }
        QuickControls.Button {
            objectName: "EmbeddedWebClose"
            width: flick.compactNavigation
                ? Math.max(touchMetrics.adaptiveMinimumControlHeight,
                    Math.min(contentItem.implicitWidth + 16, (navigation.width - 12) / 4))
                : (touchMetrics.directTouch ? Math.min(implicitWidth + 24, (navigation.width - 12) / 4)
                    : (navigation.width - 12) / 4)
            height: navigation.height
            text: qsTr("Close")
            focusPolicy: Qt.NoFocus
            onClicked: { flick.stop(); flick.nativeClosed(); }
        }
    }
    EmbeddedWebView {
        id: webView
        anchors { left: parent.left; right: parent.right; top: navigation.bottom; bottom: parent.bottom }
        enabled: flick.enabled && flick.interactive
        surface: "tablet"
        onLoadingChangedWithStatus: function(change) {
            flick.onLoadingChanged(change);
            flick.loadingChangedCallback(change);
        }
        onNativeClosed: flick.nativeClosed()
    }
}
