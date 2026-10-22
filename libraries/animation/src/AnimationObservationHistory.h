// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include <QVariantMap>
#include <QVariantList>
#include <QCoreApplication>
#include <QDateTime>
#include <cmath>
#include <algorithm>
#include <memory>
#include <QUuid>

namespace overte::e2e {
// Owned by one actual Rig and protected by its existing observation lock.
// These are native call/pose histories, never UI intent or inferred cause.
class AnimationObservationHistory {
public:
    void overrideCalled(const QString& url, float fps, bool loop, float first, float last, const QVariantMap& caller = {}) {
        if (!enabled()) { return; }
        ++_override;
        QVariantMap request {{"url",url},{"framesPerSecond",fps},{"loop",loop},{"firstFrame",first},{"lastFrame",last}};
        appendEvent("override",QDateTime::currentMSecsSinceEpoch(),request,caller);
    }
    void restoreCalled(const QVariantMap& caller = {}) {
        if (enabled()) { appendEvent("restore",QDateTime::currentMSecsSinceEpoch(),{},caller); }
    }
    void evaluated(const QVariantMap& original, float delta, const std::weak_ptr<const void>& graph,
            const std::weak_ptr<const void>& skeleton) {
        if (!enabled() || !(delta > 0.0f) || !std::isfinite(delta)
                || !original.value("graphLoaded").toBool() || !original.value("animationsEnabled").toBool()
                || !original.value("evaluationSequence").toULongLong()) { return; }
        if (_identitySeen && (_graph.owner_before(graph) || graph.owner_before(_graph)
                || _skeleton.owner_before(skeleton) || skeleton.owner_before(_skeleton))) {
            // A different graph/skeleton cannot borrow an old avatar's history.
            // Weak control-block identity prevents address reuse without keeping
            // obsolete animation/resource graphs alive for instrumentation.
            *this = AnimationObservationHistory();
        }
        _graph = graph; _skeleton = skeleton; _identitySeen = true;
        const auto epoch = original.value("capturedEpochMs").toLongLong();
        if (!_frames.isEmpty()) {
            const auto previous = _frames.last().toMap();
            if (original.value("evaluationSequence").toULongLong() <= previous.value("evaluationSequence").toULongLong()) { return; }
            if (epoch < previous.value("capturedEpochMs").toLongLong()) { _valid = false; return; }
            if (epoch-previous.value("capturedEpochMs").toLongLong() < 75
                    && _override == previous.value("overrideSequence").toULongLong()
                    && original.value("overrideActive") == previous.value("overrideActive")) { return; }
        }
        QVariantList sampled;
        const auto joints = original.value("joints").toList();
        const int count = static_cast<int>(std::min<qsizetype>(32,joints.size()));
        for (int sample = 0; sample < count; ++sample) {
            const int index = sample*joints.size()/count;
            sampled.append(QVariantMap{{"index",index},{"pose",joints[index]}});
        }
        QVariantMap frame {{"frameSequence",static_cast<qulonglong>(++_framesSequence)},
            {"overrideSequence",static_cast<qulonglong>(_override)},
            {"evaluationSequence",original.value("evaluationSequence")},{"capturedEpochMs",epoch},
            {"overrideActive",original.value("overrideActive")},{"joints",sampled}};
        if (original.contains("clip")) { frame.insert("clip",original.value("clip")); }
        _frames.append(frame);
        if (_frames.size() > 32) { _frames.removeFirst(); ++_droppedFrames; }
    }
    QVariantMap snapshot() const {
        return {{"historyVersion",2},{"instance",_instance},{"available",_valid}, {"callSequence",static_cast<qulonglong>(_calls)},
            {"overrideSequence",static_cast<qulonglong>(_override)},{"frameSequence",static_cast<qulonglong>(_framesSequence)},
            {"droppedEvents",static_cast<qulonglong>(_droppedEvents)}, {"droppedFrames",static_cast<qulonglong>(_droppedFrames)},
            {"events",_events},{"frames",_frames}};
    }
private:
    static bool enabled() { return QCoreApplication::arguments().contains("--testScript"); }
    void appendEvent(const QString& kind, qint64 epoch, const QVariantMap& request, const QVariantMap& caller) {
        if (!_events.isEmpty() && epoch < _events.last().toMap().value("capturedEpochMs").toLongLong()) { _valid = false; }
        QVariantMap event {{"eventSequence",static_cast<qulonglong>(++_calls)}, {"kind",kind},
            {"overrideSequence",static_cast<qulonglong>(_override)}, {"capturedEpochMs",epoch}};
        event.insert("caller",caller.isEmpty() ? QVariant() : QVariant(caller));
        if (kind == "override") { event.insert("request",request); }
        _events.append(event);
        if (_events.size() > 64) { _events.removeFirst(); ++_droppedEvents; }
    }
    bool _valid {true};
    QString _instance {QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')};
    bool _identitySeen {false};
    std::weak_ptr<const void> _graph, _skeleton;
    quint64 _calls {0}, _override {0}, _framesSequence {0}, _droppedEvents {0}, _droppedFrames {0};
    QVariantList _events, _frames;
};
}
#endif
