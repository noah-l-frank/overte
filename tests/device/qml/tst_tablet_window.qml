import QtQuick 2.12
import QtTest 1.2
import Hifi 1.0
import "../../../interface/resources/qml/hifi/tablet" as TabletUi
import "../../../scripts/system/places" as Places

TestCase {
    id: testCase
    name: "WholeTabletNavigation"
    when: windowShown
    visible: true
    width: 1400
    height: 1400
    readonly property string homeSource: "hifi/tablet/TabletHome.qml"
    readonly property string placesSource: "scripts/system/places/PicoPlaces.qml"
    readonly property string chatSource: Qt.resolvedUrl("../../../scripts/communityScripts/armored-chat/armored_chat.qml")
    property var currentWindow: null
    SignalSpy { id: cursorGeometry; target: Qt.inputMethod; signalName: "cursorRectangleChanged" }
    // Only the native desktop, page-loading and TabletProxy service boundaries
    // are substituted. WindowRoot, ScrollingWindow and Places are production QML.
    QtObject {
        id: desktop
        property int invalid_position: -10000
        property bool gradientsSupported: false
        property bool pinned: false
        signal hmdHandMouseActiveChanged()
        function centerOnVisible(window) { window.x = 0; window.y = 0 }
        function repositionOnVisible(window) {}
        function raise(window) {}
    }
    QtObject { id: eventBridge; signal webEventReceived(var message) }
    QtObject {
        id: proxy
        property int homes: 0
        property int closes: 0
        property bool tabletShown: false
        function gotoHomeScreen() { homes++; currentWindow.loadSource(homeSource) }
        function hideAndroidTablet() {
            closes++
            currentWindow.setShown(false)
            tabletShown = false
        }
        function loadQMLSource(source) { currentWindow.loadSource(source) }
    }
    QtObject {
        id: surface
        signal qmlLoadFailed(var parent, int generation)
        function load(source, parent, callback) {
            if (source === "broken.qml") {
                qmlLoadFailed(parent, parent.qmlLoadGeneration)
                return
            }
            var factory = source === chatSource ? Qt.createComponent(chatSource)
                : source === placesSource ? placesFactory : homeFactory
            if (source === chatSource) {
                if (factory.status !== Component.Ready) { throw new Error(factory.errorString()) }
                callback(factory.createObject(parent, { tabletMode: true }))
                return
            }
            callback(factory.createObject(parent))
        }
    }
    Component { id: homeFactory; Item {
        property string url: ""
        property string scriptURL: ""
        property real screenSpaceMinimumContentHeight: 0
    } }
    Component { id: placesFactory; Places.PicoPlaces {} }
    Component { id: scrollEditorFactory; TextInput { width: 180; height: 40; y: 500 } }
    Component {
        id: windowFactory
        TabletUi.WindowRoot {
            tabletProxy: proxy
            pageSurface: surface
        }
    }

    function init() {
        proxy.homes = 0; proxy.closes = 0; proxy.tabletShown = false
        Account.username = "Unknown user"; Account.loggedIn = false
    }
    function cleanup() { currentWindow = null }

    function openTablet() {
        var window = createTemporaryObject(windowFactory, testCase)
        verify(window !== null)
        currentWindow = window
        window.setScreenSpaceMode(true)
        window.loadSource(placesSource)
        window.setShown(true)
        proxy.tabletShown = true
        tryCompare(window, "opacity", 1)
        return window
    }

    // WindowRoot is the production Phone/toolbar presenter. The native
    // Account service is the controlled host boundary; its value must flow
    // through the actual QML binding, not a test-side setUsername call.
    // The substituted homeFactory does not prove TabletHome pixels.
    function test_initialNativeAccountLabel() {
        Account.username = "fixture-user"
        Account.loggedIn = true
        var window = openTablet()
        compare(window.username, "fixture-user")
        compare(window.usernameShort, "fixture-user")
    }

    function test_nativeProfileChangeAndLogoutLabel() {
        var window = openTablet()
        Account.username = "abcdefghijklmnop"
        Account.loggedIn = true
        tryCompare(window, "username", "abcdefghijklmnop")
        tryCompare(window, "usernameShort", "abcdefghijklmn...")
        Account.username = "Unknown user"
        Account.loggedIn = false
        tryCompare(window, "username", "Unknown user")
        tryCompare(window, "usernameShort", "Unknown user")
    }

    function test_accountLabelFormatting_data() {
        return [
            {tag: "empty", value: "", expected: ""},
            {tag: "short", value: "abc", expected: "abc"},
            {tag: "fourteen", value: "abcdefghijklmn", expected: "abcdefghijklmn"},
            {tag: "fifteen", value: "abcdefghijklmno", expected: "abcdefghijklmn..."}
        ]
    }

    function test_accountLabelFormatting(data) {
        var window = openTablet()
        window.setUsername(data.value)
        compare(window.username, data.value)
        compare(window.usernameShort, data.expected)
        verify(typeof window.playButtonClickSound === "function")
    }

    function test_windowHideReleasesTabletState() {
        var window = openTablet()
        // A host/window close bypasses the footer's hideAndroidTablet call.
        // The native proxy must still notify mobileActionBar to release input.
        window.setShown(false)
        compare(proxy.tabletShown, false)
        compare(proxy.closes, 1)
        tryCompare(window, "visible", false)
        window.setShown(false)
        compare(proxy.closes, 1)
    }

    function test_declaredPageMinimumKeepsShortFormReachable() {
        var window = openTablet()
        var profile = findChild(window, "tabletTouchProfile")
        profile.directTouch = true
        profile.surfaceWidth = 1080
        profile.surfaceHeight = 440
        profile.safeInsetBottom = 0
        profile.screenSpaceContentScale = 2.5
        tryCompare(window, "height", 440)
        window.loadSource("short-form.qml")
        var loader = findChild(window, "loader")
        tryVerify(function() { return loader.item !== null && window.footer.visible })
        loader.item.screenSpaceMinimumContentHeight = 706
        tryVerify(function() { return loader.item.height >= 706 })
        verify(window.contentFlickableInteractive)
        var scroll = null
        for (var i = 0; i < window.pane.children.length; ++i) {
            var child = window.pane.children[i]
            if (typeof child.contentY === "number" && typeof child.flick === "function") {
                scroll = child
            }
        }
        verify(scroll !== null)
        tryVerify(function() {
            return window.footer.mapToItem(window, 0, window.footer.height).y <= window.height + 1
        })
        var footerY = window.footer.mapToItem(window, 0, 0).y
        mouseDrag(scroll, scroll.width / 2, scroll.height - 20, 0, -scroll.height / 2)
        tryVerify(function() { return scroll.contentY > 20 })
        compare(window.footer.mapToItem(window, 0, 0).y, footerY)
        // A compact modal can release the page minimum again.
        loader.item.screenSpaceMinimumContentHeight = 0
        tryVerify(function() { return loader.height < 706 })
        tryCompare(window, "contentFlickableInteractive", false)
    }

    function test_editorFocusBeforeImeKeepsScrolledPageStable() {
        var window = openTablet()
        var profile = findChild(window, "tabletTouchProfile")
        profile.directTouch = true
        profile.surfaceWidth = 1080
        profile.surfaceHeight = 600
        profile.safeInsetBottom = 0
        profile.screenSpaceContentScale = 2.5
        profile.keyboardVisible = false
        window.loadSource("short-form.qml")
        var loader = findChild(window, "loader")
        tryVerify(function() { return loader.item !== null })
        loader.item.screenSpaceMinimumContentHeight = 706
        var editor = createTemporaryObject(scrollEditorFactory, loader.item)
        verify(editor !== null)
        tryVerify(function() { return loader.item.height >= 706 })
        var scroll = null
        for (var i = 0; i < window.pane.children.length; ++i) {
            var child = window.pane.children[i]
            if (typeof child.contentY === "number" && typeof child.flick === "function") {
                scroll = child
            }
        }
        verify(scroll !== null)
        wait(120)
        scroll.contentY = editor.y * loader.contentScale - 80
        wait(80)
        var before = scroll.contentY
        verify(before > 50)
        var position = editor.mapToItem(window, 0, 0)
        verify(position.y >= 0 && position.y + editor.height * loader.contentScale < window.height)
        mouseClick(editor, editor.width / 2, editor.height / 2)
        tryVerify(function() { return editor.activeFocus })
        // Native IME visibility arrives after editor focus on Android. A tap
        // must not move the selected field away while that update is pending.
        wait(120)
        compare(profile.keyboardVisible, false)
        verify(Math.abs(scroll.contentY - before) < 1,
            "Focusing a visible editor reset the scroll before native IME arrival")
        profile.imeInsetBottom = 240
        profile.keyboardVisible = true
        tryCompare(window, "height", 360)
        tryVerify(function() {
            var cursor = editor.cursorRectangle
            var top = editor.mapToItem(scroll, 0, cursor.y).y
            var bottom = editor.mapToItem(scroll, 0, cursor.y + cursor.height).y
            return top >= -1 && bottom <= scroll.height + 1
        })
        wait(120)
        cursorGeometry.clear()
        window.revealFocusedEditor()
        tryVerify(function() { return cursorGeometry.count > 0 }, 1000,
            "The native cursor geometry must refresh after the real pane exposes the editor")
        profile.keyboardVisible = false
        profile.imeInsetBottom = 0
        tryCompare(scroll, "contentY", 0)
    }

    function test_clearLongChatAfterNativeKeyboardReopen() {
        var window = openTablet()
        var profile = findChild(window, "tabletTouchProfile")
        profile.directTouch = true
        profile.surfaceWidth = 2400
        profile.surfaceHeight = 1080
        profile.safeInsetLeft = 132
        profile.safeInsetTop = 74
        profile.safeInsetBottom = 84
        profile.screenSpaceContentScale = 8 / 3
        profile.keyboardVisible = false
        window.loadSource(chatSource)
        var loader = findChild(window, "loader")
        tryVerify(function() { return loader.item !== null })
        wait(120)
        var input = loader.item.messageInput
        var draft = ("PARITY-P82-PASTE-20261022 Grüße 🙂 "
            + new Array(101).join("p82-abcdefghijklmn ")).slice(0, 1425) + "\n"
        input.text = draft
        input.cursorPosition = draft.length
        input.forceActiveFocus()
        profile.imeInsetBottom = 686
        profile.keyboardVisible = true
        wait(150)

        profile.keyboardVisible = false
        profile.imeInsetBottom = 0
        wait(120)
        var entry = findChild(loader.item, "chatEntryScroll")
        mouseClick(entry, Math.min(80, entry.width / 3), entry.height / 2)
        verify(input.activeFocus)
        profile.imeInsetBottom = 686
        profile.keyboardVisible = true
        wait(150)
        keyClick(Qt.Key_A, Qt.ControlModifier)
        keyClick(Qt.Key_Backspace)
        compare(input.text, "")

        var scroll = null
        for (var i = 0; i < window.pane.children.length; ++i) {
            var child = window.pane.children[i]
            if (typeof child.contentY === "number" && typeof child.flick === "function") {
                scroll = child
            }
        }
        verify(scroll !== null)
        tryVerify(function() {
            var cursor = input.cursorRectangle
            var top = input.mapToItem(scroll, 0, cursor.y).y
            var bottom = input.mapToItem(scroll, 0, cursor.y + cursor.height).y
            return top >= -1 && bottom <= scroll.height + 1
        }, 1000, "Clearing the reopened draft moved its cursor outside the tablet viewport")
        var send = findChild(loader.item, "chatSend")
        var sendTop = send.mapToItem(scroll, 0, 0).y
        verify(sendTop < scroll.height && sendTop + send.height * loader.contentScale > 0,
            "Clearing the reopened draft hid Send outside the tablet viewport")
    }

    function test_reopenDuringFade_data() {
        return [
            {tag: "touch", screenSpace: true},
            {tag: "desktop", screenSpace: false}
        ]
    }

    function test_reopenDuringFade(data) {
        var window = openTablet()
        window.setScreenSpaceMode(data.screenSpace)
        for (var cycle = 0; cycle < 3; ++cycle) {
            // Also cancel a close before the first animation frame is drawn.
            window.setShown(false)
            window.setShown(true)
            proxy.tabletShown = true
            wait(350)
            compare(window.opacity, 1)
            window.setShown(false)
            tryVerify(function() { return window.opacity > 0 && window.opacity < 1 })
            window.setShown(true)
            proxy.tabletShown = true
            tryCompare(window, "opacity", 1)
            verify(window.visible)
            verify(window.shown)
        }
    }

    function test_desktopHideDoesNotOwnTouchState() {
        var window = openTablet()
        window.setScreenSpaceMode(false)
        window.setShown(false)
        compare(proxy.closes, 0)
        compare(proxy.tabletShown, true)
    }

    function test_repeatedNavigationAndClose() {
        var window = openTablet()
        findChild(window, "tabletTouchProfile").directTouch = true
        var loader = findChild(window, "loader")
        for (var cycle = 0; cycle < 3; ++cycle) {
            proxy.gotoHomeScreen()
            verify(window.shown)
            verify(proxy.tabletShown)
            window.loadSource(placesSource)
            tryVerify(function() { return window.footer.visible })
            // The OS browser remains a boundary; the complete WindowRoot must
            // implement the same close callback as the immersive tablet root.
            window.loadWebBase("https://example.test/close", "", null)
            tryCompare(loader, "source", "hifi/tablet/TabletWebView.qml")
            tryCompare(loader.item, "url", "https://example.test/close")
            window.returnToPreviousApp()
            tryCompare(loader, "source", placesSource)
            var close = findChild(window.footer, "nav.close")
            mouseClick(close, close.width / 2, close.height / 2)
            verify(!window.shown)
            verify(!proxy.tabletShown)
            tryCompare(window, "visible", false)
            window.setShown(true)
            proxy.tabletShown = true
            tryCompare(window, "opacity", 1)
            compare(loader.source, placesSource)
        }
    }

    function verifyNavigation(window, loader) {
        ;["back", "home", "close"].forEach(function(action) {
            var button = findChild(window.footer, "nav." + action)
            verify(button.visible, action + " must be visible inside the real tablet")
            var top = button.mapToItem(window, 0, 0)
            var bottom = button.mapToItem(window, button.width, button.height)
            verify(top.x >= 0 && bottom.x <= window.width)
            verify(top.y >= 0 && bottom.y <= window.height)
            verify(bottom.y - top.y >= 48)
            var pageBottom = loader.item.mapToItem(window, 0, loader.item.height).y
            verify(pageBottom <= top.y, "Places must not cover the navigation")
        })
    }

    function test_homePlacesNavigation_data() {
        return [
            {tag: "ipad-portrait", w: 768, h: 900, scale: 1},
            {tag: "ipad-landscape", w: 1024, h: 700, scale: 1},
            {tag: "compact-touch", w: 360, h: 640, scale: 1},
            {tag: "scaled-touch", w: 1080, h: 900, scale: 2.5}
        ]
    }
    function test_homePlacesNavigation(data) {
        var window = createTemporaryObject(windowFactory, testCase)
        verify(window !== null)
        currentWindow = window
        var profile = findChild(window, "tabletTouchProfile")
        verify(profile !== null)
        profile.directTouch = true
        profile.screenSpaceOriginAtSafeArea = true
        profile.surfaceWidth = data.w
        profile.surfaceHeight = data.h
        profile.safeInsetBottom = 20
        profile.screenSpaceContentScale = data.scale
        var loader = findChild(window, "loader")
        window.setScreenSpaceMode(true)
        window.loadSource(homeSource)
        window.setShown(true)
        waitForRendering(window)
        verify(!window.footer.visible)
        compare(window.footer.height, 0)

        window.loadSource(placesSource)
        tryVerify(function() { return window.footer.visible && window.footer.height > 0 })
        compare(loader.item.semanticScreenId, "places.home")
        loader.item.fromScript({channel: "com.overte.places", action: "PLACE_DATA", data: []})
        verify(!loader.item.loading)
        verifyNavigation(window, loader)
        // Real container resizing must keep the footer above native IME/safe area.
        profile.imeInsetBottom = 240
        tryCompare(window, "height", data.h - 240)
        verifyNavigation(window, loader)
        profile.imeInsetBottom = 0
        profile.surfaceWidth = data.h
        profile.surfaceHeight = data.w
        tryCompare(window, "width", data.h)
        tryCompare(window, "height", data.w - 20)
        verifyNavigation(window, loader)
        profile.surfaceWidth = data.w
        profile.surfaceHeight = data.h
        tryCompare(window, "height", data.h - 20)
        tryCompare(window, "opacity", 1)
        var home = findChild(window.footer, "nav.home")
        mouseClick(home, home.width / 2, home.height / 2)
        compare(proxy.homes, 1)
        compare(loader.source, homeSource)
        compare(window.footer.height, 0)

        window.loadSource(placesSource)
        tryVerify(function() { return window.footer.visible })
        var back = findChild(window.footer, "nav.back")
        mouseClick(back, back.width / 2, back.height / 2)
        compare(loader.source, homeSource)

        window.loadSource(placesSource)
        tryVerify(function() { return window.footer.visible })
        var close = findChild(window.footer, "nav.close")
        mouseClick(close, close.width / 2, close.height / 2)
        compare(proxy.closes, 1)
        verify(!window.shown)
        window.setShown(true)
        tryVerify(function() { return window.footer.visible })
        tryCompare(window, "opacity", 1)
        verifyNavigation(window, loader)
        window.loadSource("broken.qml")
        verify(loader.loadFailed)
        verify(window.footer.visible)
        mouseClick(home, home.width / 2, home.height / 2)
        compare(loader.source, homeSource)
        compare(window.footer.height, 0)
    }
}
