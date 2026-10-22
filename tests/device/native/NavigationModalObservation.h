// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PHONE_INTERFACE)
#include <QCoreApplication>
#include <QDateTime>
#include <QPointer>
#include <QQuickItem>
#include <QThread>
#include <QUuid>
#include <QVariantMap>
namespace overte::e2e {
// Weak identities from the actual AddressBarDialog not-found slot. An identical
// modal manufactured by a Script cannot acquire the native callback's identity.
class NavigationModalObservation {
public:
    static void created(QQuickItem* item,const QVariantMap& event) {
        if (!enabled() || !item || event.isEmpty() || item->thread()!=qApp->thread()) { return; }
        auto& source=instance();
        if (!source.valid || source.rows.size()>=128
                || !event.value("contentNotFound").toBool() || event.value("httpStatus").toInt()!=404
                || !event.value("current").toBool()) { source.valid=false;return; }
        const auto now=QDateTime::currentMSecsSinceEpoch();
        if (now<event.value("callbackEpochMs").toLongLong()) { source.valid=false;return; }
        source.rows.append({item,{{"modalId",QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')},
            {"createdEpochMs",now},{"nativeEvent",event}}});
    }
    static QVariantMap original(QQuickItem* item) {
        if (!enabled() || !item || !instance().valid) { return {}; }
        QVariantMap found;
        for (const auto& row:instance().rows) {
            if (row.item==item) { if (!found.isEmpty()) { return {}; }found=row.original; }
        }
        return found;
    }
private:
    struct Row { QPointer<QQuickItem> item;QVariantMap original; };
    static bool enabled() { return qApp && QThread::currentThread()==qApp->thread() && QCoreApplication::arguments().contains("--testScript"); }
    static NavigationModalObservation& instance() { static NavigationModalObservation value;return value; }
    QList<Row> rows;bool valid{true};
};
}
#endif
