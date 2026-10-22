// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PHONE_INTERFACE)
#include "NormalControlUi.h"
#include <SettingManager.h>
#include <QDataStream>
namespace overte::e2e {
// Passive original pages, real ListModels and native backing storage. No QML
// function, dispatch handler, requested state or cached page is used as input.
class NavigationViewObservation {
public:
    QVariantMap request(const QVariantMap& command,const QList<QQuickItem*>& roots,bool shown,
            const QVariantMap& bookmarks,const QString& endpoint,const QString& protocol,const QVariantMap& nativeKeyboard) {
        const auto json=QJsonObject::fromVariantMap(command);const auto keys=json.keys();
        if (!qApp || QThread::currentThread()!=qApp->thread() || !QCoreApplication::arguments().contains("--testScript")
                || !_available || !DependencyManager::isSet<Setting::Manager>() || bookmarks.isEmpty() || roots.isEmpty()
                || QSet<QString>(keys.begin(),keys.end())!=QSet<QString>{"schemaVersion","commandId","action","runId"}
                || json.value("schemaVersion")!=QJsonValue(1) || json.value("action")!=QJsonValue("phone-navigation-view-observe")
                || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(json.value("commandId").toString()).hasMatch()
                || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(json.value("runId").toString()).hasMatch()) { return {}; }
        const auto started=tick();if (!started) { return {}; }
        QQuickItem* page{nullptr};QQuickItem* modal{nullptr};bool address=false,bookmarkDialog=false,invalid=false;int queue=0,activeTimers=0;QSet<QQuickItem*> visited;
        std::function<void(QQuickItem*,int)> walk=[&](QQuickItem* item,int depth) {
            if (!item || invalid || visited.contains(item)) { return; }
            if (depth>128 || visited.size()>=4096 || item->thread()!=qApp->thread()) { invalid=true;return; }visited.insert(item);
            const bool visible=!NormalControlUi::visibleRect(item,item->window()).isEmpty();
            if (navigationPage(item)==item) {
                const auto pending=createVariant(item->property("pendingCommands"));
                if (pending.userType()!=QMetaType::QVariantList || pending.toList().size()>128) { invalid=true;return; }
                queue+=pending.toList().size();
                QObject* timer{nullptr};
                for (auto context=qmlContext(item);context;context=context->parentContext()) {
                    auto actual=createVariant(context->contextProperty("commandInterval")).value<QObject*>();if (actual) { timer=actual;break; }
                }
                if (!timer || timer->property("running").userType()!=QMetaType::Bool) { invalid=true;return; }
                if (timer->property("running").toBool()) { ++activeTimers; }
                if (visible && shown) { if (page && page!=item) { invalid=true;return; }page=item; }
            }
            if (visible && navigationDialog(item)) { bookmarkDialog=true; }
            if (visible && item->objectName()=="PhoneAddressField" && item->inherits("QQuickTextInput")) { address=true; }
            if (visible && navigationError(item)==item) { if (modal && modal!=item) { invalid=true;return; }modal=item; }
            for (auto child:item->childItems()) { walk(child,depth+1); }
        };
        for (auto root:roots) { if (root && root->window()) {
            walk(root,0);
            if (root->parentItem()==root->window()->contentItem()) {
                for (auto layer:root->window()->contentItem()->childItems()) { if (layer!=root && layer->inherits("QQuickOverlay")) { walk(layer,0); } }
            }
        } }
        if (invalid || visited.isEmpty() || queue>128) { return {}; }
        QVariantMap ui{{"present",page!=nullptr},{"addressDialog",address},{"notFoundModal",modal!=nullptr},{"bookmarkDialog",bookmarkDialog},{"pendingCommands",queue},{"activeTimers",activeTimers},{"notFound",QVariantMap()}};
        if (modal) {
            const auto original=NavigationModalObservation::original(modal);if (original.isEmpty()) { return {}; }ui.insert("notFound",original);
        }
        if (page) {
            if (_page!=page || !_present) { _generation=nonce(); }
            QVariantList places,model,servers;QString query;bool gotSearch=false,gotList=false,gotServers=false;
            for (auto item:visited) {
                if (navigationPage(item)!=page) { continue; }
                if (item->objectName()=="placesSearch" && item->inherits("QQuickTextInput")) {
                    if (gotSearch || item->property("text").userType()!=QMetaType::QString) { return {}; }
                    gotSearch=true;query=item->property("text").toString();
                }
                if (item->inherits("QQuickListView") && (loginQmlId(item,"placesList") || loginQmlId(item,"serversList"))) {
                    auto actual=qobject_cast<QAbstractItemModel*>(createVariant(item->property("model")).value<QObject*>());
                    const bool directory=loginQmlId(item,"placesList");
                    if (!actual || actual->thread()!=qApp->thread() || actual->rowCount()<0 || actual->rowCount()>1000) { return {}; }
                    auto& rows=directory ? model : servers;
                    if (directory ? gotList : gotServers) { return {}; }
                    if (directory) { gotList=true; }else { gotServers=true; }
                    for (int i=0;i<actual->rowCount();++i) {
                        QVariantMap row;
                        for (const auto& name:directory ? QStringList{"placeId","placeName","placeAddress"} : QStringList{"serverUrl","serverIndex","fetched","pinned","failed"}) {
                            const int role=actual->roleNames().key(name.toUtf8(),-1);if (role<0) { return {}; }
                            row.insert(name,actual->data(actual->index(i,0),role));
                        }
                        rows.append(row);
                    }
                }
            }
            const auto original=createVariant(page->property("records"));
            if (!gotSearch || !gotList || !gotServers || query.size()>4096 || original.userType()!=QMetaType::QVariantList
                    || original.toList().size()>1000) { return {}; }
            // The original complete input model stays private, including utility
            // records. The host separately projects only the owned record ID.
            places=original.toList();
            ui.insert("generation",_generation);ui.insert("source",PathUtils::defaultScriptsLocation().resolved(QUrl("system/places/PicoPlaces.qml")).toString());
            ui.insert("query",query);ui.insert("records",places);ui.insert("model",model);ui.insert("servers",servers);
            ui.insert("loading",page->property("loading"));ui.insert("maturity",createVariant(page->property("maturityFilter")));
            ui.insert("currentAddress",page->property("currentAddress"));
        }
        _page=page;_present=page!=nullptr;
        auto settings=DependencyManager::get<Setting::Manager>();QVariantMap preferences;
        settings->withReadLock([&] { for (const auto& key:QStringList{"placesAppMetaverseToFetch","placesAppPinnedMetaverse","placesAppMaturityFilter","private/places/federation"}) {
            preferences.insert(key,QVariantMap{{"present",settings->contains(key)},{"value",settings->value(key)}});
        } });
        if (nativeKeyboard.value("valid").userType()!=QMetaType::Bool || !nativeKeyboard.value("valid").toBool()
                || nativeKeyboard.value("keyboardVisible").userType()!=QMetaType::Bool) { return {}; }
        const QVariantMap keyboard{{"available",true},{"backend","native-touch-metrics"},{"visible",nativeKeyboard.value("keyboardVisible")}};
        const auto captured=tick();if (!captured || captured-started>1500 || _sequence>=1000000000) { return {}; }
        return {{"navigationViewVersion",1},{"commandId",command.value("commandId")},{"runId",command.value("runId")},
            {"instance",_instance},{"sequence",static_cast<qulonglong>(++_sequence)},{"processId",QCoreApplication::applicationPid()},
            {"requestedEpochMs",started},{"capturedEpochMs",captured},
            {"source",QVariantMap{{"tabletShown",shown},{"ui",ui},{"storage",bookmarks},{"preferences",preferences},
                {"endpoint",endpoint},{"protocolSignature",protocol},{"keyboard",keyboard}}}};
    }
private:
    static QString nonce() { return QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-'); }
    qint64 tick() { const auto now=QDateTime::currentMSecsSinceEpoch();if (now<=0 || now<_epoch) { _available=false;return 0; }_epoch=now;return now; }
    QString _instance{nonce()},_generation{nonce()};QPointer<QQuickItem> _page;bool _present{false},_available{true};qint64 _epoch{0};quint64 _sequence{0};
};
}
#endif
