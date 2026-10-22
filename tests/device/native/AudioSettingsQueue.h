// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include <QCoreApplication>
#include <QMap>
#include <QMutex>
#include <QMutexLocker>
#include <QPointer>
#include <QSemaphore>
#include <QThread>
#include <QVariantMap>
#include <atomic>
#include <functional>
#include <memory>

namespace overte::e2e {
struct AudioSettingsPart {
    QVariantMap values;
    QMap<QString,QPointer<QObject>> objects;
};
// Four closed channels per actual TSI lifetime. A timed-out query remains
// owned until Qt has actually destroyed its original queued functor. No late
// value is reused or retimed, and a blocked queue cannot grow new observations.
class AudioSettingsQueue {
public:
    AudioSettingsPart read(const QString& channel,QObject* original,const std::function<AudioSettingsPart(QObject*)>& capture) {
        if (!QCoreApplication::instance() || !QCoreApplication::arguments().contains("--testScript") || !original
                || !QStringList{"dispatch","client","script","nodes"}.contains(channel)) {return {};}
        const QPointer<QObject> weak(original);
        // Callers hold the actual dependency QSharedPointer for this entire
        // call (or are the TSI method itself). No child raw association reaches
        // this dispatcher. Only the callback dereferences the weak QObject.
        if (original->thread()==QThread::currentThread()) {
            {QMutexLocker lock(&_mutex);if(!reap(channel)) {return {};}}
            return capture(original);
        }
        const auto read=std::make_shared<Read>();
        {
            QMutexLocker lock(&_mutex);
            if (!reap(channel)) {return {};}
            _pending.insert(channel,read);
        }
        auto delivery=std::make_shared<Delivery>(read);
        const bool invoked=QMetaObject::invokeMethod(original,[weak,read,delivery,capture,channel] {
            if (!read->cancelled.load() && weak && QCoreApplication::instance()
                    && QCoreApplication::arguments().contains("--testScript") && weak->thread()==QThread::currentThread()) {
                DispatchScope dispatch(channel=="dispatch" ? weak.data() : nullptr);
                auto result=capture(weak.data());
                if(!read->cancelled.load()) {read->result=std::move(result);}
            }
        },Qt::QueuedConnection);
        delivery.reset();
        if (!invoked) {read->cancelled.store(true);return {};}
        if (!read->ready.tryAcquire(1,channel=="dispatch" ? 1000 : 200)) {read->cancelled.store(true);return {};}
        QMutexLocker lock(&_mutex);
        if(_pending.value(channel)!=read) {return {};}
        _pending.remove(channel);return read->result;
    }
    static bool dispatching(QObject* owner) {return activeDispatch()==owner;}
    bool settled(const QString& except=QString()) {
        QMutexLocker lock(&_mutex);
        for(auto it=_pending.begin();it!=_pending.end();) {
            if(it.key()==except) {++it;continue;}
            if(!it.value()->retired.load()) {return false;}
            it=_pending.erase(it); // Discard every late result, even successful.
        }return true;
    }
private:
    static QObject*& activeDispatch() {static thread_local QObject* owner{nullptr};return owner;}
    struct DispatchScope {
        explicit DispatchScope(QObject* owner):previous(activeDispatch()) {if(owner) {activeDispatch()=owner;}}
        ~DispatchScope(){activeDispatch()=previous;}
        QObject* previous;
    };
    struct Read {QSemaphore ready;AudioSettingsPart result;std::atomic<bool> cancelled{false},retired{false};};
    struct Delivery {
        explicit Delivery(std::shared_ptr<Read> value):read(std::move(value)) {}
        ~Delivery(){read->retired.store(true);read->ready.release();}
        std::shared_ptr<Read> read;
    };
    bool reap(const QString& channel) {
        auto previous=_pending.find(channel);if(previous==_pending.end()) {return true;}
        if(!previous.value()->retired.load()) {return false;}
        _pending.erase(previous);return true;
    }
    QMutex _mutex;QMap<QString,std::shared_ptr<Read>> _pending;
};
} // namespace overte::e2e
#endif
