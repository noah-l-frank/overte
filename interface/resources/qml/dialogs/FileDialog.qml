// Copyright 2015 High Fidelity, Inc.
// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
import QtQuick 2.7
import QtQuick.Window 2.2
import controlsUit 1.0 as HifiControls
import "../windows" as Windows
Windows.ModalWindow {
    id: root
    objectName: "FileDialog"
    colorScheme: 0
    title: browser.caption
    property int titleWidth: 0
    resizable: true
    implicitWidth: 600
    implicitHeight: 680
    minSize: Qt.vector2d(360, touchPresentation ? 64 : 400)
    keyboardOverride: true
    contentFlickableInteractive: true
    property var touchProfile: fileTouchProfile
    HifiControls.TouchUiProfile { id: fileTouchProfile }
    readonly property bool touchPresentation: touchProfile.directTouch
        && touchProfile.screenSpacePresentation && touchProfile.surfaceWidth > 0
        && touchProfile.surfaceHeight > 0
    readonly property var inputWindow: root.Window.window
    anchors.centerIn: touchPresentation ? undefined : parent
    function alignTouchDialog() {
        if (!touchPresentation) { return; }
        var availableWidth = touchProfile.surfaceWidth - touchProfile.safeInsetLeft - touchProfile.safeInsetRight;
        var availableHeight = touchProfile.surfaceHeight - touchProfile.safeInsetTop
            - Math.max(touchProfile.safeInsetBottom, touchProfile.imeInsetBottom);
        var bounds = framedRect();
        var top = Math.max(0, -bounds.y);
        var bottom = Math.max(0, bounds.height - height - top);
        width = Math.min(600, Math.max(360, availableWidth - (bounds.width - width)));
        height = Math.min(680, Math.max(64, availableHeight - top - bottom));
        x = (touchProfile.screenSpaceOriginAtSafeArea ? 0 : touchProfile.safeInsetLeft)
            + (availableWidth - width) / 2;
        y = (touchProfile.screenSpaceOriginAtSafeArea ? 0 : touchProfile.safeInsetTop)
            + top + Math.max(0, (availableHeight - top - bottom - height) / 2);
        if (!touchProfile.keyboardVisible) {
            pane.resetContentPosition();
        } else if (inputWindow && inputWindow.activeFocusItem) {
            // Leave room for Save/Cancel below the filename as well as its cursor.
            pane.ensureEditorVisible(inputWindow.activeFocusItem, 72);
        }
    }
    Timer { id: touchLayout; interval: 50; onTriggered: root.alignTouchDialog() }
    onTouchPresentationChanged: touchLayout.restart()
    onVisibleChanged: if (visible) { touchLayout.restart(); }
    Connections {
        target: root.touchProfile
        function onKeyboardVisibleChanged() { touchLayout.restart(); }
        function onImeInsetBottomChanged() { touchLayout.restart(); }
        function onSurfaceHeightChanged() { touchLayout.restart(); }
        function onSurfaceWidthChanged() { touchLayout.restart(); }
    }
    Connections {
        target: root.inputWindow
        function onActiveFocusItemChanged() { touchLayout.restart(); }
    }
    property alias caption: browser.caption
    property alias dir: browser.dir
    property alias filter: browser.filter
    property alias options: browser.options
    property alias selectDirectory: browser.selectDirectory
    property alias showHidden: browser.showHidden
    property alias bundleMode: browser.bundleMode
    property alias primaryFilter: browser.primaryFilter
    property alias multiSelect: browser.multiSelect
    property alias saveDialog: browser.saveDialog
    property alias helper: browser.helper
    property alias model: browser.model
    signal selectedFile(var file)
    signal canceled()
    NativeFileBrowser {
        id: browser
        destroyOnCompletion: false
        anchors.fill: undefined
        width: parent.width
        height: Math.max(640, root.pane.scrollHeight)
        onSelectedFile: function(file) { root.selectedFile(file); Qt.callLater(function() { root.destroy(); }); }
        onCanceled: { root.canceled(); Qt.callLater(function() { root.destroy(); }); }
    }
}
