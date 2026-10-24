// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
import QtQuick 2.15
import QtTest 1.2
TestCase {
    id: testCase
    name: "IOSWorldWebControls"
    when: windowShown
    visible: true
    width: 480
    height: 640
    function world() {
        var component = Qt.createComponent(worldWebRoot + "/interface/resources/qml/Web3DSurface.qml");
        verify(component.status === Component.Ready, component.errorString());
        var page = createTemporaryObject(component, testCase, { width: 480, height: 640, url: "https://example.test/world" });
        verify(page !== null);
        tryVerify(function() { return findChild(page, "FakeEmbeddedWebBackend") !== null; });
        return page;
    }
    function test_worldPointerControlsPreserveTheCurrentDocument() {
        var page = world(), backend = findChild(page, "FakeEmbeddedWebBackend");
        var up = findChild(page, "IOSWorldWebScrollUp");
        var down = findChild(page, "IOSWorldWebScrollDown");
        var open = findChild(page, "IOSWorldWebOpenBrowser");
        verify(up !== null && down !== null && open !== null);
        compare(backend.surface, "world-entity");
        compare(page.item.webViewCore.y, 96);
        compare(page.item.webViewCore.height, page.height - 96);
        for (var control of [up, down, open]) {
            verify(control.visible && control.enabled && control.height >= 48);
            var position = control.mapToItem(page, 0, 0);
            verify(position.x >= 0 && position.x + control.width <= page.width);
            verify(position.y >= 0 && position.y + control.height <= page.height);
        }
        var originalSource = backend.url;
        mouseClick(down); mouseClick(up); mouseClick(open);
        compare(backend.scripts.length, 2);
        verify(/^window\.scrollBy\(0,\d+\);$/.test(backend.scripts[0]));
        compare(backend.scripts[1], backend.scripts[0].replace("(0,", "(0,-"));
        compare(backend.operations.join(","), "open");
        compare(backend.url, originalSource);
        console.warn("OVERTE_IOS_WORLD_SCROLL_SCRIPTS=" + JSON.stringify(backend.scripts));
        page.scriptUrl = "https://example.test/client.js";
        compare(backend.scriptUrl, page.scriptUrl);
        page.fromScript({ originalBridge: true });
        compare(backend.events.length, 1);
        verify(backend.events[0].originalBridge);
        // Failed texture capture keeps the existing native presentation usable.
        backend.error = "Capture unavailable";
        verify(!down.enabled && !up.enabled && open.enabled);
        mouseClick(down); mouseClick(open);
        compare(backend.scripts.length, 2);
        compare(backend.operations.join(","), "open,open");
        backend.error = ""; backend.loading = true;
        verify(!down.enabled && open.enabled);
        backend.loading = false;
        page.item.interactive = false;
        verify(!down.enabled && !open.enabled);
        var disabledOperations = backend.operations.join(",");
        mouseClick(down); mouseClick(open);
        compare(backend.scripts.length, 2);
        compare(backend.operations.join(","), disabledOperations);
        page.item.interactive = true;
        page.item.scrollWorldPage(0);
        page.item.visible = false;
        page.item.scrollWorldPage(1);
        compare(backend.scripts.length, 2);
        page.item.visible = true;
        // A replacement source owns a new backend; old calls cannot target it.
        page.url = "https://example.test/replacement";
        tryVerify(function() {
            var replacement = findChild(page, "FakeEmbeddedWebBackend");
            return replacement !== null && replacement.url === page.url;
        });
        var replacement = findChild(page, "FakeEmbeddedWebBackend");
        compare(replacement.scripts.length, 0);
        compare(replacement.scriptUrl, page.scriptUrl);
        down = findChild(page, "IOSWorldWebScrollDown");
        down.forceActiveFocus(); keyClick(Qt.Key_Space);
        compare(replacement.scripts.length, 1);
    }
    function test_tabletKeepsItsExistingNativePresentationAndViewport() {
        var component = Qt.createComponent(worldWebRoot + "/interface/resources/qml/controls/FlickableWebViewCore.qml");
        verify(component.status === Component.Ready, component.errorString());
        var page = createTemporaryObject(component, testCase, { width: 480, height: 640, surface: "tablet", url: "https://example.test/tablet" });
        verify(page !== null);
        tryVerify(function() { return page.webViewCore.backend !== null; });
        var controls = findChild(page, "IOSWorldWebControls");
        verify(controls === null || !controls.visible);
        compare(page.webViewCore.y, 48);
        compare(page.webViewCore.height, page.height - 48);
        compare(page.webViewCore.backend.surface, "tablet");
    }
}
