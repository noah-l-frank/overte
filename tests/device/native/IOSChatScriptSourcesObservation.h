// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include <QCoreApplication>
#include <QDateTime>
#include <QElapsedTimer>
#include <QJsonDocument>
#include <QUuid>
#include <QVariantMap>
#include <functional>

namespace overte::e2e {
// Actual submitted VM inputs and all-known Chat-manager lifetimes only.
// This does not identify compiled QML bytes or prove a Chat send/receive effect.
class IOSChatScriptSourcesObservation {
public:
    static IOSChatScriptSourcesObservation& instance() {static IOSChatScriptSourcesObservation value;return value;}
    QVariantMap read(const QString& request,const QString& run,const std::function<QVariantMap()>& source) {
        if (!QCoreApplication::arguments().contains("--testScript") || _sequence>=1000000000ULL) {return {};}
        const auto before=clock();const auto original=source();const auto after=clock();
        if (original.isEmpty()) {return {};}
        QVariantMap result{{"iosChatScriptSourcesVersion",1},{"requestId",request},{"runId",run},{"instance",_instance},
            {"sequence",static_cast<qulonglong>(++_sequence)},{"processId",QCoreApplication::applicationPid()},
            {"clockDomain","native-main-chat-script-sources"},{"clockBefore",before},{"clockAfter",after},{"source",original}};
        if (QJsonDocument::fromVariant(result).toJson(QJsonDocument::Compact).size()>262144) {return {};}
        return result;
    }
private:
    IOSChatScriptSourcesObservation() {_timer.start();}
    QVariantMap clock() const {return {{"epochMs",QDateTime::currentMSecsSinceEpoch()},{"monotonicMs",_timer.elapsed()}};}
    QElapsedTimer _timer;quint64 _sequence{0};
    const QString _instance{QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')};
};
}
#endif
