// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS) && defined(OVERTE_IOS_E2E_TEST_BUILD)
#include "NormalChatControls.h"
#include <qml/IOSQmlSourceObservation.h>
#include <QElapsedTimer>
#include <QCoreApplication>
#include <QDateTime>
#include <QJsonDocument>
#include <QPointer>
#include <QThread>
#include <QUuid>

namespace overte::e2e {
class IOSChatQmlSourcesObservation {
public:
    static IOSChatQmlSourcesObservation& instance() { static IOSChatQmlSourcesObservation value; return value; }
    QVariantMap read(const QString& request, const QString& run) {
        if (!qApp || QThread::currentThread() != qApp->thread()
                || !QCoreApplication::arguments().contains("--testScript") || _sequence >= 1000000000ULL) { return {}; }
        const auto before = clock();
        QPointer<QQuickItem> page;
        // All successful observed loads participate, including roots whose
        // cache/compiler association is unavailable. No Tablet getter creates UI.
        for (auto object : hifi::qml::IOSQmlSourceObservation::liveObjects()) {
            auto item = qobject_cast<QQuickItem*>(object);
            if (!item || item->thread() != qApp->thread() || chatPage(item) != item || page) { return {}; }
            page = item;
        }
        if (!page) { return {}; }
        const auto source = hifi::qml::IOSQmlSourceObservation::read(page);
        const auto control = chatControlSource(page, "chat.page");
        if (source.isEmpty() || control.isEmpty()) { return {}; }
        const auto after = clock();
        QVariantMap result {{"iosChatQmlSourcesVersion", 1}, {"requestId", request}, {"runId", run},
            {"instance", _instance}, {"sequence", qulonglong(++_sequence)}, {"processId", QCoreApplication::applicationPid()},
            {"clockDomain", "native-main-chat-qml-sources"}, {"clockBefore", before}, {"clockAfter", after},
            {"pageControlSourceSha256", control}, {"source", source}};
        return QJsonDocument::fromVariant(result).toJson(QJsonDocument::Compact).size() <= 65536 ? result : QVariantMap();
    }
private:
    IOSChatQmlSourcesObservation() { _timer.start(); }
    QVariantMap clock() const { return {{"epochMs", QDateTime::currentMSecsSinceEpoch()}, {"monotonicMs", _timer.elapsed()}}; }
    QElapsedTimer _timer;
    quint64 _sequence { 0 };
    const QString _instance { QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-') };
};
}
#endif
