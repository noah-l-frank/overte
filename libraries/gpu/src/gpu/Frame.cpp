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
#include <QMutex>
#include <QMutexLocker>
#include <QBuffer>
#include <QJsonDocument>
#include <QJsonObject>


namespace {
QMutex snapshotSceneMutex;
QVariantMap snapshotSceneLatest;
QVariantMap snapshotActorPixelLatest;
QString snapshotActorPixelAttempt;
// Strong copy of the actual consumed input map, before adding output metadata.
// Qt map copy-on-write preserves these originals if the Frame later mutates.
QVariantMap snapshotActorConsumedInputs;
QString snapshotActorInvalidatedFrame;
quint32 snapshotActorGreatestIndex {0};
QString snapshotActorGreatestIdentity;
bool snapshotActorHeadRejected {false};
// A real uint32 producer wrap or regressed presentation cannot open a new
// generation in this process. No unbounded identity history is retained.
bool snapshotActorIndexRegressed {false};
void invalidateActorInputs(const QString& identity) {
    // Caller holds snapshotSceneMutex. A rejected identity cannot be retried or
    // re-anchored by restoring its map; only a distinct recorded frame advances.
    snapshotActorHeadRejected=true;
    snapshotActorInvalidatedFrame=identity;
    snapshotActorPixelAttempt=identity;
    snapshotActorConsumedInputs.clear();
    snapshotSceneLatest.clear();snapshotActorPixelLatest.clear();
}
}
bool FeatureSnapshotProvenance::actorPixelsEnabled() {
    return sceneEnabled() && QCoreApplication::arguments().contains("--testSnapshotActorPixels");
}
bool FeatureSnapshotProvenance::beginActorPixelReadback(const QVariantMap& held,quint32 index,bool mono) {
    if (!actorPixelsEnabled()) {return false;}
    QMutexLocker lock(&snapshotSceneMutex);
    const auto identity=held.value("frameInstance").toString();
    // A later unsupported frame invalidates the old pixel slot. No old PNG
    // is returned as if it belonged to the newest scene/camera observation.
    if (index==0 || index<snapshotActorGreatestIndex) {snapshotActorIndexRegressed=true;}
    if (snapshotActorIndexRegressed || snapshotActorHeadRejected
            || index!=snapshotActorGreatestIndex || identity!=snapshotActorGreatestIdentity
            || snapshotActorInvalidatedFrame==identity || identity.isEmpty() || !mono || held.value("frameIndex").toULongLong()!=index
            || held.value("processId").toLongLong()!=QCoreApplication::applicationPid()
            || snapshotSceneLatest.value("frameInstance")!=identity
            || snapshotSceneLatest.value("frameIndex").toULongLong()!=index
            || snapshotActorConsumedInputs!=held) {
        invalidateActorInputs(identity);return false;
    }
    if (snapshotActorPixelAttempt==identity) {return false;}
    snapshotActorPixelAttempt=identity;snapshotActorPixelLatest.clear();
    const auto scene=held.value("scene").toMap();
    return scene.value("complete").toBool() && !scene.value("entities").toList().isEmpty();
}
QVariantMap FeatureSnapshotProvenance::actorPixelReadback(const QImage& callbackImage) {
    if (!actorPixelsEnabled()) {return {};}
    const auto originalFrame=original(callbackImage);
    if (originalFrame.isEmpty() || originalFrame.value("snapshotFrameProvenanceVersion").toInt()!=2) {return {};}
    QVariantMap scene;
    {
        QMutexLocker lock(&snapshotSceneMutex);
        if (snapshotActorPixelAttempt!=originalFrame.value("frameInstance").toString()
                || snapshotSceneLatest.value("frameInstance")!=originalFrame.value("frameInstance")) {return {};}
        scene=snapshotSceneLatest;
    }
    auto base=originalFrame;base.remove("readback");base.remove("callbackEpochMs");
    auto consumed=scene;consumed.remove("consumedEpochMs");
    if (base!=consumed) {return {};}
    // This is the FIRST PNG encoding of this actual callback image. No resize,
    // requested expected pixels, old PNG recompression or replacement read.
    QByteArray encoded;QBuffer buffer(&encoded);
    if (!buffer.open(QIODevice::WriteOnly) || !callbackImage.save(&buffer,"PNG")
            || encoded.isEmpty() || encoded.size()>64*1024) {return {};}
    buffer.close();
    auto frame=originalFrame;frame["consumedEpochMs"]=scene.value("consumedEpochMs");
    QVariantMap frameBinding;
    for (const auto& key:QStringList{"frameInstance","frameIndex","processId","camera","worldFromCamera","viewport","transformSlot"}) {
        frameBinding.insert(key,originalFrame.value(key));
    }
    const auto hash=QCryptographicHash::hash(encoded,QCryptographicHash::Sha256).toHex();
    QVariantMap result {{"complete",true},{"frame",frame},
        {"png",QVariantMap{{"format","png"},{"encoding","base64"},{"bytes",encoded.size()},
            {"sha256",QString::fromLatin1(hash)},{"data",QString::fromLatin1(encoded.toBase64())},{"frameBinding",frameBinding}}},
        {"resource",QVariantMap{{"profile","single-latest-actor-frame-v1"},
            {"callbackScopeRetired",false},{"retainedQImage",false},{"nativeSlotProcessLifetime",true}}}};
    if (QJsonDocument(QJsonObject::fromVariantMap(result)).toJson(QJsonDocument::Compact).size()>240*1024) {return {};}
    return result;
}
void FeatureSnapshotProvenance::commitActorPixelReadback(const QVariantMap& record) {
    if (!actorPixelsEnabled()) {return;}
    QMutexLocker lock(&snapshotSceneMutex);
    // The ordinary consumer calls this only AFTER its exact local Scope and
    // local QImage are destroyed. A reentrant or changed-frame read refuses.
    if (current()!=nullptr || record.isEmpty()) {snapshotActorPixelLatest.clear();return;}
    auto value=record;const auto frame=value.value("frame").toMap();
    auto base=frame;base.remove("readback");base.remove("callbackEpochMs");
    if (frame.value("frameInstance").toString()!=snapshotActorPixelAttempt || base!=snapshotSceneLatest) {
        snapshotActorPixelLatest.clear();return;
    }
    auto resource=value.value("resource").toMap();resource["callbackScopeRetired"]=true;value["resource"]=resource;
    snapshotActorPixelLatest=value;
}
QVariantMap FeatureSnapshotProvenance::actorPixelOriginal() {
    if (!actorPixelsEnabled()) {return {};}
    QMutexLocker lock(&snapshotSceneMutex);
    if (snapshotActorPixelLatest.isEmpty()) {return {};}
    auto base=snapshotActorPixelLatest.value("frame").toMap();base.remove("readback");base.remove("callbackEpochMs");
    if (base!=snapshotSceneLatest) {return {};}
    return snapshotActorPixelLatest;
}

bool FeatureSnapshotProvenance::sceneEnabled() {
    return enabled() && QCoreApplication::arguments().contains("--testSnapshotSceneInputs");
}
void FeatureSnapshotProvenance::entityInput(QVariantMap& frame,const QVariantMap& actual,bool returned) {
    if (!sceneEnabled() || frame.isEmpty()) {return;}
    auto scene=frame.value("scene").toMap();
    if (!scene.value("complete").toBool()) {return;}
    auto rows=scene.value("entities").toList();int found=-1;
    for (int i=0;i<rows.size();++i) {if (rows[i].toMap().value("entityId")==actual.value("entityId")) {found=i;break;}}
    if (found<0) {
        if (returned || rows.size()>=256) {scene["complete"]=false;frame["scene"]=scene;return;}
        auto row=actual;row["entered"]=0;row["returned"]=0;rows.append(row);found=rows.size()-1;
    }
    auto row=rows[found].toMap(),inputs=row;inputs.remove("entered");inputs.remove("returned");
    if (inputs!=actual || (returned && row.value("entered").toInt()<=row.value("returned").toInt())) {
        scene["complete"]=false;
    } else {const QString key=returned ? "returned" : "entered";row[key]=row.value(key).toInt()+1;rows[found]=row;}
    scene["entities"]=rows;frame["scene"]=scene;
}
void FeatureSnapshotProvenance::consumedScene(const QVariantMap& original,quint32 index,bool mono) {
    if (!sceneEnabled() || !mono || original.value("frameIndex").toULongLong()!=index
            || original.value("processId").toLongLong()!=QCoreApplication::applicationPid()) {return;}
    auto value=original;const auto scene=value.value("scene").toMap();
    // Copy at the actual execute/composite consumer. Re-presenting the same
    // frame keeps its original timestamp; a query cannot make it fresh again.
    QMutexLocker lock(&snapshotSceneMutex);
    const auto identity=original.value("frameInstance").toString();
    if (actorPixelsEnabled()) {
        if (index==0 || index<snapshotActorGreatestIndex) {snapshotActorIndexRegressed=true;}
        if (snapshotActorIndexRegressed) {invalidateActorInputs(identity);return;}
        if (index==snapshotActorGreatestIndex
                && (identity!=snapshotActorGreatestIdentity || snapshotActorHeadRejected)) {
            invalidateActorInputs(identity);return;
        }
        if (index>snapshotActorGreatestIndex) {
            snapshotActorGreatestIndex=index;snapshotActorGreatestIdentity=identity;
            snapshotActorHeadRejected=false;
        }
        if (snapshotActorInvalidatedFrame==identity) {invalidateActorInputs(identity);return;}
        if (snapshotSceneLatest.value("frameInstance")==identity) {
            // Compare ALL actual input fields before the duplicate early return.
            // In particular no camera/scene/backend/clock field is projected out.
            if (snapshotActorConsumedInputs!=original) {invalidateActorInputs(identity);}
            return;
        }
    }
    if (scene.isEmpty()) {return;}
    if (snapshotSceneLatest.value("frameInstance")==value.value("frameInstance")) {return;}
    if (actorPixelsEnabled()) {
        snapshotActorInvalidatedFrame.clear();snapshotActorConsumedInputs=original;
    }
    value.remove("readback");value.remove("callbackEpochMs");
    value["backend"]="opengl";value["consumedEpochMs"]=QDateTime::currentMSecsSinceEpoch();
    snapshotSceneLatest=value;
}
QVariantMap FeatureSnapshotProvenance::sceneOriginal() {
    if (!sceneEnabled()) {return {};}
    QMutexLocker lock(&snapshotSceneMutex);return snapshotSceneLatest;
}

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
