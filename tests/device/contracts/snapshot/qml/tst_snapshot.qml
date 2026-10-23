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
    function init() {
        Snapshot.selectedFormat = "png"
        review = createTemporaryObject(factory, this); verify(review)
        outgoing.target = review; wait(1); outgoing.clear()
        review.fromScript({type: "snapshot", action: "captureSettings", setting: false})
    }
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
    function test_landscape_drag_reaches_capture() {
        review.width = 856
        review.height = 290
        wait(30)
        var button = findChild(review, "snapshotCapture")
        var flick = button.parent
        while (flick && typeof flick.contentY !== "number") { flick = flick.parent }
        verify(flick)
        verify(flick.contentHeight > flick.height)
        mouseDrag(flick, flick.width * 0.8, flick.height * 0.85, 0, -flick.height * 0.6,
            Qt.LeftButton, Qt.NoModifier, 200)
        tryVerify(function() { return flick.contentY > 0 })
        flick.cancelFlick()
        var point = button.mapToItem(flick, button.width / 2, button.height / 2)
        verify(point.y > 0 && point.y < flick.height)
        mouseClick(button, button.width / 2, button.height / 2)
        compare(outgoing.count, 1)
        compare(outgoing.signalArguments[0][0].action, "takeSnapshot")
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
            mouseClick(mode)
            tryCompare(mode.popup, "visible", true)
            for (var option = 0; option < modes.length; ++option) {
                var row = visualItem(mode.popup.contentItem, "snapshotMode.option." + modes[option])
                verify(row); compare(row.checked, option === index)
            }
            mouseClick(choice)
            tryCompare(mode.popup, "visible", false)
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
            mouseClick(format)
            tryCompare(format.popup, "visible", true)
            compare(choice.checked, true)
            mouseClick(choice)
            tryCompare(format.popup, "visible", false)
        }
    }
    function test_initial_capture_settings_do_not_echo_a_user_preference_write() {
        review.destroy()
        review = createTemporaryObject(factory, this); outgoing.target = review
        wait(1); outgoing.clear()
        compare(review.captureSettingsLoaded, false)
        verify(!findChild(review, "snapshotMode").enabled)
        verify(!findChild(review, "snapshotCapture").enabled)
        review.fromScript({type: "snapshot", action: "captureSettings", setting: true})
        compare(review.captureSettingsLoaded, true)
        compare(findChild(review, "snapshotMode").currentIndex, 1)
        compare(outgoing.count, 0)
        review.fromScript({type: "snapshot", action: "captureSettings", setting: false})
        compare(findChild(review, "snapshotMode").currentIndex, 0)
        compare(outgoing.count, 0)
    }
    function test_delayed_initial_settings_cannot_overwrite_a_user_choice() {
        var mode = findChild(review, "snapshotMode")
        mouseClick(mode)
        tryCompare(mode.popup, "visible", true)
        var row = null
        tryVerify(function() {
            row = visualItem(mode.popup.contentItem, "snapshotMode.option.panorama")
            return row !== null
        })
        mouseClick(row)
        tryCompare(mode.popup, "visible", false)
        compare(mode.currentIndex, 2)
        outgoing.clear()
        review.fromScript({type: "snapshot", action: "captureSettings", setting: true})
        compare(mode.currentIndex, 2)
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
        compare(review.images[0].image_url, undefined)
        compare(review.images[1].image_url, "https://host/animation.gif")
    }
    function test_uploaded_url_can_be_copied_from_the_actual_review_button() {
        review.fromScript({type:"snapshot", action:"showPreviousImages", options:{isLoggedIn:true,canShare:true},
            image_data:[{localPath:"/native/still.png"}]})
        var button = null
        tryVerify(function() { button = visualItem(review, "snapshotCopyUrl"); return button !== null })
        compare(button.visible, false)
        review.fromScript({type:"snapshot",action:"snapshotUploadComplete",image_url:"https://host/snapshot.png",story_id:42})
        tryVerify(function() { button = visualItem(review, "snapshotCopyUrl"); return button !== null && button.visible })
        outgoing.clear()
        mouseClick(button)
        compare(outgoing.count, 1)
        compare(outgoing.signalArguments[0][0].action, "copySnapshotUrl")
        compare(outgoing.signalArguments[0][0].url, "https://host/snapshot.png")
        compare(outgoing.signalArguments[0][0].story_id, 42)
        review.fromScript({type:"snapshot",action:"snapshotUrlCopied"})
        compare(review.statusError, false)
        compare(review.statusText, "Snapshot URL copied.")
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
