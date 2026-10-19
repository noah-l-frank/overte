// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
import QtQuick 2.15
import QtTest 1.2

TestCase {
    id: test
    name: "PhoneGraphics"
    when: windowShown
    visible: true
    width: 420
    height: 600
    property string currentPage: "Graphics"
    property var packets: []
    property var page
    function toScript(message) { packets.push(message) }

    function test_normalPhoneProfileAdmitsItsBoundedGraphicsPage() {
        // The original test forced a directly constructed page visible. That
        // could pass while the normal Settings capability gate hid its entry.
        var profileComponent = Qt.createComponent(phoneProfileSource)
        compare(profileComponent.status, Component.Ready, profileComponent.errorString())
        var profile = profileComponent.createObject(test)
        verify(profile !== null)
        var configuration = null
        try {
            var configurationComponent = Qt.createComponent(settingsConfigurationSource)
            compare(configurationComponent.status, Component.Ready, configurationComponent.errorString())
            configuration = configurationComponent.createObject(test, {profile: profile})
            verify(configuration !== null)
            verify(configuration.showGraphicsSettings, "Normal Phone Settings must expose its implemented graphics page")
            verify(configuration.admitsSemanticControl("settings.graphics"))
            verify(!configuration.showControllerSettings)
            verify(!configuration.showPicoResolutionSettings)
            verify(!configuration.admitsSemanticControl("settings.controllers"))
        } finally {
            // Retire the consumer before its actual profile, including when a
            // failing assertion aborts this method.
            if (configuration) configuration.destroy()
            profile.destroy()
        }
    }

    function initTestCase() {
        var component = Qt.createComponent(pageSource)
        compare(component.status, Component.Ready, component.errorString())
        page = component.createObject(test, { width: 420, height: 600 })
        verify(page !== null, component.errorString())
        // The host runs Linux; show the Android-only page to exercise the
        // production controls through Qt's real pointer delivery.
        page.visible = true
        page.fromScript({ type: "phone.graphics.state", values: {
            localLights: false, haze: false, proceduralMaterials: false,
            mirrors: false, resolutionScale: 0.65
        } })
        wait(50)
    }
    function test_switchAndConfirmedState() {
        page.width = 420
        wait(50)
        var control = findChild(page, "settings.graphics.localLights")
        verify(control !== null)
        verify(control.enabled)
        verify(control.height >= 48)
        mouseClick(control, 20, control.height / 2)
        compare(packets[packets.length - 1].type, "phone.graphics.update")
        compare(packets[packets.length - 1].key, "localLights")
        compare(packets[packets.length - 1].value, true)
        page.fromScript({ type: "phone.graphics.state", values: {
            localLights: false, haze: false, proceduralMaterials: false,
            mirrors: false, resolutionScale: 0.65
        } })
        compare(control.checked, false, "confirmed controller response replaces UI optimism")
        page.fromScript({ type: "phone.graphics.state", values: {
            localLights: true, haze: true, proceduralMaterials: true,
            mirrors: true, resolutionScale: 0.7
        } })
        compare(control.checked, true)
    }
    function test_scaleAndNarrowLayout() {
        var slider = findChild(page, "settings.graphics.resolutionScale")
        compare(slider.from, 0.5)
        compare(slider.to, 0.7)
        verify(slider.height >= 48)
        page.width = 280
        wait(50)
        var metrics = findChild(page, "phone.graphics.metrics")
        metrics.profile.fontScale = 1.5
        wait(50)
        compare(page.contentWidth, 280)
        verify(slider.width <= 248)
    }
}
