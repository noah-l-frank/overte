// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include "PlacesHttpObservation.h"
#include <QHash>
#include <QMutex>
#include <QMutexLocker>
#include <QTimer>

namespace overte::e2e {
// Passive original code/People protocol timer ledger. Inputs originate only
// from real ScriptManager evaluate/timer/callback/destruction call sites.
class AvatarScriptObservation {
public:
    void submitted(const QString& url,const QString& code) {
        const QStringList suffixes {"/system/avatarapp.js","/system/pal.js","/system/libraries/peopleConnection.js",
            "/modules/request.js","/system/request-service.js"};
        bool relevant {false};for (const auto& suffix:suffixes) { relevant=relevant || PlacesHttpObservation::installed(url,suffix); }
        if (!enabled() || !relevant) { return; }
        QMutexLocker lock(&_mutex);
        if (!_valid || code.isEmpty() || code.size()>4194304 || _code.size()>=128) { _valid=false;return; }
        QByteArray bytes;bytes.reserve(code.size()*2);
        for (const auto c:code) { const auto unit=c.unicode();bytes.append(static_cast<char>(unit&0xff));bytes.append(static_cast<char>((unit>>8)&0xff)); }
        _code.append(QVariantMap{{"sequence",_code.size()+1},{"url",url},{"submittedEpochMs",now()},
            {"encoding","utf-16le-code-units"},{"codeUnits",code.size()},
            {"sha256",QString::fromLatin1(QCryptographicHash::hash(bytes,QCryptographicHash::Sha256).toHex())}});
    }
    QString created(int handle,const QStringList& callers,const QTimer* timer) {
        bool relevant {false};for (const auto& caller:callers) {
            relevant=relevant || PlacesHttpObservation::installed(caller,"/system/libraries/peopleConnection.js");
        }
        if (!enabled() || !relevant) { return {}; }
        QMutexLocker lock(&_mutex);
        if (!_valid || !timer || handle<=0 || _handles.contains(handle) || _births>=256 || callers.size()>32) { _valid=false;return {}; }
        const auto id=PlacesHttpObservation::nonce();++_births;_handles.insert(handle,id);_callbacks.insert(id,0);
        append(id,"created",{{"handle",handle},{"callerChain",callers},{"active",timer->isActive()},
            {"singleShot",timer->isSingleShot()},{"intervalMs",timer->interval()},{"remainingMs",timer->remainingTime()}});
        return id;
    }
    QString fired(int handle,const QTimer* timer) {
        QMutexLocker lock(&_mutex);const auto id=_handles.value(handle);if (id.isEmpty()) { return {}; }
        if (!timer || !_valid) { _valid=false;return {}; }
        append(id,"fired",{{"active",timer->isActive()},{"remainingMs",timer->remainingTime()}});return id;
    }
    void callback(const QString& id,bool entering) {
        if (id.isEmpty()) { return; }
        QMutexLocker lock(&_mutex);
        if (!_valid || !_callbacks.contains(id) || (entering && _callbacks[id]>=16) || (!entering && _callbacks[id]==0)) { _valid=false;return; }
        _callbacks[id]+=entering ? 1 : -1;append(id,entering ? "callback-enter" : "callback-leave");
    }
    void destroyed(const QString& id) {
        if (id.isEmpty()) { return; }
        QMutexLocker lock(&_mutex);const auto handle=_handles.key(id,-1);
        if (!_valid || handle<=0) { _valid=false;return; }
        _handles.remove(handle);append(id,"destroyed");
    }
    QVariantMap snapshot() const {
        QMutexLocker lock(&_mutex);
        return {{"avatarScriptVersion",1},{"instance",_instance},{"complete",_valid},{"code",_code},{"events",_events}};
    }
    void unavailable() { QMutexLocker lock(&_mutex);_valid=false; }
private:
    static bool enabled() { return QCoreApplication::instance() && QCoreApplication::arguments().contains("--testScript"); }
    qint64 now() {
        const auto epoch=QDateTime::currentMSecsSinceEpoch();if (epoch<=0 || epoch<_epoch) { _valid=false;return 0; }
        _epoch=epoch;return epoch;
    }
    void append(const QString& id,const QString& kind,const QVariantMap& details={}) {
        if (!_valid || _events.size()>=2048) { _valid=false;return; }
        _events.append(QVariantMap{{"sequence",_events.size()+1},{"timerId",id},{"kind",kind},
            {"capturedEpochMs",now()},{"details",details}});
    }
    mutable QMutex _mutex;
    const QString _instance {PlacesHttpObservation::nonce()};
    QVariantList _code,_events;QHash<int,QString> _handles;QHash<QString,int> _callbacks;
    qint64 _epoch {0};int _births {0};bool _valid {true};
};
} // namespace overte::e2e
#endif
