// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include <memory>
#include <utility>
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDateTime>
#include <QHash>
#include <QMutex>
#include <QMutexLocker>
#include <QUuid>
#include <QUrl>
#include <QUrlQuery>
#include <QVariantMap>

namespace overte::e2e {
// Observations only: no request cancellation, navigation or product decisions.
class PhoneSceneLoads : public std::enable_shared_from_this<PhoneSceneLoads> {
public:
    class Lease {
    public:
        Lease(std::shared_ptr<PhoneSceneLoads> owner, QString id) : _owner(std::move(owner)), _id(std::move(id)) {}
        ~Lease() { _owner->release(_id); }
        void phase(const QString& value) { _owner->phase(_id,value); }
        void reply(int result, qint64 bytes) { _owner->phase(_id,"reply",result,bytes); }
    private:
        std::shared_ptr<PhoneSceneLoads> _owner;
        QString _id;
    };
    using Pointer = std::shared_ptr<Lease>;

    Pointer begin(const QString& kind, quint64 generation, const QUrl& url) {
        if (!QCoreApplication::arguments().contains("--testScript")) { return {}; }
        QMutexLocker lock(&_mutex);
        if (_rows.size() >= 128 || (kind != "request" && kind != "delivery")) { _complete=false; return {}; }
        auto resource=url;QUrlQuery query(resource);query.removeAllQueryItems("location");
        if (query.isEmpty()) { resource.setQuery(QString()); } else { resource.setQuery(query); }
        const auto id=QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');
        const auto now=QDateTime::currentMSecsSinceEpoch();
        _indices.insert(id,_rows.size());
        _rows.append(QVariantMap{{"id",id},{"kind",kind},{"generation",static_cast<qulonglong>(generation)},
            {"resourceSha256",QString::fromLatin1(QCryptographicHash::hash(resource.toEncoded(QUrl::FullyEncoded),QCryptographicHash::Sha256).toHex())},
            {"startedEpochMs",now},{"updatedEpochMs",now},{"releasedEpochMs",QVariant()},
            {"phase","requested"},{"pending",true},{"result",QVariant()},{"bytes",QVariant()}});
        return std::make_shared<Lease>(shared_from_this(),id);
    }

    QVariantMap snapshot(quint64 currentGeneration) {
        QMutexLocker lock(&_mutex);
        int pending=0;
        for (const auto& value : _rows) { pending += value.toMap().value("pending").toBool() ? 1 : 0; }
        return {{"sceneLoadVersion",1},{"instance",_instance},{"sequence",static_cast<qulonglong>(++_sequence)},
            {"currentGeneration",static_cast<qulonglong>(currentGeneration)},{"pendingLeases",pending},
            {"complete",_complete},{"requests",_rows}};
    }
private:
    void phase(const QString& id, const QString& phase, QVariant result={}, QVariant bytes={}) {
        QMutexLocker lock(&_mutex);
        if (!_indices.contains(id)) { _complete=false; return; }
        auto row=_rows[_indices.value(id)].toMap();
        if (!row.value("pending").toBool()) { _complete=false; return; }
        row.insert("phase",phase);row.insert("updatedEpochMs",QDateTime::currentMSecsSinceEpoch());
        if (result.isValid()) { row.insert("result",result);row.insert("bytes",bytes); }
        _rows[_indices.value(id)]=row;
    }
    void release(const QString& id) {
        QMutexLocker lock(&_mutex);
        if (!_indices.contains(id)) { _complete=false; return; }
        auto row=_rows[_indices.value(id)].toMap();
        if (!row.value("pending").toBool()) { _complete=false; return; }
        const auto phase=row.value("phase").toString();
        if (phase!="committed" && phase!="failed" && phase!="stale" && phase!="empty" && phase!="delivered") { row.insert("phase","destroyed"); }
        const auto now=QDateTime::currentMSecsSinceEpoch();
        row.insert("pending",false);row.insert("releasedEpochMs",now);row.insert("updatedEpochMs",now);
        _rows[_indices.value(id)]=row;
    }
    QMutex _mutex;
    QString _instance=QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');
    quint64 _sequence {0};
    bool _complete {true};
    QHash<QString,int> _indices;
    QVariantList _rows;
};
} // namespace overte::e2e
