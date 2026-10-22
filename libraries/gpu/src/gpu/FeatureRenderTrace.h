// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include "Backend.h"
#include "Batch.h"
#include <QDateTime>
#include <QVariantMap>
#include <QMap>
#include <QSet>
#include <QRegularExpression>
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
            validateModelCameras(backend,original,mirror);
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

    // Immutable actual mesh-payload facts, acquired only by the lambda directly
    // following its indexed command. This is draw provenance, not visibility.
    void model(Backend* backend,const Batch* batch,size_t commandIndex,const QVariantMap& original) {
        if (!sameFrame(backend) || !_modelsAvailable) { return; }
        Backend::FeatureBatchCameras cameras;
        if (!batch || !backend->featureExecutedDrawCameras(batch,commandIndex,cameras)
                || !cameras.complete || cameras.frame!=_frame || cameras.execution!=_execution
                || !cameras.sequence || cameras.rawDraws!=1 || cameras.executedDraws!=1
                || cameras.cameras.size()!=2 || cameras.cameras[0].eye!=0 || cameras.cameras[1].eye!=1
                || cameras.cameras[0].draws!=1 || cameras.cameras[1].draws!=1) { failModels();return; }
        const auto model=original.value("modelInstance").toString(),geometry=original.value("geometryInstance").toString();
        const auto source=original.value("loadedSourceSha256").toString();
        static const QRegularExpression id("\\A[0-9a-f]{32}\\z"),sha("\\A[0-9a-f]{64}\\z");
        auto low=original.value("minimum").toList(),high=original.value("maximum").toList();
        bool valid=id.match(model).hasMatch() && id.match(geometry).hasMatch() && sha.match(source).hasMatch()
            && low.size()==3 && high.size()==3;
        for (const auto& key:{"loadedSourcePresent","skinned","blendshaped","originalGeometry"}) {
            valid=valid && original.value(key).userType()==QMetaType::Bool;
        }
        for (int axis=0;valid && axis<3;++axis) {
            valid=std::isfinite(low[axis].toDouble()) && std::isfinite(high[axis].toDouble())
                && -1e6<=low[axis].toDouble() && low[axis].toDouble()<=high[axis].toDouble() && high[axis].toDouble()<=1e6;
        }
        const auto indices=original.value("indices").toULongLong();
        const auto draw=QString::number(cameras.sequence)+":"+QString::number(commandIndex);
        const auto key=model+":"+geometry;
        if (!valid || !indices || indices>100000000 || _modelDraws>=4096 || _modelCommands.contains(draw)
                || (!_models.contains(key) && _models.size()>=128)) { failModels();return; }
        auto row=_models.value(key);
        if (row.isEmpty()) {
            row={{"modelInstance",model},{"geometryInstance",geometry},{"loadedSourcePresent",original.value("loadedSourcePresent")},
                {"loadedSourceSha256",source},{"drawCommands",qulonglong(0)},{"skinnedDrawCommands",qulonglong(0)},
                {"blendshapedDrawCommands",qulonglong(0)},{"originalGeometryDrawCommands",qulonglong(0)},
                {"indices",qulonglong(0)},{"minimum",low},{"maximum",high},{"cameraUses",QVariantList()}};
        } else {
            if (row.value("loadedSourcePresent")!=original.value("loadedSourcePresent")
                    || row.value("loadedSourceSha256")!=original.value("loadedSourceSha256")) { failModels();return; }
            const auto previousLow=row.value("minimum").toList(),previousHigh=row.value("maximum").toList();
            for (int axis=0;axis<3;++axis) {
                low[axis]=qMin(low[axis].toDouble(),previousLow[axis].toDouble());
                high[axis]=qMax(high[axis].toDouble(),previousHigh[axis].toDouble());
            }
            row.insert("minimum",low);row.insert("maximum",high);
        }
        auto uses=row.value("cameraUses").toList();
        for (const auto& camera:cameras.cameras) {
            QVariantMap use{{"batchSequence",static_cast<qulonglong>(cameras.sequence)},{"slot",camera.slot},
                {"eye",camera.eye ? "right" : "left"},
                {"drawViewport",QVariantList{camera.drawViewport.x,camera.drawViewport.y,camera.drawViewport.z,camera.drawViewport.w}}};
            bool found=false;
            for (auto& previous:uses) {
                auto value=previous.toMap();const auto count=value.take("drawCommands").toULongLong();
                if (value==use) {use.insert("drawCommands",count+1);previous=use;found=true;break;}
            }
            if (!found) {
                if (++_modelCameraRows>512) {failModels();return;}
                use.insert("drawCommands",qulonglong(1));uses.append(use);
            }
        }
        row.insert("cameraUses",uses);
        row.insert("drawCommands",row.value("drawCommands").toULongLong()+1);
        row.insert("indices",row.value("indices").toULongLong()+indices);
        row.insert("skinnedDrawCommands",row.value("skinnedDrawCommands").toULongLong()+(original.value("skinned").toBool()?1:0));
        row.insert("blendshapedDrawCommands",row.value("blendshapedDrawCommands").toULongLong()+(original.value("blendshaped").toBool()?1:0));
        row.insert("originalGeometryDrawCommands",row.value("originalGeometryDrawCommands").toULongLong()+(original.value("originalGeometry").toBool()?1:0));
        _models.insert(key,row);_modelCommands.insert(draw);++_modelDraws;
        _modelPending.push_back({batch,cameras});_modelCompleted=now();
    }

    // Additive Pico-specific contract; Phone main-mono trace v1 is not relabelled.
    QVariantMap modelSnapshot(Backend* backend) const {
        if (!sameFrame(backend) || !_modelsAvailable || !_modelPending.empty() || _modelValidatedDraws!=_modelDraws
                || !_camerasComplete || _cameraBatches.isEmpty()) { return {}; }
        QVariantList rows;for (auto i=_models.cbegin();i!=_models.cend();++i) {rows.append(i.value());}
        return {{"picoModelTraceVersion",1},{"frameId",_id},{"frameIndex",_frame},{"executionSequence",static_cast<qulonglong>(_execution)},
            {"recordedEpochMs",_recorded},{"begunEpochMs",_begun},{"completedEpochMs",qMax(_begun,_modelCompleted)},
            {"renderer","forward"},{"view","main-stereo"},{"drawCommands",_modelDraws},{"models",rows}};
    }
private:
    void failModels() {_modelsAvailable=false;_models.clear();_modelPending.clear();}
    void validateModelCameras(Backend* backend,const Batch* batch,bool mirror) {
        if (!_modelsAvailable) {return;}
        bool pending=false;for (const auto& proof:_modelPending) {if (proof.batch==batch) {pending=true;break;}}
        if (!pending) {return;}
        Backend::FeatureBatchCameras actual;
        if (mirror || !backend->featureExecutedBatchCameras(batch,actual) || !actual.complete
                || actual.frame!=_frame || actual.execution!=_execution) {failModels();return;}
        std::vector<uint64_t> claims(actual.cameras.size(),0);
        for (const auto& proof:_modelPending) {
            if (proof.batch!=batch) {continue;}
            if (proof.cameras.sequence!=actual.sequence || proof.cameras.instanced!=actual.instanced) {failModels();return;}
            for (const auto& used:proof.cameras.cameras) {
                bool found=false;
                for (size_t i=0;i<actual.cameras.size();++i) {
                    const auto& camera=actual.cameras[i];
                    if (used.slot==camera.slot && used.eye==camera.eye && used.view==camera.view && used.projection==camera.projection
                            && used.viewport==camera.viewport && used.stereoInfo==camera.stereoInfo && used.drawViewport==camera.drawViewport) {
                        if (++claims[i]>camera.draws) {failModels();return;}found=true;break;
                    }
                }
                if (!found) {failModels();return;}
            }
        }
        for (auto i=_modelPending.begin();i!=_modelPending.end();) {
            if (i->batch==batch) {++_modelValidatedDraws;i=_modelPending.erase(i);}else {++i;}
        }
    }
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
    struct ModelProof {const Batch* batch;Backend::FeatureBatchCameras cameras;};
    bool _modelsAvailable {true};
    QMap<QString,QVariantMap> _models;
    QSet<QString> _modelCommands;
    std::vector<ModelProof> _modelPending;
    qulonglong _modelDraws {0},_modelValidatedDraws {0};
    uint32_t _modelCameraRows {0};
    qint64 _modelCompleted {0};
};
}
#endif
