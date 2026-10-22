//
//  AnimationCache.cpp
//  libraries/animation/src/
//
//  Created by Andrzej Kapolka on 4/14/14.
//  Copyright (c) 2014 High Fidelity, Inc. All rights reserved.
//
//  Distributed under the Apache License, Version 2.0.
//  See the accompanying file LICENSE or http://www.apache.org/licenses/LICENSE-2.0.html
//

#include "AnimationCache.h"
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include "AnimationDataObservation.h"
#include <QCryptographicHash>
#include <QReadLocker>
#include <QThread>
#include <algorithm>
#endif

#include <QRunnable>
#include <QThreadPool>

#include <shared/QtHelpers.h>
#include <Trace.h>
#include <StatTracker.h>
#include <Profile.h>

#include "AnimationLogging.h"
#include <FBXSerializer.h>

int animationPointerMetaTypeId = qRegisterMetaType<AnimationPointer>();

AnimationCache::AnimationCache(QObject* parent) :
    ResourceCache(parent)
{
#if defined(Q_OS_ANDROID)
    const qint64 ANIMATION_DEFAULT_UNUSED_MAX_SIZE = 8 * BYTES_PER_MEGABYTES;
#else
    const qint64 ANIMATION_DEFAULT_UNUSED_MAX_SIZE = 50 * BYTES_PER_MEGABYTES;
#endif
    setUnusedResourceCacheSize(ANIMATION_DEFAULT_UNUSED_MAX_SIZE);
    setObjectName("AnimationCache");
}

AnimationPointer AnimationCache::getAnimation(const QUrl& url) {
    return getResource(url).staticCast<Animation>();
}

QSharedPointer<Resource> AnimationCache::createResource(const QUrl& url) {
    return QSharedPointer<Animation>(new Animation(url), &Resource::deleter);
}

QSharedPointer<Resource> AnimationCache::createResourceCopy(const QSharedPointer<Resource>& resource) {
    return QSharedPointer<Animation>(new Animation(*resource.staticCast<Animation>()), &Resource::deleter);
}

AnimationReader::AnimationReader(const QUrl& url, const QByteArray& data) :
    _url(url),
    _data(data) {
    DependencyManager::get<StatTracker>()->incrementStat("PendingProcessing");
}

void AnimationReader::run() {
    DependencyManager::get<StatTracker>()->decrementStat("PendingProcessing");
    CounterStat counter("Processing");

    PROFILE_RANGE_EX(resource_parse, __FUNCTION__, 0xFF00FF00, 0, { { "url", _url.toString() } });
    auto originalPriority = QThread::currentThread()->priority();
    if (originalPriority == QThread::InheritPriority) {
        originalPriority = QThread::NormalPriority;
    }
    QThread::currentThread()->setPriority(QThread::LowPriority);
    try {
        if (_data.isEmpty()) {
            throw QString("Reply is NULL ?!");
        }
        QString urlname = _url.path().toLower();
        bool urlValid = true;
        urlValid &= !urlname.isEmpty();
        urlValid &= !_url.path().isEmpty();

        if (urlValid) {
            // Parse the FBX directly from the QNetworkReply
            HFMModel::Pointer hfmModel;
            if (_url.path().toLower().endsWith(".fbx")) {
                hfmModel = FBXSerializer().read(_data, QVariantHash(), _url.path());
#if defined(OVERTE_E2E_FEATURE_TESTS)
                overte::e2e::animationDataObservation().record(hfmModel,_url,_data,false);
#endif
            } else {
                QString errorStr("usupported format");
                emit onError(299, errorStr);
            }
            emit onSuccess(hfmModel);
        } else {
            throw QString("url is invalid");
        }

    } catch (const QString& error) {
        emit onError(299, error);
    }
    QThread::currentThread()->setPriority(originalPriority);
}

bool Animation::isLoaded() const {
    return _loaded && _hfmModel;
}

QStringList Animation::getJointNames() const {
    if (QThread::currentThread() != thread()) {
        QStringList result;
        BLOCKING_INVOKE_METHOD(const_cast<Animation*>(this), "getJointNames",
            Q_RETURN_ARG(QStringList, result));
        return result;
    }
    QStringList names;
    if (_hfmModel) {
        foreach (const HFMJoint& joint, _hfmModel->joints) {
            names.append(joint.name);
        }
    }
    return names;
}

QVector<HFMAnimationFrame> Animation::getFrames() const {
    if (QThread::currentThread() != thread()) {
        QVector<HFMAnimationFrame> result;
        BLOCKING_INVOKE_METHOD(const_cast<Animation*>(this), "getFrames",
            Q_RETURN_ARG(QVector<HFMAnimationFrame>, result));
        return result;
    }
    if (_hfmModel) {
        return _hfmModel->animationFrames;
    } else {
        return QVector<HFMAnimationFrame>();
    }
}

const QVector<HFMAnimationFrame>& Animation::getFramesReference() const {
    return _hfmModel->animationFrames;
}

#if defined(OVERTE_E2E_FEATURE_TESTS)
QVariantMap AnimationCache::featureResourceObservation() {
    const QVariantMap unavailable{{"complete",false}};
    const auto app=QCoreApplication::instance();
    if (!app || !QCoreApplication::arguments().contains("--testScript") || QThread::currentThread()!=app->thread()) { return unavailable; }
    QHash<QUrl,QMultiHash<size_t,QWeakPointer<Resource>>> original;
    {
        QReadLocker lock(&_resourcesLock);
        if (_resources.size()>1024) { return unavailable; }
        original=_resources; // Weak owners only; no resource creation or load.
    }
    int slotCount=0,expired=0;QHash<QString,QVariantMap> rows;
    QList<QPair<QWeakPointer<Resource>,bool>> observed;
    for (auto urls=original.constBegin();urls!=original.constEnd();++urls) {
        for (auto slot=urls.value().constBegin();slot!=urls.value().constEnd();++slot) {
            if (++slotCount>1024) { return unavailable; }
            // Drop all temporary strong refs outside the registry read lock.
            // Resource state/HFM publication belongs to the actual GUI thread.
            const auto resource=slot.value().toStrongRef();
            observed.append(qMakePair(slot.value(),bool(resource)));
            if (!resource) { ++expired;continue; }
            const auto animation=qSharedPointerDynamicCast<Animation>(resource);
            if (!animation || animation->thread()!=QThread::currentThread()) { return unavailable; }
            auto row=animation->featureResourceObservation();
            const auto id=row.value("resourceInstance").toString();
            if (id.isEmpty()) { return unavailable; }
            if (rows.contains(id)) {
                auto previous=rows.value(id);const auto count=previous.take("registrySlots").toInt();
                if (previous!=row) { return unavailable; }
                row.insert("registrySlots",count+1);
            } else {
                if (rows.size()>=256) { return unavailable; }
                row.insert("registrySlots",1);
            }
            rows.insert(id,row);
        }
    }
    {
        QReadLocker lock(&_resourcesLock);
        // QWeakPointer equality includes its weak control block, including
        // expired entries. Reused addresses cannot mimic the captured map.
        if (_resources!=original) { return unavailable; }
        for (const auto& slot:observed) { if (slot.first.isNull()==slot.second) { return unavailable; } }
    }
    auto ids=rows.keys();std::sort(ids.begin(),ids.end());QVariantList resources;
    for (const auto& id:ids) { resources.append(rows.value(id)); }
    return {{"complete",true},{"registrySlots",slotCount},{"expiredSlots",expired},{"resources",resources}};
}

QVariantMap Animation::featureResourceObservation() const {
    const auto app=QCoreApplication::instance();
    if (!app || _featureInstance.isEmpty() || QThread::currentThread()!=app->thread() || thread()!=QThread::currentThread()) { return {}; }
    const auto original=overte::e2e::animationDataObservation().source(_hfmModel.get());
    return {{"resourceInstance",_featureInstance},
        {"urlSha256",QString::fromLatin1(QCryptographicHash::hash(getURL().toString().toUtf8(),QCryptographicHash::Sha256).toHex())},
        {"loaded",isLoaded()},{"failed",isFailed()},{"model",original.isEmpty() ? QVariant() : QVariant(original)}};
}

QVariantMap Animation::featureSourceForModel(const HFMModel* original) const {
    if (_featureInstance.isEmpty() || !original || _hfmModel.get()!=original) { return {}; }
    const auto model=overte::e2e::animationDataObservation().source(original);
    return model.isEmpty() ? QVariantMap() : QVariantMap{{"animationSourceVersion",1},{"resourceInstance",_featureInstance},{"model",model}};
}
#endif

void Animation::downloadFinished(const QByteArray& data) {
    // parse the animation/fbx file on a background thread.
    AnimationReader* animationReader = new AnimationReader(_url, data);
    connect(animationReader, SIGNAL(onSuccess(HFMModel::Pointer)), SLOT(animationParseSuccess(HFMModel::Pointer)));
    connect(animationReader, SIGNAL(onError(int, QString)), SLOT(animationParseError(int, QString)));
    QThreadPool::globalInstance()->start(animationReader);
}

void Animation::animationParseSuccess(HFMModel::Pointer hfmModel) {
    _hfmModel = hfmModel;
    finishedLoading(true);
}

void Animation::animationParseError(int error, QString str) {
    qCCritical(animation) << "Animation parse error, code =" << error << str;
    emit failed(QNetworkReply::UnknownContentError);
    finishedLoading(false);
}
