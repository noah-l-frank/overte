// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
#include <QCoreApplication>
#include <QDateTime>
#include <QJsonDocument>
#include <QJsonObject>
#include <QPointer>
#include <QThread>
#include <QVariantMap>
#include <functional>

class QQuickItem;

namespace overte::e2e {
struct NavigationDirectoryEvent {
    QString kind;QPointer<QThread> sourceThread;QVariantMap facts;QVariant message;qint64 epoch{0};
};
struct NavigationDirectoryProvider {
    std::function<void(const NavigationDirectoryEvent&)> event;
    std::function<void(QQuickItem*,const QJsonObject&)> watch;
    std::function<void(QQuickItem*)> changed;
    std::function<QVariantMap(const QVariantMap&)> snapshot;
};
inline const char* navigationDirectoryProperty() { return "_overteE2ENavigationDirectoryProviderV1"; }
inline bool navigationDirectoryEnabled() {
    return QCoreApplication::instance() && QCoreApplication::arguments().contains("--testScript");
}
}
Q_DECLARE_METATYPE(overte::e2e::NavigationDirectoryProvider)
namespace overte::e2e {
inline NavigationDirectoryProvider navigationDirectoryProvider() {
    if (!navigationDirectoryEnabled() || QThread::currentThread()!=QCoreApplication::instance()->thread()) { return {}; }
    const auto value=QCoreApplication::instance()->property(navigationDirectoryProperty());
    return value.userType()==qMetaTypeId<NavigationDirectoryProvider>() ? value.value<NavigationDirectoryProvider>() : NavigationDirectoryProvider();
}
inline void postNavigationDirectoryEvent(NavigationDirectoryEvent event) {
    if (!navigationDirectoryEnabled()) { return; }
    event.sourceThread=QThread::currentThread();event.epoch=QDateTime::currentMSecsSinceEpoch();
    QMetaObject::invokeMethod(QCoreApplication::instance(),[event] {
        const auto provider=navigationDirectoryProvider();if (provider.event) { provider.event(event); }
    },Qt::QueuedConnection);
}
inline void observeNavigationDirectoryOutgoing(const QVariant& original) {
    if (!navigationDirectoryEnabled()) { return; }
    const auto object=QJsonObject::fromVariantMap(original.toMap());
    if (object.value("channel")!="com.overte.places" || object.value("action")!="PLACE_DATA") { return; }
    NavigationDirectoryEvent event;event.kind="outgoing";event.message=original;postNavigationDirectoryEvent(event);
}
}
#endif
