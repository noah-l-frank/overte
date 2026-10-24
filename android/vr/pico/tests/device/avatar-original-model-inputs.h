// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include "AvatarOriginalModelResource.h"
#include <QFile>
#include <QFileInfo>
#include <QRegularExpression>
#include <QJsonDocument>
#include <hfm/ModelFormatRegistry.h>
// Exact source bytes are read through this declared host HTTP service. It
// never returns a Model, geometry, success flag or rewritten resource URL.
struct AvatarOriginalByteScope {
    QString fixtureBase;
    QHash<QString,QJsonObject> files;
    QJsonArray reads,requests;
    QMutex mutex;
};
inline AvatarOriginalByteScope avatarOriginalByteScope;
QByteArray avatarOriginalBytes(const QString& relative) {
    const auto entry=avatarOriginalByteScope.files.value(relative);if(entry.isEmpty()){qFatal("Unsealed Avatar input");}
    const auto path=entry.value("path").toString();QFile file(path);
    if(QFileInfo(path).isSymLink() || !file.open(QIODevice::ReadOnly)){qFatal("Original Avatar input disappeared");}
    const auto raw=file.read(16*1024*1024+1);
    if(raw.size()!=entry.value("bytes").toInt() || !file.atEnd()
            || QCryptographicHash::hash(raw,QCryptographicHash::Sha256).toHex()!=entry.value("sha256").toString().toLatin1()){
        qFatal("Original Avatar input bytes changed");}
    QMutexLocker lock(&avatarOriginalByteScope.mutex);
    avatarOriginalByteScope.reads.append(QJsonObject{{"relative",relative},{"bytes",raw.size()},
        {"sha256",entry.value("sha256")},{"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()}});
    return raw;
}
void initializeAvatarOriginalInputs() {
    QFile input(qEnvironmentVariable("OVERTE_AVATAR_MODEL_INPUTS"));
    if(!input.open(QIODevice::ReadOnly)){qFatal("Original Avatar source manifest missing");}
    const auto raw=input.read(65537);if(raw.size()>65536 || !input.atEnd()){qFatal("Original Avatar source manifest too large");}
    const auto value=QJsonDocument::fromJson(raw).object();
    if(value.size()!=3 || value.value("avatarOriginalModelInputsVersion")!=QJsonValue(1)
            || !value.value("files").isArray()){qFatal("Original Avatar source manifest invalid");}
    avatarOriginalByteScope.fixtureBase=value.value("fixtureBase").toString();
    if(!QRegularExpression("\\Ahttp://controlled\\.test/feature-fixture/v1/runs/[0-9a-f]{32}/\\z").match(avatarOriginalByteScope.fixtureBase).hasMatch()){
        qFatal("Original Avatar fixture authority invalid");}
    qint64 bytes=0;
    for(const auto& item:value.value("files").toArray()){
        const auto entry=item.toObject();const auto name=entry.value("relative").toString();
        if(entry.size()!=4 || avatarOriginalByteScope.files.contains(name) || name.contains("..") || name.startsWith('/')){
            qFatal("Original Avatar input inventory invalid");}
        bytes+=entry.value("bytes").toInt();if(bytes>16*1024*1024 || avatarOriginalByteScope.files.size()>=512){qFatal("Original Avatar inputs exceed fixed bounds");}
        avatarOriginalByteScope.files.insert(name,entry);avatarOriginalBytes(name);
    }
    DependencyManager::set<ResourceManager>(false);DependencyManager::set<ModelFormatRegistry>();
    DependencyManager::set<ResourceRequestObserver>();DependencyManager::set<ResourceCacheSharedItems>();
    DependencyManager::set<StatTracker>();DependencyManager::set<TextureCache>();DependencyManager::set<ModelCache>();
}
class AvatarOriginalRecordedRequest final:public ResourceRequest {
    QByteArray original;
public:
    AvatarOriginalRecordedRequest(const QUrl& url,const QByteArray& data,bool observable,qint64 caller,const QString& extra):
        ResourceRequest(url,observable,caller,extra),original(data){}
private:
    void doSend()override{QTimer::singleShot(0,this,[this]{_data=original;_result=Success;_state=Finished;
        emit progress(_data.size(),_data.size());emit finished();});}
};
ResourceRequest* avatarOriginalRecordedRequest(QObject* owner,const QUrl& url,bool observable,qint64 caller,const QString& extra){
    const auto full=url.toString(),prefix=avatarOriginalByteScope.fixtureBase+"tickets/";
    if(!full.startsWith(prefix) || url.hasFragment() || url.hasQuery() || !url.userInfo().isEmpty()){
        qFatal("Foreign Avatar input request");}
    const auto tail=full.mid(prefix.size());
    if(!QRegularExpression("\\A[0-9a-f]{32}/").match(tail).hasMatch()){qFatal("Foreign Avatar resource ticket");}
    const auto relative=tail.mid(33);auto request=new AvatarOriginalRecordedRequest(url,avatarOriginalBytes(relative),observable,caller,extra);
    if(owner){QObject::connect(owner,&QObject::destroyed,request,&QObject::deleteLater);}
    QMutexLocker lock(&avatarOriginalByteScope.mutex);avatarOriginalByteScope.requests.append(QJsonObject{
        {"url",full},{"factoryParentArgument",owner!=nullptr},{"actualQObjectParent",request->parent()!=nullptr},
        {"requestOnCallerThread",request->thread()==QThread::currentThread()},{"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()}});
    return request;
}
void observeAssetsMaterialRequest(ResourceRequest*,QObject*,const QUrl&) {
    // The existing original qrc factory remains unchanged. HTTP originals are
    // separately archived above, with no glTF single-request assumptions.
}
QJsonObject avatarOriginalModelSnapshot(const std::shared_ptr<avatar_bookmark_host::MyAvatar>& avatar){
    assert(avatar && avatar->thread()==QThread::currentThread());const auto model=avatar->getSkeletonModel();
    assert(model && model->thread()==QThread::currentThread());const auto geometry=model->getGeometry();
    static QList<QPair<QString,std::weak_ptr<Geometry>>> originals;
    if(geometry){const auto id=geometry->e2eGeometryInstance();bool found=false;
        for(const auto& item:originals){found=found || item.first==id;}
        if(!found){originals.append(qMakePair(id,std::weak_ptr<Geometry>(geometry)));}}
    QJsonArray weak,resources;
    for(const auto& item:originals){weak.append(QJsonObject{{"instance",item.first},{"alive",!item.second.expired()}});}
    for(const auto& original:model->_renderWatcher.originals){resources.append(QJsonObject{{"instance",original.id},{"url",original.url},
        {"qObjectAlive",!original.object.isNull()},{"originalWeakHandleAlive",!original.weak.isNull()}});}
    QJsonValue current;
    if(geometry){current=QJsonObject{{"instance",geometry->e2eGeometryInstance()},
        {"url",geometry->getHFMModel().originalURL},{"hfmLoaded",geometry->isHFMModelLoaded()},
        {"meshes",int(geometry->getHFMModel().meshes.size())},{"joints",int(geometry->getHFMModel().joints.size())}};}
    QJsonObject value{{"avatarOriginalModelObservationVersion",2},
        {"avatarLoads",QJsonObject::fromVariantMap(avatar->e2eAvatarLoads())},
        {"modelInstance",model->e2eModelInstance()},{"modelUrl",model->getURL().toString()},
        {"modelLoads",QJsonObject::fromVariantMap(model->e2eModelLoads())},{"loaded",model->isLoaded()},
        {"geometry",current},{"geometryOwners",weak},{"resources",resources},
        {"rigSceneRendererConstructorQualified",false}};
    const auto cache=DependencyManager::get<ModelCache>();
    value.insert("cache",QJsonObject{{"numTotal",double(cache->getNumTotalResources())},
        {"numCached",double(cache->getNumCachedResources())},{"unusedLimit",double(cache->getUnusedResourceCacheSize())}});
    value.insert("capturedEpochMs",QDateTime::currentMSecsSinceEpoch());return value;
}
