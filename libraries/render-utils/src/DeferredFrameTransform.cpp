//
//  DeferredFrameTransform.cpp
//  libraries/render-utils/src/
//
//  Created by Sam Gateau 6/3/2016.
//  Copyright 2016 High Fidelity, Inc.
//  Copyright 2024 Overte e.V.
//
//  Distributed under the Apache License, Version 2.0.
//  See the accompanying file LICENSE or http://www.apache.org/licenses/LICENSE-2.0.html
//
#include "DeferredFrameTransform.h"

#include "gpu/Context.h"
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include <gpu/FeatureSnapshotProvenance.h>
#include <QDateTime>
#include <QCoreApplication>
#include <QUuid>
#endif
#include "render/Engine.h"

DeferredFrameTransform::DeferredFrameTransform() {
    FrameTransform frameTransform;
    _frameTransformBuffer = gpu::BufferView(std::make_shared<gpu::Buffer>(gpu::Buffer::UniformBuffer, sizeof(FrameTransform), (const gpu::Byte*) &frameTransform));
}

void DeferredFrameTransform::update(RenderArgs* args) {

    // Update the depth info with near and far (same for stereo)
    auto nearZ = args->getViewFrustum().getNearClip();
    auto farZ = args->getViewFrustum().getFarClip();

    auto& frameTransformBuffer = _frameTransformBuffer.edit<FrameTransform>();
    frameTransformBuffer.infos.depthInfo = glm::vec4(nearZ * farZ, farZ - nearZ, -farZ, 0.0f);
    frameTransformBuffer.infos.pixelInfo = args->_viewport;

    args->getViewFrustum().evalProjectionMatrix(frameTransformBuffer.infos.projectionMono);

    // Running in stereo ?
    bool isStereo = args->isStereo();
    if (!isStereo) {
        frameTransformBuffer.infos.stereoInfo = glm::vec4(0.0f, (float)args->_viewport.z, 0.0f, 0.0f);
        frameTransformBuffer.infos.invPixelInfo = glm::vec4(1.0f / args->_viewport.z, 1.0f / args->_viewport.w, 0.0f, 0.0f);
    } else {
        frameTransformBuffer.infos.pixelInfo.z *= 0.5f;
        frameTransformBuffer.infos.stereoInfo = glm::vec4(1.0f, (float)(args->_viewport.z >> 1), 0.0f, 1.0f);
        frameTransformBuffer.infos.invPixelInfo = glm::vec4(2.0f / (float)(args->_viewport.z), 1.0f / args->_viewport.w, 0.0f, 0.0f);
    }
}

void GenerateDeferredFrameTransform::run(const render::RenderContextPointer& renderContext, Output& frameTransform) {
    if (!frameTransform) {
        frameTransform = std::make_shared<DeferredFrameTransform>();
    }

    RenderArgs* args = renderContext->args;
    frameTransform->update(args);

    gpu::doInBatch("GenerateDeferredFrameTransform::run", args->_context, [&](gpu::Batch& batch) {
        args->_batch = &batch;

        glm::mat4 projMat;
        Transform viewMat;
        args->getViewFrustum().evalProjectionMatrix(projMat);
        args->getViewFrustum().evalViewTransform(viewMat);
        batch.setProjectionTransform(projMat);
        batch.setViewTransform(viewMat);
        // This is the main view / projection transform that will be reused later on
        batch.saveViewProjectionTransform(_transformSlot);
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
        if (gpu::FeatureSnapshotProvenance::enabled() && args->_takingSnapshot && args->_mirrorDepth==0
                && args->_renderMode==RenderArgs::DEFAULT_RENDER_MODE && args->_renderMethod==RenderArgs::FORWARD
                && !args->isStereo()) {
            // These are the SAME actual matrix locals just handed to the
            // ordinary batch's main saved projection/view transform slot.
            const auto& view=args->getViewFrustum();const auto& position=view.getPosition();const auto& rotation=view.getOrientation();
            const auto viewMatrix=viewMat.getMatrix();QVariantList projection,worldFromCamera;
            for (int row=0;row<4;++row) {for (int column=0;column<4;++column) {
                projection.append(projMat[column][row]);worldFromCamera.append(viewMatrix[column][row]);
            }}
            args->_featureSnapshotProvenance={{"snapshotFrameProvenanceVersion",1},
                {"frameInstance",QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')},
                {"processId",QCoreApplication::applicationPid()},{"pipeline","forward-primary-mono"},
                {"recordedEpochMs",QDateTime::currentMSecsSinceEpoch()},
                {"transformSlot",static_cast<qulonglong>(_transformSlot)},
                {"viewport",QVariantList{args->_viewport.x,args->_viewport.y,args->_viewport.z,args->_viewport.w}},
                {"worldFromCamera",worldFromCamera},{"camera",QVariantMap{
                    {"position",QVariantList{position.x,position.y,position.z}},
                    {"rotation",QVariantList{rotation.x,rotation.y,rotation.z,rotation.w}},
                    {"projection",projection},{"fieldOfViewDegrees",view.getFieldOfView()},
                    {"aspectRatio",view.getAspectRatio()},{"nearClip",view.getNearClip()},
                    {"farClip",view.getFarClip()},{"perspective",view.isPerspective()}}}};
        }
#endif

        // Copy it to the deferred transform for the lighting pass
        batch.copySavedViewProjectionTransformToBuffer(_transformSlot, frameTransform->getFrameTransformBuffer()._buffer,
                                                       sizeof(DeferredFrameTransform::DeferredFrameInfo));
    });
}
