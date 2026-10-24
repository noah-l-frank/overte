// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
// One actual Resource/DependencyManager/Texture declaration universe. The
// previously acquired ATP bytes and optional Domain startup remain host seams.
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDateTime>
#include <QJsonArray>
#include <QJsonObject>
#include <QMutex>
#include <QPointer>
#include <QThread>
#include <QTimer>
#include <QVariantMap>
#include <QElapsedTimer>
#include <QEvent>
#include <QTest>
#include <memory>
#include <mutex>
#include <DependencyManager.h>
#include <ResourceManager.h>
#include <ResourceRequest.h>
#include <ResourceRequestObserver.h>
#include <ResourceCache.h>
#include <StatTracker.h>
#include <PathUtils.h>
#include <SettingManager.h>
#include <SettingHelpers.h>
#include <material-networking/TextureCache.h>
#include "AssetsGeometryResource.h"
Q_DECLARE_LOGGING_CATEGORY(networking)
Q_DECLARE_LOGGING_CATEGORY(modelnetworking)

class DomainHandler:public QObject {
 Q_OBJECT
signals:void disconnectedFromDomain();
};
class NodeList:public Dependency {
 DomainHandler domain;
public:DomainHandler& getDomainHandler(){return domain;}
};

// Existing model-format startup is deliberately one glTF registry. The actual
// ResourceCache constructor/default LRU, all acquisition/removal logic and the
// original ModelCache create/get bodies remain unchanged. No eviction/wipe is
// performed to obtain a death or a zero counter.
class ModelCache:public ResourceCache,public Dependency {
 friend class GeometryResource;
 ModelLoader _modelLoader;
public:
 GeometryResource::Pointer getGeometryResource(const QUrl&,const GeometryMappingPair&,const QUrl&);
 QSharedPointer<Resource> createResource(const QUrl&)override;
 QSharedPointer<Resource> createResourceCopy(const QSharedPointer<Resource>&)override{
  qFatal("Alternate-extra model acquisition remains outside this original glTF input");return {};
 }
};
class FSTReader {
public:
 static QVariantHash readMapping(const QByteArray&){qFatal("FST parsing is outside the original glTF material join");return {};}
 static QStringList getScripts(const QUrl&,const QVariantHash&){qFatal("FST scripts are outside the original glTF material join");return {};}
};

struct AssetsRecordedInput {
 QHash<QUrl,QByteArray> originalBytes;QList<QPointer<ResourceRequest>> requests;
 QJsonArray transportOriginals;QMutex mutex;
};
extern AssetsRecordedInput* assetsMaterialInput;
ResourceRequest* assetsRecordedRequest(QObject*,const QUrl&,bool,qint64,const QString&);
void observeAssetsMaterialRequest(ResourceRequest*,QObject*,const QUrl&);

// A passively copied receipt contains no owning Resource/Material/pixel pointer.
struct AssetsMaterialRequestOriginal {
 QPointer<ResourceRequest> request;QPointer<QObject> factoryOwner,objectParent;
 QString url;bool parentArgument{false};QVariantMap threads,finished;
};
struct AssetsMaterialOriginal {
 std::weak_ptr<NetworkMaterial> material;QWeakPointer<NetworkTexture> texture;
 QPointer<NetworkTexture> textureGuard;std::weak_ptr<gpu::Texture> pixels;
 QString geometry,materialId,textureId,url,slot;int channel{-1};bool pixelsObserved{false};QString pixelId;
};
