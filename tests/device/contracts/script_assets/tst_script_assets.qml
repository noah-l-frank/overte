// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
import QtQuick 2.7
import QtQuick.Controls 2.3
import QtTest 1.2

TestCase {
    id: testCase
    name: "NativeScriptsAssets"
    width: 360; height: 760
    visible: true
    property var selectedUrls: []
    when: windowShown
    function production(path) {
        var component = Qt.createComponent(String(ProductionRoot) + path);
        compare(component.status, Component.Ready, component.errorString());
        var object = createTemporaryObject(component, testCase, {width:360,height:760});
        verify(object !== null, component.errorString());
        wait(40);
        return object;
    }
    function control(root, name) {var found = findChild(root,name);verify(found !== null,name);return found;}
    function click(root, name) {
        wait(30)
        var item=control(root,name)
        verify(item.visible && item.enabled,name+" visible="+item.visible+" enabled="+item.enabled+" size="+item.width+"x"+item.height)
        var ancestor=item.parent
        while (ancestor) {
            if (typeof ancestor.contentY === "number" && ancestor.height > 0) {
                for (var attempt=0; attempt<20; ++attempt) {
                    var point=item.mapToItem(ancestor,item.width/2,item.height/2)
                    if (point.y >= 0 && point.y < ancestor.height) break
                    var upward=point.y >= ancestor.height
                    mouseDrag(ancestor,ancestor.width*0.85,ancestor.height*(upward?0.8:0.2),
                        0,ancestor.height*(upward?-0.6:0.6),Qt.LeftButton,Qt.NoModifier,80)
                    wait(30)
                }
                ancestor.cancelFlick()
            }
            ancestor=ancestor.parent
        }
        mouseClick(item,item.width/2,item.height/2)
        wait(20)
    }
    function initTestCase() {TestServices.bindSurface(testCase);}
    function init() {TestServices.reset(); selectedUrls = [];}
    function cleanup() {TestServices.removePicker();}
    function test_normalTouchAppEntriesLoadActualScriptsAndReadOnlyAssets() {
        var scriptsSource = TestServices.firstPartyAppSource("SCRIPTS");
        compare(scriptsSource, "hifi/dialogs/TabletRunningScripts.qml");
        var scripts = production(scriptsSource);
        compare(scripts.objectName, "RunningScripts");
        verify(control(scripts, "scriptFromUrl").visible);
        scripts.visible = false;
        var assetSource = TestServices.firstPartyAppSource("ASSETS");
        compare(assetSource, "hifi/dialogs/TabletAssetServer.qml");
        var assets = production(assetSource);
        compare(assets.objectName, "AssetServer");
        verify(!assets.assetWriteAllowed);
        verify(!control(assets, "assetUpload").enabled);
        compare(TestServices.assetCalls.length, 0);
    }
    function test_actualAssetMenuAndDesktopTabletRoutes() {
        var routes = TestServices.exerciseAssetMenuRoutes();
        verify(routes.readable); verify(routes.desktop); verify(routes.tabletOnce);
    }
    function test_documentRequestPermissionsLimitsAndLifetime() {
        var result = TestServices.exerciseDocumentBoundaries();
        verify(result.busy); verify(result.staleIgnored); verify(result.distinctIds);
        compare(result.selected, 1); compare(result.failed, 3);
        compare(result.canceledRequests, 1); compare(result.canceledLeases, 2);
        verify(result.retained);
    }
    function test_desktopCompatibilityWrappers() {
        var scripts = production("hifi/dialogs/RunningScripts.qml");
        var tree = control(scripts, "scriptTree");
        tree.toggle(0); tree.selectRow(1, false);
        click(scripts, "scriptLoadSelected");
        compare(TestServices.scriptCalls.length, 1);
        scripts.destroy(); wait(30);
        var assets = production("hifi/AssetServer.qml");
        tree = control(assets, "assetTree"); tree.toggle(0); tree.selectRow(2, false);
        click(assets, "assetImport"); compare(TestServices.entityCalls.length, 1);
        assets.destroy(); wait(30);
        var browser = production("dialogs/FileDialog.qml");
        verify(control(browser, "systemDocumentPicker").enabled);
        browser.dir = "file://" + TestServices.fixtureDirectory;
        browser.selectedFile.connect(function(url){testCase.selectedUrls=[url];});
        control(browser,"fileNameInput").text="ordinary.js";
        click(browser,"fileAccept");
        compare(selectedUrls.length,1); compare(String(selectedUrls[0]),"file://"+TestServices.fixtureFile);
    }
    function test_saveDialogFilenameAndActionsRemainAbovePhoneIme() {
        var dialog = production("dialogs/FileDialog.qml");
        dialog.saveDialog = true;
        var profile = dialog.touchProfile;
        profile.directTouch = true;
        profile.screenSpacePresentation = true;
        profile.surfaceWidth = 900;
        profile.surfaceHeight = 900;
        profile.keyboardVisible = true;
        profile.imeInsetBottom = 550;
        dialog.dir = "file://" + TestServices.fixtureDirectory;
        var filename = control(dialog, "fileNameInput");
        filename.forceActiveFocus();
        filename.text = "export-with-keyboard.json";
        var save = control(dialog, "fileAccept");
        tryVerify(function() {
            return filename.mapToItem(testCase, 0, 0).y >= 0
                && save.mapToItem(testCase, 0, save.height).y <= 350;
        }, 1000, "The filename and Save must be visible above the IME");
        dialog.selectedFile.connect(function(url) { testCase.selectedUrls = [url]; });
        mouseClick(save, save.width / 2, save.height / 2);
        compare(selectedUrls.length, 1);
        verify(String(selectedUrls[0]).endsWith("/export-with-keyboard.json"));
    }
    function test_queryDialogInputAndActionsRemainAbovePhoneIme() {
        width = 900; height = 900;
        try {
            var dialog = production("dialogs/QueryDialog.qml");
            dialog.title = "Open and Run Script";
            dialog.label = "Script URL";
            var profile = dialog.touchProfile;
            profile.directTouch = true;
            profile.screenSpacePresentation = true;
            profile.surfaceWidth = 900;
            profile.surfaceHeight = 900;
            profile.keyboardVisible = true;
            profile.imeInsetBottom = 550;
            var input = control(dialog, "queryTextInput");
            input.forceActiveFocus(); input.selectAll();
            keyClick(Qt.Key_1); keyClick(Qt.Key_2);
            var accept = control(dialog, "queryAccept");
            tryVerify(function() {
                return input.mapToItem(testCase, 0, 0).y >= 0
                    && input.mapToItem(testCase, 0, input.height).y <= 350
                    && accept.mapToItem(dialog, 0, 0).x >= 0
                    && accept.mapToItem(dialog, accept.width, 0).x <= dialog.width
                    && accept.mapToItem(testCase, 0, accept.height).y <= 350;
            }, 1000, "The entered URL and OK must be visible above the IME");
            var selected = null;
            dialog.selected.connect(function(value) { selected = value; });
            wait(100);
            mouseClick(accept, accept.width / 2, accept.height / 2);
            wait(30);
            compare(selected, "12");
        } finally {
            width = 360; height = 760;
        }
    }
    function test_scriptLifecycleAndNativeTree() {
        var scripts=production("hifi/dialogs/TabletRunningScripts.qml");
        var tree=control(scripts,"scriptTree");
        compare(tree.rows.length,1);
        mouseClick(control(scripts,"nativeTreeRow0"),12,24);compare(tree.rows.length,2);
        mouseClick(control(scripts,"nativeTreeRow1"),100,24);click(scripts,"scriptLoadSelected");
        compare(TestServices.scriptCalls.length,1);compare(TestServices.scriptCalls[0].url,"https://example.invalid/ordinary.js");
        click(scripts,"scriptReloadAll");click(scripts,"scriptStopAll");
        compare(TestServices.scriptCalls.length,3);
        verify(TestServices.scriptCalls[1].restart);verify(!TestServices.scriptCalls[2].restart);
        verify(TestServices.scriptCalls.every(function(call){return call.url!=="https://example.invalid/defaultScripts.js";}));
        click(scripts,"scriptFromUrl");click(scripts,"scriptFromFile");
        compare(TestServices.urlDialogCount,1);compare(TestServices.fileDialogCount,1);
        TestServices.loadError();verify(scripts.status.indexOf("Failed to load")===0);
        tree.filterText="ordinary";wait(20);compare(tree.rows.length,2);
        tree.filterText="absent";wait(20);compare(tree.rows.length,0);
        TestServices.developer(true);scripts.developerMenuEnabled=true;click(scripts,"scriptLoadDefaults");
        compare(TestServices.scriptCalls[3].url,"https://example.invalid/defaults/defaultScripts.js");
    }
    function test_shortSurfaceKeepsInstalledScriptSelectionReachable() {
        var scripts = production("hifi/dialogs/TabletRunningScripts.qml");
        scripts.width = 850; scripts.height = 286;
        wait(80);
        var tree = control(scripts, "scriptTree");
        verify(tree.height >= 120, "Installed scripts need a usable viewport on a scaled phone");
        var viewport = control(scripts, "scriptViewport");
        viewport.contentY = viewport.contentHeight - viewport.height;
        wait(80);
        var point = tree.mapToItem(scripts, 0, 0);
        verify(point.y >= 0 && point.y + tree.height <= scripts.height + 1);
        mouseClick(control(scripts, "nativeTreeRow0"), 12, 24);
        wait(30);
        compare(tree.rows.length, 2);
        click(scripts, "nativeTreeRow1");
        click(scripts, "scriptLoadSelected");
        compare(TestServices.scriptCalls.length, 1);
        compare(TestServices.scriptCalls[0].url, "https://example.invalid/ordinary.js");
    }
    function test_readOnlyBrowseImageModelImportAndFailure() {
        var assets=production("hifi/dialogs/TabletAssetServer.qml");
        var tree=control(assets,"assetTree");tree.toggle(0);compare(tree.rows.length,3);
        verify(!control(assets,"assetUpload").enabled);
        tree.selectRow(2,false);click(assets,"assetImport");
        compare(TestServices.entityCalls.length,1);compare(TestServices.entityCalls[0].kind,"image");
        compare(TestServices.entityCalls[0].position, {x:1, y:2, z:1});
        compare(String(TestServices.entityCalls[0].lastEditedBy), "{11111111-2222-3333-4444-555555555555}");
        verify(TestServices.entityCalls[0].collisionless); verify(!TestServices.entityCalls[0].dynamic);
        verify(assets.status.indexOf("Added")===0);
        TestServices.denyImport(true);click(assets,"assetImport");verify(assets.status.indexOf("Import failed")===0);
        TestServices.denyImport(false);tree.selectRow(1,false);click(assets,"assetImport");
        var url=control(assets,"assetModelUrl");url.forceActiveFocus();wait(20);verify(TestServices.keyboardRaised);
        keyClick(Qt.Key_Escape);tryVerify(function(){return !TestServices.keyboardRaised;});
        click(assets,"assetImport");
        var confirm = control(assets,"modelDialog").standardButton(Dialog.Ok);
        mouseClick(confirm, confirm.width/2, confirm.height/2); wait(30);
        compare(TestServices.entityCalls.length,3); compare(TestServices.entityCalls[2].kind,"model");
        compare(TestServices.entityCalls[2].position, {x:1, y:2, z:1});
        compare(TestServices.entityCalls[2].shape,"simple-compound");
        TestServices.permissions(false,false);verify(!control(assets,"assetImport").enabled);
        assets.doDeleteFile(["/models/scene.fbx"]);compare(TestServices.assetCalls.length,0);
    }
    function test_assetMutationsErrorsAndPermissionRevocation() {
        TestServices.permissions(true,true);
        var assets=production("hifi/dialogs/TabletAssetServer.qml");var tree=control(assets,"assetTree");tree.toggle(0);tree.selectRow(1,false);
        assets.doRenameFile("/models/scene.fbx","/models/renamed.fbx");compare(TestServices.assetCalls[0].kind,"rename");
        assets.setMapping("/new.fbx","a".repeat(64));compare(TestServices.assetCalls[1].kind,"mapping");
        assets.setBakingEnabled(false);compare(TestServices.assetCalls[2].kind,"baking");
        assets.doDeleteFile(["/models/scene.fbx"]);compare(TestServices.assetCalls[4].kind,"delete");
        assets.uploadFile("file://"+TestServices.fixtureFile,false);wait(20);
        var uploadConfirm=control(assets,"singleUploadDialog").standardButton(Dialog.Ok);
        mouseClick(uploadConfirm,uploadConfirm.width/2,uploadConfirm.height/2);wait(20);compare(TestServices.assetCalls[5].kind,"upload");
        compare(TestServices.assetCalls[5].mapping,"/models/ordinary.js");
        TestServices.backendError("permission changed");assets.doDeleteFile(["/models/scene.fbx"]);verify(assets.status.indexOf("failed")!==-1);
        TestServices.permissions(false,true);assets.doRenameFile("/models/scene.fbx","/later.fbx");compare(TestServices.assetCalls.length,7);
    }
    function test_nativeModelChangesAndSurfaceCleanup() {
        TestServices.permissions(true,true);
        var assets=production("hifi/dialogs/TabletAssetServer.qml");
        var tree=control(assets,"assetTree");tree.toggle(0);tree.selectRow(1,false);
        verify(TestServices.assetRefreshEnabled());
        TestServices.assetBakingState("Not Baked");wait(30);
        var baking=control(assets,"assetBaking");verify(baking.enabled);verify(!baking.checked);
        mouseClick(baking,baking.width/2,baking.height/2);wait(30);
        compare(TestServices.assetCalls.length,1);verify(TestServices.assetCalls[0].enabled);
        TestServices.resetAssetModel();wait(30);
        compare(tree.rows.length,0);compare(assets.selectedItemCount,0);compare(assets.selectedUrl,"");
        verify(!control(assets,"assetImport").enabled);
        assets.destroy();wait(30);verify(!TestServices.assetRefreshEnabled());
    }
    function test_folderRenamePreservesNestedMappingsAndUnrelatedAssets() {
        TestServices.permissions(true, true);
        TestServices.seedAssetRename({"/source/main.gltf":"a", "/source/mesh/triangle.bin":"b", "/other/keep.png":"c"});
        var assets = production("hifi/dialogs/TabletAssetServer.qml");
        assets.doRenameFile("/source/", "/renamed");
        compare(assets.status, "Rename complete.");
        verify(!assets.busy);
        compare(TestServices.assetRenameMappings(), {"/renamed/main.gltf":"a", "/renamed/mesh/triangle.bin":"b", "/other/keep.png":"c"});
        compare(TestServices.assetCalls.length, 2);
        verify(TestServices.assetCalls.every(function(call) { return call.old.slice(-1) !== "/" && call.new.slice(-1) !== "/"; }));
    }
    function test_avatarUrlPopupStaysBoundedAndRevealsItsFocusedInput() {
        testCase.height = 100;
        try {
            var popup = production("hifi/avatarapp/MessageBox.qml");
            popup.titleText = "Specify Avatar URL";
            popup.bodyText = "Avatar help and validation information. ".repeat(12);
            popup.button1text = "Cancel"; popup.button2text = "Confirm";
            popup.inputText.visible = true;
            popup.inputText.text = "qrc:///meshes/defaultAvatar_full.fst";
            popup.open();
            popup.inputText.forceActiveFocus();
            wait(80);
            var panel = control(popup, "avatarMessageContainer");
            var viewport = control(popup, "avatarMessageContent");
            verify(panel.height <= popup.height - 16);
            verify(viewport.contentY > 0);
            var y = popup.inputText.mapToItem(viewport, 0, 0).y;
            verify(y >= 0 && y + popup.inputText.height <= viewport.height);
            var originalHeight = panel.height;
            for (var i = 0; i < 3; ++i) { testCase.height = 120; wait(20); testCase.height = 100; wait(20); }
            compare(panel.height, originalHeight);
            popup.close(); wait(20);
            verify(!popup.inputText.activeFocus);
        } finally { testCase.height = 760; }
    }
    function test_folderRenameRollsBackCompletedFilesOnFailure() {
        TestServices.permissions(true, true);
        var original = {"/source/a.gltf":"a", "/source/b.bin":"b", "/other/keep.png":"c"};
        TestServices.seedAssetRename(original, 1);
        var assets = production("hifi/dialogs/TabletAssetServer.qml");
        assets.doRenameFile("/source/", "/renamed/");
        verify(assets.status.indexOf("Rename failed:") === 0);
        verify(!assets.busy);
        compare(TestServices.assetRenameMappings(), original);
        compare(TestServices.assetCalls.length, 3);
        compare(TestServices.assetCalls[2].old, "/renamed/a.gltf");
        compare(TestServices.assetCalls[2].new, "/source/a.gltf");
    }
    function test_folderRenameRejectsDescendantAndExistingDestinationWithoutMutation() {
        TestServices.permissions(true, true);
        TestServices.seedAssetRename({"/source/a.gltf":"a", "/renamed/a.gltf":"b"});
        var assets = production("hifi/dialogs/TabletAssetServer.qml");
        assets.doRenameFile("/source/", "/source/nested/");
        compare(assets.status, "Cannot move a folder inside itself.");
        assets.doRenameFile("/source/", "/renamed/");
        verify(assets.status.indexOf("destination contains") !== -1);
        compare(TestServices.assetCalls.length, 0);
        verify(!assets.busy);
    }
    function test_popupKeyboardFieldsAndCancel() {
        TestServices.permissions(true,true);
        var assets=production("hifi/dialogs/TabletAssetServer.qml");var tree=control(assets,"assetTree");tree.toggle(0);tree.selectRow(1,false);
        click(assets,"assetRename");var field=control(assets,"assetRenamePath");field.forceActiveFocus();wait(20);verify(TestServices.keyboardRaised);keyClick(Qt.Key_A);keyClick(Qt.Key_Escape);tryVerify(function(){return !TestServices.keyboardRaised;});
        click(assets,"assetMapping");field=control(assets,"assetMappingHash");field.forceActiveFocus();wait(20);verify(TestServices.keyboardRaised);keyClick(Qt.Key_A);keyClick(Qt.Key_Escape);tryVerify(function(){return !TestServices.keyboardRaised;});
        TestServices.keyboard3D(false);click(assets,"assetRename");field=control(assets,"assetRenamePath");field.forceActiveFocus();wait(40);
        var dialog = control(assets, "renameDialog");
        var keyboard=control(dialog,"keyboard");verify(keyboard.raised);verify(keyboard.visible);verify(keyboard.parent.scale<=1);
        var before = field.text;
        keyboard.forEachKey(function(key) { if (key.glyph === "q") mouseClick(key.mouseArea, key.width/2, key.height/2); });
        compare(field.text, before + "q");
        verify(dialog.y >= 0 && dialog.y + dialog.height <= assets.height + 1);
        keyClick(Qt.Key_Escape);tryVerify(function(){return !keyboard.raised;});
    }
    function fileRow(browser, name) {
        for (var i=0; i<browser.model.count; ++i) if (browser.model.get(i,"fileName") === name) return i;
        return -1;
    }
    function test_localBrowserNavigationFilterSelectionAndSave() {
        var browser=production("dialogs/TabletFileDialog.qml");
        browser.dir="file://"+TestServices.fixtureDirectory;
        tryVerify(function(){return fileRow(browser,"ordinary.js") >= 0;});
        var nested=fileRow(browser,"nested"); verify(nested >= 0);
        click(browser,"fileRow"+nested);
        tryVerify(function(){return String(browser.dir).endsWith("/nested");});
        click(browser,"fileBack");
        tryVerify(function(){return fileRow(browser,"ordinary.js") >= 0;});
        browser.filter="Scripts (*.js)"; wait(50);
        verify(fileRow(browser,"ordinary.js")>=0);
        var sort=control(browser,"fileSort"); sort.currentIndex=2; wait(30);
        browser.selectedFiles.connect(function(urls){testCase.selectedUrls=urls;});
        click(browser,"fileRow"+fileRow(browser,"ordinary.js")); click(browser,"fileAccept");
        compare(selectedUrls.length,1);compare(String(selectedUrls[0]),"file://"+TestServices.fixtureFile);
        selectedUrls=[];
        browser=production("dialogs/NativeFileBrowser.qml");
        browser.dir="file://"+TestServices.fixtureDirectory;browser.saveDialog=true;browser.filter="Scripts (*.js)";
        browser.selectedFiles.connect(function(urls){testCase.selectedUrls=urls;});
        control(browser,"fileNameInput").text="ordinary.js";click(browser,"fileAccept");
        var confirm=control(browser,"fileOverwriteDialog").standardButton(Dialog.No);
        mouseClick(confirm,confirm.width/2,confirm.height/2);wait(30);verify(!browser.closing);compare(selectedUrls.length,0);
        control(browser,"fileNameInput").text="new-script";click(browser,"fileAccept");
        compare(selectedUrls.length,1);verify(String(selectedUrls[0]).endsWith("/new-script.js"));
    }
    function test_realFolderBrowserSystemPickerAndOldCallbacks() {
        var browser=production("dialogs/NativeFileBrowser.qml");browser.dir="file://"+TestServices.fixtureDirectory;browser.selectedFiles.connect(function(urls){testCase.selectedUrls=urls;});wait(100);
        verify(browser.model.count>=2);TestServices.installPicker();click(browser,"systemDocumentPicker");verify(browser.requestId.length>0);
        TestServices.completePicker(true);wait(30);verify(browser.error.indexOf("readable local file")!==-1);verify(!browser.closing);
        click(browser,"systemDocumentPicker");var oldId=browser.requestId;
        browser.helper.cancelDocuments(oldId);wait(20);verify(TestServices.pickerCanceled);verify(!browser.requestId);
        TestServices.completePicker();wait(20);verify(!browser.closing);
        click(browser,"systemDocumentPicker");TestServices.completePicker();wait(30);compare(selectedUrls.length,1);compare(String(selectedUrls[0]),"file://"+TestServices.fixtureFile);
    }
    function test_actualDesktopPickerAndLocalFileSelection() {
        var browser=production("dialogs/NativeFileBrowser.qml");browser.dir="file://"+TestServices.fixtureDirectory;browser.selectedFiles.connect(function(urls){testCase.selectedUrls=urls;});
        click(browser,"systemDocumentPicker");verify(browser.requestId.length>0);verify(TestServices.selectDesktopFile());wait(40);compare(selectedUrls.length,1);compare(String(selectedUrls[0]),"file://"+TestServices.fixtureFile);
        // The production QFileDialog and helper complete into this QML listener;
        // mobile provider UI is a separate adapter/device boundary.
    }
    function test_bundleSelectionTreeAndActualRelativeScript() {
        TestServices.writeCompanions(); TestServices.installTreePicker();
        var browser=production("dialogs/NativeFileBrowser.qml");
        browser.bundleMode=true; browser.primaryFilter="\\.js$";
        browser.selectedBundle.connect(function(manifest){selectedUrls=[manifest.primary];});
        click(browser,"systemDocumentTree"); verify(browser.requestId.length>0);
        TestServices.completeTreePicker();tryVerify(function(){return browser.bundle!==null;});
        verify(browser.bundle.relativePaths.indexOf("nested/helper.js")>=0);
        control(browser,"bundlePrimary").currentIndex=browser.bundle.relativePaths.indexOf("main.js");
        click(browser,"bundleConfirm");compare(selectedUrls.length,1);
        var scripts=production("hifi/dialogs/TabletRunningScripts.qml");
        scripts.loadScript(String(selectedUrls[0]));
        compare(TestServices.localScriptResult(),42);
        verify(scripts.status.indexOf("Loading main.js")===0);
        var bundled=TestServices.bundledScriptResolution();
        for (var key in bundled) verify(bundled[key], key);
    }
    function test_bundleUploadPreservesRealBytesAndModelReferences() {
        TestServices.writeCompanions();TestServices.permissions(true,true);
        var assets=production("hifi/dialogs/TabletAssetServer.qml");
        click(assets,"assetUpload");
        var browser=control(assets,"nativeFileBrowser");
        browser.reviewBundle([],"file://"+TestServices.fixtureDirectory);
        control(browser,"bundlePrimary").currentIndex=browser.bundle.relativePaths.indexOf("scene.gltf");
        click(browser,"bundleConfirm");
        var dialog=control(assets,"bundleDestinationDialog");tryVerify(function(){return dialog.visible;});
        var field=control(assets,"assetBundleDestination");field.text="/family/";field.forceActiveFocus();wait(20);verify(TestServices.keyboardRaised);
        var confirm=dialog.standardButton(Dialog.Ok);mouseClick(confirm,confirm.width/2,confirm.height/2);
        tryVerify(function(){return !assets.busy && assets.uploadedPrimaryUrl.length>0;});
        var paths=TestServices.publishedBundle();verify(paths.length>=6);compare(paths[paths.length-1],"/family/scene.gltf");
        var model=TestServices.inspectUploadedModel("/family/");
        verify(model.gltf);verify(model.image);verify(model.obj);
        click(assets,"assetUploadedImport");confirm=control(assets,"modelDialog").standardButton(Dialog.Ok);
        mouseClick(confirm,confirm.width/2,confirm.height/2);wait(20);
        compare(TestServices.entityCalls[0].url,"atp:/family/scene.gltf");
        verify(assets.status.indexOf("Added")===0);
    }
    function test_bundleObjCompanionsAndOriginalRelativeNames() {
        TestServices.writeCompanions();TestServices.permissions(true,true);
        var assets=production("hifi/dialogs/TabletAssetServer.qml");click(assets,"assetUpload");
        var browser=control(assets,"nativeFileBrowser");browser.reviewBundle([],"file://"+TestServices.fixtureDirectory);
        control(browser,"bundlePrimary").currentIndex=browser.bundle.relativePaths.indexOf("scene.obj");click(browser,"bundleConfirm");
        var dialog=control(assets,"bundleDestinationDialog");tryVerify(function(){return dialog.visible;});
        control(assets,"assetBundleDestination").text="/obj/";
        var confirm=dialog.standardButton(Dialog.Ok);mouseClick(confirm,confirm.width/2,confirm.height/2);
        tryVerify(function(){return !assets.busy && assets.uploadedPrimaryUrl.length>0;});
        var published=TestServices.publishedBundle();compare(published[published.length-1],"/obj/scene.obj");
        var inspected=TestServices.inspectUploadedModel("/obj/");verify(inspected.obj);verify(inspected.image);
        click(assets,"assetUploadedImport");confirm=control(assets,"modelDialog").standardButton(Dialog.Ok);mouseClick(confirm,confirm.width/2,confirm.height/2);
        compare(TestServices.entityCalls[0].url,"atp:/obj/scene.obj");
        var files=fileDialogHelper.documentBundle([],"file://"+TestServices.fixtureDirectory);
        var paths=files.urls.map(function(url){return fileDialogHelper.urlToPath(url);});
        var changed=files.relativePaths.slice();changed[0]="renamed.bin";var outcome="";
        Assets.uploadBundle(paths,changed,"/changed/","scene.gltf",function(){},function(error){outcome=error;});
        tryVerify(function(){return outcome.length>0;});compare(TestServices.publishedBundle().length,published.length);
    }
    function test_desktopBundleWindowAndMainFileListener() {
        TestServices.writeCompanions();var dialog=production("dialogs/FileDialog.qml");
        dialog.bundleMode=true;dialog.primaryFilter="\\.js$";
        dialog.selectedFile.connect(function(url){testCase.selectedUrls=[url];});
        var browser=control(dialog,"nativeFileBrowser");browser.reviewBundle([],"file://"+TestServices.fixtureDirectory);
        control(browser,"bundlePrimary").currentIndex=browser.bundle.relativePaths.indexOf("main.js");
        click(dialog,"bundleConfirm");compare(selectedUrls.length,1);verify(String(selectedUrls[0]).endsWith("/main.js"));
    }
    function test_normalSingleUploadRouteRemainsAvailable() {
        TestServices.permissions(true,true);var assets=production("hifi/dialogs/TabletAssetServer.qml");
        click(assets,"assetSingleUpload");var browser=control(assets,"nativeFileBrowser");verify(!browser.bundleMode);
        browser.finish(["file://"+TestServices.fixtureFile]);wait(40);
        compare(TestServices.assetCalls.length,0);verify(control(assets,"singleUploadDialog").visible);
        var cancel=control(assets,"singleUploadDialog").standardButton(Dialog.Cancel);
        mouseClick(cancel,cancel.width/2,cancel.height/2);wait(20);
        compare(TestServices.assetCalls.length,0);compare(assets.singleUploadUrl,"");
        assets.uploadFile("file://"+TestServices.fixtureFile,false);wait(20);
        var confirm=control(assets,"singleUploadDialog").standardButton(Dialog.Ok);
        mouseClick(confirm,confirm.width/2,confirm.height/2);wait(20);
        compare(TestServices.assetCalls[0].kind,"upload");verify(TestServices.assetCalls[0].confirmed);
        compare(TestServices.assetCalls[0].mapping,"/ordinary.js");
        assets.uploadFile("file://"+TestServices.fixtureFile,false);wait(20);
        control(assets,"assetSinglePath").text="/exists.fbx";
        confirm=control(assets,"singleUploadDialog").standardButton(Dialog.Ok);
        mouseClick(confirm,confirm.width/2,confirm.height/2);wait(20);
        verify(control(assets,"singleUploadOverwriteDialog").visible);compare(TestServices.assetCalls.length,1);
        var reject=control(assets,"singleUploadOverwriteDialog").standardButton(Dialog.No);
        mouseClick(reject,reject.width/2,reject.height/2);wait(20);compare(TestServices.assetCalls.length,1);
        assets.uploadFile("file://"+TestServices.fixtureFile,false);wait(20);
        control(assets,"assetSinglePath").text="/exists.fbx";
        confirm=control(assets,"singleUploadDialog").standardButton(Dialog.Ok);
        mouseClick(confirm,confirm.width/2,confirm.height/2);wait(20);
        var overwrite=control(assets,"singleUploadOverwriteDialog").standardButton(Dialog.Yes);
        mouseClick(overwrite,overwrite.width/2,overwrite.height/2);wait(20);
        compare(TestServices.assetCalls.length,2);compare(TestServices.assetCalls[1].mapping,"/exists.fbx");
        verify(TestServices.assetCalls[1].confirmed);
        assets.uploadFile("file://"+TestServices.fixtureFile,false);wait(20);
        TestServices.permissions(false,true);
        confirm=control(assets,"singleUploadDialog").standardButton(Dialog.Ok);
        mouseClick(confirm,confirm.width/2,confirm.height/2);wait(20);compare(TestServices.assetCalls.length,2);
        verify(!control(assets,"assetSingleUpload").enabled);
    }
    function test_bundleFailureAndCancelReportActualPartialOutcome() {
        TestServices.writeCompanions();TestServices.permissions(true,true);TestServices.failBundleMapping(1);
        var assets=production("hifi/dialogs/TabletAssetServer.qml");
        assets.pendingBundle=fileDialogHelper.documentBundle([],"file://"+TestServices.fixtureDirectory);
        assets.pendingBundle.primaryPath="scene.gltf";
        control(assets,"assetBundleDestination").text="/partial/";assets.uploadBundle();
        tryVerify(function(){return !assets.busy;});
        compare(TestServices.publishedBundle().length,1);verify(assets.status.indexOf("Published mappings: 1")>=0);
        compare(assets.uploadedPrimaryUrl,"");
        TestServices.failBundleMapping(-1);
        assets.pendingBundle=fileDialogHelper.documentBundle([],"file://"+TestServices.fixtureDirectory);assets.pendingBundle.primaryPath="scene.gltf";
        control(assets,"assetBundleDestination").text="/canceled/";assets.uploadBundle();
        verify(assets.bundleRequest.length>0);Assets.cancelUploadBundle(assets.bundleRequest);
        tryVerify(function(){return !assets.busy;});verify(assets.status.indexOf("canceled")>=0);
        compare(TestServices.publishedBundle().length,1);
    }

    function test_normalScriptBundleCallerListenerAndExpiredOwner() {
        TestServices.writeCompanions();
        var dialog=TestServices.openRetainedScriptDialog();verify(dialog.bundleMode);
        dialog.reviewBundle([],"file://"+TestServices.fixtureDirectory);
        control(dialog,"bundlePrimary").currentIndex=dialog.bundle.relativePaths.indexOf("main.js");
        click(dialog,"bundleConfirm");
        compare(TestServices.actualCallerScriptCalls().length,1);compare(TestServices.actualCallerScriptResult(),42);
        dialog=TestServices.openActualScriptDialog();
        dialog.reviewBundle([],"file://"+TestServices.fixtureDirectory);
        control(dialog,"bundlePrimary").currentIndex=dialog.bundle.relativePaths.indexOf("main.js");
        click(dialog,"bundleConfirm");
        compare(TestServices.actualCallerScriptCalls().length,1);
        dialog=TestServices.openRetainedScriptDialog();click(dialog,"fileCancel");
        compare(TestServices.actualCallerScriptCalls().length,1);
    }

    function test_bundleTreeBoundsCancelAndWrongProviderResult() {
        var limits=TestServices.exerciseBundleBounds();
        for(var key in limits) verify(limits[key],key);
        TestServices.installTreePicker();
        var browser=production("dialogs/NativeFileBrowser.qml");browser.bundleMode=true;
        click(browser,"systemDocumentTree");TestServices.completePicker();
        tryVerify(function(){return browser.error.length>0;});verify(!browser.bundle);
        click(browser,"systemDocumentTree");browser.helper.cancelDocuments(browser.requestId);wait(20);
        verify(TestServices.pickerCanceled);TestServices.completeTreePicker();wait(20);verify(!browser.bundle);
    }
    function test_bundlePermissionConflictAndPageDestruction() {
        TestServices.writeCompanions();TestServices.permissions(true,true);
        var manifest=fileDialogHelper.documentBundle([],"file://"+TestServices.fixtureDirectory);
        var paths=manifest.urls.map(function(url){return fileDialogHelper.urlToPath(url);});
        var outcome=null;
        Assets.uploadBundle(paths,manifest.relativePaths,"/revoked/","scene.gltf",function(){TestServices.permissions(false,true);},function(error,published){outcome={error:error,published:JSON.parse(published)};});
        tryVerify(function(){return outcome!==null;});verify(outcome.error.indexOf("revoked")>=0);compare(outcome.published.length,0);
        TestServices.permissions(true,true);outcome=null;
        Assets.uploadBundle([paths[0]],["exists.fbx"],"/","exists.fbx",function(){},function(error){outcome=error;});
        tryVerify(function(){return outcome!==null;});verify(outcome.indexOf("already exists")>=0);
        var assets=production("hifi/dialogs/TabletAssetServer.qml");assets.pendingBundle=manifest;assets.pendingBundle.primaryPath="scene.gltf";
        control(assets,"assetBundleDestination").text="/closed/";TestServices.holdBundleUploads(true);assets.uploadBundle();wait(20);assets.destroy();wait(30);TestServices.releaseBundleUploads();wait(20);
        compare(TestServices.publishedBundle().length,0);
        var available=Assets.uploadBundle(paths,manifest.relativePaths,"/after-close/","scene.gltf",function(){},function(){ });verify(available.length>0);
        verify(Assets.cancelUploadBundle(available));wait(30);
    }

}
