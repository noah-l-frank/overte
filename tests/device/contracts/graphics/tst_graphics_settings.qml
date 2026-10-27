// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
import QtQuick 2.15
import QtTest 1.2
import "production/pages" as Production
TestCase {
    id: testCase
    name: "GraphicsSelectedNativeControls"
    width: 900
    height: 700
    visible: true
    when: windowShown
    property var page: null
    Component { id: factory; Production.GraphicsSettingsBase { } }
    function cleanup() { page = null }
    function createPage(deferred) {
        Render.useDeferred(deferred)
        page = createTemporaryObject(factory, testCase, {width:900,height:700})
        verify(page !== null)
        waitForRendering(page)
    }
    function toggle(item) {
        if (typeof item.checked === "boolean" && typeof item.toggle === "function") return item
        for (var i=0;i<item.children.length;++i) {
            var candidate=toggle(item.children[i])
            if (candidate) return candidate
        }
        return null
    }
    function test_forwardOnlyNativePathKeepsHazeReachable() {
        createPage(false)
        compare(page.deferredRenderingAvailable,false)
        compare(findChild(page,"settings.graphics.deferred").visible,false)
        compare(findChild(page,"settings.graphics.antialiasing").visible,false)
        var row=findChild(page,"settings.graphics.haze")
        verify(row.visible && row.enabled && row.height >= 30)
        page.contentY=Math.max(0,row.y-40)
        var control=toggle(row)
        verify(control !== null)
        var previous=Render.hazeEnabled
        mouseClick(control,control.width/2,control.height/2)
        compare(Render.hazeEnabled,!previous)
        mouseClick(control,control.width/2,control.height/2)
        compare(Render.hazeEnabled,previous)
    }
    function test_deferredCapablePathKeepsExistingControls() {
        createPage(true)
        compare(findChild(page,"settings.graphics.deferred").visible,true)
        compare(findChild(page,"settings.graphics.antialiasing").visible,true)
        verify(findChild(page,"settings.graphics.haze").visible)
    }
}
