// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDateTime>
#include <QJsonObject>
#include <QRegularExpression>
#include <QSet>
#include <QUuid>
#include <QVariantMap>
#include <cmath>
namespace overte::e2e {
class ChatPeerPosition {
public:
    static QString identity(const QString& run,const QUuid& id) {
        return QString::fromLatin1(QCryptographicHash::hash(run.toUtf8()+':'+id.toRfc4122(),QCryptographicHash::Sha256).toHex());
    }
    static bool command(const QVariantMap& value) {
        const auto keys=value.keys();
        return QSet<QString>(keys.begin(),keys.end())==QSet<QString>{"schemaVersion","commandId","runId","action","peerSha256"}
            && QJsonObject::fromVariantMap(value).value("schemaVersion")==QJsonValue(1)
            && value.value("action")==QVariant("feature-chat-peer-position")
            && QRegularExpression("\\A[0-9a-f]{32}\\z").match(value.value("commandId").toString()).hasMatch()
            && QRegularExpression("\\A[0-9a-f]{32}\\z").match(value.value("runId").toString()).hasMatch()
            && QRegularExpression("\\A[0-9a-f]{64}\\z").match(value.value("peerSha256").toString()).hasMatch();
    }
    static bool position(const QVariantMap& value) {
        const auto keys=value.keys();
        if (QSet<QString>(keys.begin(),keys.end())!=QSet<QString>{"x","y","z"}) { return false; }
        for (const auto key:{"x","y","z"}) {
            const auto actual=value.value(key);
            if ((actual.userType()!=QMetaType::Double && actual.userType()!=QMetaType::Float)
                    || !std::isfinite(actual.toDouble()) || std::abs(actual.toDouble())>100000) { return false; }
        }
        return true;
    }
    QVariantMap request(const QVariantMap& value,const QUuid& self,const QVariantMap& selfPosition,
            const QUuid& peer,const QVariantMap& peerPosition) {
        const auto now=QDateTime::currentMSecsSinceEpoch();
        if (!_available || !QCoreApplication::arguments().contains("--testScript") || !command(value)
                || now<=0 || now<_epoch || self.isNull() || peer.isNull() || self==peer
                || !position(selfPosition) || !position(peerPosition) || _queries.size()>=4096) {
            if (now<=0 || now<_epoch) { _available=false; }return {};
        }
        const auto id=value.value("commandId").toString();const auto run=value.value("runId").toString();
        if (_queries.contains(id) || identity(run,peer)!=value.value("peerSha256").toString()) { return {}; }
        _queries.insert(id);_epoch=now;
        return {{"chatPeerPositionVersion",1},{"commandId",id},{"runId",run},{"instance",_instance},
            {"sequence",++_sequence},{"processId",QCoreApplication::applicationPid()},{"capturedEpochMs",now},
            {"source",QVariantMap{{"selfSha256",identity(run,self)},{"peerSha256",identity(run,peer)},
                {"selfPosition",selfPosition},{"peerPosition",peerPosition}}}};
    }
private:
    bool _available{true};qint64 _epoch{0},_sequence{0};QSet<QString> _queries;
    const QString _instance{QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')};
};
} // namespace overte::e2e
#endif
