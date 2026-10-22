// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include "NormalScriptControls.h"
#include "NormalCreateControls.h"
#include <PathUtils.h>
#include <QPointer>

namespace overte::e2e {
// NormalControlUi and the original Pico normal bridge share this admission.
// Nothing here creates an entity, assigns text or invokes a QML handler.
inline QUrl lifecycleCreateSource() {
    auto base=PathUtils::defaultScriptsLocation();
    if (!base.path().endsWith('/')) { base.setPath(base.path()+'/'); }
    return base.resolved(QUrl("system/create/qml/NativeCreate.qml"));
}
inline QQmlContext* lifecycleCreateContext(QQuickItem* item) {
    if (!audioGuiItem(item) || item->objectName()!="NativeCreateText" || !item->inherits("QQuickTextInput")) { return nullptr; }
    const auto expected=lifecycleCreateSource();int depth{0};
    for (auto context=qmlContext(item);context && ++depth<=128;context=context->parentContext()) {
        if (context->isValid() && context->thread()==qApp->thread() && context->baseUrl()==expected
                && context->nameForObject(item)=="newText") { return context; }
    }
    return nullptr;
}
inline QString lifecycleControlId(QQuickItem* item) {
    auto context=lifecycleCreateContext(item);auto page=context ? createPage(item) : nullptr;
    return page && context->nameForObject(page)=="root" && page->property("currentTab").toInt()==0
        ? QStringLiteral("lifecycle.create.text") : QString();
}
inline bool lifecycleControlText(const QString& text) {
    return text.isEmpty() || QRegularExpression(QStringLiteral("\\AOverte ä Ω 東京 [0-9a-f]{32}\\z")).match(text).hasMatch();
}
inline QString lifecycleControlObject(QObject* value) {
    struct Identity { QPointer<QObject> object;QString id; };
    static QList<Identity> originals;
    if (!value || !qApp || QThread::currentThread()!=qApp->thread() || value->thread()!=qApp->thread()
            || !QCoreApplication::arguments().contains("--testScript")) { return {}; }
    for (const auto& original:originals) { if (original.object==value) { return original.id; } }
    if (originals.size()>=256) { return {}; }
    const auto id=QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');
    originals.append({value,id});return id;
}
inline void appendLifecycleControlObservation(QJsonObject& row,QQuickItem* item,const QString& id) {
    if (id!="lifecycle.create.text" || lifecycleControlId(item)!=id || !item->window()) { row["inputReady"]=false;return; }
    auto page=createPage(item);auto context=lifecycleCreateContext(item);
    const auto text=item->property("text"),readOnly=item->property("readOnly");
    if (text.userType()!=QMetaType::QString || !lifecycleControlText(text.toString()) || readOnly.userType()!=QMetaType::Bool) {
        row["inputReady"]=false;return;
    }
    const QHash<QString,QObject*> objects{{"fieldId",item},{"pageId",page},{"contextId",context},{"windowId",item->window()}};
    for (auto entry=objects.begin();entry!=objects.end();++entry) {
        const auto identity=lifecycleControlObject(entry.value());
        if (identity.isEmpty()) { row["inputReady"]=false;return; }
        row[entry.key()]=identity;
    }
    row["text"]=text.toString();row["componentSourceSha256"]=QString::fromLatin1(QCryptographicHash::hash(
        lifecycleCreateSource().toString(QUrl::FullyEncoded).toUtf8(),QCryptographicHash::Sha256).toHex());
    row["inputReady"]=item->isEnabled() && !readOnly.toBool();
}
inline QString lifecycleControlSource(QQuickItem* item,const QString& id) {
    QJsonObject row;appendLifecycleControlObservation(row,item,id);
    if (!row.contains("text") || !item || !item->window()) { return {}; }
    const auto center=item->mapToScene(QPointF(item->width()/2,item->height()/2));
    if (!std::isfinite(center.x()) || !std::isfinite(center.y()) || !std::isfinite(item->width()) || !std::isfinite(item->height())) { return {}; }
    row["focused"]=item->hasActiveFocus();row["sceneX"]=center.x();row["sceneY"]=center.y();
    row["width"]=item->width();row["height"]=item->height();
    return QString::fromLatin1(QCryptographicHash::hash(QJsonDocument(row).toJson(QJsonDocument::Compact),QCryptographicHash::Sha256).toHex());
}
} // namespace overte::e2e
#endif
