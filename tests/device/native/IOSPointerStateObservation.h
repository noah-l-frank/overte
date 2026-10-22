// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include "IOSPointerObservation.h"
#include <QRegularExpression>

namespace overte::e2e {
class IOSPointerStateObservation {
public:
    IOSPointerStateObservation() { _clock.start(); }
    QVariantMap read(const QString& request,const QString& run,bool actualWorldTapActive) {
        auto app=QCoreApplication::instance();
        if (!app || app->thread()!=QThread::currentThread() || !IOSPointerObservation::enabled() || _sequence>=1000000000
                || !QRegularExpression("^ios-[a-f0-9]{32}$").match(request).hasMatch()
                || !QRegularExpression("^[a-f0-9]{32}$").match(run).hasMatch()) { return {}; }
        const auto before=clock();const auto source=IOSPointerObservation::instance().snapshot(actualWorldTapActive);const auto after=clock();
        if (source.isEmpty() || QJsonDocument::fromVariant(source).toJson(QJsonDocument::Compact).size()>1040000) { return {}; }
        return {{"iosPointerStateVersion",1},{"requestId",request},{"runId",run},{"instance",_instance},{"sequence",static_cast<double>(++_sequence)},
            {"processId",static_cast<double>(QCoreApplication::applicationPid())},{"clockDomain","native-main-ios-pointer"},
            {"clockBefore",before},{"clockAfter",after},{"source",source}};
    }
private:
    QVariantMap clock() const { return {{"epochMs",static_cast<double>(QDateTime::currentMSecsSinceEpoch())},{"monotonicMs",static_cast<double>(_clock.elapsed())}}; }
    const QString _instance{QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')};quint64 _sequence{0};QElapsedTimer _clock;
};
} // namespace overte::e2e
#endif
