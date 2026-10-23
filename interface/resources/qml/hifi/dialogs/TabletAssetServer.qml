// Copyright 2017 High Fidelity, Inc.
// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
import QtQuick 2.7
import QtQuick.Controls 2.3
import QtQuick.Layouts 1.3
import controlsUit 1.0 as HifiControls
import "../../dialogs"

Rectangle {
    id: root
    objectName: "AssetServer"
    color: "#292929"
    implicitWidth: 600
    implicitHeight: 700
    property string title: "Asset Browser"
    property var assetProxyModel: Assets.proxyModel
    property var assetMappingsModel: Assets.mappingModel
    property var currentDirectory: fileDialogHelper.home()
    property bool assetWriteAllowed: Entities.canWriteAssets()
    property bool importAllowed: Entities.canRez() || Entities.canRezTmp()
    property var pendingBundle: null
    property string bundleRequest: ""
    property string uploadedPrimaryUrl: ""
    property string singleUploadUrl: ""
    property string singleUploadMapping: ""
    property bool busy: false
    property string status: ""
    property var lifecycle: ({active: true})
    readonly property int updatesCount: tree.revision
    readonly property int selectedItemCount: tree.selectedIndexes.length
    readonly property var currentIndex: tree.currentIndex
    readonly property string selectedUrl: currentIndex !== null ? String(assetProxyModel.data(currentIndex, 259) || "") : ""
    readonly property string selectedPath: currentIndex !== null ? String(assetProxyModel.data(currentIndex, 256) || "") : ""
    signal sendToScript(var message)
    function writable() {
        assetWriteAllowed = Entities.canWriteAssets();
        if (!assetWriteAllowed) status = "You can browse assets; writing requires Asset Server permission.";
        return assetWriteAllowed;
    }
    function reload() { assetMappingsModel.refresh(); }
    function selectedPaths() {
        return tree.selectedIndexes.map(function(index) { return String(assetProxyModel.data(index, 256) || ""); }).filter(function(path) { return path.length > 0; });
    }
    function normalizedPath(path) {
        path = String(path).trim();
        if (path.charAt(0) !== "/") path = "/" + path;
        if (path.split("/").some(function(part) { return part === "." || part === ".."; })) return "";
        return path;
    }
    function resultHandler(operation, done) {
        var lifetime = lifecycle;
        return function(error) {
            if (!lifetime.active) return;
            busy = false;
            status = error ? operation + " failed: " + String(error) : operation + " complete.";
            if (done) done(error);
            reload();
        };
    }
    function doDeleteFile(paths) {
        if (!writable() || busy || !paths.length) return;
        busy = true;
        Assets.deleteMappings(paths, resultHandler("Delete"));
    }
    function doRenameFile(oldPath, newPath) {
        if (!writable() || busy || !oldPath) return;
        newPath = normalizedPath(newPath);
        if (!newPath || newPath === "/") { status = "Enter a valid asset path."; return; }
        if (oldPath.slice(-1) === "/" && newPath.slice(-1) !== "/") newPath += "/";
        if (newPath === oldPath) { status = "Rename complete."; return; }
        if (oldPath.slice(-1) === "/" && newPath.indexOf(oldPath) === 0) {
            status = "Cannot move a folder inside itself."; return;
        }
        if (Assets.isKnownFolder(newPath)) { status = "Cannot overwrite an existing folder."; return; }
        if (oldPath.slice(-1) === "/") { renameFolder(oldPath, newPath); return; }
        if (Assets.isKnownMapping(newPath) && newPath !== oldPath) {
            pendingRenameOld = oldPath; pendingRenameNew = newPath; overwriteDialog.open(); return;
        }
        busy = true;
        Assets.renameMapping(oldPath, newPath, resultHandler("Rename"));
    }
    function renameFolder(oldPath, newPath) {
        // Older asset servers accept file renames but reject trailing slashes
        // before reaching their folder branch. Rename the actual mappings so
        // folder operations also work with these existing domains.
        busy = true;
        var finish = resultHandler("Rename");
        Assets.getAllMappings(function(error, mappings) {
            if (error) { finish(error); return; }
            var paths = Object.keys(mappings).filter(function(path) { return path.indexOf(oldPath) === 0; }).sort();
            if (!paths.length) { finish("The selected folder no longer exists."); return; }
            var moves = paths.map(function(path) { return {oldPath: path, newPath: newPath + path.slice(oldPath.length)}; });
            if (moves.some(function(move) { return mappings[move.newPath] !== undefined; })) {
                finish("The destination contains an existing asset."); return;
            }
            var completed = [];
            function rollback(reason) {
                if (!completed.length) { finish(reason); return; }
                var move = completed.pop();
                Assets.renameMapping(move.newPath, move.oldPath, function(rollbackError) {
                    if (rollbackError) {
                        finish(reason + " Some moved assets could not be restored: " + String(rollbackError));
                        return;
                    }
                    rollback(reason);
                });
            }
            function next(index) {
                if (index === moves.length) { finish(""); return; }
                var move = moves[index];
                Assets.renameMapping(move.oldPath, move.newPath, function(renameError) {
                    if (renameError) { rollback(String(renameError)); return; }
                    completed.push(move);
                    next(index + 1);
                });
            }
            next(0);
        });
    }
    property string pendingRenameOld: ""
    property string pendingRenameNew: ""
    function setMapping(path, hash) {
        if (!writable() || busy) return;
        path = normalizedPath(path); hash = String(hash).trim().toLowerCase();
        if (!path || path === "/" || !/^[a-f0-9]{64}$/.test(hash)) { status = "Provide an asset path and a 64-digit SHA-256 hash."; return; }
        busy = true;
        Assets.setMapping(path, hash, resultHandler("Mapping"));
    }
    function bakingAvailable() {
        var revision = tree.revision;
        var indexes = tree.selectedIndexes;
        if (tree.currentIndex === null || !indexes.length) return false;
        var states = indexes.map(function(index) { return assetProxyModel.data(index, 261); });
        return states.indexOf("--") === -1 && states.every(function(state) { return (state !== "Not Baked") === (states[0] !== "Not Baked"); });
    }
    function setBakingEnabled(enabled) {
        if (!writable() || busy || !bakingAvailable()) return;
        var paths = selectedPaths();
        var lifetime = lifecycle;
        var finished = resultHandler("Baking selection");
        busy = true;
        Assets.setBakingEnabled(paths, enabled, function(error) {
            if (!lifetime.active) return;
            if (error || enabled) { finished(error); return; }
            if (!writable()) { finished("Asset Server permission changed."); return; }
            // Older servers remove named bake metadata on the first disable.
            // Repeat the idempotent operation to install their canonical
            // original-file redirect as well, so the asset stays Not Baked.
            Assets.setBakingEnabled(paths, false, finished);
        });
    }
    function canAddToWorld(url) { return selectedItemCount === 1 && /\.(fbx|obj|gltf|glb|vrm|jpg|jpeg|png)(?:[?#]|$)/i.test(url); }
    function importSucceeded(id) {
        status = !id || !String(id).replace(/[0{}-]/g, "") ? "Import failed: entity creation was denied or unavailable." : "Added asset to the world.";
    }
    function addToWorld() {
        if (!canAddToWorld(selectedUrl)) return;
        if (!Entities.canRez() && !Entities.canRezTmp()) { status = "You do not have permission to create entities."; return; }
        var grabbable = MenuInterface.isOptionChecked("Create Entities As Grabbable (except Zones, Particles, and Lights)");
        var position = Vec3.sum(MyAvatar.position, Vec3.multiply(2, Quat.getForward(MyAvatar.orientation)));
        var name = String(assetProxyModel.data(currentIndex, 0));
        if (/\.(jpg|jpeg|png)(?:[?#]|$)/i.test(selectedUrl)) {
            importSucceeded(Entities.addImageEntity(name, selectedUrl, grabbable, position));
        } else {
            modelUrl.text = selectedUrl;
            modelName = name;
            modelPosition = position;
            shape.currentIndex = 2;
            dynamic.checked = false;
            modelDialog.open();
        }
    }
    property string modelName: ""
    property var modelPosition
    function importModel() {
        if (!Entities.canRez() && !Entities.canRezTmp()) { status = "You do not have permission to create entities."; return; }
        var types = ["none", "simple-hull", "simple-compound", "static-mesh", "box", "sphere"];
        var type = types[shape.currentIndex];
        if (type === "static-mesh" && dynamic.checked) { status = "A static mesh cannot be dynamic."; return; }
        var gravity = Vec3.multiply(Vec3.fromPolar(Math.PI / 2, 0), dynamic.checked ? 10 : 0);
        importSucceeded(Entities.addModelEntity(modelName, modelUrl.text.trim(), "", type, dynamic.checked, type === "none",
            MenuInterface.isOptionChecked("Create Entities As Grabbable (except Zones, Particles, and Lights)"), modelPosition, gravity));
    }
    function uploadFile(url, dropping) {
        if (!writable() || busy) return;
        var local = fileDialogHelper.urlToPath(url);
        if (!local || !fileDialogHelper.urlIsFile(url)) { status = "Select a readable local document."; return; }
        var folder = selectedPath ? selectedPath.slice(0, selectedPath.lastIndexOf("/") + 1) : "/";
        var name = local.replace(/\\/g, "/").split("/").pop();
        singleUploadUrl = url;
        singlePath.text = folder + name;
        Qt.callLater(function() { if (root.lifecycle.active) singleDialog.open(); });
    }
    function confirmSingleUpload() {
        var path = normalizedPath(singlePath.text);
        if (!path || path === "/" || path.slice(-1) === "/") {
            singleUploadUrl = ""; status = "Enter a valid file mapping."; return;
        }
        singleUploadMapping = path;
        if (Assets.isKnownMapping(path)) { singleOverwriteDialog.open(); }
        else { startSingleUpload(); }
    }
    function cancelSingleUpload() {
        singleUploadUrl = ""; singleUploadMapping = ""; status = "Upload canceled.";
    }
    function startSingleUpload() {
        if (!writable() || busy || !singleUploadUrl) { singleUploadUrl = ""; return; }
        var local = fileDialogHelper.urlToPath(singleUploadUrl);
        var lifetime = lifecycle;
        var name = singleUploadMapping.split("/").pop();
        singleUploadUrl = "";
        busy = true; status = "Preparing upload...";
        Assets.uploadFile(local, singleUploadMapping,
            function() { if (lifetime.active) status = "Uploading " + name; },
            resultHandler("Upload", function(error) { if (error === -1) status = "Upload canceled."; }), false, true);
    }
    function uploadClicked(url) {
        if (!writable() || busy) return;
        if (url) { uploadFile(url, true); return; }
        var browser = fileBrowser.createObject(root, {dir: currentDirectory});
        if (!browser) { status = "The file browser is unavailable."; return; }
        browser.selectedBundle.connect(function(manifest) {
            currentDirectory = browser.dir; pendingBundle = manifest;
            bundleDestination.text = selectedPath ? selectedPath.slice(0, selectedPath.lastIndexOf("/") + 1) : "/";
            Qt.callLater(function() { bundleDialog.open(); });
        });
    }
    function uploadSingleClicked() {
        if (!writable() || busy) return;
        var browser = fileBrowser.createObject(root, {dir: currentDirectory, bundleMode: false, caption: "Select one asset to upload"});
        if (!browser) { status = "The file browser is unavailable."; return; }
        browser.selectedFile.connect(function(url) { currentDirectory = browser.dir; root.uploadFile(url, false); });
    }
    function uploadBundle() {
        if (!writable() || busy || !pendingBundle) return;
        var lifetime = lifecycle;
        var files = pendingBundle.urls.map(function(url) { return fileDialogHelper.urlToPath(url); });
        uploadedPrimaryUrl = ""; busy = true; status = "Preparing bundle upload...";
        bundleRequest = Assets.uploadBundle(files, pendingBundle.relativePaths, bundleDestination.text, pendingBundle.primaryPath,
            function(index, phase) { if (lifetime.active) status = phase + " · " + (index + 1) + "/" + files.length; },
            function(error, published, primary) {
                if (!lifetime.active) return;
                bundleRequest = ""; busy = false;
                var count = JSON.parse(published).length;
                status = error ? "Bundle upload stopped: " + error + " Published mappings: " + count + "." : "Uploaded " + count + " files with their relative paths.";
                if (!error) uploadedPrimaryUrl = "atp:" + primary.split("/").map(encodeURIComponent).join("/");
                pendingBundle = null; reload();
            });
        if (!bundleRequest) { busy = false; status = "The upload service is busy or unavailable."; }
    }
    function importUploadedMain() {
        if (!Entities.canRez() && !Entities.canRezTmp()) { status = "You do not have permission to create entities."; return; }
        modelUrl.text = uploadedPrimaryUrl;
        modelName = decodeURIComponent(uploadedPrimaryUrl.split("/").pop());
        modelPosition = Vec3.sum(MyAvatar.position, Vec3.multiply(2, Quat.getForward(MyAvatar.orientation)));
        shape.currentIndex = 2; dynamic.checked = false; modelDialog.open();
    }
    Component.onCompleted: { assetMappingsModel.autoRefreshEnabled = true; reload(); }
    Component.onDestruction: { lifecycle.active = false; if (bundleRequest) Assets.cancelUploadBundle(bundleRequest); assetMappingsModel.autoRefreshEnabled = false; }
    Connections {
        target: root.assetMappingsModel
        function onErrorGettingMappings(message) { root.status = "Could not browse assets: " + message; }
    }
    Connections {
        target: ApplicationInterface
        function onUploadRequest(url) { root.uploadClicked(url); }
    }
    Connections {
        target: Entities
        function onCanWriteAssetsChanged(allowed) { root.assetWriteAllowed = allowed; }
        function onCanRezChanged() { root.importAllowed = Entities.canRez() || Entities.canRezTmp(); }
        function onCanRezTmpChanged() { root.importAllowed = Entities.canRez() || Entities.canRezTmp(); }
    }
    HifiControls.TouchUiMetrics { id: metrics }
    Component { id: fileBrowser; NativeFileBrowser { bundleMode: true; caption: "Select an asset and its companion files" } }
    DropArea { anchors.fill: parent; onDropped: function(drop) { if (drop.hasUrls && drop.urls.length === 1 && root.writable()) { root.uploadFile(drop.urls[0], true); drop.acceptProposedAction(); } } }
    Flickable {
        id: assetScroll
        anchors.fill: parent; anchors.margins: 12
        clip: true
        contentWidth: width
        contentHeight: contentItem.childrenRect.height
        boundsBehavior: Flickable.StopAtBounds
        pressDelay: 0
        ScrollBar.vertical: ScrollBar { }
        ColumnLayout {
            id: assetColumn
            width: assetScroll.width
            spacing: 8
            Label { text: root.title; font.pixelSize: 22; color: "white"; Layout.fillWidth: true }
            Label { text: root.assetWriteAllowed ? "Browse and manage domain assets" : "Browse domain assets · writing unavailable"; color: "#cccccc"; Layout.fillWidth: true; wrapMode: Text.WordWrap }
            Flow {
                Layout.fillWidth: true; spacing: 8
                Button { objectName: "assetRefresh"; text: "Refresh"; implicitHeight: 48; onClicked: root.reload() }
                Button { objectName: "assetImport"; text: "Add to World"; implicitHeight: 48; enabled: root.importAllowed && root.canAddToWorld(root.selectedUrl); onClicked: root.addToWorld() }
                Button { objectName: "assetCopyUrl"; text: "Copy URL"; implicitHeight: 48; enabled: root.selectedUrl.length > 0; onClicked: Window.copyToClipboard(root.selectedUrl) }
            }
            TextField { id: search; objectName: "assetFilter"; placeholderText: "Filter assets and folders"; Layout.fillWidth: true; implicitHeight: 48; onTextChanged: tree.filterText = text }
            CheckBox { text: "Select multiple"; checked: tree.multiSelect; onToggled: tree.multiSelect = checked }
            NativeModelTree { id: tree; objectName: "assetTree"; Layout.fillWidth: true; Layout.preferredHeight: 120; sourceModel: root.assetProxyModel; folderRole: 257; statusRole: 261 }
            Label { text: root.selectedUrl; color: "#cccccc"; elide: Text.ElideMiddle; Layout.fillWidth: true }
            Label { text: root.updatesCount, root.currentIndex !== null ? String(root.assetProxyModel.data(root.currentIndex, 262) || "") : ""; visible: text.length > 0; color: "#ffaaaa"; wrapMode: Text.WordWrap; Layout.fillWidth: true }
            CheckBox { objectName: "assetBaking"; text: "Use baked version"; palette.windowText: "#dddddd"; enabled: root.assetWriteAllowed && !root.busy && root.bakingAvailable(); checked: root.currentIndex !== null && root.bakingAvailable() && root.assetProxyModel.data(root.currentIndex, 261) !== "Not Baked"; onToggled: root.setBakingEnabled(checked) }
            Flow {
                Layout.fillWidth: true; spacing: 8
                Button { objectName: "assetBundleCancel"; text: "Cancel upload"; implicitHeight: 48; visible: !!root.bundleRequest; onClicked: { Assets.cancelUploadBundle(root.bundleRequest); root.status = "Canceling upload; waiting for the current server operation..."; } }
                Button { objectName: "assetUploadedImport"; text: "Add uploaded model"; implicitHeight: 48; visible: /\.(fbx|obj|gltf|glb|vrm)$/i.test(root.uploadedPrimaryUrl); enabled: root.importAllowed && !root.busy; onClicked: root.importUploadedMain() }
                Button { objectName: "assetUpload"; text: "Upload with companions"; implicitHeight: 48; enabled: root.assetWriteAllowed && !root.busy; onClicked: root.uploadClicked() }
                Button { objectName: "assetSingleUpload"; text: "Upload one file"; implicitHeight: 48; enabled: root.assetWriteAllowed && !root.busy; onClicked: root.uploadSingleClicked() }
                Button { objectName: "assetRename"; text: "Rename"; implicitHeight: 48; enabled: root.assetWriteAllowed && !root.busy && root.selectedItemCount === 1; onClicked: { renamePath.text = root.selectedPath; renameDialog.open(); } }
                Button { objectName: "assetDelete"; text: "Delete"; implicitHeight: 48; enabled: root.assetWriteAllowed && !root.busy && root.selectedItemCount > 0; onClicked: deleteDialog.open() }
                Button { objectName: "assetMapping"; text: "Set Mapping"; implicitHeight: 48; enabled: root.assetWriteAllowed && !root.busy; onClicked: mappingDialog.open() }
            }
            BusyIndicator { running: root.busy; visible: running; Layout.preferredHeight: 36 }
            Label { objectName: "assetStatus"; text: root.status; color: "#cccccc"; wrapMode: Text.WordWrap; Layout.fillWidth: true; visible: text.length > 0 }
            NativeKeyboardHost { id: inputKeyboard; Layout.fillWidth: true; Layout.preferredHeight: implicitHeight; inputFocused: search.activeFocus }
        }
    }
    Dialog {
        id: singleDialog
        objectName: "singleUploadDialog"
        title: "Specify asset path"
        font.pixelSize: 16
        modal: true; focus: true
        width: Math.min(root.width - 24, 500)
        x: (root.width - width) / 2
        y: Qt.platform.os === "android" && !HMD.active && singlePath.activeFocus
            ? 0 : Math.max(0, (root.height - height) / 2)
        standardButtons: Dialog.Ok | Dialog.Cancel
        Column {
            width: parent.width
            TextField {
                id: singlePath
                objectName: "assetSinglePath"
                width: parent.width; implicitHeight: 48
                placeholderText: "/asset/path"
                Keys.onEscapePressed: function(event) { singleDialog.reject(); event.accepted = true; }
            }
            NativeKeyboardHost { width: parent.width; inputFocused: singleDialog.visible && singlePath.activeFocus }
        }
        onAccepted: root.confirmSingleUpload()
        onRejected: root.cancelSingleUpload()
        onClosed: { singlePath.focus = false; Qt.inputMethod.hide(); tree.view.forceActiveFocus(); }
    }
    Dialog {
        id: singleOverwriteDialog
        objectName: "singleUploadOverwriteDialog"
        title: "Overwrite existing asset?"
        font.pixelSize: 16
        modal: true; focus: true
        width: Math.min(root.width - 24, 500)
        x: (root.width - width) / 2
        y: Math.max(0, (root.height - height) / 2)
        standardButtons: Dialog.Yes | Dialog.No
        Label { width: parent.width; text: root.singleUploadMapping; wrapMode: Text.WrapAnywhere }
        onAccepted: root.startSingleUpload()
        onRejected: root.cancelSingleUpload()
        onClosed: tree.view.forceActiveFocus()
    }
    Dialog {
        id: renameDialog
        objectName: "renameDialog"
        title: "Rename asset or folder"
        modal: true; focus: true
        width: Math.min(root.width - 24, 500)
        x: (root.width - width) / 2
        y: Math.max(0, (root.height - height) / 2)
        standardButtons: Dialog.Ok | Dialog.Cancel
        Column {
            width: parent.width
            TextField {
                id: renamePath
                objectName: "assetRenamePath"
                width: parent.width; implicitHeight: 48
                Keys.onEscapePressed: function(event) { renameDialog.reject(); event.accepted = true; }
            }
            NativeKeyboardHost { width: parent.width; inputFocused: renameDialog.visible && renamePath.activeFocus }
        }
        onClosed: tree.view.forceActiveFocus()
        onAccepted: root.doRenameFile(root.selectedPath, renamePath.text)
    }
    Dialog {
        id: overwriteDialog
        title: "Overwrite existing mapping?"
        modal: true; focus: true
        width: Math.min(root.width - 24, 500)
        x: (root.width - width) / 2
        y: Math.max(0, (root.height - height) / 2)
        standardButtons: Dialog.Yes | Dialog.No
        onAccepted: {
            if (root.writable() && !root.busy) {
                root.busy = true;
                Assets.renameMapping(root.pendingRenameOld, root.pendingRenameNew, root.resultHandler("Rename"));
            }
        }
    }
    Dialog {
        id: deleteDialog
        title: "Delete selected mappings?"
        modal: true; focus: true
        width: Math.min(root.width - 24, 500)
        x: (root.width - width) / 2
        y: Math.max(0, (root.height - height) / 2)
        standardButtons: Dialog.Yes | Dialog.No
        Label { text: root.selectedPaths().join("\n"); wrapMode: Text.WordWrap; width: Math.max(100, Math.min(root.width - 60, 500)) }
        onAccepted: root.doDeleteFile(root.selectedPaths())
    }
    Dialog {
        id: mappingDialog
        objectName: "mappingDialog"
        title: "Set asset mapping"
        modal: true; focus: true
        width: Math.min(root.width - 24, 500)
        x: (root.width - width) / 2
        y: Math.max(0, (root.height - height) / 2)
        standardButtons: Dialog.Ok | Dialog.Cancel
        Column {
            width: parent.width
            TextField {
                id: mappingPath
                objectName: "assetMappingPath"
                width: parent.width; implicitHeight: 48
                placeholderText: "/asset/path"
                Keys.onEscapePressed: function(event) { mappingDialog.reject(); event.accepted = true; }
            }
            TextField {
                id: mappingHash
                objectName: "assetMappingHash"
                width: parent.width; implicitHeight: 48
                placeholderText: "SHA-256 hash"
                Keys.onEscapePressed: function(event) { mappingDialog.reject(); event.accepted = true; }
            }
            NativeKeyboardHost { width: parent.width; inputFocused: mappingDialog.visible && (mappingPath.activeFocus || mappingHash.activeFocus) }
        }
        onClosed: tree.view.forceActiveFocus()
        onAccepted: root.setMapping(mappingPath.text, mappingHash.text)
    }
    Dialog {
        id: bundleDialog; objectName: "bundleDestinationDialog"; title: "Choose an asset destination folder"
        modal: true; focus: true; width: Math.min(root.width - 24, 500)
        x: (root.width - width) / 2; y: Math.max(0, (root.height - height) / 2)
        standardButtons: Dialog.Ok | Dialog.Cancel
        Column {
            width: parent.width; spacing: 8
            Label { text: "Relative paths will be preserved. Choose a new folder: bundle uploads stop at known existing mappings. Concurrent server changes may still affect the destination."; width: parent.width; wrapMode: Text.WordWrap }
            TextField { id: bundleDestination; objectName: "assetBundleDestination"; width: parent.width; implicitHeight: 48; placeholderText: "/my-model/"; Keys.onEscapePressed: function(event) { bundleDialog.reject(); event.accepted = true; } }
            NativeKeyboardHost { width: parent.width; inputFocused: bundleDialog.visible && bundleDestination.activeFocus }
        }
        onAccepted: root.uploadBundle()
        onRejected: root.pendingBundle = null
        onClosed: tree.view.forceActiveFocus()
    }
    Dialog {
        id: modelDialog
        objectName: "modelDialog"
        title: "Import model"
        modal: true; focus: true
        width: Math.min(root.width - 24, 500)
        x: (root.width - width) / 2
        y: Math.max(0, (root.height - height) / 2)
        standardButtons: Dialog.Ok | Dialog.Cancel
        Column {
            width: parent.width; spacing: 8
            TextField {
                id: modelUrl
                objectName: "assetModelUrl"
                width: parent.width; implicitHeight: 48
                Keys.onEscapePressed: function(event) { modelDialog.reject(); event.accepted = true; }
            }
            ComboBox {
                id: shape
                objectName: "assetModelShape"
                width: parent.width; implicitHeight: 48
                model: ["No Collision", "Basic · whole model", "Good · sub-meshes", "Exact · static polygons", "Box", "Sphere"]
            }
            CheckBox {
                id: dynamic
                objectName: "assetModelDynamic"
                text: "Dynamic"
                enabled: shape.currentIndex !== 3
                onEnabledChanged: { if (!enabled) checked = false; }
            }
            NativeKeyboardHost { width: parent.width; inputFocused: modelDialog.visible && modelUrl.activeFocus }
        }
        onClosed: tree.view.forceActiveFocus()
        onAccepted: root.importModel()
    }
}
