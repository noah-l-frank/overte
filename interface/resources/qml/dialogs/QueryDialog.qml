//
//  QueryDialog.qml
//
//  Created by Bradley Austin Davis on 22 Jan 2016
//  Copyright 2015 High Fidelity, Inc.
//
//  Distributed under the Apache License, Version 2.0.
//  See the accompanying file LICENSE or http://www.apache.org/licenses/LICENSE-2.0.html
//

import QtQuick 2.7
import QtQuick.Window 2.2
import QtQuick.Controls 2.3

import controlsUit 1.0
import stylesUit 1.0
import "../windows"

ModalWindow {
    id: root
    objectName: "QueryDialog"
    property var touchProfile: queryTouchProfile
    TouchUiProfile { id: queryTouchProfile }
    readonly property bool touchPresentation: touchProfile.directTouch
        && touchProfile.screenSpacePresentation && touchProfile.surfaceWidth > 0
        && touchProfile.surfaceHeight > 0
    readonly property var inputWindow: root.Window.window
    anchors.centerIn: touchPresentation ? undefined : parent
    minSize: Qt.vector2d(100, touchPresentation ? 64 : 100)
    Binding {
        target: root.frame
        property: "titleVisible"
        value: !(root.touchPresentation && root.touchProfile.keyboardVisible)
    }
    function alignTouchDialog() {
        if (!touchPresentation) { return; }
        var availableWidth = touchProfile.surfaceWidth - touchProfile.safeInsetLeft - touchProfile.safeInsetRight;
        var availableHeight = touchProfile.surfaceHeight - touchProfile.safeInsetTop
            - Math.max(touchProfile.safeInsetBottom, touchProfile.imeInsetBottom);
        var bounds = framedRect();
        var top = Math.max(0, -bounds.y);
        var bottom = Math.max(0, bounds.height - height - top);
        width = Math.min(d.preferredWidth, Math.max(360, availableWidth - (bounds.width - width)));
        height = Math.min(d.preferredHeight, Math.max(64, availableHeight - top - bottom));
        x = (touchProfile.screenSpaceOriginAtSafeArea ? 0 : touchProfile.safeInsetLeft)
            + (availableWidth - width) / 2;
        y = (touchProfile.screenSpaceOriginAtSafeArea ? 0 : touchProfile.safeInsetTop)
            + top + Math.max(0, (availableHeight - top - bottom - height) / 2);
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
    HifiConstants { id: hifi }
    implicitWidth: 640
    implicitHeight: 320
    visible: true
    keyboardOverride: true  // Disable ModalWindow's keyboard.

    signal selected(var result);
    signal canceled();

    property int icon: hifi.icons.none
    property string iconText: ""
    property int iconSize: 35
    onIconChanged: updateIcon();

    property var items;
    property string label
    property var result;
    property var current: ""

    // For text boxes
    property alias placeholderText: textResult.placeholderText

    // For combo boxes
    property bool editable: true;

    property int titleWidth: 0
    onTitleWidthChanged: d.resize();

    property bool keyboardEnabled: false
    property bool keyboardRaised: false
    property bool punctuationMode: false

    onKeyboardRaisedChanged: d.resize();

    function updateIcon() {
        if (!root) {
            return;
        }
        iconText = hifi.glyphForIcon(root.icon);
    }

    Item {
        id: modalWindowItem
        clip: true
        width: pane.width
        height: pane.height
        anchors.margins: 0

        QtObject {
            id: d
            readonly property int minWidth: 480
            readonly property int maxWidth: 1280
            readonly property int minHeight: 120
            readonly property int maxHeight: 720
            property real preferredWidth: 640
            property real preferredHeight: 320

            function resize() {
                var targetWidth = Math.max(titleWidth, pane.width)
                var targetHeight = (items ? comboBox.controlHeight : textResult.controlHeight) + 5 * hifi.dimensions.contentSpacing.y + buttons.height
                preferredWidth = Math.max(d.minWidth, Math.min(d.maxWidth, targetWidth));
                preferredHeight = Math.max(d.minHeight, Math.min(d.maxHeight, targetHeight))
                    + ((keyboardEnabled && keyboardRaised) ? (keyboard.raisedHeight + 2 * hifi.dimensions.contentSpacing.y) : 0);
                if (root.touchPresentation) {
                    touchLayout.restart();
                } else {
                    root.width = preferredWidth;
                    root.height = preferredHeight;
                }
            }
        }

        Item {
            anchors {
                top: parent.top
                bottom: keyboard.top;
                left: parent.left;
                right: parent.right;
                margins: 0
                bottomMargin: 2 * hifi.dimensions.contentSpacing.y
            }

            // FIXME make a text field type that can be bound to a history for autocompletion
            TextField {
                id: textResult
                objectName: "queryTextInput"
                text: root.items ? "" : (root.current === undefined || root.current === null ? "" : String(root.current))
                label: root.label
                visible: items ? false : true
                anchors {
                    left: parent.left;
                    right: parent.right;
                    bottom: parent.bottom
                }
                KeyNavigation.down: acceptButton
                KeyNavigation.tab: acceptButton
            }

            ComboBox {
                id: comboBox
                label: root.label
                visible: items ? true : false
                anchors {
                    left: parent.left
                    right: parent.right
                    bottom: parent.bottom
                }
                model: items ? items : []
                editable: root.editable
                currentIndex: typeof root.current === "number" ? root.current : 0
                KeyNavigation.down: acceptButton
                KeyNavigation.tab: acceptButton
            }
        }

        property alias keyboardOverride: root.keyboardOverride
        property alias keyboardRaised: root.keyboardRaised
        property alias punctuationMode: root.punctuationMode
        Keyboard {
            id: keyboard
            raised: keyboardEnabled && keyboardRaised
            numeric: punctuationMode
            anchors {
                left: parent.left
                right: parent.right
                bottom: buttons.top
                bottomMargin: raised ? 2 * hifi.dimensions.contentSpacing.y : 0
            }
        }

        Flow {
            id: buttons
            spacing: hifi.dimensions.contentSpacing.x
            onHeightChanged: d.resize(); onWidthChanged: d.resize();
            layoutDirection: Qt.RightToLeft
            anchors {
                bottom: parent.bottom
                right: parent.right
                margins: 0
                bottomMargin: hifi.dimensions.contentSpacing.y
            }
            Button {
                id: cancelButton
                objectName: "queryCancel"
                width: root.touchPresentation
                    ? Math.min(Math.max(100, implicitWidth), Math.max(0, (root.width - buttons.spacing) / 2))
                    : hifi.dimensions.buttonWidth
                action: cancelAction
                KeyNavigation.left: acceptButton
                KeyNavigation.up: items ? comboBox : textResult
                KeyNavigation.backtab: acceptButton
            }
            Button {
                id: acceptButton
                objectName: "queryAccept"
                width: root.touchPresentation
                    ? Math.min(Math.max(100, implicitWidth), Math.max(0, (root.width - buttons.spacing) / 2))
                    : hifi.dimensions.buttonWidth
                action: acceptAction
                KeyNavigation.right: cancelButton
                KeyNavigation.up: items ? comboBox : textResult
                KeyNavigation.tab: cancelButton
                KeyNavigation.backtab: items ? comboBox : textResult
            }
        }

        Action {
            id: cancelAction
            text: qsTr("Cancel");
            shortcut: "Esc"
            onTriggered: {
                root.canceled();
                root.destroy();
            }
        }

        Action {
            id: acceptAction
            text: qsTr("OK");
            shortcut: "Return"
            onTriggered: {
                root.result = items ? (comboBox.editable ? comboBox.editText : comboBox.currentText) : textResult.text
                root.selected(root.result);
                root.destroy();
            }
        }
    }

    Keys.onPressed: {
        if (!visible) {
            return
        }

        switch (event.key) {
        case Qt.Key_Escape:
        case Qt.Key_Back:
            cancelAction.trigger()
            event.accepted = true;
            break;

        case Qt.Key_Return:
        case Qt.Key_Enter:
            if (acceptButton.focus) {
                acceptAction.trigger()
            } else if (cancelButton.focus) {
                cancelAction.trigger()
            } else if (comboBox.focus || comboBox.popup.focus) {
                comboBox.showList()
            }
            event.accepted = true;
            break;
        }
    }

    Component.onCompleted: {
        keyboardEnabled = HMD.active;
        updateIcon();
        d.resize();
        if (items) {
            comboBox.forceActiveFocus()
        } else {
            textResult.forceActiveFocus()
        }
    }
}
