// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include <QAction>
#include <QActionGroup>
#include <QCoreApplication>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJSValue>
#include <QPointer>
#include <QQuickItem>
#include <QThread>
#include <QUuid>

namespace overte::e2e {
struct ViewMenuContext {
    QPointer<QAction> view,first,third;
    bool hmd {false};
    bool valid() const {
        return QCoreApplication::instance() && QThread::currentThread()==QCoreApplication::instance()->thread()
            && QCoreApplication::arguments().contains("--testScript") && hmd && view && first && third
            && view->thread()==QThread::currentThread() && first->thread()==QThread::currentThread()
            && third->thread()==QThread::currentThread() && view->text()=="View" && first->text()=="First Person"
            && third->text()=="Third Person" && first->isCheckable() && third->isCheckable()
            && first->actionGroup() && first->actionGroup()==third->actionGroup() && first->actionGroup()->isExclusive();
    }
};

inline QObject* viewMenuSource(QQuickItem* item) {
    if (!item || item->thread()!=QThread::currentThread()
            || !QString::fromLatin1(item->metaObject()->className()).startsWith("TabletMenuItem_QMLTYPE_")) {return nullptr;}
    const auto value=item->property("source");
    auto source=value.value<QObject*>();
    if (!source && value.userType()==qMetaTypeId<QJSValue>()) {source=value.value<QJSValue>().toQObject();}
    return source && source->thread()==QThread::currentThread() ? source : nullptr;
}

inline bool viewMenuBinding(QObject* source,QAction* action) {
    if (!source || !action) {return false;}
    // VrMenu's original MenuUserData is attached to both real objects. A
    // lookalike label or copied checked bit cannot bind a different QAction.
    const auto a=source->property("user_data"),b=action->property("user_data");
    return a.isValid() && a.userType()==b.userType()
        && QMetaType::typeFlags(a.userType()).testFlag(QMetaType::PointerToQObject)
        && a.value<QObject*>() && a.value<QObject*>()==b.value<QObject*>();
}

inline QString viewMenuControlId(QQuickItem* item,const ViewMenuContext& context) {
    if (!context.valid()) {return {};}
    const auto source=viewMenuSource(item);if (!source) {return {};}
    const auto text=item->property("text"),nativeText=source->property("text");
    if (text.userType()!=QMetaType::QString || nativeText.userType()!=QMetaType::QString || text!=nativeText) {return {};}
    const auto type=source->property("type");if (type.userType()!=QMetaType::Int) {return {};}
    for (const auto& pair:{qMakePair(QString("view-menu.view"),context.view.data()),
            qMakePair(QString("view-menu.first"),context.first.data()),qMakePair(QString("view-menu.third"),context.third.data())}) {
        if (viewMenuBinding(source,pair.second) && text.toString()==pair.second->text()
                && type.toInt()==(pair.first=="view-menu.view" ? 2 : 1)) {return pair.first;}
    }
    return {};
}

inline void appendViewMenuObservation(QJsonObject& row,QQuickItem* item,const QString& id,const ViewMenuContext& context) {
    const auto source=viewMenuSource(item);
    const auto action=id=="view-menu.view" ? context.view.data() : id=="view-menu.first" ? context.first.data() : context.third.data();
    const auto visible=source ? (source->property("tabletVisible").isValid() ? source->property("tabletVisible") : source->property("visible")) : QVariant();
    const auto checked=source ? source->property("checked") : QVariant();
    const auto checkable=source ? source->property("checkable") : QVariant();
    const auto enabled=source ? source->property("enabled") : QVariant();
    const auto platform=item ? item->property("platformEnabled") : QVariant();
    const auto instance=source ? QUuid(source->objectName()) : QUuid();
    const auto bound=context.valid() && action && source && viewMenuControlId(item,context)==id && !instance.isNull();
    row["menuInstance"]=instance.toString(QUuid::WithoutBraces);row["checked"]=action && action->isChecked();
    row["inputReady"]=bound && item->isEnabled() && action->isEnabled() && action->isVisible()
        && visible.userType()==QMetaType::Bool && visible.toBool() && enabled.userType()==QMetaType::Bool && enabled.toBool()
        && platform.userType()==QMetaType::Bool && platform.toBool() && checked.userType()==QMetaType::Bool
        && checked.toBool()==action->isChecked() && checkable.userType()==QMetaType::Bool && checkable.toBool()==action->isCheckable();
}

inline QString viewMenuControlSource(QQuickItem* item,const QString& id,const ViewMenuContext& context) {
    QJsonObject value;appendViewMenuObservation(value,item,id,context);
    return QString::fromUtf8(QJsonDocument(value).toJson(QJsonDocument::Compact));
}
} // namespace overte::e2e
#endif
