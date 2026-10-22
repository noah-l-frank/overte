// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
#include "NavigationDirectoryBridge.h"
#include "NormalPlacesControls.h"
#include <QMetaMethod>
#include <QSet>
#include <QUuid>
#include <memory>

namespace overte::e2e {
// GUI-owned passive provenance: actual responseText read -> unchanged original
// sendToQml queue -> actual original root.records notify. No product mutation.
class NavigationDirectoryObservation {
public:
    explicit NavigationDirectoryObservation(QObject* receiver) : _receiver(receiver) { }
    void watch(QQuickItem* root,const QJsonObject& frame) {
        if (!gui()) { _valid=false;return; }
        _frame=frame;_current=root;
        if (!root) { _currentId.clear();return; }
        if (placesComponent(root).isEmpty()) { _valid=false;return; }
        QJsonObject page;
        for (const auto& row:frame.value("controls").toArray()) {
            if (row.toObject().value("id")=="places.page") { if (!page.isEmpty()) { _valid=false;return; }page=row.toObject(); }
        }
        const auto id=page.value("rootInstance").toString();
        if (!identifier(id) || !_receiver || _roots.size()>=128 && !_roots.contains(id)) { _valid=false;return; }
        _currentId=id;
        if (_roots.contains(id)) {
            if (_roots[id].root!=root) { _valid=false;return; }
            _roots[id].frameRevision=_roots[id].revision;return;
        }
        const auto signal=root->metaObject()->indexOfSignal("recordsChanged()");
        const auto slot=_receiver->metaObject()->indexOfSlot("featurePlacesRecordsChanged()");
        if (signal<0 || slot<0 || !QObject::connect(root,root->metaObject()->method(signal),_receiver,
                _receiver->metaObject()->method(slot),Qt::DirectConnection)) { _valid=false;return; }
        Root value;value.root=root;value.source=page.value("componentSourceSha256").toString();_roots.insert(id,value);
    }
    void event(const NavigationDirectoryEvent& event) {
        if (!gui() || !_valid || !event.sourceThread || event.epoch<=0 || event.epoch>QDateTime::currentMSecsSinceEpoch()) { _valid=false;return; }
        if (event.kind=="read") {
            const auto id=event.facts.value("readId").toString();
            if (!identifier(id) || event.facts.value("readEpochMs").toLongLong()>event.epoch || _reads.contains(id) || _reads.size()>=128) { _valid=false;return; }
            _reads.insert(id,event.facts);_threads[id]=event.sourceThread;_order.append(id);return;
        }
        if (event.kind!="outgoing") { _valid=false;return; }
        const auto message=QJsonObject::fromVariantMap(event.message.toMap());
        if (!message.value("data").isArray()) { return; }
        const auto data=message.value("data").toArray();
        if (data.size()>256) { _valid=false;return; }
        QString selected;
        for (auto i=_order.crbegin();i!=_order.crend();++i) {
            if (_threads.value(*i)!=event.sourceThread) { continue; }
            const auto read=_reads.value(*i);
            if (read.value("readEpochMs").toLongLong()>event.epoch) { _valid=false;return; }
            int matches{0};
            for (const auto& raw:data) {
                const auto row=raw.toObject();
                if (placesHash(row.value("id").toString())==read.value("idSha256").toString()
                        && placesHash(row.value("name").toString())==read.value("nameSha256").toString()
                        && placesHash(row.value("address").toString())==read.value("addressSha256").toString()) { ++matches; }
            }
            if (matches==1) { selected=*i;break; }
        }
        if (selected.isEmpty()) { return; }
        if (_messages.size()>=128) { _valid=false;return; }
        const auto id=nonce();
        _messages.append(QVariantMap{{"messageId",id},{"readId",selected},{"outgoingEpochMs",event.epoch},
            {"recordsSha256",dataHash(data)},{"targetRootId",_currentId},{"deliveredRootId",QVariant()},{"deliveredEpochMs",QVariant()}});
    }
    void changed(QQuickItem* root) {
        if (!gui() || !_valid || !root || root!=_current || _currentId.isEmpty()) { return; }
        auto& original=_roots[_currentId];
        const auto records=QJsonValue::fromVariant(placesVariant(root->property("records")));
        if (!records.isArray() || records.toArray().size()>256) { _valid=false;return; }
        const auto digest=dataHash(records.toArray());const auto now=QDateTime::currentMSecsSinceEpoch();
        // Same-thread queued ordering preserves the original outgoing call.
        // Exact original array identity/content and target root are required;
        // a later UI search rebuild cannot manufacture a records notification.
        for (auto& raw:_messages) {
            auto message=raw.toMap();
            if (!message.value("deliveredRootId").isNull() || message.value("targetRootId").toString()!=_currentId
                    || message.value("recordsSha256").toString()!=digest) { continue; }
            if (now<message.value("outgoingEpochMs").toLongLong()) { _valid=false;return; }
            message["deliveredRootId"]=_currentId;message["deliveredEpochMs"]=now;raw=message;
            original.lastMessage=message.value("messageId").toString();original.recordsHash=digest;++original.revision;return;
        }
        // Unowned/new records remain visible but cannot borrow old provenance.
        original.lastMessage.clear();original.recordsHash=digest;++original.revision;
    }
    QVariantMap snapshot(const QVariantMap& request) {
        const auto object=QJsonObject::fromVariantMap(request);const auto keys=object.keys();
        if (!gui() || !_valid || QSet<QString>(keys.begin(),keys.end())!=QSet<QString>{"schemaVersion","commandId","action","runId"}
                || object.value("schemaVersion")!=QJsonValue(1) || object.value("action")!="feature-navigation-directory"
                || !identifier(object.value("commandId").toString()) || !identifier(object.value("runId").toString())
                || _queries.size()>=4096 || _queries.contains(object.value("commandId").toString())) { return {}; }
        const auto now=QDateTime::currentMSecsSinceEpoch();
        const auto uiEpoch=static_cast<qint64>(_frame.value("updatedEpochMs").toDouble());
        if (now<=0 || now<_epoch) { _valid=false;return {}; }
        if (!uiEpoch || now<uiEpoch || now-uiEpoch>1500) { return {}; }
        _epoch=now;_queries.insert(object.value("commandId").toString());QVariantList reads,roots;
        for (const auto& id:_order) { reads.append(_reads.value(id)); }
        for (auto i=_roots.cbegin();i!=_roots.cend();++i) {
            roots.append(QVariantMap{{"rootId",i.key()},{"alive",!i->root.isNull()},
                {"current",i->root && i->root==_current},{"sourceSha256",i->source},
                {"revision",static_cast<qulonglong>(i->revision)},{"frameRevision",static_cast<qulonglong>(i->frameRevision)},{"lastMessageId",i->lastMessage.isEmpty()?QVariant():QVariant(i->lastMessage)},
                {"recordsSha256",i->recordsHash.isEmpty()?QVariant():QVariant(i->recordsHash)}});
        }
        return {{"navigationDirectoryVersion",1},{"commandId",request.value("commandId")},{"runId",request.value("runId")},
            {"instance",_instance},{"sequence",static_cast<qulonglong>(++_sequence)},{"processId",QCoreApplication::applicationPid()},
            {"capturedEpochMs",now},{"ui",QVariantMap{{"bridgeId",_frame.value("bridgeId").toString()},
                {"generation",_frame.value("generation").toString()},{"sequence",_frame.value("lastCommandSequence").toVariant()},
                {"elapsedMs",_frame.value("elapsedMs").toVariant()},{"observedEpochMs",uiEpoch}}},
            {"reads",reads},{"messages",_messages},{"roots",roots}};
    }
private:
    struct Root { QPointer<QQuickItem> root;QString source,lastMessage,recordsHash;quint64 revision{0},frameRevision{0}; };
    static bool gui() { return navigationDirectoryEnabled() && QThread::currentThread()==QCoreApplication::instance()->thread(); }
    static bool identifier(const QString& value) { return QRegularExpression("\\A[0-9a-f]{32}\\z").match(value).hasMatch(); }
    static QString nonce() { return QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-'); }
    static QString dataHash(const QJsonArray& value) { return QString::fromLatin1(QCryptographicHash::hash(QJsonDocument(value).toJson(QJsonDocument::Compact),QCryptographicHash::Sha256).toHex()); }
    QPointer<QObject> _receiver;QPointer<QQuickItem> _current;QString _currentId,_instance{nonce()};QJsonObject _frame;
    QHash<QString,Root> _roots;QHash<QString,QVariantMap> _reads;QHash<QString,QPointer<QThread>> _threads;QStringList _order;
    QVariantList _messages;QSet<QString> _queries;qint64 _epoch{0};quint64 _sequence{0};bool _valid{true};
};
inline void ensureNavigationDirectoryProvider(QObject* receiver) {
    if (!navigationDirectoryEnabled() || QThread::currentThread()!=QCoreApplication::instance()->thread()) { return; }
    const auto previous=QCoreApplication::instance()->property(navigationDirectoryProperty());
    if (previous.isValid()) { return; }
    auto source=std::make_shared<NavigationDirectoryObservation>(receiver);NavigationDirectoryProvider provider;
    provider.event=[source](const NavigationDirectoryEvent& event) { source->event(event); };
    provider.watch=[source](QQuickItem* root,const QJsonObject& frame) { source->watch(root,frame); };
    provider.changed=[source](QQuickItem* root) { source->changed(root); };
    provider.snapshot=[source](const QVariantMap& request) { return source->snapshot(request); };
    QCoreApplication::instance()->setProperty(navigationDirectoryProperty(),QVariant::fromValue(provider));
}
}
#endif
