// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Explicit native audio service boundary; never physical audio evidence.
import QtQuick 2.7
QtObject {
    property string context: "VR"
    property bool mutedDesktop: false
    property bool mutedHMD: false
    property bool muted: mutedHMD
    property bool pushToTalkDesktop: false
    property bool pushToTalkHMD: false
    property bool warnWhenMuted: false
    property bool isStereoInput: false
    property bool acousticEchoCancellation: false
    property bool noiseReduction: false
    property bool noiseReductionAutomatic: false
    property real inputLevel: 0
    property real avatarGain: 0
    property real injectorGain: 0
    property real localInjectorGain: 0
    property real systemInjectorGain: 0
    property real noiseReductionThreshold: 0
    property bool echo: false
    property int starts: 0
    property int cancels: 0
    property var status: ({ phase: "idle", error: "" })
    property QtObject devices: QtObject {
        property QtObject input: QtObject { property bool peakValuesEnabled: false; property bool peakValuesAvailable: false }
        property var output: []
    }
    signal recordedVoiceTestStatusChanged(var status)
    signal noiseGateOpened()
    signal noiseGateClosed()
    function getRecordedVoiceTestStatus() { return status }
    function getLocalEcho() { return echo }
    function setLocalEcho(value) { echo = value }
    function startRecordedVoiceTest() {
        starts++
        status = { phase: mutedHMD ? "error" : "capturing", error: mutedHMD ? "microphone-muted" : "" }
        recordedVoiceTestStatusChanged(status)
    }
    function cancelRecordedVoiceTest() { cancels++ }
    function getAvatarGain() { return avatarGain }
    function setAvatarGain(value) { avatarGain = value }
    function getInjectorGain() { return injectorGain }
    function setInjectorGain(value) { injectorGain = value }
    function setLocalInjectorGain(value) { localInjectorGain = value }
    function getSystemInjectorGain() { return systemInjectorGain }
    function setSystemInjectorGain(value) { systemInjectorGain = value }
    function getNoiseReductionThreshold() { return noiseReductionThreshold }
    function setNoiseReductionThreshold(value) { noiseReductionThreshold = value }
}
