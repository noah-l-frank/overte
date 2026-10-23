// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include <QCoreApplication>
#include <QJsonObject>
#include <QQuickItem>
#include <QQuickWindow>
#include <QThread>
#include <QDateTime>
#include <functional>
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
inline QJsonObject scriptManagerRootStatus(QQuickItem* root) {
    QJsonObject result{{"managerSourceVersion", 2}, {"available", false}};
#if defined(OVERTE_E2E_FEATURE_TESTS)
    if (!qApp || !root || QThread::currentThread() != qApp->thread() || root->thread() != qApp->thread()
            || !QCoreApplication::arguments().contains("--testScript") || root->objectName() != "RunningScripts") { return result; }
    QQmlContext* original {nullptr}; int contexts {0};
    for (auto context=qmlContext(root); context && ++contexts<=128; context=context->parentContext()) {
        const auto url=context->baseUrl();
        if (context->thread()==root->thread() && context->nameForObject(root)=="root"
                && (url.scheme()=="file" || url.scheme()=="qrc") && url.authority().isEmpty()
                && !url.hasQuery() && !url.hasFragment() && url.toString().size()<=4096
                && url==PathUtils::qmlUrl(QStringLiteral("hifi/dialogs/TabletRunningScripts.qml"))) {
            original=context; break;
        }
    }
    if (!original) { return result; }
    // The product places the Label inside a Flickable now. A stable objectName
    // is eligible only when this exact component context owns a declared id
    // for that object; foreign inline objects/delegates cannot impersonate it.
    QQuickItem* label {nullptr}; int visited {0}; bool invalid {false};
    std::function<void(QQuickItem*,int)> walk=[&](QQuickItem* item,int depth) {
        if (!item || invalid) { return; }
        if (++visited>4096 || depth>128 || item->thread()!=root->thread()) { invalid=true;return; }
        const auto declared=original->nameForObject(item);
        if ((item->objectName()=="scriptStatus" || declared=="scriptStatus") && !declared.isEmpty()) {
            if (label || !item->inherits("QQuickText")) { invalid=true;return; }
            label=item;
        }
        for (auto child:item->childItems()) { walk(child,depth+1); }
    };
    walk(root,0);if (invalid) { return result; }
    const auto status=root->property("status");
    const auto text=label ? label->property("text") : QVariant();
    const auto errorUrl=root->property("lastLoadErrorUrl");
    const auto errorEpoch=root->property("lastLoadErrorEpochMs");
    if (!label || status.userType()!=QMetaType::QString || text.userType()!=QMetaType::QString
            || errorUrl.userType()!=QMetaType::QString || errorEpoch.userType()!=QMetaType::Double
            || status.toString().size()>8192 || text.toString().size()>8192 || errorUrl.toString().size()>8192
            || !std::isfinite(errorEpoch.toDouble()) || errorEpoch.toDouble()<0
            || errorEpoch.toDouble()>QDateTime::currentMSecsSinceEpoch()
            || std::floor(errorEpoch.toDouble())!=errorEpoch.toDouble()
            || (errorUrl.toString().isEmpty() ? errorEpoch.toDouble()!=0 : errorEpoch.toDouble()<1)) { return result; }
    result["available"]=true;
    result["componentSource"]=original->baseUrl().toString(QUrl::FullyEncoded);
    result["statusText"]=status.toString(); result["labelText"]=text.toString();
    result["errorUrl"]=errorUrl.toString();result["errorEpochMs"]=static_cast<qint64>(errorEpoch.toDouble());
    result["rootVisible"]=scriptManagerVisible(root);
    result["labelVisible"]=label->window()==root->window() && scriptManagerVisible(label);
#else
    Q_UNUSED(root)
#endif
    return result;
}

inline QJsonObject scriptManagerStatus(QQuickItem* item) {
#if defined(OVERTE_E2E_FEATURE_TESTS)
    if (qApp && item && QThread::currentThread()==qApp->thread() && item->thread()==qApp->thread()
            && QCoreApplication::arguments().contains("--testScript") && item->objectName()=="scriptFromFile") {
        int depth {0};
        for (auto parent=item->parentItem();parent && ++depth<=128;parent=parent->parentItem()) {
            if (parent->objectName()!="RunningScripts") { continue; }
            auto loaders=item->parentItem();
            auto content=loaders ? loaders->parentItem() : nullptr;
            QQmlContext* original {nullptr}; int contexts {0};
            for (auto context=qmlContext(item);context && ++contexts<=128;context=context->parentContext()) {
                if (context->nameForObject(parent)=="root"
                        && context->nameForObject(loaders)=="loaders"
                        && context->nameForObject(content)=="content"
                        && context->baseUrl()==PathUtils::qmlUrl(QStringLiteral("hifi/dialogs/TabletRunningScripts.qml"))) {
                    original=context;break;
                }
            }
            if (!original || qmlContext(item)!=qmlContext(loaders)) { break; }
            int controls {0};
            for (auto child:loaders->childItems()) {
                if (child->objectName()=="scriptFromFile") { ++controls; }
            }
            if (controls!=1) { break; }
            return scriptManagerRootStatus(parent);
        }
    }
#else
    Q_UNUSED(item)
#endif
    return {{"managerSourceVersion",2},{"available",false}};
}
} // namespace overte::e2e
