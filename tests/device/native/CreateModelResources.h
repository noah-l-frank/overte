// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDateTime>
#include <QElapsedTimer>
#include <QMap>
#include <QJsonDocument>
#include <QRegularExpression>
#include <QPointer>
#include <QSemaphore>
#include <QThread>
#include <QUuid>
#include <QVariantMap>
#include <memory>
#include <algorithm>
#include <Model.h>
#include <model-networking/ModelCache.h>

namespace overte::e2e {
// GUI-owned append-only weak originals. Resource fields are plain booleans in
// Resource: read them on the actual object's thread, with a bounded weak job.
// Never calls areTexturesLoaded(), getGPUTexture(), cache lookup or eviction.
class CreateModelResources {
public:
    using Models=QList<QPair<QString,std::shared_ptr<Model>>>;
    QVariantMap observe(const QString& run,const Models& actual) {
        if (!_valid || !QCoreApplication::instance() || QThread::currentThread()!=QCoreApplication::instance()->thread()
                || !QCoreApplication::arguments().contains("--testScript") || !identifier(run) || actual.size()>32) {return {};}
        const auto epoch=QDateTime::currentMSecsSinceEpoch();
        if (epoch<=0 || epoch<_epoch) {_valid=false;return {};}_epoch=epoch;
        if (!_runs.contains(run)) {if (_runs.size()>=4) {return {};}_runs.insert(run,{});}
        auto& state=_runs[run];QVariantList bindings;QString last;
        QElapsedTimer clock;clock.start();
        for (const auto& item:actual) {
            if (item.first<=last || QUuid(item.first).isNull()) {return {};}
            last=item.first;const auto& model=item.second;
            if (!model) {bindings.append(QVariantMap{{"entityId",item.first},{"model",QVariant()}});continue;}
            if (model->thread()!=QThread::currentThread()) {return {};}
            const auto modelId=remember(state.models,model,model->e2eModelInstance(),epoch,64);
            if (modelId.isEmpty()) {return {};}
            const auto geometry=model->getGeometry();
            QString geometryId,sourceHash;QVariantList textures;
            const bool loaded=model->isLoaded();
            if (geometry) {
                geometryId=remember(state.geometries,geometry,geometry->e2eGeometryInstance(),epoch,64);
                if (geometryId.isEmpty()) {return {};}
                if (geometry->isHFMModelLoaded()) {
                    const auto source=geometry->getHFMModel().originalURL.toUtf8();
                    if (source.isEmpty() || source.size()>4096) {return {};}
                    sourceHash=QString::fromLatin1(QCryptographicHash::hash(source,QCryptographicHash::Sha256).toHex());
                }
                const auto& materials=geometry->featureCreateMaterials();if (materials.size()>64) {return {};}
                int materialIndex=-1;
                for (const auto& material:materials) {
                    ++materialIndex;
                    if (!material) {return {};}
                    const auto materialId=remember(state.materials,material,QString(),epoch,128);
                    if (materialId.isEmpty()) {return {};}
                    const auto original=material->getTextures();if (original.size()>32) {return {};}
                    QList<int> channels;for (const auto& entry:original) {channels.append(static_cast<int>(entry.first));}std::sort(channels.begin(),channels.end());
                    for (const auto channel:channels) {
                        if (channel<0 || channel>31) {return {};}
                        const auto entry=original.at(static_cast<NetworkMaterial::MapChannel>(channel));
                        if (!entry.texture) {continue;}
                        if (entry.name.isEmpty() || entry.name.size()>256 || entry.name.contains(QRegularExpression("[\\x00-\\x1f]"))) {return {};}
                        const auto resourceId=rememberTexture(state,entry.texture,epoch);
                        if (resourceId.isEmpty() || textures.size()>=128) {return {};}
                        textures.append(QVariantMap{{"material",materialId},{"materialIndex",materialIndex},{"channel",channel},{"slot",entry.name},{"resource",resourceId}});
                    }
                }
            }
            if (loaded && (!geometry || sourceHash.isEmpty())) {return {};}
            bindings.append(QVariantMap{{"entityId",item.first},{"model",modelId},
                {"geometry",geometryId.isEmpty() ? QVariant() : QVariant(geometryId)},
                {"loaded",loaded},{"loadedSourceSha256",sourceHash},{"textures",textures}});
        }
        QVariantList resources;
        for (auto it=state.textures.cbegin();it!=state.textures.cend();++it) {
            const auto object=it->object.toStrongRef();auto row=lifetime(it.key(),it->created,!it->guard.isNull());
            row.insert("sharedAvailable",bool(object));
            if (object && it->guard.data()!=object.data()) {return {};}
            if (object) {
                const auto observed=resource(object,qMax(0,750-static_cast<int>(clock.elapsed())));
                if (observed.isEmpty()) {return {};}
                row.insert("state",observed);
            } else {row.insert("state",QVariant());}
            resources.append(row);
        }
        const QVariantMap result{{"createModelResourcesVersion",1},{"runId",run},{"bindings",bindings},
            {"models",history(state.models)},{"geometries",history(state.geometries)},
            {"materials",history(state.materials)},{"resources",resources}};
        if (QJsonDocument::fromVariant(result).toJson(QJsonDocument::Compact).size()>196608) {return {};}
        return result;
    }
private:
    template<class T> struct Original {qint64 created;std::weak_ptr<T> object;};
    struct TextureOriginal {qint64 created;QWeakPointer<NetworkTexture> object;QPointer<NetworkTexture> guard;};
    struct Run {
        QMap<QString,Original<Model>> models;QMap<QString,Original<Geometry>> geometries;
        QMap<QString,Original<NetworkMaterial>> materials;QMap<QString,TextureOriginal> textures;
    };
    static bool identifier(const QString& value) {return QRegularExpression("\\A[0-9a-f]{32}\\z").match(value).hasMatch();}
    static QString birth() {return QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');}
    static QVariantMap lifetime(const QString& id,qint64 epoch,bool alive) {
        return {{"instance",id},{"firstObservedEpochMs",epoch},{"alive",alive}};
    }
    template<class T> static QString remember(QMap<QString,Original<T>>& records,const std::shared_ptr<T>& object,
            const QString& nativeId,qint64 epoch,int maximum) {
        for (auto it=records.cbegin();it!=records.cend();++it) {
            const auto original=it->object.lock();
            if (original && original.get()==object.get()) {return nativeId.isEmpty() || nativeId==it.key() ? it.key() : QString();}
        }
        const auto id=nativeId.isEmpty() ? birth() : nativeId;
        if (!identifier(id) || records.contains(id) || records.size()>=maximum) {return {};}
        records.insert(id,{epoch,object});return id;
    }
    static QString rememberTexture(Run& state,const QSharedPointer<NetworkTexture>& object,qint64 epoch) {
        for (auto it=state.textures.begin();it!=state.textures.end();++it) {
            if (it->guard.data()==object.data()) {it->object=object.toWeakRef();return it.key();}
        }
        if (state.textures.size()>=64) {return {};}
        const auto id=birth();state.textures.insert(id,{epoch,object.toWeakRef(),object.data()});return id;
    }
    template<class T> static QVariantList history(const QMap<QString,Original<T>>& records) {
        QVariantList rows;for (auto it=records.cbegin();it!=records.cend();++it) {rows.append(lifetime(it.key(),it->created,!it->object.expired()));}return rows;
    }
    static QVariantMap resource(const QSharedPointer<NetworkTexture>& original,int budget) {
        if (!original || !original->thread() || !original->thread()->isRunning() || budget<=0) {return {};}
        auto read=[](NetworkTexture* texture) -> QVariantMap {
            const auto url=texture->getURL().toString();
            if (url.isEmpty() || url.size()>4096 || url.contains(QRegularExpression("[\\x00-\\x1f]"))) {return {};}
            return {{"url",url},{"loaded",texture->isLoaded()},{"failed",texture->isFailed()}};
        };
        if (original->thread()==QThread::currentThread()) {return read(original.data());}
        struct Result {QSemaphore ready;QVariantMap value;};const auto result=std::make_shared<Result>();
        const auto weak=original.toWeakRef();
        if (!QMetaObject::invokeMethod(original.data(),[weak,result,read] {
            const auto texture=weak.toStrongRef();
            if (texture && texture->thread()==QThread::currentThread()) {result->value=read(texture.data());}
            result->ready.release();
        },Qt::QueuedConnection) || !result->ready.tryAcquire(1,budget)) {return {};}
        return result->value;
    }
    QMap<QString,Run> _runs;bool _valid {true};qint64 _epoch {0};
};
} // namespace overte::e2e
#endif
