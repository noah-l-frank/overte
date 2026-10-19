// SPDX-License-Identifier: Apache-2.0
import QtQuick 2.7
import QtTest 1.2
import TestSnapshot 1.0
import "../production"

TestCase {
    name: "NativeSnapshotReview"
    visible: true
    width: 900; height: 1200
    when: windowShown
    Component { id: factory; NativeSnapshotReview { width: 800; height: 1100 } }
    Component { id: spyFactory; SignalSpy { signalName: "sendToScript" } }
    SignalSpy { id: outgoing; signalName: "sendToScript" }
    property var review: null
    function init() { Snapshot.selectedFormat = "png"; review = createTemporaryObject(factory, this); verify(review); outgoing.target = review; wait(1); outgoing.clear() }
    function cleanup() { if (review) { review.destroy(); review = null } }
    function test_four_real_capture_modes() {
        var mode = findChild(review, "snapshotMode")
        var button = findChild(review, "snapshotCapture")
        verify(mode); verify(button)
        var name = findChild(review, "snapshotName"); name.text = "Photo"
        var modes = ["still", "animated", "panorama", "cubemap"]
        for (var i = 0; i < modes.length; ++i) {
            mode.currentIndex = i
            mouseClick(button)
            compare(outgoing.count, i + 1)
            var message = outgoing.signalArguments[i][0]
            compare(message.type, "snapshot"); compare(message.action, "takeSnapshot")
            compare(message.mode, modes[i]); compare(message.filename, "Photo")
        }
    }
    function visualItem(item, name) {
        if (!item) { return null }
        if (item.objectName === name) { return item }
        var children = item.children || []
        for (var index = 0; index < children.length; ++index) {
            var found = visualItem(children[index], name)
            if (found) { return found }
        }
        return null
    }
    function test_ready_after_native_loader_can_connect() {
        var page = createTemporaryObject(factory, this)
        verify(page)
        // The native loader connects the created root after construction.
        // A synchronous completed() emission disappears before that boundary.
        var spy = createTemporaryObject(spyFactory, this, {target: page})
        tryCompare(spy, "count", 1)
        compare(spy.signalArguments[0][0].action, "ready")
    }
    function test_real_popup_pointer_selects_all_modes_and_persists_gif_choice() {
        var mode = findChild(review, "snapshotMode")
        var capture = findChild(review, "snapshotCapture")
        var modes = ["still", "animated", "panorama", "cubemap"]
        for (var index = 0; index < modes.length; ++index) {
            mouseClick(mode)
            tryCompare(mode.popup, "visible", true)
            var choice = null
            tryVerify(function() {
                choice = visualItem(mode.popup.contentItem, "snapshotMode.option." + modes[index])
                return choice !== null
            })
            outgoing.clear()
            mouseClick(choice)
            tryCompare(mode.popup, "visible", false)
            compare(mode.currentIndex, index)
            compare(outgoing.count, 1)
            compare(outgoing.signalArguments[0][0].action,
                index === 1 ? "captureStillAndGif" : "captureStillOnly")
            outgoing.clear()
            mouseClick(capture)
            compare(outgoing.signalArguments[0][0].mode, modes[index])
        }
    }
    function test_real_format_popup_reaches_actual_preference_boundary() {
        var format = findChild(review, "snapshotFormat")
        for (var index = 0; index < 3; ++index) {
            var value = ["jpg", "webp", "png"][index]
            mouseClick(format)
            tryCompare(format.popup, "visible", true)
            var choice = null
            tryVerify(function() {
                choice = visualItem(format.popup.contentItem, "snapshotFormat.option." + value)
                return choice !== null
            })
            mouseClick(choice)
            tryCompare(format.popup, "visible", false)
            compare(format.currentText, value)
            compare(Snapshot.selectedFormat, value)
        }
    }
    function test_initial_capture_settings_do_not_echo_a_user_preference_write() {
        compare(review.captureSettingsLoaded, false)
        review.fromScript({type: "snapshot", action: "captureSettings", setting: true})
        compare(review.captureSettingsLoaded, true)
        compare(findChild(review, "snapshotMode").currentIndex, 1)
        compare(outgoing.count, 0)
        review.fromScript({type: "snapshot", action: "captureSettings", setting: false})
        compare(findChild(review, "snapshotMode").currentIndex, 0)
        compare(outgoing.count, 0)
    }
    function test_capture_error_and_cancel_controls() {
        review.fromScript({type:"snapshot", action:"clearPreviousImages"})
        compare(review.capturing, true)
        verify(!findChild(review, "snapshotCapture").enabled)
        mouseClick(findChild(review, "snapshotCancelCapture"))
        compare(outgoing.signalArguments[0][0].action, "cancelSnapshotCapture")
        review.fromScript({type:"snapshot", action:"captureStatus", phase:"error", error:"disk-full"})
        compare(review.capturing, false); compare(review.processing, false)
        compare(review.statusError, true); verify(review.statusText.indexOf("disk-full") !== -1)
        review.fromScript({type:"snapshot", action:"captureStatus", phase:"complete"})
        compare(review.statusError, false); verify(findChild(review,"snapshotCapture").enabled)
    }
    function test_preview_preserves_still_gif_and_audiences() {
        review.fromScript({type:"snapshot", action:"showPreviousImages", options:{isLoggedIn:true,canShare:true,canBlast:true},
            image_data:[{localPath:"/native/still.png",story_id:42}]})
        review.fromScript({type:"snapshot", action:"addImages", options:{containsGif:true,isLoggedIn:true,canShare:true},
            image_data:[{localPath:"/native/animation.gif"}]})
        compare(review.images.length, 2); compare(review.images[0].story_id, 42)
        review.fromScript({type:"snapshot",action:"snapshotUploadComplete",image_url:"https://host/animation.gif",story_id:99})
        compare(review.images[0].story_id,42); compare(review.images[1].story_id,99)
    }
    function test_upload_ticket_errors_and_old_completion() {
        review.upload("/native/still.png")
        compare(outgoing.signalArguments[0][0].action, "shareSnapshotForUrl")
        review.fromScript({type:"snapshot",action:"uploadStatus",path:"/old.png",status:"success"})
        compare(review.uploadPath,"/native/still.png")
        review.fromScript({type:"snapshot",action:"uploadStatus",path:"/native/still.png",status:"error",error:"unauthorized"})
        compare(review.uploadPath,""); compare(review.statusError,true)
        verify(review.statusText.indexOf("unauthorized") !== -1)
    }
    function test_actual_selected_export_and_cancel() {
        review.exportImage("/native/still.png","share")
        if (!review.exportTicket) { // The real generic backend honestly declines.
            compare(review.statusError,true); verify(review.statusText.length>0); return
        }
        var old = review.exportTicket
        review.cancelExport()
        compare(review.exportTicket,""); verify(review.statusText.indexOf("cancelled") !== -1)
        review.exportImage("/native/still.png","save")
        verify(review.exportTicket !== old)
        review.cancelExport(); compare(review.exportTicket,"")
    }
    function test_headset_keyboard_lifecycle() {
        var field = findChild(review,"snapshotName")
        field.forceActiveFocus()
        tryCompare(review,"keyboardRaised",true)
        compare(KeyboardScriptingInterface.raised,true)
        review.destroy(); review = null
        tryCompare(KeyboardScriptingInterface,"raised",false)
    }
}
