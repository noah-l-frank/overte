// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include <QCoreApplication>
#include <QJsonObject>
#include <QQuickItem>
#include <QQuickWindow>
#include <QThread>
#include <cmath>
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include <PathUtils.h>
#include <QQmlContext>
#include <QQmlEngine>
#endif

namespace overte::e2e {
inline bool scriptManagerVisible(QQuickItem* item) {
#if defined(OVERTE_E2E_FEATURE_TESTS)
    if (!item || !item->window() || item->width()<=0 || item->height()<=0) { return false; }
    const auto center=item->mapToScene(QPointF(item->width()/2,item->height()/2));
    auto bounds=item->mapRectToScene(QRectF(0,0,item->width(),item->height()));
    if (!std::isfinite(center.x()) || !std::isfinite(center.y()) || !std::isfinite(bounds.x())
            || !std::isfinite(bounds.y()) || !std::isfinite(bounds.width()) || !std::isfinite(bounds.height())) { return false; }
    bounds=bounds.intersected(QRectF(0,0,item->window()->width(),item->window()->height()));
    int depth {0};
    for (auto parent=item;parent;parent=parent->parentItem()) {
        if (++depth>128 || !parent->isVisible() || !std::isfinite(parent->opacity()) || parent->opacity()<=0.01) { return false; }
        if (parent->clip()) { bounds=bounds.intersected(parent->mapRectToScene(parent->clipRect())); }
    }
    return !bounds.isEmpty() && bounds.contains(center);
#else
    Q_UNUSED(item)
    return false;
#endif
}
// Passive original root and separately bound Label properties. No handler,
// model mutation, text assignment, preferred error or requested URL is input.
inline QJsonObject scriptManagerStatus(QQuickItem* item) {
    QJsonObject result{{"managerSourceVersion", 1}, {"available", false}};
#if defined(OVERTE_E2E_FEATURE_TESTS)
    if (!qApp || !item || QThread::currentThread() != qApp->thread() || item->thread() != qApp->thread()
            || !QCoreApplication::arguments().contains("--testScript") || item->objectName() != "scriptFromFile") { return result; }
    QQuickItem* root {nullptr}; QQmlContext* original {nullptr}; int depth {0};
    for (auto parent=item; parent && ++depth<=128; parent=parent->parentItem()) {
        if (parent->objectName() != "RunningScripts") { continue; }
        int contexts {0};
        for (auto context=qmlContext(parent); context && ++contexts<=128; context=context->parentContext()) {
            const auto url=context->baseUrl();
            if (context->thread()==item->thread() && context->nameForObject(parent)=="root"
                    && (url.scheme()=="file" || url.scheme()=="qrc") && url.authority().isEmpty()
                    && !url.hasQuery() && !url.hasFragment() && url.toString().size()<=4096
                    && url==PathUtils::qmlUrl(QStringLiteral("hifi/dialogs/TabletRunningScripts.qml"))) {
                root=parent; original=context; break;
            }
        }
        break;
    }
    if (!root || !original) { return result; }
    // The original Label is a direct child of the original manager's layout,
    // not a delegate, popup or matching text elsewhere in the application.
    auto flow=item->parentItem(); auto layout=flow ? flow->parentItem() : nullptr;
    if (!layout || layout->parentItem()!=root) { return result; }
    QQuickItem* label {nullptr}; int count {0};
    for (auto child:layout->childItems()) {
        if (++count>128 || child->thread()!=root->thread()) { return result; }
        if (original->nameForObject(child)=="scriptStatus") {
            if (label || !child->inherits("QQuickText")) { return result; }
            label=child;
        }
    }
    const auto status=root->property("status");
    const auto text=label ? label->property("text") : QVariant();
    if (!label || status.userType()!=QMetaType::QString || text.userType()!=QMetaType::QString
            || status.toString().size()>8192 || text.toString().size()>8192) { return result; }
    result["available"]=true;
    result["componentSource"]=original->baseUrl().toString(QUrl::FullyEncoded);
    result["statusText"]=status.toString(); result["labelText"]=text.toString();
    result["rootVisible"]=scriptManagerVisible(root);
    result["labelVisible"]=label->window()==root->window() && scriptManagerVisible(label);
#else
    Q_UNUSED(item)
#endif
    return result;
}
} // namespace overte::e2e
