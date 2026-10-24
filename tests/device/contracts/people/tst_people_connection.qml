// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
import QtQuick 2.12
import QtTest 1.2
import "../../../../interface/resources/qml/hifi" as People
TestCase {
    id: testCase
    name: "PeopleConnection"
    when: windowShown
    visible: true
    width: 600
    height: 750
    Component { id: app; People.Pal { width: 600; height: 700 } }
    SignalSpy { id: messages; signalName: "sendToScript" }
    function visibleControl(item, name) {
        if (item.objectName === name && item.visible) { return item; }
        var children = item.children || [];
        for (var i = 0; i < children.length; ++i) {
            var found = visibleControl(children[i], name);
            if (found) { return found; }
        }
        return null;
    }
    function state(page, phase) {
        page.fromScript({ method: "connectionState", params: { phase: phase,
            message: "A connection status from the actual script", peerName: "Actual peer" } });
        waitForRendering(page);
    }
    function profiles() { return [ { tag: "touch", width: 480, height: 706, touch: true },
        { tag: "vr-pointer", width: 600, height: 700, touch: false } ]; }
    function test_explicitPromptButtonsAndBack_data() { return profiles(); }
    function test_explicitPromptButtonsAndBack(data) {
        var page = createTemporaryObject(app, testCase, { width: data.width, height: data.height });
        verify(page !== null);
        messages.target = page; messages.clear();
        state(page, "incoming");
        waitForRendering(page);
        var prompt = findChild(page, "peopleConnectionPrompt");
        tryCompare(prompt, "visible", true);
        var accept = findChild(page, "peopleConnectionAccept");
        verify(accept.visible);
        var panel = findChild(page, "peopleConnectionPanel");
        var bounds = panel.mapToItem(page, 0, 0);
        verify(bounds.x >= 0 && bounds.y >= 0);
        verify(bounds.x + panel.width <= page.width && bounds.y + panel.height <= page.height);
        for (var name of ["peopleConnectionAccept", "peopleConnectionDecline"]) {
            var control = findChild(page, name), point = control.mapToItem(page, 0, 0);
            verify(point.x >= bounds.x && point.y >= bounds.y);
            verify(point.x + control.width <= bounds.x + panel.width);
            verify(point.y + control.height <= bounds.y + panel.height);
        }
        mouseClick(accept, accept.width / 2, accept.height / 2);
        compare(messages.signalArguments[messages.count - 1][0].method, "connectionRespond");
        compare(messages.signalArguments[messages.count - 1][0].params, true);
        var decline = findChild(page, "peopleConnectionDecline");
        mouseClick(decline, decline.width / 2, decline.height / 2);
        compare(messages.signalArguments[messages.count - 1][0].params, false);
        state(page, "outgoing");
        verify(!accept.visible);
        var cancel = findChild(page, "peopleConnectionCancel");
        compare(cancel.text, "Cancel"); mouseClick(cancel, cancel.width / 2, cancel.height / 2);
        compare(messages.signalArguments[messages.count - 1][0].method, "connectionCancel");
        verify(page.handleTabletBack());
        messages.clear();
        keyClick(Qt.Key_Escape);
        compare(messages.signalArguments[messages.count - 1][0].method, "connectionCancel");
        state(page, "idle"); tryCompare(prompt, "visible", false); verify(!page.handleTabletBack());
        verify(!prompt.activeFocus);
        state(page, "submitting"); compare(cancel.text, "Stop waiting");
        state(page, "success"); compare(cancel.text, "Close");
        state(page, "error"); compare(cancel.text, "Close");
    }
    function test_selectedNearbyPersonHasReachableConnectControl_data() { return profiles(); }
    function test_selectedNearbyPersonHasReachableConnectControl(data) {
        Users.avatarGain = 1;
        var page = createTemporaryObject(app, testCase, { width: data.width, height: data.height });
        verify(page !== null); messages.target = page; messages.clear();
        page.fromScript({ method: "nearbyUsers", params: [
            { sessionId: "", displayName: "Self", userName: "fixture", connection: "self", profileUrl: "", audioLevel: 0, avgAudioLevel: 0, admin: false, personalMute: false, ignore: false, isPresent: true, isReplicated: false },
            { sessionId: "{22222222-2222-4222-8222-222222222222}", displayName: "Nearby", userName: "", connection: "", profileUrl: "", audioLevel: 0, avgAudioLevel: 0, admin: false, personalMute: false, ignore: false, isPresent: true, isReplicated: false }
        ] });
        page.fromScript({ method: "select", params: [["{22222222-2222-4222-8222-222222222222}"], true, true] });
        var button = null;
        tryVerify(function() { button = visibleControl(page, "peopleRequestConnection"); return button && button.visible; });
        verify(button.enabled); verify(button.height >= 48);
        var point = button.mapToItem(page, 0, 0);
        verify(point.x >= 0 && point.x + button.width <= page.width);
        verify(point.y >= 0 && point.y + button.height <= page.height);
        var gain = visibleControl(page, "peopleAvatarGain");
        verify(gain !== null);
        findChild(gain, "peopleGainMetrics").directTouch = data.touch;
        tryCompare(gain, "height", data.touch ? 48 : 14);
        var gainPoint = gain.mapToItem(page, 0, 0);
        verify(gainPoint.y + gain.height <= point.y, "Gain and Connect occupy independent bands");
        var oldGain = Users.avatarGain;
        mouseClick(gain, gain.width / 4, gain.height / 2);
        verify(Users.avatarGain !== oldGain, "Real pointer input still reaches the existing gain control");
        mouseClick(button, button.width / 2, button.height / 2);
        compare(messages.signalArguments[messages.count - 1][0].method, "connectionRequest");
        compare(messages.signalArguments[messages.count - 1][0].params, "{22222222-2222-4222-8222-222222222222}");
    }
}
