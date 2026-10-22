// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
#include "NormalPlacesControls.h"
#include <QQuickWindow>
#include <QDateTime>
#include <functional>

namespace overte::e2e {
// Original GUI root lifetimes, including hidden retained pages. No root creation,
// property setter, handler call, strong QObject ownership or inferred destruction.
class NavigationPanelsObservation {
public:
    void observe(QQuickItem* root,QQuickWindow* window,const QJsonObject& frame) {
        if (!enabled()) { return; }
        _frame=frame;_root=root;_window=window;_current.clear();_complete=false;
        const auto now=epoch();if (!now) { return; }
        if (!root) { _complete=!frame.value("open").toBool();return; }
        if (root->thread()!=QCoreApplication::instance()->thread() || !window
                || window->thread()!=root->thread() || root->window()!=window) { _valid=false;return; }
        int count{0};
        std::function<void(QQuickItem*,int)> walk=[&](QQuickItem* item,int depth) {
            if (!item || !_valid) { return; }
            if (++count>4096 || depth>128 || item->thread()!=root->thread()) { _valid=false;return; }
            QString profile,source=placesComponent(item);
            if (!source.isEmpty()) { profile="pico-places-v1"; }
            else {
                source=addressComponent(item);
                if (!source.isEmpty()) { profile="pico-address-v1"; }
            }
            if (!profile.isEmpty()) {
                QString id;
                for (auto i=_rows.cbegin();i!=_rows.cend();++i) { if (i->root && i->root==item) { id=i.key();break; } }
                const auto digest=placesHash(source);
                if (id.isEmpty()) {
                    if (_rows.size()>=128) { _valid=false;return; }
                    id=profile=="pico-places-v1" ? placesRootInstance(item) : nonce();
                    if (!identifier(id) || _rows.contains(id)) { _valid=false;return; }
                    Row row;row.root=item;row.profile=profile;row.source=digest;row.first=now;_rows.insert(id,row);
                } else if (_rows[id].profile!=profile || _rows[id].source!=digest) { _valid=false;return; }
                _current.insert(id);
            }
            for (auto child:item->childItems()) { walk(child,depth+1); }
        };
        walk(root,0);_complete=_valid;
    }
    QVariantMap snapshot(const QVariantMap& request) {
        const auto object=QJsonObject::fromVariantMap(request);const auto keys=object.keys();
        if (!enabled() || !_valid || !_complete || QSet<QString>(keys.begin(),keys.end())!=QSet<QString>{"schemaVersion","commandId","action","runId"}
                || object.value("schemaVersion")!=QJsonValue(1) || object.value("action")!=QJsonValue("feature-navigation-panels")
                || !object.value("commandId").isString() || !identifier(object.value("commandId").toString())
                || !object.value("runId").isString() || !identifier(object.value("runId").toString())
                || _queries.size()>=4096 || _queries.contains(object.value("commandId").toString())) { return {}; }
        const auto now=epoch(),observed=static_cast<qint64>(_frame.value("updatedEpochMs").toDouble());
        if (!now || !observed || now<observed || now-observed>1500) { return {}; }
        _queries.insert(object.value("commandId").toString());QVariantList roots;
        for (auto i=_rows.cbegin();i!=_rows.cend();++i) {
            if (i->root && i->root->thread()!=QCoreApplication::instance()->thread()) { _valid=false;return {}; }
            roots.append(QVariantMap{{"rootId",i.key()},{"profile",i->profile},{"sourceSha256",i->source},
                {"firstObservedEpochMs",i->first},{"alive",!i->root.isNull()},
                {"inCurrentTree",i->root && _current.contains(i.key()) && within(i->root,_root)},
                {"visible",_frame.value("open").toBool() && _current.contains(i.key()) && within(i->root,_root) && visible(i->root,_window)}});
        }
        return {{"navigationPanelsVersion",1},{"commandId",request.value("commandId")},{"runId",request.value("runId")},
            {"instance",_instance},{"sequence",static_cast<qulonglong>(++_sequence)},{"processId",QCoreApplication::applicationPid()},
            {"capturedEpochMs",now},{"complete",true},{"roots",roots},
            {"ui",QVariantMap{{"bridgeId",_frame.value("bridgeId").toString()},{"generation",_frame.value("generation").toString()},
                {"sequence",_frame.value("lastCommandSequence").toVariant()},{"elapsedMs",_frame.value("elapsedMs").toVariant()},
                {"observedEpochMs",observed},{"open",_frame.value("open").toBool()},{"ready",_frame.value("ready").toBool()}}}};
    }
private:
    struct Row { QPointer<QQuickItem> root;QString profile,source;qint64 first{0}; };
    static bool enabled() { return QCoreApplication::instance() && QCoreApplication::arguments().contains("--testScript")
        && QThread::currentThread()==QCoreApplication::instance()->thread(); }
    qint64 epoch() {
        const auto now=QDateTime::currentMSecsSinceEpoch();if (now<=0 || now<_epoch) { _valid=false;return 0; }_epoch=now;return now;
    }
    static bool identifier(const QString& v) { return QRegularExpression("\\A[0-9a-f]{32}\\z").match(v).hasMatch(); }
    static QString nonce() { return QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-'); }
    static bool within(QQuickItem* item,QQuickItem* root) {
        int depth{0};for (auto p=item;p && ++depth<=128;p=p->parentItem()) { if (p==root) { return true; } }return false;
    }
    static bool visible(QQuickItem* item,QQuickWindow* window) {
        if (!item || !window || item->window()!=window || item->width()<=0 || item->height()<=0) { return false; }
        int depth{0};for (auto p=item;p && ++depth<=128;p=p->parentItem()) {
            if (!p->isVisible() || !std::isfinite(p->opacity()) || p->opacity()<=.01) { return false; }
        }
        return depth<=128;
    }
    static QString addressComponent(QQuickItem* item) {
        if (!loginGuiItem(item) || item->objectName()!="tabletAddressDialog"
                || !QString(item->metaObject()->className()).startsWith("TabletAddressDialog_QMLTYPE_")) { return {}; }
        int depth{0};for (auto c=qmlContext(item);c && ++depth<=128;c=c->parentContext()) {
            const auto url=c->baseUrl();
            if (c->nameForObject(item)=="root" && (url.scheme()=="qrc" || url.scheme()=="file")
                    && url.authority().isEmpty() && !url.hasQuery() && !url.hasFragment()
                    && url.path().endsWith("/hifi/tablet/TabletAddressDialog.qml")) { return url.toString(); }
        }
        return {};
    }
    QPointer<QQuickItem> _root;QPointer<QQuickWindow> _window;QJsonObject _frame;QHash<QString,Row> _rows;
    QSet<QString> _queries,_current;QString _instance{nonce()};qint64 _epoch{0};quint64 _sequence{0};bool _valid{true},_complete{false};
};
inline NavigationPanelsObservation& navigationPanelsObservation() { static NavigationPanelsObservation value;return value; }
}
#endif
