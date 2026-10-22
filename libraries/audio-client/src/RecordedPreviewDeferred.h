// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include <QCoreApplication>
#include <QDateTime>
#include <QPointer>
#include <QThread>
#include <QUuid>
#include <QVariantMap>
#include <QVariantList>
#include <memory>
#include <atomic>

namespace overte::e2e {
// Original Qt functor ownership, not timer expiry inferred from requested time.
// Only actual registration, callback execution and final captured-lease death
// change these facts. PCM clear never retires an outstanding callback.
class RecordedPreviewDeferred {
    struct Clock {qint64 epoch{0};std::atomic<bool> valid{true};};
    struct Original {
        QString id;QPointer<QObject> receiver;QThread* thread{nullptr};quint64 cycle{0};
        qint64 registered{0},entered{0},completed{0},retired{0};int delay{0};
        bool active{false},released{false};std::atomic<bool> valid{true};std::shared_ptr<Clock> clock;
    };
public:
    struct Lease {
        ~Lease() {
            if(!original) {return;}
            const auto now=QDateTime::currentMSecsSinceEpoch();
            if(QThread::currentThread()!=original->thread || original->active || now<original->registered
                    || (original->completed && now<original->completed) || now<original->clock->epoch) {
                original->valid.store(false);original->clock->valid.store(false);return;
            }
            original->clock->epoch=now;original->retired=now;original->released=true;
        }
    private:
        explicit Lease(std::shared_ptr<Original> value):original(std::move(value)) {}
        std::shared_ptr<Original> original;
        friend class RecordedPreviewDeferred;
    };
    struct Invocation {
        Invocation(const Invocation&)=delete;Invocation& operator=(const Invocation&)=delete;
        Invocation(Invocation&& other) noexcept:original(std::move(other.original)) {}
        ~Invocation() {
            if(!original) {return;}
            const auto now=QDateTime::currentMSecsSinceEpoch();
            if(QThread::currentThread()!=original->thread || !original->active || now<original->entered || now<original->clock->epoch) {
                original->valid.store(false);original->clock->valid.store(false);return;
            }
            original->clock->epoch=now;original->completed=now;original->active=false;
        }
    private:
        explicit Invocation(std::shared_ptr<Original> value):original(std::move(value)) {}
        std::shared_ptr<Original> original;
        friend class RecordedPreviewDeferred;
    };
    std::shared_ptr<Lease> registerCallback(QObject* receiver,quint64 cycle,int delay) {
        if(!bind(receiver) || !cycle || cycle>9007199254740991ULL || delay<0 || delay>30000 || _originals.size()>=64) {
            _valid=false;return {};
        }
        const auto now=QDateTime::currentMSecsSinceEpoch();
        if(now<=0 || now<_clock->epoch || (!_originals.isEmpty() && cycle<=_originals.last()->cycle)) {_valid=false;return {};}
        _clock->epoch=now;auto value=std::make_shared<Original>();value->id=nonce();value->receiver=receiver;value->thread=QThread::currentThread();
        value->cycle=cycle;value->registered=now;value->delay=delay;value->clock=_clock;_originals.append(value);
        return std::shared_ptr<Lease>(new Lease(value));
    }
    static Invocation enter(const std::shared_ptr<Lease>& lease) {
        const auto value=lease ? lease->original : nullptr;
        if(!value) {return Invocation(nullptr);}
        const auto now=QDateTime::currentMSecsSinceEpoch();
        if(!enabled() || !value->valid.load() || !value->clock->valid.load() || !value->receiver || value->receiver->thread()!=QThread::currentThread()
                || QThread::currentThread()!=value->thread || value->entered || value->released || now<value->registered || now<value->clock->epoch) {
            value->valid.store(false);value->clock->valid.store(false);return Invocation(nullptr);
        }
        value->clock->epoch=now;value->entered=now;value->active=true;return Invocation(value);
    }
    QVariantMap snapshot(QObject* receiver) {
        if(!bind(receiver)) {return {};}
        const auto now=QDateTime::currentMSecsSinceEpoch();if(now<=0 || now<_clock->epoch) {_valid=false;return {};}_clock->epoch=now;
        QVariantList rows;bool complete=_valid;
        for(const auto& original:_originals) {
            complete=complete && original->valid.load() && _clock->valid.load();
            rows.append(QVariantMap{{"id",original->id},{"cycle",static_cast<qulonglong>(original->cycle)},
                {"registeredEpochMs",original->registered},{"scheduledDelayMs",original->delay},
                {"enteredEpochMs",original->entered},{"completedEpochMs",original->completed},{"retiredEpochMs",original->retired},
                {"receiverAlive",!original->receiver.isNull()},{"active",original->active},{"retired",original->released}});
        }
        return {{"complete",complete},{"receiverId",_receiverId},{"callbacks",rows}};
    }
private:
    static QString nonce(){return QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');}
    static bool enabled(){return QCoreApplication::instance() && QCoreApplication::arguments().contains("--testScript");}
    bool bind(QObject* receiver) {
        if(!enabled() || !receiver || receiver->thread()!=QThread::currentThread() || !_valid) {return false;}
        if(_receiverId.isEmpty()) {_receiver=receiver;_receiverId=nonce();_thread=QThread::currentThread();_clock=std::make_shared<Clock>();}
        if(!_receiver || _receiver!=receiver || QThread::currentThread()!=_thread || !_clock->valid.load()) {_valid=false;return false;}
        return true;
    }
    QPointer<QObject> _receiver;QString _receiverId;QThread* _thread{nullptr};bool _valid{true};std::shared_ptr<Clock> _clock;
    QList<std::shared_ptr<Original>> _originals;
};
} // namespace overte::e2e
#endif
