import QtQuick 2.7
import QtTest 1.2
import QtQuick.Window 2.2
import "production" as Production

TestCase {
    id: testCase
    name: "PhoneEmoteProductionControls"
    when: windowShown
    visible: true
    width: 640
    height: 480
    property var page: null
    property var events: []
    readonly property var agreed: ["Crying", "Surprised", "Dancing", "Cheering", "Waving",
        "Fall", "Pointing", "Clapping", "Sit", "Love"]
    Component {
        id: factory
        Production.PhoneEmote {
            onSendToScript: testCase.events.push(JSON.parse(JSON.stringify(message)))
        }
    }
    function init() {
        testCase.Window.window.width = width
        testCase.Window.window.height = height
        events = []
        page = createTemporaryObject(factory, testCase)
        verify(page !== null)
        waitForRendering(page)
        compare(events.length, 1)
        compare(events[0].method, "phoneEmote.ready")
        events = []
    }
    function cleanup() { page = null }
    function button(name) {
        tryVerify(function() { return findChild(page, "PhoneEmoteButton_" + name) !== null }, 2000)
        return findChild(page, "PhoneEmoteButton_" + name)
    }
    function test_actualMouseDispatchForAllTenAndStatusFeedback() {
        var dispatched = []
        for (var i = 0; i < agreed.length; ++i) {
            var name = agreed[i]
            var item = button(name)
            verify(item.visible && item.enabled && item.width > 40 && item.height > 40)
            mouseClick(item, item.width / 2, item.height / 2)
            compare(events.length, i + 1)
            compare(events[i].method, "phoneEmote.play")
            compare(events[i].name, name)
            dispatched.push(events[i])
            page.fromScript({ method: "phoneEmote.state", active: name, status: "Playing " + name })
            compare(item.highlighted, true)
            compare(findChild(page, "PhoneEmoteStatus").text, "Playing " + name)
        }
        console.log("OVERTE_EMOTE_ACTIONS_JSON=" + JSON.stringify(dispatched))
        page.fromScript({ method: "phoneEmote.state", active: "", status: "Choose an emote" })
        compare(button("Love").highlighted, false)
    }
    function test_repeatedClickAndKeyboardKeepActualDispatch() {
        var item = button("Waving")
        mouseClick(item, item.width / 2, item.height / 2)
        mouseClick(item, item.width / 2, item.height / 2)
        item.forceActiveFocus()
        keyClick(Qt.Key_Space)
        compare(events.length, 3)
        for (var i = 0; i < events.length; ++i) {
            compare(events[i].method, "phoneEmote.play")
            compare(events[i].name, "Waving")
        }
    }
    function test_loadingErrorAndMalformedStateAreVisibleAndScoped() {
        var status = findChild(page, "PhoneEmoteStatus")
        for (var i = 0; i < 2; ++i) {
            var text = i === 0 ? "Animation is still loading" : "Animation failed to load"
            page.fromScript({ method: "phoneEmote.state", active: "", status: text })
            compare(status.text, text)
            verify(status.visible)
        }
        page.fromScript({ method: "other", active: "Waving", status: "Foreign state" })
        compare(status.text, "Animation failed to load")
        page.fromScript(null)
        compare(status.text, "Animation failed to load")
        page.fromScript({ method: "phoneEmote.state", active: 7, status: "" })
        compare(status.text, "Choose an emote")
        compare(page.activeEmote, "")
        compare(events.length, 0)
    }
}
