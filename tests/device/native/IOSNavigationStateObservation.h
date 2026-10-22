// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include <QCoreApplication>
#include <QDateTime>
#include <QElapsedTimer>
#include <QJsonDocument>
#include <QThread>
#include <QUuid>
#include <QVariantMap>
#include <functional>

namespace overte::e2e {
// A native GUI-thread read bracket, not a render fence or arrival verdict.
class IOSNavigationStateObservation {
public:
    IOSNavigationStateObservation() { _clock.start(); }
    QVariantMap read(const QString& request,const QString& run,const std::function<QVariantMap()>& reader) {
        if (!qApp || QThread::currentThread()!=qApp->thread() || !reader || _sequence>=1000000000
                || !QCoreApplication::arguments().contains("--testScript")) { return {}; }
        const auto before=clock();const auto source=reader();const auto after=clock();
        if (source.isEmpty() || QJsonDocument::fromVariant(source).toJson(QJsonDocument::Compact).size()>250000) { return {}; }
        return {{"iosNavigationStateVersion",1},{"requestId",request},{"runId",run},{"instance",_instance},
            {"sequence",static_cast<double>(++_sequence)},{"processId",static_cast<double>(QCoreApplication::applicationPid())},
            {"clockDomain","native-main-navigation"},{"clockBefore",before},{"clockAfter",after},{"source",source}};
    }
private:
    QVariantMap clock() const { return {{"epochMs",static_cast<double>(QDateTime::currentMSecsSinceEpoch())},
        {"monotonicMs",static_cast<double>(_clock.elapsed())}}; }
    QString _instance=QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');
    quint64 _sequence {0};QElapsedTimer _clock;
};
} // namespace overte::e2e
#endif
