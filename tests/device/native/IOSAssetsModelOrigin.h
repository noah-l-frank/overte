// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include "NativeReadBracket.h"
#include <ResourceCache.h>
#include <QCryptographicHash>
#include <QMutex>
#include <QMutexLocker>
#include <QPointer>
#include <QSet>
#include <QStringList>
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
        if (!main() || _rows.size()>=64 || resource.isNull() || requested.toEncoded().size()>4096 || effective.toEncoded().size()>4096) {_complete=false;return {};}
        Row row;row.id=nonce();row.resource=resource;row.object=resource.toStrongRef().data();
        if (row.object.isNull()) {_complete=false;return {};}
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
        if (!main()) {_complete=false;return {};}
        // Match the original queued argument's live shared ownership and actual
        // receiving resource, never its current URL or a wanted UUID.
        const std::shared_ptr<const void> actual=model;
        for (auto& row:_rows) {
            if (!row.modelKnown || row.object.data()!=resource || row.model.expired()
                    || row.model.owner_before(actual) || actual.owner_before(row.model)) {continue;}
            if (!id.isEmpty() || !row.value.value("deliveryEntered").isNull()) {_complete=false;return {};}
            id=row.id;
        }
        return id;
    }
    struct Consumer {QString kind;int slot;std::weak_ptr<const void> holder;};
    QString geometry(const QString& reader,const QStringList& mappings,const std::shared_ptr<void>& holder,const QString& kind,
            const QVector<Consumer>& consumers) {
        if (!enabled() || reader.isEmpty()) {return {};}QMutexLocker lock(&_mutex);auto source=find(reader);
        // Copy construction can occur off the main thread. Only weak standard
        // ownership and immutable lineage are inspected here, never QObjects.
        if (!source || source->value.value("kind")!="model" || !source->modelKnown || !holder
                || mappings.size()>8 || consumers.size()>256
                || (kind!="resource" && kind!="mapping-resource" && kind!="copy")) {_complete=false;return {};}
        QSet<QString> seen;
        for (const auto& id:mappings) {
            const auto row=find(id);
            if (!row || row->value.value("kind")!="mapping" || seen.contains(id)) {_complete=false;return {};}
            seen.insert(id);
        }
        GeometryRow* geometry=nullptr;
        for (auto& row:_geometries) {
            if (row.reader==reader && row.mappings==mappings
                    && !row.holder.owner_before(holder) && !holder.owner_before(row.holder)) {geometry=&row;break;}
        }
        if (!geometry) {
            if (_geometries.size()>=128) {_complete=false;return {};}
            GeometryRow row;row.reader=reader;row.mappings=mappings;row.kind=kind;row.holder=holder;
            row.value={{"id",nonce()},{"readerId",reader},{"mappingIds",mappings},{"kind",kind},{"born",stamp()},
                {"destructionObserved",QVariant()}};
            _geometries.append(row);geometry=&_geometries.last();
        }
        const auto geometryId=geometry->value.value("id").toString();
        QSet<QString> slots;
        for (const auto& consumer:consumers) {
            const auto slot=consumer.kind+":"+QString::number(consumer.slot);
            if ((consumer.kind!="mesh" && consumer.kind!="material") || consumer.slot<0 || consumer.slot>=256
                    || consumer.holder.expired() || slots.contains(slot)) {_complete=false;return {};}
            slots.insert(slot);bool known=false;
            for (const auto& row:_consumers) {
                if (row.geometry==geometryId && row.kind==consumer.kind && row.slot==consumer.slot
                        && !row.holder.owner_before(consumer.holder) && !consumer.holder.owner_before(row.holder)) {known=true;break;}
            }
            if (known) {continue;}
            if (_consumers.size()>=256) {_complete=false;return {};}
            ConsumerRow row;row.geometry=geometryId;row.kind=consumer.kind;row.slot=consumer.slot;row.holder=consumer.holder;
            row.value={{"id",nonce()},{"geometryId",geometryId},{"kind",consumer.kind},{"slot",consumer.slot},
                {"born",stamp()},{"ownershipExpiryObserved",QVariant()}};
            _consumers.append(row);
        }
        return geometryId;
    }
    // Callbacks enter here while the Material mutex is held. No registry path
    // calls back into Material; arguments retain no product owner after return.
    void texture(const QString& geometry,int slot,int channel,const std::shared_ptr<const void>& map,
            const std::shared_ptr<const void>& source) {
        QMutexLocker lock(&_mutex);
        if (!_complete) {return;}
        bool known=false;
        for (const auto& row:_geometries) {if (row.value.value("id")==geometry) {known=true;break;}}
        if (!known || slot<0 || slot>=256 || channel<-1 || channel>=256
                || (channel==-1 && (map || source)) || (!map && source) || _textureRevision>=1048576) {
            _complete=false;return;
        }
        const auto observed=stamp();++_textureRevision;
        // A -1 marker records initial/copy/assignment snapshots, including
        // empty maps. Repeated identities still advance the mutation revision.
        const auto mapId=textureNode("map",map,observed);
        const auto sourceId=textureNode("source",source,observed);
        if (!_complete) {return;}
        for (auto& row:_textureLinks) {
            if (row.geometry==geometry && row.slot==slot && row.channel==channel && row.map==mapId && row.source==sourceId) {
                row.value["lastObserved"]=observed;row.value["revision"]=_textureRevision;return;
            }
        }
        if (_textureLinks.size()>=512) {_complete=false;return;}
        TextureLink row;row.geometry=geometry;row.slot=slot;row.channel=channel;row.map=mapId;row.source=sourceId;
        row.value={{"id",nonce()},{"geometryId",geometry},{"materialSlot",slot},{"channel",channel},
            {"mapId",mapId},{"sourceId",sourceId},{"born",observed},{"lastObserved",observed},{"revision",_textureRevision}};
        _textureLinks.append(row);
    }
    void textureIncomplete() noexcept {
        QMutexLocker lock(&_mutex);_complete=false;
    }
    QVariantMap snapshot() {
        if (!enabled() || !main()) {return {};}QMutexLocker lock(&_mutex);QVariantList rows,geometries,consumers,textures,textureLinks;
        for (const auto& row:_rows) {
            // Resource::allReferencesCleared may recreate shared ownership for
            // the same cached QObject. The original weak lease and actual
            // QObject lifetime must remain independent observations.
            auto value=row.value;value["resourceAlive"]=!row.resource.isNull();value["resourceObjectAlive"]=!row.object.isNull();value["readerKnown"]=row.readerKnown;
            value["readerAlive"]=row.readerKnown && !row.holder.expired();value["modelKnown"]=row.modelKnown;
            value["parsedModelAlive"]=row.modelKnown && !row.model.expired();rows.append(value);
        }
        for (auto& row:_geometries) {
            const bool alive=!row.holder.expired();
            if (!alive && row.value.value("destructionObserved").isNull()) {row.value["destructionObserved"]=stamp();}
            auto value=row.value;value["alive"]=alive;geometries.append(value);
        }
        for (auto& row:_consumers) {
            // weak_ptr expiry reports zero strong owners, not completion of a
            // destructor, renderer command, GPU fence or backend allocation.
            const bool alive=!row.holder.expired();
            if (!alive && row.value.value("ownershipExpiryObserved").isNull()) {row.value["ownershipExpiryObserved"]=stamp();}
            auto value=row.value;value["strongOwnersAlive"]=alive;consumers.append(value);
        }
        for (auto& row:_textures) {
            const bool alive=!row.holder.expired();
            if (!alive && row.value.value("ownershipExpiryObserved").isNull()) {row.value["ownershipExpiryObserved"]=stamp();}
            auto value=row.value;value["strongOwnersAlive"]=alive;textures.append(value);
        }
        for (const auto& row:_textureLinks) {textureLinks.append(row.value);}
        return {{"assetModelOriginHistoryVersion",5},{"instance",_instance},{"complete",_complete},{"clock",stamp()},
            {"downloads",rows},{"geometries",geometries},
            {"consumerOwnership",QVariantMap{{"assetModelConsumerOwnershipVersion",1},{"rows",consumers}}},
            {"textureOwnership",QVariantMap{{"assetModelTextureOwnershipVersion",1},{"revision",_textureRevision},
                {"nodes",textures},{"links",textureLinks}}}};
    }
private:
    struct GeometryRow {QString reader,kind;QStringList mappings;std::weak_ptr<void> holder;QVariantMap value;};
    struct ConsumerRow {QString geometry,kind;int slot;std::weak_ptr<const void> holder;QVariantMap value;};
    struct TextureNode {QString kind,id;std::weak_ptr<const void> holder;QVariantMap value;};
    struct TextureLink {QString geometry,map,source;int slot,channel;QVariantMap value;};
    struct Row {QString id;QWeakPointer<Resource> resource;QPointer<Resource> object;std::weak_ptr<void> holder;std::weak_ptr<const void> model;
        bool readerKnown{false},modelKnown{false};QVariantMap value;};
    IOSAssetsModelOrigin() {_clock.start();}
    static bool main() {const auto app=QCoreApplication::instance();return app && QThread::currentThread()==app->thread();}
    static QString nonce() {return QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');}
    QString textureNode(const QString& kind,const std::shared_ptr<const void>& holder,const QVariantMap& born) {
        if (!holder) {return {};}
        for (const auto& row:_textures) {
            if (row.kind==kind && !row.holder.owner_before(holder) && !holder.owner_before(row.holder)) {return row.id;}
        }
        if (_textures.size()>=256) {_complete=false;return {};}
        TextureNode row;row.kind=kind;row.id=nonce();row.holder=holder;
        row.value={{"id",row.id},{"kind",kind},{"born",born},{"ownershipExpiryObserved",QVariant()}};
        _textures.append(row);return row.id;
    }
    QVariantMap stamp() const {return {{"epochMs",QDateTime::currentMSecsSinceEpoch()},{"monotonicMs",_clock.elapsed()}};}
    Row* find(const QString& id) {for (auto& row:_rows) {if (row.id==id) {return &row;}}return nullptr;}
    void body(const QString& id,bool delivery,bool returned) {
        QMutexLocker lock(&_mutex);auto row=find(id);const auto field=delivery ? (returned ? "deliveryReturned" : "deliveryEntered") : (returned ? "runReturned" : "runEntered");
        const auto entered=delivery ? "deliveryEntered" : "runEntered";
        if (!row || !row->readerKnown || (delivery && !row->modelKnown) || !row->value.value(field).isNull()
                || (returned && row->value.value(entered).isNull())) {_complete=false;return;}
        row->value[field]=stamp();
    }
    QMutex _mutex;QVector<Row> _rows;QVector<GeometryRow> _geometries;QVector<ConsumerRow> _consumers;
    QVector<TextureNode> _textures;QVector<TextureLink> _textureLinks;qint64 _textureRevision{0};
    bool _complete{true};qint64 _bytes{0};QElapsedTimer _clock;QString _instance{nonce()};
};
} // namespace overte::e2e
#endif
