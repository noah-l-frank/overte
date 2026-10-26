// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include "NativeReadBracket.h"
#include <ResourceCache.h>
#include <QCryptographicHash>
#include <QMutex>
#include <QMutexLocker>
#include <QVector>
#include <memory>

namespace overte::e2e {
// Original download/parser/delivery observations only. No resource, model or
// task is retained strongly. Cache/texture/decoder retirement is a separate
// source; neither an accepted definition nor a dead parser proves it.
class IOSAssetsModelOrigin {
public:
    static IOSAssetsModelOrigin& shared() {static IOSAssetsModelOrigin value;return value;}
    static bool enabled() {return QCoreApplication::instance() && QCoreApplication::arguments().contains("--testScript");}
    QString download(const QWeakPointer<Resource>& resource,const QUrl& requested,const QUrl& effective,const QByteArray& bytes,bool mapping) {
        if (!enabled() || (requested.scheme()!="atp" && effective.scheme()!="atp")) {return {};}
        QMutexLocker lock(&_mutex);
        if (_rows.size()>=64 || resource.isNull() || requested.toEncoded().size()>4096 || effective.toEncoded().size()>4096) {_complete=false;return {};}
        Row row;row.id=nonce();row.resource=resource;
        const bool retained=!bytes.isEmpty() && bytes.size()<=32768 && _bytes+bytes.size()<=65536;
        if (retained) {_bytes+=bytes.size();} else {_complete=false;}
        row.value={{"id",row.id},{"kind",mapping ? "mapping" : "model"},{"requestedUrl",requested.toString(QUrl::FullyEncoded)},
            {"effectiveUrl",effective.toString(QUrl::FullyEncoded)},{"received",stamp()},{"bytes",bytes.size()},
            {"sha256",QString::fromLatin1(QCryptographicHash::hash(bytes,QCryptographicHash::Sha256).toHex())},
            {"base64",retained ? QVariant(QString::fromLatin1(bytes.toBase64())) : QVariant()},
            {"readerCreated",QVariant()},{"runEntered",QVariant()},{"runReturned",QVariant()},
            {"queued",QVariant()},{"invokeReturned",QVariant()},{"invokeAccepted",QVariant()},
            {"deliveryEntered",QVariant()},{"deliveryReturned",QVariant()}};
        _rows.append(row);return row.id;
    }
    void reader(const QString& id,const std::shared_ptr<void>& holder) {
        if (id.isEmpty()) {return;}QMutexLocker lock(&_mutex);auto row=find(id);
        if (!row || !holder || row->readerKnown || row->value.value("kind")!="model") {_complete=false;return;}
        row->readerKnown=true;row->holder=holder;row->value["readerCreated"]=stamp();
    }
    class Body {
    public:
        Body(const QString& id,bool delivery=false) : _id(id),_delivery(delivery) {if (!_id.isEmpty()) {shared().body(_id,_delivery,false);}}
        ~Body() {if (!_id.isEmpty()) {shared().body(_id,_delivery,true);}}
        Body(const Body&)=delete;Body& operator=(const Body&)=delete;
    private:QString _id;bool _delivery;
    };
    template<class T> void queued(const QString& id,const std::shared_ptr<T>& model) {
        if (id.isEmpty()) {return;}QMutexLocker lock(&_mutex);auto row=find(id);
        if (!row || !model || row->modelKnown || row->value.value("runEntered").isNull()) {_complete=false;return;}
        row->modelKnown=true;row->model=model;row->value["queued"]=stamp();
    }
    void invokeReturned(const QString& id,bool accepted) {
        if (id.isEmpty()) {return;}QMutexLocker lock(&_mutex);auto row=find(id);
        if (!row || !row->modelKnown || !row->value.value("invokeReturned").isNull()) {_complete=false;return;}
        row->value["invokeReturned"]=stamp();row->value["invokeAccepted"]=accepted;
    }
    template<class T> QString delivery(Resource* resource,const std::shared_ptr<T>& model) {
        if (!enabled() || !resource || !model) {return {};}
        QMutexLocker lock(&_mutex);QString id;
        // Match the original queued argument's live shared ownership and actual
        // receiving resource, never its current URL or a wanted UUID.
        const std::shared_ptr<const void> actual=model;
        for (auto& row:_rows) {
            if (!row.modelKnown || row.resource.toStrongRef().data()!=resource || row.model.expired()
                    || row.model.owner_before(actual) || actual.owner_before(row.model)) {continue;}
            if (!id.isEmpty() || !row.value.value("deliveryEntered").isNull()) {_complete=false;return {};}
            id=row.id;
        }
        return id;
    }
    QVariantMap snapshot() {
        if (!enabled()) {return {};}QMutexLocker lock(&_mutex);QVariantList rows;
        for (const auto& row:_rows) {
            auto value=row.value;value["resourceAlive"]=!row.resource.isNull();value["readerKnown"]=row.readerKnown;
            value["readerAlive"]=row.readerKnown && !row.holder.expired();value["modelKnown"]=row.modelKnown;
            value["parsedModelAlive"]=row.modelKnown && !row.model.expired();rows.append(value);
        }
        return {{"assetModelOriginHistoryVersion",1},{"instance",_instance},{"complete",_complete},{"clock",stamp()},{"downloads",rows}};
    }
private:
    struct Row {QString id;QWeakPointer<Resource> resource;std::weak_ptr<void> holder;std::weak_ptr<const void> model;
        bool readerKnown{false},modelKnown{false};QVariantMap value;};
    IOSAssetsModelOrigin() {_clock.start();}
    static QString nonce() {return QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');}
    QVariantMap stamp() const {return {{"epochMs",QDateTime::currentMSecsSinceEpoch()},{"monotonicMs",_clock.elapsed()}};}
    Row* find(const QString& id) {for (auto& row:_rows) {if (row.id==id) {return &row;}}return nullptr;}
    void body(const QString& id,bool delivery,bool returned) {
        QMutexLocker lock(&_mutex);auto row=find(id);const auto field=delivery ? (returned ? "deliveryReturned" : "deliveryEntered") : (returned ? "runReturned" : "runEntered");
        const auto entered=delivery ? "deliveryEntered" : "runEntered";
        if (!row || !row->readerKnown || (delivery && !row->modelKnown) || !row->value.value(field).isNull()
                || (returned && row->value.value(entered).isNull())) {_complete=false;return;}
        row->value[field]=stamp();
    }
    QMutex _mutex;QVector<Row> _rows;bool _complete{true};qint64 _bytes{0};QElapsedTimer _clock;QString _instance{nonce()};
};
} // namespace overte::e2e
#endif
