// Copyright 2016 High Fidelity, Inc.
// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
import QtQuick 2.7
import QtQuick.Controls 2.3
import QtQuick.Layouts 1.3
import controlsUit 1.0 as HifiControls

Rectangle {
    id: root
    objectName: "RunningScripts"
    color: "#292929"
    implicitWidth: 600
    implicitHeight: 700
    property string title: "Running Scripts"
    property var scripts: ScriptDiscoveryService
    property var scriptsModel: scripts.scriptsModelFilter
    property var runningScriptsModel: []
    property bool developerMenuEnabled: false
    property bool isHMD: HMD.active
    property string status: ""
    readonly property int controlHeight: Math.max(32, metrics.adaptiveMinimumControlHeight)
    signal sendToScript(var message)
    function filename(url) { return String(url).split(/[?#]/)[0].replace(/\\/g, "/").split("/").pop(); }
    function canEditScript(url) { var name = filename(url); return developerMenuEnabled || (name !== "controllerScripts.js" && name !== "defaultScripts.js"); }
    function updateRunningScripts() {
        var list = scripts.getRunning().slice();
        list.sort(function(a, b) { var aa = filename(a.url || a.path).toLowerCase(), bb = filename(b.url || b.path).toLowerCase(); return aa < bb ? -1 : aa > bb ? 1 : 0; });
        runningScriptsModel = list;
    }
    function loadScript(url) {
        if (!String(url).trim()) return;
        if (/^atp:/i.test(String(url).trim())) { status = "Client scripts cannot be loaded over ATP."; return; }
        status = "Loading " + filename(url);
        scripts.loadOneScript(String(url).trim());
    }
    function reloadScript(url) { if (canEditScript(url)) { scripts.stopScript(url, true); status = "Restarting " + filename(url); } }
    function stopScript(url) { if (canEditScript(url)) { scripts.stopScript(url); status = "Stopping " + filename(url); } }
    function reloadAll() {
        if (developerMenuEnabled) scripts.reloadAllScripts();
        else runningScriptsModel.forEach(function(script) { root.reloadScript(script.url || script.path); });
    }
    function stopAll() { runningScriptsModel.forEach(function(script) { root.stopScript(script.url || script.path); }); }
    function loadDefaults() { if (developerMenuEnabled) loadScript(scripts.defaultScriptsPath + "/defaultScripts.js"); }
    Component.onCompleted: { developerMenuEnabled = MenuInterface.isOptionChecked("Developer Menu"); updateRunningScripts(); }
    Connections {
        target: root.scripts
        function onScriptCountChanged() { root.updateRunningScripts(); }
        function onScriptLoadError(url, error) { root.status = "Failed to load " + root.filename(url) + (error ? ": " + error : ""); }
    }
    Timer { interval: 1000; repeat: true; running: root.visible; onTriggered: root.developerMenuEnabled = MenuInterface.isOptionChecked("Developer Menu") }
    HifiControls.TouchUiMetrics { id: metrics }
    Flickable {
        id: viewport
        objectName: "scriptViewport"
        anchors.fill: parent; anchors.margins: 12
        clip: true
        contentWidth: width
        contentHeight: content.height
        boundsBehavior: Flickable.StopAtBounds
        pressDelay: metrics.pressDelay
        flickDeceleration: metrics.flickDeceleration
        maximumFlickVelocity: metrics.maximumFlickVelocity
        ScrollBar.vertical: ScrollBar {}
    ColumnLayout {
        id: content
        width: viewport.width
        height: Math.max(viewport.height, heading.implicitHeight
            + (statusLabel.visible ? statusLabel.implicitHeight + spacing : 0)
            + actions.height + running.Layout.preferredHeight + loaders.height
            + filter.implicitHeight + 180 + 6 * spacing + keyboard.implicitHeight)
        spacing: 8
        Label { id: heading; text: root.title; color: "white"; font.pixelSize: 22; Layout.fillWidth: true }
        Label {
            id: statusLabel
            objectName: "scriptStatus"
            text: root.status
            color: "#cccccc"
            wrapMode: Text.WordWrap
            maximumLineCount: 3
            elide: Text.ElideRight
            Layout.fillWidth: true
            visible: text.length > 0
            Accessible.role: Accessible.StaticText
            Accessible.name: text
        }
        Flow {
            id: actions
            Layout.fillWidth: true; spacing: 8
            Button { objectName: "scriptReloadAll"; text: "Reload All"; implicitHeight: root.controlHeight; onClicked: root.reloadAll() }
            Button { objectName: "scriptStopAll"; text: "Stop All"; implicitHeight: root.controlHeight; onClicked: root.stopAll() }
            Button { objectName: "scriptLoadDefaults"; text: "Load Defaults"; visible: root.developerMenuEnabled; implicitHeight: root.controlHeight; onClicked: root.loadDefaults() }
        }
        ListView {
            id: running; objectName: "runningScriptList"; Layout.fillWidth: true; Layout.preferredHeight: Math.min(220, root.height / 3); clip: true; model: root.runningScriptsModel
            ScrollBar.vertical: ScrollBar {}
            delegate: RowLayout {
                width: running.width; height: root.controlHeight
                Label { text: root.filename(modelData.url || modelData.path); color: "white"; Layout.fillWidth: true; elide: Text.ElideMiddle; ToolTip.text: modelData.url || modelData.path; ToolTip.visible: scriptHover.containsMouse; MouseArea { id: scriptHover; anchors.fill: parent; hoverEnabled: true; acceptedButtons: Qt.NoButton } }
                Button { objectName: "scriptRestart" + index; text: "Restart"; enabled: root.canEditScript(modelData.url || modelData.path); implicitHeight: root.controlHeight; onClicked: root.reloadScript(modelData.url || modelData.path) }
                Button { objectName: "scriptStop" + index; text: "Stop"; enabled: root.canEditScript(modelData.url || modelData.path); implicitHeight: root.controlHeight; onClicked: root.stopScript(modelData.url || modelData.path) }
            }
        }
        Flow {
            id: loaders
            Layout.fillWidth: true; spacing: 8
            Button { objectName: "scriptFromUrl"; text: "From URL"; implicitHeight: root.controlHeight; onClicked: ApplicationInterface.loadScriptURLDialog() }
            Button { objectName: "scriptFromFile"; text: "From File"; implicitHeight: root.controlHeight; onClicked: ApplicationInterface.loadDialog() }
            Button { objectName: "scriptLoadSelected"; text: "Load Selected"; implicitHeight: root.controlHeight; enabled: browser.currentIndex !== null && !!root.scriptsModel.data(browser.currentIndex, 256); onClicked: root.loadScript(root.scriptsModel.data(browser.currentIndex, 256)) }
        }
        TextField { objectName: "scriptFilter"; placeholderText: "Filter installed scripts"; Layout.fillWidth: true; implicitHeight: root.controlHeight; onTextChanged: browser.filterText = text; id: filter }
        NativeModelTree { id: browser; objectName: "scriptTree"; Layout.fillWidth: true; Layout.fillHeight: true; Layout.minimumHeight: 180; sourceModel: root.scriptsModel; onActivated: function(index) { root.loadScript(root.scriptsModel.data(index, 256)); } }
        NativeKeyboardHost { id: keyboard; Layout.fillWidth: true; Layout.preferredHeight: implicitHeight; inputFocused: filter.activeFocus }
    }
    }
}
