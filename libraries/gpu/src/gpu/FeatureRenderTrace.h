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
#include <cmath>

namespace gpu {
// One primary stereo forward view, retained by that view's original GPU commands.
// Only Present-thread callbacks write execution facts. This is draw-batch
// provenance, not proof that a particular fragment was shaded or visible.
class FeatureRenderTrace {
public:
    explicit FeatureRenderTrace(const QVariantMap& view) :
        _id(QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')), _recorded(now()), _view(view) {}

    void begin(Backend* backend) {
        const auto frame=backend ? backend->featureFrame() : nullptr;
        if (backend && backend == Backend::featureExecutingBackend() && frame && frame->stereo.isStereo() && !_begun) {
            _backend=backend;_frame=frame->index;_execution=frame->execution;_begun=_completed=now();
        }
    }

    qint64 recordedEpochMs() const { return _recorded; }

    void batch(Backend* backend, const Batch* original, bool mirror, bool haze) {
        if (!sameFrame(backend) || !original) { return; }
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
            observeCameras(backend,original,mirror,draws);
        }
        _completed = now();
    }

    QVariantMap snapshot(Backend* backend) const {
        if (!sameFrame(backend) || !_camerasComplete || _cameraBatches.isEmpty()) { return {}; }
        return {{"traceVersion",4},{"frameId",_id},{"frameIndex",_frame},{"executionSequence",static_cast<qulonglong>(_execution)},
            {"recordedEpochMs",_recorded},{"recordedView",_view},{"cameraBatches",_cameraBatches},
            {"begunEpochMs",_begun},{"completedEpochMs",_completed},{"renderer","forward"},{"view","main-stereo"},
            {"forwardBatches",_forwardBatches},{"forwardDrawCommands",_forwardDraws},
            {"hazeBatches",_hazeBatches},{"hazeDrawCommands",_hazeDraws},
            {"mirrorBatches",_mirrorBatches},{"mirrorDrawCommands",_mirrorDraws}};
    }
private:
    void observeCameras(Backend* backend,const Batch* original,bool mirror,quint64 draws) {
        Backend::FeatureBatchCameras originalCameras;
        if (!backend->featureExecutedBatchCameras(original,originalCameras) || !originalCameras.complete
                || originalCameras.frame!=_frame || originalCameras.execution!=_execution
                || originalCameras.rawDraws!=draws || !originalCameras.executedDraws || originalCameras.cameras.empty()
                || _cameraBatches.size()>=128) { _camerasComplete=false; }
        else {
            QVariantList cameras;
            for (const auto& camera:originalCameras.cameras) {
                if (++_cameraRowCount>128) { _camerasComplete=false;break; }
                const auto view=matrix(camera.view),projection=matrix(camera.projection);
                if (view.isEmpty() || projection.isEmpty()) { _camerasComplete=false;break; }
                cameras.append(QVariantMap{{"slot",camera.slot},{"eye",camera.eye ? "right" : "left"},
                    {"view",view},{"projection",projection},
                    {"viewport",QVariantList{camera.viewport.x,camera.viewport.y,camera.viewport.z,camera.viewport.w}},
                    {"drawViewport",QVariantList{camera.drawViewport.x,camera.drawViewport.y,camera.drawViewport.z,camera.drawViewport.w}},
                    {"stereoInfo",QVariantList{camera.stereoInfo.x,camera.stereoInfo.y,camera.stereoInfo.z,camera.stereoInfo.w}},
                    {"drawCommands",static_cast<qulonglong>(camera.draws)}});
            }
            _cameraBatches.append(QVariantMap{{"sequence",static_cast<qulonglong>(originalCameras.sequence)},{"role",mirror ? "mirror" : "forward"},
                {"frameIndex",originalCameras.frame},{"executionSequence",static_cast<qulonglong>(originalCameras.execution)},
                {"rawDrawCommands",static_cast<qulonglong>(originalCameras.rawDraws)},
                {"executedDrawCommands",static_cast<qulonglong>(originalCameras.executedDraws)},
                {"technique",originalCameras.instanced ? "instanced" : "doubled"},{"cameras",cameras}});
        }
    }
    bool sameFrame(Backend* backend) const {
        const auto frame=backend ? backend->featureFrame() : nullptr;
        return _begun && backend && backend==_backend && backend==Backend::featureExecutingBackend()
            && frame && frame->stereo.isStereo() && frame->index==_frame && frame->execution==_execution;
    }
    static QVariantList matrix(const Mat4& value) {
        QVariantList result;
        for (int column=0;column<4;++column) { for (int row=0;row<4;++row) {
            if (!std::isfinite(value[column][row])) { return {}; }
            result.append(static_cast<double>(value[column][row]));
        } }
        return result;
    }
    static qint64 now() { return QDateTime::currentMSecsSinceEpoch(); }
    const QString _id;
    const qint64 _recorded;
    const QVariantMap _view;
    Backend* _backend {nullptr};
    bool _camerasComplete {true};
    QVariantList _cameraBatches;
    uint32_t _cameraRowCount {0};
    uint32_t _frame {0};
    uint64_t _execution {0};
    qint64 _begun {0}, _completed {0};
    qulonglong _forwardBatches {0}, _forwardDraws {0}, _hazeBatches {0}, _hazeDraws {0}, _mirrorBatches {0}, _mirrorDraws {0};
};
}
#endif
