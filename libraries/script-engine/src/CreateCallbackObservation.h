// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include <QCoreApplication>
#include <QDateTime>
#include <QMap>
#include <QUuid>
#include <QVariantList>
#include <QVariantMap>
#include <memory>
#include <mutex>

namespace overte::e2e {
// Actual Window signal-proxy connections and dispatch leases. Publication never
// enters V8, invokes a callback, waits on a script thread or stores result paths.
class CreateCallbackObservation : public std::enable_shared_from_this<CreateCallbackObservation> {
public:
    CreateCallbackObservation() {
        if (QCoreApplication::arguments().contains("--testScript")) { _instance=identity(); }
    }
    static bool supported(const QString& targetClass,const QString& signal) {
        return targetClass=="WindowScriptingInterface" && (signal=="browseChanged(QString)" || signal=="saveFileChanged(QString)");
    }
    QString born(const QString& targetClass,const QString& signal) {
        std::lock_guard<std::mutex> lock(_mutex);
        if (_instance.isEmpty() || !_complete) { return {}; }
        if (!supported(targetClass,signal) || _proxies.size()>=128 || !advance()) {
            _complete=false;return {};
        }
        const auto id=identity();
        _proxies.insert(id,{{"id",id},{"targetClass",targetClass},{"signal",signal},{"createdEpochMs",_epoch},
            {"retiredEpochMs",static_cast<qint64>(0)},{"dispatches",0}});
        return id;
    }
    QString connected(const QString& proxy,int scriptId) {
        std::lock_guard<std::mutex> lock(_mutex);
        if (proxy.isEmpty() || _instance.isEmpty() || !_complete) { return {}; }
        if (!_proxies.contains(proxy) || _proxies[proxy].value("retiredEpochMs").toLongLong()!=0
                || scriptId<=0 || _callbacks.size()>=512 || !advance()) { _complete=false;return {}; }
        const auto id=identity();
        _callbacks.insert(id,{{"id",id},{"proxyId",proxy},{"scriptId",scriptId},{"connectedEpochMs",_epoch},
            {"disconnectedEpochMs",static_cast<qint64>(0)}});
        return id;
    }
    void disconnected(const QString& proxy,const QString& callback) {
        std::lock_guard<std::mutex> lock(_mutex);
        if (proxy.isEmpty() || _instance.isEmpty() || !_complete) { return; }
        if (!_callbacks.contains(callback) || _callbacks[callback].value("proxyId").toString()!=proxy
                || _callbacks[callback].value("disconnectedEpochMs").toLongLong()!=0 || !advance()) { _complete=false;return; }
        _callbacks[callback]["disconnectedEpochMs"]=_epoch;
    }
    // The lease starts before copying the actual connection list and ends only
    // after every return path from the original Qt/V8 signal dispatcher. A
    // callback disconnecting itself cannot establish quiet while still running.
    std::shared_ptr<void> dispatch(const QString& proxy) {
        {
            std::lock_guard<std::mutex> lock(_mutex);
            if (proxy.isEmpty() || _instance.isEmpty() || !_complete) { return {}; }
            if (!_proxies.contains(proxy) || _proxies[proxy].value("retiredEpochMs").toLongLong()!=0
                    || _proxies[proxy].value("dispatches").toInt()>=128 || !advance()) { _complete=false;return {}; }
            _proxies[proxy]["dispatches"]=_proxies[proxy].value("dispatches").toInt()+1;
        }
        const auto self=shared_from_this();
        return std::shared_ptr<void>(new int(0),[self,proxy](void* value) {
            delete static_cast<int*>(value);self->finished(proxy);
        });
    }
    void retired(const QString& proxy) {
        std::lock_guard<std::mutex> lock(_mutex);
        if (proxy.isEmpty() || _instance.isEmpty() || !_complete) { return; }
        bool connected=false;
        for (const auto& row:_callbacks) {
            connected=connected || (row.value("proxyId").toString()==proxy && row.value("disconnectedEpochMs").toLongLong()==0);
        }
        if (!_proxies.contains(proxy) || _proxies[proxy].value("retiredEpochMs").toLongLong()!=0
                || _proxies[proxy].value("dispatches").toInt()!=0 || connected || !advance()) { _complete=false;return; }
        _proxies[proxy]["retiredEpochMs"]=_epoch;
    }
    QVariantMap snapshot() const {
        std::lock_guard<std::mutex> lock(_mutex);
        if (_instance.isEmpty()) { return {}; }
        QVariantList proxies,callbacks;
        if (_complete) {
            for (const auto& row:_proxies) { proxies.append(row); }
            for (const auto& row:_callbacks) { callbacks.append(row); }
        }
        return {{"callbackSourceVersion",1},{"instance",_instance},{"sequence",static_cast<qulonglong>(_sequence)},
            {"complete",_complete},{"proxies",proxies},{"callbacks",callbacks}};
    }
private:
    static QString identity() { return QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-'); }
    bool advance() {
        const auto epoch=QDateTime::currentMSecsSinceEpoch();
        if (_sequence>=9007199254740991ULL || epoch<=0 || epoch<_epoch) { return false; }
        _epoch=epoch;++_sequence;return true;
    }
    void finished(const QString& proxy) {
        std::lock_guard<std::mutex> lock(_mutex);
        if (!_complete) { return; }
        if (!_proxies.contains(proxy) || _proxies[proxy].value("dispatches").toInt()<=0 || !advance()) { _complete=false;return; }
        _proxies[proxy]["dispatches"]=_proxies[proxy].value("dispatches").toInt()-1;
    }
    mutable std::mutex _mutex;
    QString _instance;
    bool _complete {true};
    quint64 _sequence {0};qint64 _epoch {0};
    QMap<QString,QVariantMap> _proxies,_callbacks;
};
} // namespace overte::e2e
#endif
