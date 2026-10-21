// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
#include "TabletHttpObservationBridge.h"
#include <QCryptographicHash>
#include <QJSValue>
#include <QJSValueIterator>
#include <QJsonArray>
#include <QJsonDocument>
#include <QQuickItem>
#include <QQmlContext>
#include <QQmlEngine>
#include <QUuid>
#include <algorithm>
#include <memory>
#include <cmath>
#include <QHash>

namespace overte::e2e {
// Original QML callback maps and actual XHR/reply weak ownership. No request,
// cancellation, navigation, callback delivery or product decision lives here.
class TabletHttpObservation {
public:
    void observeTree(QObject* root) {
        if (!gui()) { _complete=false;return; }
        _container=root;QSet<QObject*> seen;int count {0};
        std::function<void(QObject*,int)> walk=[&](QObject* node,int depth) {
            if (!node || !_complete) { return; }
            if (++count>4096 || depth>128 || node->thread()!=QCoreApplication::instance()->thread()
                    || seen.contains(node)) { _complete=false;return; }
            seen.insert(node);
            if (QString::fromLatin1(node->metaObject()->className()).startsWith("RootHttpRequest_QMLTYPE_")) {
                registerRoot(node);
            }
            for (auto child:node->children()) { walk(child,depth+1); }
        };
        if (root) { walk(root,0); }
        _inTree=seen;
    }
    QString begin(QObject* root,const QVariantMap& message) {
        if (!gui() || !tabletHttpEnabled()) { return {}; }
        observeTree(root);
        const auto object=QJsonObject::fromVariantMap(message);const auto id=object.value("id");
        if (!_complete || !id.isDouble() || !std::isfinite(id.toDouble()) || id.toDouble()<0
                || id.toDouble()>1000000000 || std::floor(id.toDouble())!=id.toDouble()
                || object.value("method")!=QJsonValue("http.request") || !object.contains("params")
                || _rows.size()>=512) { _complete=false;return {}; }
        Root* selected {nullptr};
        const auto key=QString::number(static_cast<qlonglong>(id.toDouble()));
        for (auto& source:_roots) {
            if (!source.helper || !_inTree.contains(source.helper.data())) { continue; }
            const auto calls=callbackMap(source);
            if (!calls.isObject()) { _complete=false;return {}; }
            if (calls.property(key).isCallable()) {
                if (selected) { _complete=false;return {}; }selected=&source;
            }
        }
        if (!selected) { _complete=false;return {}; }
        for (const auto& row:_rows) {
            if (row.rootId==selected->id && row.qmlId==id.toDouble()) { _complete=false;return {}; }
        }
        Row value;value.id=nonce();value.rootId=selected->id;value.qmlId=static_cast<qlonglong>(id.toDouble());
        value.params=hash(QJsonDocument(QJsonArray{object.value("params")}).toJson(QJsonDocument::Compact));
        value.queued=QDateTime::currentMSecsSinceEpoch();_indices.insert(value.id,_rows.size());_rows.append(value);
        return value.id;
    }
    void event(const TabletHttpEvent& event) {
        if (!gui() || !_indices.contains(event.lease) || _events>=8192) { _complete=false;return; }
        auto& row=_rows[_indices.value(event.lease)];
        const auto received=QDateTime::currentMSecsSinceEpoch();
        const QSet<QString> kinds {"bound","state","callback-enter","callback-exit","destroying","destroyed","reply","reply-destroyed"};
        if (!kinds.contains(event.kind) || event.occurredEpochMs<row.queued || event.occurredEpochMs>received
                || row.events.size()>=128 || (row.destroyed && event.kind!="reply-destroyed")) { _complete=false;return; }
        if (event.kind=="bound") {
            if (row.bound || event.state.isEmpty()) { _complete=false;return; }
            row.bound=true;row.request=event.request;
        } else if (!row.bound) { _complete=false;return; }
        if (event.kind=="reply") {
            if (!QRegularExpression("\\A[0-9a-f]{32}\\z").match(event.replyId).hasMatch()
                    || !QRegularExpression("\\A[0-9a-f]{64}\\z").match(event.urlSha256).hasMatch()
                    || row.replies.size()>=8) { _complete=false;return; }
            for (const auto& reply:row.replies) { if (reply.id==event.replyId) { _complete=false;return; } }
            row.replies.append({event.replyId,event.reply,event.occurredEpochMs,event.urlSha256,false});
        } else if (event.kind=="reply-destroyed") {
            Reply* selected {nullptr};
            for (auto& reply:row.replies) { if (reply.id==event.replyId) { selected=&reply; } }
            if (!selected || selected->destroyed || selected->object) { _complete=false;return; }
            selected->destroyed=true;
        } else if (event.kind=="destroyed") {
            if (row.request) { _complete=false;return; }row.destroyed=true;
        }
        if (!event.state.isEmpty()) { row.state=event.state; }
        row.events.append(QVariantMap{{"sequence",static_cast<qulonglong>(++_events)},
            {"kind",event.kind},{"occurredEpochMs",event.occurredEpochMs},{"receivedEpochMs",received},
            {"state",event.state.isEmpty() ? QVariant() : QVariant(event.state)},
            {"replyId",event.replyId.isEmpty() ? QVariant() : QVariant(event.replyId)}});
    }
    QVariantMap snapshot(const QVariantMap& command) {
        if (!gui() || !tabletHttpCommand(command) || _nonces.contains(command.value("commandId").toString()) || _nonces.size()>=4096) { return {}; }
        _nonces.insert(command.value("commandId").toString());observeTree(_container);
        QVariantList roots,requests;
        for (const auto& source:_roots) {
            QVariant callbacks;
            if (source.helper) {
                const auto calls=callbackMap(source);QVariantList ids;
                if (!calls.isObject()) { _complete=false; }
                else {
                    QJSValueIterator iterator(calls);
                    while (iterator.hasNext()) {
                        if (ids.size()>=512) { _complete=false;break; }
                        iterator.next();bool okay {false};const auto id=iterator.name().toLongLong(&okay);
                        if (!okay || id<0 || id>1000000000 || !iterator.value().isCallable()) { _complete=false;break; }
                        bool known {false};
                        for (const auto& row:_rows) { known=known || row.rootId==source.id && row.qmlId==id; }
                        if (!known) { _complete=false; }
                        ids.append(id);
                    }
                    std::sort(ids.begin(),ids.end(),[](const QVariant& a,const QVariant& b) { return a.toLongLong()<b.toLongLong(); });
                    callbacks=ids;
                }
            }
            roots.append(QVariantMap{{"id",source.id},{"sourceSha256",source.source},
                {"helperAlive",bool(source.helper)},{"rootAlive",bool(source.root)},
                {"inCurrentTree",source.helper && _inTree.contains(source.helper.data())},{"callbackIds",callbacks},
                {"callbackDepth",source.helper ? source.helper->property("featureCallbackDepth") : QVariant()}});
        }
        for (const auto& row:_rows) {
            QVariantList replies;
            for (const auto& reply:row.replies) {
                replies.append(QVariantMap{{"id",reply.id},{"createdEpochMs",reply.created},{"urlSha256",reply.url},{"alive",bool(reply.object)},{"destroyed",reply.destroyed}});
            }
            requests.append(QVariantMap{{"id",row.id},{"rootId",row.rootId},{"qmlRequestId",row.qmlId},
                {"paramsSha256",row.params},{"queuedEpochMs",row.queued},{"events",row.events},
                {"bound",row.bound},{"requestAlive",row.bound ? QVariant(bool(row.request)) : QVariant()},
                {"state",row.state.isEmpty() ? QVariant() : QVariant(row.state)},{"replies",replies},{"destroyed",row.destroyed}});
        }
        QVariantMap result {{"tabletHttpVersion",1},{"commandId",command.value("commandId")},{"runId",command.value("runId")},
            {"instance",_instance},{"sequence",static_cast<qulonglong>(++_sequence)},
            {"processId",QCoreApplication::applicationPid()},{"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()},
            {"complete",_complete},{"containerPresent",bool(_container)},{"roots",roots},{"requests",requests}};
        if (QJsonDocument::fromVariant(result).toJson(QJsonDocument::Compact).size()>262144) { return {}; }
        return result;
    }
private:
    struct Root {QString id,source;QPointer<QObject> helper,root;};
    struct Reply {QString id;QPointer<QObject> object;qint64 created;QString url;bool destroyed {false};};
    struct Row {QString id,rootId,params;qlonglong qmlId {0};qint64 queued {0};
        bool bound {false},destroyed {false};QPointer<QObject> request;QVariantMap state;QVariantList events;QList<Reply> replies;};
    static bool gui() { return QCoreApplication::instance() && QThread::currentThread()==QCoreApplication::instance()->thread(); }
    static QString nonce() { return QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-'); }
    static QString hash(const QByteArray& bytes) { return QString::fromLatin1(QCryptographicHash::hash(bytes,QCryptographicHash::Sha256).toHex()); }
    QJSValue callbackMap(const Root& source) {
        if (!source.helper || !source.root || source.helper->parent()!=source.root || source.helper->thread()!=QCoreApplication::instance()->thread()) {
            _complete=false;return {};
        }
        const auto value=source.helper->property("httpCalls");
        if (value.userType()!=qMetaTypeId<QJSValue>()) { _complete=false;return {}; }
        return value.value<QJSValue>();
    }
    void registerRoot(QObject* helper) {
        for (const auto& source:_roots) { if (source.helper==helper) { return; } }
        if (_roots.size()>=128 || !helper->parent() || !qmlContext(helper->parent())) { _complete=false;return; }
        if (!helper->setProperty("featureObservationEnabled",true)
                || helper->property("featureCallbackDepth").userType()!=QMetaType::Int) { _complete=false;return; }
        _roots.append({nonce(),hash(qmlContext(helper->parent())->baseUrl().toEncoded(QUrl::FullyEncoded)),helper,helper->parent()});
    }
    QString _instance {nonce()};bool _complete {true};quint64 _sequence {0},_events {0};
    QPointer<QObject> _container;QList<Root> _roots;QList<Row> _rows;QHash<QString,int> _indices;
    QSet<QString> _nonces;QSet<QObject*> _inTree;
};
inline TabletHttpProvider ensureTabletHttpProvider(QObject* root) {
    if (!tabletHttpEnabled() || QThread::currentThread()!=QCoreApplication::instance()->thread()) { return {}; }
    const auto existing=QCoreApplication::instance()->property(tabletHttpProperty());
    if (existing.userType()==qMetaTypeId<TabletHttpProvider>()) {
        auto provider=existing.value<TabletHttpProvider>();if (provider.observeTree) { provider.observeTree(root); }return provider;
    }
    const auto source=std::make_shared<TabletHttpObservation>();
    TabletHttpProvider provider;
    provider.observeTree=[source](QObject* root) { source->observeTree(root); };
    provider.begin=[source](QObject* root,const QVariantMap& message) { return source->begin(root,message); };
    provider.event=[source](const TabletHttpEvent& event) { source->event(event); };
    provider.snapshot=[source](const QVariantMap& command) { return source->snapshot(command); };
    QCoreApplication::instance()->setProperty(tabletHttpProperty(),QVariant::fromValue(provider));source->observeTree(root);
    return provider;
}
inline QVariant observeTabletHttpMessage(QObject* root,const QVariant& original) {
    auto message=original.toMap();if (message.value("method").toString()!="http.request") { return original; }
    const auto provider=ensureTabletHttpProvider(root);
    const auto lease=provider.begin ? provider.begin(root,message) : QString();
    if (!lease.isEmpty()) { message.insert("_overteE2ETabletHttpLease",lease);return message; }
    return original;
}
}
#endif
