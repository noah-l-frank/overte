// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include "Backend.h"
#include "Batch.h"
#include <QDateTime>
#include <QVariantMap>
#include <QMap>
#include <QUuid>
#include <memory>
#include <cmath>

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

    void model(Backend* backend, const QVariantMap& original) {
        if (!_begun || !backend || backend != _backend || backend != Backend::featureExecutingBackend() || !_modelsAvailable) { return; }
        const auto key = original.value("modelInstance").toString()+":"+original.value("geometryInstance").toString();
        auto low = original.value("minimum").toList(), high = original.value("maximum").toList();
        bool valid = low.size() == 3 && high.size() == 3;
        for (int axis = 0; valid && axis < 3; ++axis) {
            valid = std::isfinite(low[axis].toDouble()) && std::isfinite(high[axis].toDouble())
                && low[axis].toDouble() <= high[axis].toDouble();
        }
        if (!valid || (!_models.contains(key) && _models.size() >= 128) || _modelDraws >= 1000000) {
            _modelsAvailable = false; _models.clear(); return;
        }
        auto row = _models.value(key);
        if (row.isEmpty()) {
            row = {{"modelInstance",original.value("modelInstance")},{"geometryInstance",original.value("geometryInstance")},
                {"loadedSourcePresent",original.value("loadedSourcePresent")},{"loadedSourceSha256",original.value("loadedSourceSha256")},
                {"drawCommands",qulonglong(0)},{"skinnedDrawCommands",qulonglong(0)},
                {"blendshapedDrawCommands",qulonglong(0)},{"originalGeometryDrawCommands",qulonglong(0)},{"indices",qulonglong(0)},
                {"minimum",low},{"maximum",high}};
        } else {
            if (row.value("loadedSourcePresent") != original.value("loadedSourcePresent")
                    || row.value("loadedSourceSha256") != original.value("loadedSourceSha256")) {
                _modelsAvailable = false; _models.clear(); return;
            }
            const auto previousLow = row.value("minimum").toList(), previousHigh = row.value("maximum").toList();
            for (int axis = 0; axis < 3; ++axis) {
                low[axis] = qMin(low[axis].toDouble(),previousLow[axis].toDouble());
                high[axis] = qMax(high[axis].toDouble(),previousHigh[axis].toDouble());
            }
            row.insert("minimum",low); row.insert("maximum",high);
        }
        row.insert("drawCommands",row.value("drawCommands").toULongLong()+1);
        row.insert("skinnedDrawCommands",row.value("skinnedDrawCommands").toULongLong()+(original.value("skinned").toBool() ? 1 : 0));
        row.insert("blendshapedDrawCommands",row.value("blendshapedDrawCommands").toULongLong()+(original.value("blendshaped").toBool() ? 1 : 0));
        row.insert("originalGeometryDrawCommands",row.value("originalGeometryDrawCommands").toULongLong()+(original.value("originalGeometry").toBool() ? 1 : 0));
        row.insert("indices",row.value("indices").toULongLong()+original.value("indices").toULongLong());
        _models.insert(key,row); ++_modelDraws; _modelCompleted = now();
    }

    // Separate additive contract: existing trace v2 consumers stay unchanged.
    QVariantMap modelSnapshot(Backend* backend) const {
        if (!_begun || !backend || backend != _backend || backend != Backend::featureExecutingBackend() || !_modelsAvailable) { return {}; }
        QVariantList rows;
        for (auto i = _models.cbegin(); i != _models.cend(); ++i) { rows.append(i.value()); }
        return {{"modelTraceVersion",1},{"frameId",_id},{"recordedEpochMs",_recorded},
            {"begunEpochMs",_begun},{"completedEpochMs",qMax(_begun,_modelCompleted)},
            {"renderer","forward"},{"view","main-mono"},{"drawCommands",_modelDraws},{"models",rows}};
    }
private:
    static qint64 now() { return QDateTime::currentMSecsSinceEpoch(); }
    const QString _id;
    const qint64 _recorded;
    const QVariantMap _view;
    Backend* _backend {nullptr};
    qint64 _begun {0}, _completed {0};
    qulonglong _forwardBatches {0}, _forwardDraws {0}, _hazeBatches {0}, _hazeDraws {0}, _mirrorBatches {0}, _mirrorDraws {0};
    bool _modelsAvailable {true};
    qint64 _modelCompleted {0};
    qulonglong _modelDraws {0};
    QMap<QString,QVariantMap> _models;
};
}
#endif
