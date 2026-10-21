// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
#include <QCoreApplication>
#include <QDateTime>
#include <QJsonObject>
#include <QPointer>
#include <QRegularExpression>
#include <QSet>
#include <QThread>
#include <QVariantMap>
#include <functional>

namespace overte::e2e {
struct TabletHttpEvent {
    QString lease, kind, replyId, urlSha256;
    qint64 occurredEpochMs {0};
    QVariantMap state;
    QPointer<QObject> request, reply;
};
struct TabletHttpProvider {
    std::function<void(QObject*)> observeTree;
    std::function<QString(QObject*,const QVariantMap&)> begin;
    std::function<void(const TabletHttpEvent&)> event;
    std::function<QVariantMap(const QVariantMap&)> snapshot;
};
inline const char* tabletHttpProperty() { return "_overteE2ETabletHttpProviderV1"; }
inline bool tabletHttpEnabled() {
    if (!QCoreApplication::instance()) { return false; }
    const auto args=QCoreApplication::arguments();
    const int script=args.indexOf("--testScript"),results=args.indexOf("--testResultsLocation");
    return script>=0 && script+1<args.size() && !args[script+1].isEmpty()
        && results>=0 && results+1<args.size() && !args[results+1].isEmpty();
}
inline bool tabletHttpCommand(const QVariantMap& input) {
    const auto json=QJsonObject::fromVariantMap(input);const auto keys=json.keys();
    return QSet<QString>(keys.begin(),keys.end())==QSet<QString>{"schemaVersion","commandId","action","runId"}
        && json.value("schemaVersion")==QJsonValue(1) && json.value("action")==QJsonValue("feature-tablet-http-observe")
        && QRegularExpression("\\A[0-9a-f]{32}\\z").match(json.value("commandId").toString()).hasMatch()
        && QRegularExpression("\\A[0-9a-f]{32}\\z").match(json.value("runId").toString()).hasMatch();
}
}
Q_DECLARE_METATYPE(overte::e2e::TabletHttpProvider)
namespace overte::e2e {
inline void postTabletHttpEvent(TabletHttpEvent event) {
    if (!tabletHttpEnabled()) { return; }
    if (!event.occurredEpochMs) { event.occurredEpochMs=QDateTime::currentMSecsSinceEpoch(); }
    QMetaObject::invokeMethod(QCoreApplication::instance(),[event] {
        const auto value=QCoreApplication::instance()->property(tabletHttpProperty());
        if (value.userType()!=qMetaTypeId<TabletHttpProvider>()) { return; }
        const auto provider=value.value<TabletHttpProvider>();
        if (provider.event) { provider.event(event); }
    },Qt::QueuedConnection);
}
}
#endif
