// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once

// Identities/readiness for existing Audio widgets. No handler invocation,
// property assignment, audio source mutation or preferred result is performed.
#include <QCoreApplication>
#include <QJsonDocument>
#include <QJsonObject>
#include <QQuickItem>
#include <QThread>
#include <QVariantMap>
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include <QJSValue>
#endif

namespace overte::e2e {
struct AudioUiContext {
    bool valid {false}, active {false}, muted {false}, echo {false}, hmd {false};
    quint64 cycle {0};
    // The platform owner supplies its actual audio-thread observation and
    // actual current context; none of these values is accepted from UI input.
    static AudioUiContext fromNative(const QVariantMap& voice, bool muted, bool echo, bool hmd) {
        AudioUiContext result;
#if defined(OVERTE_E2E_FEATURE_TESTS)
        bool okay {false};
        const auto cycle = voice.value("cycle").toULongLong(&okay);
        if (QCoreApplication::arguments().contains("--testScript") && okay && voice.value("cycle").userType() == QMetaType::ULongLong && cycle <= 9007199254740991ULL
                && voice.value("historyVersion").userType() == QMetaType::Int
                && voice.value("historyVersion").toInt() == 1
                && voice.value("active").userType() == QMetaType::Bool) {
            result.valid = true; result.cycle = cycle; result.active = voice.value("active").toBool();
            result.muted = muted; result.echo = echo; result.hmd = hmd;
        }
#else
        Q_UNUSED(voice) Q_UNUSED(muted) Q_UNUSED(echo) Q_UNUSED(hmd)
#endif
        return result;
    }
};

inline bool audioGuiItem(QQuickItem* item) {
#if defined(OVERTE_E2E_FEATURE_TESTS)
    return item && qApp && QThread::currentThread() == qApp->thread()
        && item->thread() == qApp->thread() && QCoreApplication::arguments().contains("--testScript");
#else
    Q_UNUSED(item)
    return false;
#endif
}

inline QQuickItem* audioPage(QQuickItem* item) {
    if (!audioGuiItem(item)) { return nullptr; }
    int depth {0};
    for (auto node = item; node && ++depth <= 128; node = node->parentItem()) {
        if (node->objectName() == QStringLiteral("settings.audio")
                && node->property("title").toString() == QStringLiteral("Audio Settings")
                && node->property("isVR").userType() == QMetaType::Bool) { return node; }
    }
    return nullptr;
}

inline QQuickItem* audioLoopbackRoot(QQuickItem* item) {
    if (!audioPage(item)) { return nullptr; }
    for (auto node = item; node; node = node->parentItem()) {
        if (node->property("recordedStatus").isValid()
                && node->property("recordingRequested").userType() == QMetaType::Bool) { return node; }
    }
    return nullptr;
}

inline int audioSelectedMode(QQuickItem* page) {
    if (!page) { return -1; }
    QQuickItem* bar {nullptr};
    for (auto child : page->childItems()) {
        if (child->inherits("QQuickTabBar")) { if (bar) { return -1; } bar = child; }
    }
    if (!bar || bar->property("count").toInt() != 2) { return -1; }
    const auto index = bar->property("currentIndex");
    return index.userType() == QMetaType::Int && index.toInt() >= 0 && index.toInt() <= 1 ? index.toInt() : -1;
}

inline QString audioControlId(QQuickItem* item) {
    if (!audioGuiItem(item)) { return {}; }
    const auto name = item->objectName();
    const bool click = item->metaObject()->indexOfSignal("clicked()") >= 0;
    if (!audioPage(item)) {
        if (click && item->property("text").toString() == QStringLiteral("AUDIO")) { return "audio.entry"; }
        if (click && (name == "app.settings" || item->property("semanticId").toString() == "app.settings"
                || item->property("text").toString() == "SETTINGS")) { return "settings.entry"; }
        if (name == "settings.audio" && item->property("targetPage").toString() == "hifi/audio/Audio.qml"
                && item->property("pageName").toString() == "Audio") { return "audio.settings-entry"; }
        return {};
    }
    if (audioPage(item) == item) { return "audio.page"; }
    if (click && name == "recordedVoiceTestButton" && audioLoopbackRoot(item)) { return "audio.record"; }
    if (click && name == "liveVoiceEchoButton" && audioLoopbackRoot(item)) { return "audio.live-echo"; }
    if (click && item->property("labelTextOn").toString() == "Mute microphone"
            && item->property("checked").userType() == QMetaType::Bool) { return "audio.mute"; }
    if (click && item->inherits("QQuickTabButton")) {
        if (item->property("text").toString() == "Desktop") { return "audio.mode.desktop"; }
        if (item->property("text").toString() == "VR") { return "audio.mode.vr"; }
    }
    if (item->inherits("QQuickScrollBar") && item->property("orientation").toInt() == Qt::Vertical
            && item->parentItem() == audioPage(item)) { return "audio.scrollbar"; }
    if (click && name == "nav.back") { return "audio.back"; }
    return {};
}

inline QVariantMap audioRecordedStatus(QQuickItem* loopback) {
#if defined(OVERTE_E2E_FEATURE_TESTS)
    auto value = loopback ? loopback->property("recordedStatus") : QVariant();
    if (value.userType() == qMetaTypeId<QJSValue>()) { value = value.value<QJSValue>().toVariant(); }
    return value.toMap();
#else
    Q_UNUSED(loopback)
    return {};
#endif
}

inline void appendAudioControlObservation(QJsonObject& row, QQuickItem* item, const QString& id, const AudioUiContext& context) {
    if (!audioGuiItem(item)) { return; }
    const auto page = audioPage(item);
    const auto mode = audioSelectedMode(page);
    const bool modeReady = page && mode == (context.hmd ? 1 : 0) && page->property("isVR").toBool() == context.hmd;
    bool inputReady = context.valid && item->isEnabled() && id != "audio.page";
    if (id == "audio.page") {
        row["mode"] = mode; row["nativeHmd"] = context.hmd; row["uiHmd"] = page->property("isVR").toBool();
        row["cycle"] = static_cast<double>(context.cycle);
    } else if (id == "audio.record" || id == "audio.live-echo") {
        const auto loopback = audioLoopbackRoot(item);
        const bool uiActive = loopback && loopback->property("recordingActive").toBool();
        const bool requested = loopback && loopback->property("recordingRequested").toBool();
        row["cycle"] = static_cast<double>(context.cycle);
        row["nativeActive"] = context.active; row["uiActive"] = uiActive; row["requested"] = requested;
        const auto phase = audioRecordedStatus(loopback).value("phase").toString();
        const bool phaseKnown = QStringList{"idle", "capturing", "playing", "draining", "completed", "cancelled", "error"}.contains(phase);
        inputReady = inputReady && phaseKnown;
        if (id == "audio.record") {
            row["phase"] = phase;
            row["label"] = item->property("text").toString();
            inputReady = inputReady && modeReady && context.active == uiActive && !requested;
        } else {
            const bool echo = loopback && loopback->property("audioLoopedBack").toBool();
            row["checked"] = echo; row["nativeEcho"] = context.echo;
            inputReady = inputReady && modeReady && !context.active && !uiActive && !requested && echo == context.echo;
        }
    } else if (id == "audio.mute") {
        const bool checked = item->property("checked").toBool();
        row["checked"] = checked; row["nativeMuted"] = context.muted; row["mode"] = mode;
        inputReady = inputReady && modeReady && checked == context.muted;
    } else if (id == "audio.mode.desktop" || id == "audio.mode.vr") {
        row["checked"] = item->property("checked").toBool(); row["nativeHmd"] = context.hmd;
        // This closed fixture changes only the actual current audio context.
        inputReady = inputReady && ((id == "audio.mode.vr") == context.hmd);
    } else if (id == "audio.scrollbar") {
        row["position"] = item->property("position").toDouble();
        row["size"] = item->property("size").toDouble();
    }
    row["inputReady"] = inputReady;
}

// A normal scrollbar groove press uses actual thumb geometry. This does not
// set ScrollBar.position/Flickable.contentY or dispatch wheel events over gain
// sliders. Return a scene point only when the requested side has real space.
inline bool audioScrollPoint(QQuickItem* item, const QString& direction, QPointF& point) {
    if (audioControlId(item) != "audio.scrollbar" || (direction != "up" && direction != "down")) { return false; }
    auto thumb = qobject_cast<QQuickItem*>(item->property("contentItem").value<QObject*>());
    if (!thumb || thumb->parentItem() != item || !thumb->isVisible() || !item->isEnabled()) { return false; }
    const auto rect = thumb->mapRectToItem(item, QRectF(0, 0, thumb->width(), thumb->height()));
    if (!std::isfinite(rect.top()) || !std::isfinite(rect.bottom()) || rect.top() < 0 || rect.bottom() > item->height()) { return false; }
    const double low = direction == "up" ? 0 : rect.bottom();
    const double high = direction == "up" ? rect.top() : item->height();
    if (high - low < 2) { return false; }
    point = item->mapToScene(QPointF(item->width()/2, (low+high)/2));
    return std::isfinite(point.x()) && std::isfinite(point.y());
}

inline QString audioControlSource(QQuickItem* item, const QString& id, const AudioUiContext& context) {
    if (!audioGuiItem(item)) { return {}; }
    QJsonObject source{{"cycle", static_cast<double>(context.cycle)}, {"active", context.active},
        {"hmd", context.hmd}, {"mode", audioSelectedMode(audioPage(item))}};
    if (id == "audio.record") {
        const auto loopback = audioLoopbackRoot(item);
        source["uiActive"] = loopback && loopback->property("recordingActive").toBool();
        source["requested"] = loopback && loopback->property("recordingRequested").toBool();
    } else if (id == "audio.mute" || id.startsWith("audio.mode.")) { source["checked"] = item->property("checked").toBool(); }
    else if (id == "audio.live-echo") {
        source["echo"] = context.echo;
        const auto loopback = audioLoopbackRoot(item);
        source["uiEcho"] = loopback && loopback->property("audioLoopedBack").toBool();
    } else if (id == "audio.scrollbar") {
        source["position"] = item->property("position").toDouble(); source["size"] = item->property("size").toDouble();
    }
    return QString::fromUtf8(QJsonDocument(source).toJson(QJsonDocument::Compact));
}
} // namespace overte::e2e
