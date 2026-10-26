// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS) && defined(OVERTE_IOS_E2E_TEST_BUILD)
#include "../../tests/device/native/NormalControlUi.h"
#include <QJsonDocument>
#include <QCoreApplication>
#include <QList>
#include <QPointer>
#include <QQmlContext>
#include <QRegularExpression>
#include <QUuid>
#include <QtQml/qqml.h>

namespace overte::ios::lifecycle_navigation {
inline bool control(const QString& id) {
    return QStringList{"hud.tablet","tablet.home","tablet.close","create.entry","chat.entry",
        "scripts.entry","scripts.menu","scripts.menu-edit","scripts.menu-running"}.contains(id)
        || QRegularExpression("\\Atablet\\.page\\.([1-9]|[12][0-9]|3[0-2])\\z").match(id).hasMatch();
}
// Source identities retain only weak pointers. A reused QObject address cannot
// borrow the identity of its destroyed predecessor. Capacity exhaustion closes
// the inventory instead of pruning the history or making up a new generation.
struct Identity {QPointer<QObject> object;QString id;};
inline QString identity(QObject* object) {
    static QList<Identity> values;
    const auto app=QCoreApplication::instance();
    if (!app || !object || object->thread()!=app->thread()) {return {};}
    for (const auto& value:values) {if (value.object==object) {return value.id;}}
    if (values.size()>=512) {return {};}
    const auto id=QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');
    values.append({QPointer<QObject>(object),id});return id;
}
inline QJsonObject observation(QQuickItem* item,const QString& id,QQuickItem* container) {
    if (!control(id) || !item || !container || !item->window() || item->window()!=container->window()) {return {};}
    bool attached=false;
    for (auto parent=item;parent;parent=parent->parentItem()) {if (parent==container) {attached=true;break;}}
    if (!attached) {return {};}
    // Dynamically created HUD buttons may inherit their source context. Record
    // the actual nearest available context; never prescribe a caller's URI.
    QQmlContext* context=nullptr;
    for (auto parent=item;parent;parent=parent->parentItem()) {
        const auto candidate=qmlContext(parent);
        if (candidate && !candidate->baseUrl().isEmpty()) {context=candidate;break;}
        if (parent==container) {break;}
    }
    if (!context) {return {};}
    const auto url=context->baseUrl();
    if (!QStringList{"file","qrc"}.contains(url.scheme()) || !url.authority().isEmpty()
            || url.hasQuery() || url.hasFragment() || url.toString().size()>4096 || !url.path().endsWith(".qml")) {return {};}
    const auto objectId=identity(item),windowId=identity(item->window()),containerId=identity(container),contextId=identity(context);
    if (objectId.isEmpty() || windowId.isEmpty() || containerId.isEmpty() || contextId.isEmpty()) {return {};}
    const auto buttonEnabled=item->property("buttonEnabled");
    return {{"controlId",id},{"controlObject",objectId},{"windowObject",windowId},{"containerObject",containerId},
        {"contextObject",contextId},{"qmlSource",url.toString()},{"surface",id=="hud.tablet" ? "hud" : "tablet"},
        {"inputReady",item->isEnabled() && (!buttonEnabled.isValid() || buttonEnabled.toBool())
            && overte::e2e::NormalControlUi::ownsPoint(item,item->window(),item->mapToScene(QPointF(item->width()/2,item->height()/2)))}};
}
inline QString source(QQuickItem* item,const QString& id,QQuickItem* container) {
    auto value=observation(item,id,container);if (value.isEmpty()) {return {};}
    value.remove("inputReady");return QString::fromUtf8(QJsonDocument(value).toJson(QJsonDocument::Compact));
}
}
#endif
