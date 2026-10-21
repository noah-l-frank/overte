// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once

// Passive identities for the actual tablet File/account QAction delegates.
// Never triggers a QAction, emits a QML signal or changes account state.
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QJsonObject>
#include <QQuickItem>
#include <QThread>
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include <QQmlContext>
#include <QQmlEngine>
#include <QJSValue>
#endif

namespace overte::e2e {
inline QObject* accountMenuSource(QQuickItem* item) {
#if defined(OVERTE_E2E_FEATURE_TESTS)
    if (!item || !qApp || item->thread()!=qApp->thread() || QThread::currentThread()!=qApp->thread()
            || !QCoreApplication::arguments().contains("--testScript")
            || !QString::fromLatin1(item->metaObject()->className()).startsWith("TabletMenuItem_QMLTYPE_")) { return nullptr; }
    const auto context=QQmlEngine::contextForObject(item);
    if (!context || !context->baseUrl().path().endsWith("/hifi/tablet/TabletMenuItem.qml")) { return nullptr; }
    auto source=item->property("source");
    QObject* object {nullptr};
    if (source.userType()==qMetaTypeId<QJSValue>()) { object=source.value<QJSValue>().toQObject(); }
    else if (source.canConvert<QObject*>()) { object=source.value<QObject*>(); }
    if (!object || object->thread()!=qApp->thread() || item->property("text").userType()!=QMetaType::QString
            || object->property("enabled").userType()!=QMetaType::Bool || !object->property("enabled").toBool()
            || item->property("platformEnabled").userType()!=QMetaType::Bool || !item->property("platformEnabled").toBool()) { return nullptr; }
    const auto visible=object->property("tabletVisible").isValid() ? object->property("tabletVisible") : object->property("visible");
    if (visible.userType()!=QMetaType::Bool || !visible.toBool()) { return nullptr; }
    if (object->property("type").userType()!=QMetaType::Int) { return nullptr; }
    const auto kind=object->property("type").toInt();
    return kind==1 || kind==2 ? object : nullptr;
#else
    Q_UNUSED(item)
    return nullptr;
#endif
}
inline QString accountMenuControlId(QQuickItem* item) {
    auto source=accountMenuSource(item);
    if (!source) { return {}; }
    const auto text=item->property("text").toString();
    if (text=="File" && source->property("type").toInt()==2) { return "account.menu-file"; }
    if (text.startsWith("Directory Service: Logout ") && text.size()<=4096
            && source->property("type").toInt()==1) { return "account.logout"; }
    return {};
}
inline QString accountMenuControlSource(QQuickItem* item) {
    auto source=accountMenuSource(item);
    if (!source || accountMenuControlId(item).isEmpty()) { return {}; }
    return QString::number(reinterpret_cast<quintptr>(source),16)+":"+QString::fromLatin1(
        QCryptographicHash::hash(item->property("text").toString().toUtf8(),QCryptographicHash::Sha256).toHex());
}
inline void appendAccountMenuObservation(QJsonObject& row,QQuickItem* item) {
    auto source=accountMenuSource(item);
    if (!source || accountMenuControlId(item).isEmpty()) { return; }
    row["menuSourceVersion"]=1;
    row["sourceType"]=source->property("type").toInt();
    row["labelSha256"]=QString::fromLatin1(QCryptographicHash::hash(
        item->property("text").toString().toUtf8(),QCryptographicHash::Sha256).toHex());
}
} // namespace overte::e2e
