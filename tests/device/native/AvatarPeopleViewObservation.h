// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PHONE_INTERFACE)
#include "NormalControlUi.h"
#include <QAbstractItemModel>
#include <QSettings>
namespace overte::e2e {
// Passive QML state only. The model, backend, native entity and render sources
// are acquired separately; a page or consent message cannot prove their effect.
class AvatarPeopleViewObservation {
public:
    QVariantMap read(const QList<QQuickItem*>& roots,bool shown) {
        if (!qApp || QThread::currentThread()!=qApp->thread() || !QCoreApplication::arguments().contains("--testScript")) { return {}; }
        QSet<QQuickItem*> visited;QQuickItem* avatar{nullptr};QQuickItem* people{nullptr};bool invalid=false,prompt=false;
        QVariantList dialogs;QVariantMap models;QSet<QQuickItem*> dialogRoots;
        std::function<void(QQuickItem*,int)> walk=[&](QQuickItem* item,int depth) {
            if (!item || invalid || visited.contains(item)) { return; }
            if (depth>128 || visited.size()>=4096 || item->thread()!=qApp->thread()) { invalid=true;return; }visited.insert(item);
            const bool visible=shown && !NormalControlUi::visibleRect(item,item->window()).isEmpty();
            if (visible && avatarApp(item)==item) { if (avatar && avatar!=item) { invalid=true;return; }avatar=item; }
            if (visible && peopleApp(item)==item) { if (people && people!=item) { invalid=true;return; }people=item; }
            if (visible) { if (auto dialog=avatarDialog(item)) { if (!dialogRoots.contains(dialog) && !NormalControlUi::visibleRect(dialog,dialog->window()).isEmpty()) {
                dialogRoots.insert(dialog);dialogs.append(QVariantMap{{"title",dialog->property("titleText")},{"source",QString::fromLatin1(dialog->metaObject()->className())}});
            } } }
            if (visible && peopleApp(item) && item->objectName()=="peopleConnectionPrompt") { prompt=true; }
            for (auto child:item->childItems()) { walk(child,depth+1); }
        };
        for (auto root:roots) { if (root && root->window()) { walk(root,0);
            if (root->parentItem()==root->window()->contentItem()) { for (auto layer:root->window()->contentItem()->childItems()) { if (layer!=root && layer->inherits("QQuickOverlay")) { walk(layer,0); } } }
        } }
        if (invalid || visited.isEmpty() || dialogs.size()>4) { return {}; }
        QVariantMap avatarSource{{"present",avatar!=nullptr},{"dialogs",dialogs}};
        if (avatar) {
            avatarSource.insert("current",createVariant(avatar->property("currentAvatar")));
            avatarSource.insert("settings",createVariant(avatar->property("currentAvatarSettings")));
            avatarSource.insert("managing",avatar->property("isInManageState"));
            for (const auto& key:QStringList{"allAvatars","pageOfAvatars"}) {
                const auto source=model(avatar,"hifi/AvatarApp.qml",key);if (source.isEmpty()) { return {}; }models.insert(key,source);
            }
        }
        QVariantMap peopleSource{{"present",people!=nullptr},{"dialog",prompt}};
        if (people) {
            peopleSource.insert("consent",createVariant(people->property("connectionState")));
            peopleSource.insert("nearby",createVariant(people->property("nearbyUserModelData")));
            peopleSource.insert("self",createVariant(people->property("myData")));
            peopleSource.insert("tab",people->property("activeTab"));
            for (const auto& key:QStringList{"connectionsUserModel","nearbyUserModel"}) {
                const auto source=model(people,"hifi/Pal.qml",key);if (source.isEmpty()) { return {}; }models.insert(key,source);
            }
        }
        QSettings settings;settings.beginGroup("pal");QVariantMap preferences;
        for (const auto& key:QStringList{"filtered","nearDistance","nearbySortIndicatorColumn","nearbySortIndicatorOrder","connectionsSortIndicatorColumn","connectionsSortIndicatorOrder"}) {
            preferences.insert(key,QVariantMap{{"present",settings.contains(key)},{"value",settings.value(key)}});
        }
        if (settings.status()!=QSettings::NoError) { return {}; }
        return {{"avatarPeopleViewVersion",1},{"tabletShown",shown},{"avatar",avatarSource},{"people",peopleSource},{"models",models},{"preferences",preferences}};
    }
private:
    static QVariantMap model(QQuickItem* page,const QString& path,const QString& id) {
        QAbstractItemModel* actual{nullptr};
        for (auto context=qmlContext(page);context;context=context->parentContext()) {
            if (context->baseUrl()!=PathUtils::qmlUrl(path)) { continue; }
            auto candidate=qobject_cast<QAbstractItemModel*>(createVariant(context->contextProperty(id)).value<QObject*>());
            if (candidate && context->nameForObject(candidate)==id) { actual=candidate;break; }
        }
        if (!actual || actual->thread()!=qApp->thread() || actual->rowCount()<0 || actual->rowCount()>1000) { return {}; }
        QVariantList rows;const auto roles=actual->roleNames();if (roles.size()>128) { return {}; }
        for (int index=0;index<actual->rowCount();++index) {
            QVariantMap row;for (auto role=roles.begin();role!=roles.end();++role) { row.insert(QString::fromUtf8(role.value()),createVariant(actual->data(actual->index(index,0),role.key()))); }rows.append(row);
        }
        return {{"complete",true},{"rows",rows},{"count",actual->rowCount()}};
    }
};
}
#endif
