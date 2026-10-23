// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
#include <atomic>
#include <memory>
#include <QPointer>
#include <QCoreApplication>
#include <QThread>
#include <QJsonArray>
#include <QCryptographicHash>
#include <QRegularExpression>
#include <FeatureAssetRequestBirth.h>
#include "AssetsRequestLifetimes.h"

namespace overte::e2e {
struct AssetsRequestBirthArchive { QJsonArray originals; };
// The factory caller queues this binding before its first ordinary send. The
// queued functor owns no QObject; it never starts/replays a request or callback.
class AssetsRequestBirthBinding: public FeatureAssetRequestBirth {
public:
    static std::shared_ptr<AssetsRequestBirthBinding> attach(AssetResourceRequest* source,QObject* originalOwner,
            const QString& run,const std::shared_ptr<AssetsRequestLifetimes>& collector,
            const std::shared_ptr<AssetsRequestBirthArchive>& archive) {
        if(!QCoreApplication::instance() || !QCoreApplication::arguments().contains("--testScript") || !source || !originalOwner
                || !collector || !archive || source->thread()==nullptr || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(run).hasMatch()
                || run==QString(32,'0')) {return {};}
        auto binding=std::shared_ptr<AssetsRequestBirthBinding>(new AssetsRequestBirthBinding(source,originalOwner,run,collector,archive));
        if(source->thread()==QThread::currentThread()) {
            if(!binding->scope(source) || source->getState()!=ResourceRequest::NotStarted) {binding->_failed.store(true);return binding;}
            source->_featurePicoRequestBirth=binding;binding->_attached.store(true);binding->_retired->store(true);return binding;
        }
        const std::weak_ptr<AssetsRequestBirthBinding> weak(binding);const auto delivery=std::make_shared<Delivery>(binding->_retired);
        if(!QMetaObject::invokeMethod(source,[weak,delivery] {
            const auto value=weak.lock();if(!value) {return;}
            const auto actual=value->_source.data();
            if(!value->scope(actual) || actual->getState()!=ResourceRequest::NotStarted) {value->_failed.store(true);return;}
            actual->_featurePicoRequestBirth=value;value->_attached.store(true);
        },Qt::QueuedConnection)) {binding->_failed.store(true);}
        return binding;
    }
    void observe(AssetResourceRequest* original) override {
        if(!_attached.load() || !scope(original)) {_failed.store(true);return;}
        const auto collector=_collector.lock();const auto archive=_archive.lock();
        if(!collector || !archive || !collector->observe(original,_run)) {_failed.store(true);return;}
        const auto frame=collector->snapshot(_run);
        if(frame.isEmpty() || archive->originals.size()>=512) {_failed.store(true);return;}
        archive->originals.append(frame);
    }
    bool valid()const{return _attached.load() && !_failed.load() && _retired->load();}
    bool sourceAlive()const{return !_source.isNull();}bool ownerAlive()const{return !_owner.isNull();}
private:
    AssetsRequestBirthBinding(AssetResourceRequest* source,QObject* owner,const QString& run,
            const std::shared_ptr<AssetsRequestLifetimes>& collector,const std::shared_ptr<AssetsRequestBirthArchive>& archive):
        _source(source),_owner(owner),_thread(source->thread()),_run(run),_url(source->getUrl().toString()),_collector(collector),_archive(archive){}
    bool scope(AssetResourceRequest* source) const {
        return QCoreApplication::instance() && QCoreApplication::arguments().contains("--testScript") && source
            && _source.data()==source && !_owner.isNull() && !_thread.isNull() && QThread::currentThread()==_thread.data()
            && source->thread()==_thread.data() && source->getUrl().toString()==_url;
    }
    struct Delivery {
        explicit Delivery(std::shared_ptr<std::atomic<bool>> retired):retired(std::move(retired)){}
        ~Delivery(){retired->store(true);}
        std::shared_ptr<std::atomic<bool>> retired;
    };
    QPointer<AssetResourceRequest> _source;QPointer<QObject> _owner;QPointer<QThread> _thread;QString _run,_url;
    std::weak_ptr<AssetsRequestLifetimes> _collector;std::weak_ptr<AssetsRequestBirthArchive> _archive;
    std::shared_ptr<std::atomic<bool>> _retired{std::make_shared<std::atomic<bool>>(false)};
    std::atomic<bool> _attached{false},_failed{false};
};
}
#endif
