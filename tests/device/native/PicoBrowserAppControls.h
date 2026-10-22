// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJSValue>
#include <QQmlContext>
#include <QQmlEngine>
#include <QQuickItem>
#include <QThread>
#include <QUuid>
#include <PathUtils.h>
#include <cmath>
namespace overte::e2e {
inline QJsonObject picoBrowserAppOriginal(QQuickItem* item) {
    if (!item || !QCoreApplication::instance() || item->thread()!=QCoreApplication::instance()->thread()
            || QThread::currentThread()!=item->thread() || item->metaObject()->indexOfSignal("clicked()")<0) { return {}; }
    const auto caption=item->property("text");
    if (caption.userType()!=QMetaType::QString || (caption!="WEB TEST" && caption!="INLINE TEST")) { return {}; }
    bool original=false;int depth=0;const auto expected=PathUtils::qmlUrl("hifi/tablet/TabletButton.qml");
    for (auto context=qmlContext(item);context && depth++<128;context=context->parentContext()) {
        if (context->nameForObject(item)=="tabletButton" && context->baseUrl()==expected) { original=true;break; }
    }
    if (!original) { return {}; }
    auto value=item->property("uuid");
    if (value.userType()==qMetaTypeId<QJSValue>()) { value=value.value<QJSValue>().toVariant(); }
    QUuid uuid;
    if (value.userType()==QMetaType::QUuid) { uuid=value.value<QUuid>(); }
    else if (value.userType()==QMetaType::QString) {
        const auto parsed=QUuid(value.toString());
        if (value.toString()!=parsed.toString() && value.toString()!=parsed.toString(QUuid::WithoutBraces)) { return {}; }
        uuid=parsed;
    } else { return {}; }
    if (uuid.isNull()) { return {}; }
    return {{"buttonId",uuid.toString(QUuid::WithoutBraces)},{"caption",caption.toString()},
        {"componentSourceSha256",QString::fromLatin1(QCryptographicHash::hash(expected.toString().toUtf8(),QCryptographicHash::Sha256).toHex())}};
}
inline QString picoBrowserAppControlId(QQuickItem* item) {
    const auto original=picoBrowserAppOriginal(item);if (original.isEmpty()) { return {}; }
    return original.value("caption")==QJsonValue("WEB TEST") ? "browser-app.web" : "browser-app.inline";
}
inline void appendPicoBrowserAppObservation(QJsonObject& row,QQuickItem* item,const QString& id) {
    const auto actual=picoBrowserAppOriginal(item);
    if (actual.isEmpty() || picoBrowserAppControlId(item)!=id) { row["inputReady"]=false;return; }
    for (auto value=actual.begin();value!=actual.end();++value) { row[value.key()]=value.value(); }
    const auto explicitEnabled=item->property("buttonEnabled");
    row["inputReady"]=item->isEnabled() && (!explicitEnabled.isValid() || explicitEnabled.toBool());
}
inline QString picoBrowserAppControlSource(QQuickItem* item,const QString& id) {
    QJsonObject original;appendPicoBrowserAppObservation(original,item,id);
    if (!original.contains("buttonId") || !item->window()) { return {}; }
    const auto center=item->mapToScene(QPointF(item->width()/2,item->height()/2));
    if (!std::isfinite(center.x()) || !std::isfinite(center.y()) || !std::isfinite(item->width()) || !std::isfinite(item->height())) { return {}; }
    original["sceneX"]=center.x();original["sceneY"]=center.y();original["width"]=item->width();original["height"]=item->height();
    original["focused"]=item->hasActiveFocus();
    return QString::fromUtf8(QJsonDocument(original).toJson(QJsonDocument::Compact));
}
}
#endif
