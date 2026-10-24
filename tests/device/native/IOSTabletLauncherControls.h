// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include "NormalControlUi.h"
#include <QJsonDocument>
#include <QQmlContext>
#include <QRegularExpression>
#include <QUuid>
#include <QtQml/qqml.h>

namespace overte::e2e {
// Passive access to the real SwipeView selection. No setter or input path.
inline QQuickItem* tabletLauncherRoot(QQuickItem* item) {
    for (int depth=0;item && depth<128;++depth,item=item->parentItem()) {
        if (item->objectName()!="tablet" || item->property("semanticScreenId")!=QVariant("tablet.home")) {continue;}
        const auto context=qmlContext(item);
        if (!context || item->property("featureLauncherObservation")!=QVariant(true)) {return nullptr;}
        const auto url=context->baseUrl();
        if (!QStringList{"file","qrc"}.contains(url.scheme()) || !url.authority().isEmpty()
                || url.hasQuery() || url.hasFragment() || !url.path().endsWith("/hifi/tablet/TabletHome.qml")) {return nullptr;}
        return item;
    }
    return nullptr;
}
inline QJsonObject tabletLauncherControlObservation(QQuickItem* item,const QString& id) {
    if (id!="snapshot.entry" && !QRegularExpression("\\Atablet\\.page\\.([1-9]|[12][0-9]|3[0-2])\\z").match(id).hasMatch()) {return {};}
    const auto root=tabletLauncherRoot(item);if (!root) {return {};}
    const auto index=root->property("featureLauncherCurrentIndex"),count=root->property("featureLauncherCount");
    if (index.userType()!=QMetaType::Int || count.userType()!=QMetaType::Int || count.toInt()<1 || count.toInt()>32
            || index.toInt()<0 || index.toInt()>=count.toInt()) {return {};}
    const int page=id=="snapshot.entry" ? -1 : id.mid(12).toInt()-1;
    if (page>=count.toInt() || (page>=0 && item->objectName()!=QStringLiteral("tabletPage.%1").arg(page+1))) {return {};}
    auto birth=root->property("_overteE2ETabletLauncherRootId").toString();
    if (birth.isEmpty()) {birth=QUuid::createUuid().toString(QUuid::WithoutBraces);root->setProperty("_overteE2ETabletLauncherRootId",birth);}
    const auto window=item->window();const auto point=item->mapToScene(QPointF(item->width()/2,item->height()/2));
    return {{"tabletLauncherControlVersion",1},{"launcherRootId",birth},{"launcherQmlSource",qmlContext(root)->baseUrl().toString()},
        {"launcherCurrentIndex",index.toInt()},{"launcherPageCount",count.toInt()},{"launcherControlIndex",page},
        {"inputReady",window && item->isEnabled() && NormalControlUi::ownsPoint(item,window,point)}};
}
inline QString tabletLauncherControlSource(QQuickItem* item,const QString& id) {
    const auto value=tabletLauncherControlObservation(item,id);
    return value.isEmpty()?QString():QString::fromUtf8(QJsonDocument(value).toJson(QJsonDocument::Compact));
}
}
#endif
