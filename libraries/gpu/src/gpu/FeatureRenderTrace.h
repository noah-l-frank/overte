// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include "Backend.h"
#include "Batch.h"
#include <QDateTime>
#include <QVariantMap>
#include <QUuid>
#include <memory>

namespace gpu {
// One primary forward view, retained by that view's original GPU commands.
// Only Present-thread callbacks write execution facts. This is draw-batch
// provenance, not proof that a particular fragment was shaded or visible.
class FeatureRenderTrace {
public:
    explicit FeatureRenderTrace(const QVariantMap& view) :
        _id(QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')), _recorded(now()), _view(view) {}

    void begin(Backend* backend) {
        if (backend && backend == Backend::featureExecutingBackend() && !_begun) {
            _backend = backend; _begun = _completed = now();
        }
    }

    void batch(Backend* backend, const Batch* original, bool mirror, bool haze) {
        if (!_begun || !backend || backend != _backend || backend != Backend::featureExecutingBackend() || !original) { return; }
        // Named/instanced calls are appended by Frame::finish. Inspect the
        // final original batch here, after its execution, rather than counting
        // CPU items or commands before named calls have been materialized.
        quint64 draws {0};
        for (const auto command : original->getCommands()) {
            if (command >= Batch::COMMAND_draw && command <= Batch::COMMAND_multiDrawIndexedIndirect) { ++draws; }
        }
        if (draws) {
            if (mirror) { ++_mirrorBatches; _mirrorDraws += draws; }
            else {
                ++_forwardBatches; _forwardDraws += draws;
                if (haze) { ++_hazeBatches; _hazeDraws += draws; }
            }
        }
        _completed = now();
    }

    QVariantMap snapshot(Backend* backend) const {
        if (!_begun || !backend || backend != _backend || backend != Backend::featureExecutingBackend()) { return {}; }
        return {{"traceVersion",2},{"frameId",_id},{"recordedEpochMs",_recorded},{"recordedView",_view},
            {"begunEpochMs",_begun},{"completedEpochMs",_completed},{"renderer","forward"},{"view","main-mono"},
            {"forwardBatches",_forwardBatches},{"forwardDrawCommands",_forwardDraws},
            {"hazeBatches",_hazeBatches},{"hazeDrawCommands",_hazeDraws},
            {"mirrorBatches",_mirrorBatches},{"mirrorDrawCommands",_mirrorDraws}};
    }
private:
    static qint64 now() { return QDateTime::currentMSecsSinceEpoch(); }
    const QString _id;
    const qint64 _recorded;
    const QVariantMap _view;
    Backend* _backend {nullptr};
    qint64 _begun {0}, _completed {0};
    qulonglong _forwardBatches {0}, _forwardDraws {0}, _hazeBatches {0}, _hazeDraws {0}, _mirrorBatches {0}, _mirrorDraws {0};
};
}
#endif
