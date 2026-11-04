//
//  Created by Bradley Austin Davis on 2016/07/26
//  Copyright 2013-2016 High Fidelity, Inc.
//
//  Distributed under the Apache License, Version 2.0.
//  See the accompanying file LICENSE or http://www.apache.org/licenses/LICENSE-2.0.html
//

#include "Frame.h"
#include <unordered_set>

using namespace gpu;

Frame::Frame() {
    batches.reserve(16);
}

Frame::~Frame() {
    if (framebuffer && framebufferRecycler) {
        framebufferRecycler(framebuffer);
        framebuffer.reset();
    }

    bufferUpdates.clear();
}

void Frame::finish() {
    PROFILE_RANGE(render_gpu, __FUNCTION__);
    for (const auto& batch : batches) {
        batch->finishFrame(bufferUpdates);
    }
}

void Frame::preRender() {
    PROFILE_RANGE(render_gpu, __FUNCTION__);
    for (auto& update : bufferUpdates) {
        update.apply();
    }
    bufferUpdates.clear();
}

#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include "FeatureSnapshotProvenance.h"
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDateTime>

bool FeatureSnapshotProvenance::enabled() {
    const auto args=QCoreApplication::arguments();
    return args.contains("--testScript") && args.contains("--testSnapshotProvenance");
}
FeatureSnapshotProvenance::Scope*& FeatureSnapshotProvenance::current() {
    static thread_local Scope* value=nullptr;return value;
}
FeatureSnapshotProvenance::Scope::Scope(const QVariantMap& frame,quint32 index,bool mono) : _previous(current()) {
    // Nested/reentrant consumers cannot inherit or replace a parent's readback.
    _valid=enabled() && !_previous && mono && !frame.isEmpty()
        && frame.value("frameIndex").toULongLong()==index
        && frame.value("processId").toLongLong()==QCoreApplication::applicationPid();
    if (_valid) {_frame=frame;_frame.insert("backend","opengl");}
    current()=this;
}
FeatureSnapshotProvenance::Scope::~Scope() {_frame.clear();current()=_previous;}
QByteArray FeatureSnapshotProvenance::pixelHash(const QImage& image) {
    if (image.isNull() || image.width()<=0 || image.height()<=0 || image.width()>8192 || image.height()>8192) {return {};}
    const auto rgba=image.convertToFormat(QImage::Format_RGBA8888);QCryptographicHash digest(QCryptographicHash::Sha256);
    for (int y=0;y<rgba.height();++y) {digest.addData(reinterpret_cast<const char*>(rgba.constScanLine(y)),rgba.width()*4);}
    return digest.result().toHex();
}
void FeatureSnapshotProvenance::readback(int sourceWidth,int sourceHeight,int x,int y,int width,int height,const QImage& bottomUp) {
    auto* scope=current();if (!scope || !scope->_valid) {return;}
    if (scope->_read || sourceWidth<=0 || sourceHeight<=0 || x<0 || y<0 || width<=0 || height<=0
            || x+width>sourceWidth || y+height>sourceHeight || bottomUp.width()!=width || bottomUp.height()!=height) {
        scope->_valid=false;return;
    }
    // Match the ordinary getScreenshot return, including its actual Y mirror.
    const auto hash=pixelHash(bottomUp.mirrored(false,true));
    if (hash.isEmpty()) {scope->_valid=false;return;}
    scope->_frame.insert("readback",QVariantMap{{"sourceExtent",QVariantList{sourceWidth,sourceHeight}},
        {"rectBottomLeft",QVariantList{x,y,width,height}},{"imageExtent",QVariantList{width,height}},
        {"pixelFormat","rgba8-top-left"},{"pixelSha256",QString::fromLatin1(hash)},
        {"readEpochMs",QDateTime::currentMSecsSinceEpoch()}});scope->_read=true;
}
QVariantMap FeatureSnapshotProvenance::original(const QImage& callbackImage) {
    auto* scope=current();if (!scope || !scope->_valid || !scope->_read) {return {};}
    const auto read=scope->_frame.value("readback").toMap();
    if (QString::fromLatin1(pixelHash(callbackImage))!=read.value("pixelSha256").toString()
            || read.value("imageExtent").toList()!=QVariantList{callbackImage.width(),callbackImage.height()}) {return {};}
    auto result=scope->_frame;result.insert("callbackEpochMs",QDateTime::currentMSecsSinceEpoch());return result;
}
#endif
