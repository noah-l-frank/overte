// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS) && defined(OVERTE_IOS_E2E_TEST_BUILD)
#include "NormalControlUi.h"
#include <PathUtils.h>
#include <QCryptographicHash>
#include <QJSValue>
#include <QJsonArray>
#include <QJsonDocument>
#include <QQmlContext>
#include <QtQml/qqml.h>

namespace overte::e2e {
// The existing rendered Back button only. There is no direct QML invocation,
// navigation setter, requested screen or expected feature outcome here.
inline QJsonObject tabletBackControlObservation(QQuickItem* item) {
    if (!qApp || QThread::currentThread()!=qApp->thread()
            || !QCoreApplication::arguments().contains("--testScript") || !item
            || item->objectName()!="nav.back" || !qmlContext(item)
            || qmlContext(item)->baseUrl()!=PathUtils::qmlUrl("hifi/tablet/TabletNavigation.qml")) {return {};}
    QQuickItem* root=nullptr;
    int depth=0;
    for (auto parent=item->parentItem();parent && depth<128;parent=parent->parentItem(),++depth) {
        if (parent->objectName()=="tabletRoot") {root=parent;break;}
    }
    if (!root || !qmlContext(root) || qmlContext(root)->baseUrl()!=PathUtils::qmlUrl("hifi/tablet/WindowRoot.qml")
            || root->window()!=item->window() || root->property("screenSpaceMode")!=QVariant(true)) {return {};}
    const auto screen=root->property("semanticScreenId"),target=root->property("semanticBackTarget");
    if (screen.userType()!=QMetaType::QString || target.userType()!=QMetaType::QString
            || screen.toString().size()>4096 || target.toString().size()>4096) {return {};}
    const auto originalHistory=root->property("semanticSourceHistory");
    QJsonArray sources;
    if (originalHistory.userType()==qMetaTypeId<QJSValue>()) {
        const auto history=originalHistory.value<QJSValue>();if (!history.isArray()) {return {};}
        const auto length=history.property("length");
        if (!length.isNumber() || length.toNumber()<0 || length.toNumber()>128
                || length.toNumber()!=length.toInt()) {return {};}
        for (int index=0;index<length.toInt();++index) {
            const auto entry=history.property(index);
            if (!entry.isString() || entry.toString().size()>4096) {return {};}
            sources.append(entry.toString());
        }
    } else if (originalHistory.userType()==QMetaType::QVariantList) {
        const auto history=originalHistory.toList();if (history.size()>128) {return {};}
        for (const auto& entry:history) {
            if (entry.userType()!=QMetaType::QString || entry.toString().size()>4096) {return {};}
            sources.append(entry.toString());
        }
    } else {
        return {};
    }
    auto identity=root->property("_overteE2ETabletBackRootId").toString();
    if (identity.isEmpty()) {
        identity=QUuid::createUuid().toString(QUuid::WithoutBraces);
        root->setProperty("_overteE2ETabletBackRootId",identity);
    }
    if (QUuid(identity).isNull() || QUuid(identity).toString(QUuid::WithoutBraces)!=identity) {return {};}
    const auto hash=[](const QByteArray& raw) {
        return QString::fromLatin1(QCryptographicHash::hash(raw,QCryptographicHash::Sha256).toHex());
    };
    const auto window=item->window();const auto point=item->mapToScene(QPointF(item->width()/2,item->height()/2));
    return {{"tabletBackControlVersion",1},{"navigationRootId",identity},
        {"navigationQmlSource",qmlContext(root)->baseUrl().toString(QUrl::FullyEncoded)},
        {"screenIdSha256",hash(screen.toString().toUtf8())},
        {"sourceHistorySha256",hash(QJsonDocument(sources).toJson(QJsonDocument::Compact))},
        {"sourceHistoryLength",sources.size()},{"backTargetPending",!target.toString().isEmpty()},
        {"inputReady",window && target.toString().isEmpty() && item->isEnabled()
            && NormalControlUi::ownsPoint(item,window,point)}};
}
inline QString tabletBackControlSource(QQuickItem* item) {
    const auto value=tabletBackControlObservation(item);
    return value.isEmpty() ? QString() : QString::fromUtf8(QJsonDocument(value).toJson(QJsonDocument::Compact));
}
}
#endif
