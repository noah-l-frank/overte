// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDateTime>
#include <QMutex>
#include <QMutexLocker>
#include <QRegularExpression>
#include <QSet>
#include <QUuid>
#include <QVariantMap>
namespace overte::e2e {
// Original DomainHandler fields are recorded at their actual assignments,
// before ordinary signals. No URL, requested domain or fixture ACK is a source.
class ChatDomainSession {
public:
    void changed(const QUuid& domain,bool connected,bool originalThread) {
        if (!QCoreApplication::arguments().contains("--testScript")) { return; }
        QMutexLocker lock(&_mutex);const auto now=tick();
        if (!now || !originalThread || _revision>=9007199254740991LL) { _valid=false;return; }
        if (_domain==domain && _connected==connected) { return; }
        if (!_connected && connected) { _connectionBirth=nonce();_connectedEpochMs=now; }
        else if (!connected) { _connectionBirth.clear();_connectedEpochMs=0; }
        _domain=domain;_connected=connected;++_revision;
    }
    QVariantMap snapshot(const QString& run) {
        if (!QCoreApplication::arguments().contains("--testScript")
                || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(run).hasMatch()) { return {}; }
        QMutexLocker lock(&_mutex);
        if (!tick() || (_connected && (_domain.isNull() || _connectionBirth.isEmpty() || !_connectedEpochMs))) { return {}; }
        return {{"domainSessionVersion",1},{"instance",_instance},{"revision",_revision},{"connected",_connected},
            {"domainSha256",_domain.isNull()?QString():QString::fromLatin1(QCryptographicHash::hash(run.toUtf8()+':'+_domain.toRfc4122(),QCryptographicHash::Sha256).toHex())},
            {"connectionBirth",_connectionBirth},{"connectedEpochMs",_connectedEpochMs}};
    }
    static bool valid(const QVariantMap& value) {
        const auto keys=value.keys();
        if (QSet<QString>(keys.begin(),keys.end())!=QSet<QString>{"domainSessionVersion","instance","revision","connected",
                "domainSha256","connectionBirth","connectedEpochMs","mixerActive"}
                || value.value("domainSessionVersion").userType()!=QMetaType::Int || value.value("domainSessionVersion")!=QVariant(1)
                || value.value("revision").userType()!=QMetaType::LongLong || value.value("connectedEpochMs").userType()!=QMetaType::LongLong
                || value.value("connected").userType()!=QMetaType::Bool
                || value.value("mixerActive").userType()!=QMetaType::Bool
                || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(value.value("instance").toString()).hasMatch()
                || value.value("revision").toLongLong()<0 || value.value("revision").toLongLong()>9007199254740991LL) { return false; }
        const auto domain=value.value("domainSha256").toString(),birth=value.value("connectionBirth").toString();
        if (!domain.isEmpty() && !QRegularExpression("\\A[0-9a-f]{64}\\z").match(domain).hasMatch()) { return false; }
        return value.value("connected").toBool()
            ? value.value("revision").toLongLong()>=1 && !domain.isEmpty() && QRegularExpression("\\A[0-9a-f]{32}\\z").match(birth).hasMatch() && value.value("connectedEpochMs").toLongLong()>0
            : birth.isEmpty() && value.value("connectedEpochMs").toLongLong()==0;
    }
private:
    static QString nonce() { return QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-'); }
    qint64 tick() {
        const auto now=QDateTime::currentMSecsSinceEpoch();
        if (!_valid || now<=0 || now<_epoch) { _valid=false;return 0; }_epoch=now;return now;
    }
    QMutex _mutex;bool _valid{true},_connected{false};QUuid _domain;
    qint64 _revision{0},_epoch{0},_connectedEpochMs{0};QString _connectionBirth;
    const QString _instance{nonce()};
};
}
#endif
