// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include "Backend.h"
#include <QDateTime>
#include <QVariantMap>
#include <QUuid>
#include <memory>
#include <utility>

namespace gpu {
// Original issued Vulkan API commands, rather than requested settings or the
// number of draw opcodes in a CPU batch. Completion is qualified separately by
// the original frame fence; original visible effect pixels remain mandatory.
class FeatureCompletedDrawTrace {
public:
    FeatureCompletedDrawTrace(const QVariantMap& view,std::shared_ptr<void> lifetime) : _lifetime(std::move(lifetime)),_view(view) {}
    void begin(Backend* backend) {
        quint64 sequence {0};
        if (_begun || !current(backend,sequence)) { return; }
        _backend=backend;_begun=_completed=now();_lastSequence=sequence;
    }
    void before(Backend* backend) {
        quint64 sequence {0};
        if (!_valid || !_begun || _batch || backend!=_backend || !current(backend,sequence)
                || sequence<_lastSequence) { _valid=false;return; }
        _batch=true;_before=sequence;
    }
    void after(Backend* backend,bool mirror,bool haze) {
        quint64 sequence {0};
        if (!_valid || !_batch || backend!=_backend || !current(backend,sequence)
                || sequence<_before) { _valid=false;return; }
        const auto draws=sequence-_before;
        if (draws) {
            if (mirror) { ++_mirrorBatches;_mirrorDraws+=draws; }
            else { ++_forwardBatches;_forwardDraws+=draws;if (haze) { ++_hazeBatches;_hazeDraws+=draws; } }
        }
        _batch=false;_lastSequence=sequence;_completed=now();
    }
    QVariantMap snapshot(Backend* backend) const {
        quint64 sequence {0};
        if (!_valid || !_begun || _batch || backend!=_backend || !current(backend,sequence)
                || sequence<_lastSequence) { return {}; }
        return {{"completedDrawTraceVersion",1},{"frameId",_id},{"recordedEpochMs",_recorded},
            {"recordedView",_view},{"begunEpochMs",_begun},{"completedEpochMs",_completed},
            {"drawSource","vulkan-api-issued"},{"renderer","forward"},{"view","main-mono"},
            {"forwardBatches",_forwardBatches},{"forwardDrawCalls",_forwardDraws},
            {"hazeBatches",_hazeBatches},{"hazeDrawCalls",_hazeDraws},
            {"mirrorBatches",_mirrorBatches},{"mirrorDrawCalls",_mirrorDraws}};
    }
private:
    static qint64 now() { return QDateTime::currentMSecsSinceEpoch(); }
    static bool current(Backend* backend,quint64& sequence) {
        return backend && backend==Backend::featureExecutingBackend() && backend->featureIssuedDraws(sequence);
    }
    // Declared first so this is released last, after original trace metadata.
    // Every retained draw callback and Args copy therefore retains the actual
    // capture group, even when its original gpu::Frame has already died.
    std::shared_ptr<void> _lifetime;
    QVariantMap _view;
    QString _id=QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');
    qint64 _recorded {now()},_begun {0},_completed {0};Backend* _backend {nullptr};
    bool _valid {true},_batch {false};quint64 _before {0},_lastSequence {0};
    qulonglong _forwardBatches {0},_forwardDraws {0},_hazeBatches {0},_hazeDraws {0},_mirrorBatches {0},_mirrorDraws {0};
};
} // namespace gpu
#endif
