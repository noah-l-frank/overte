// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include <CreateEntityObservation.h>
#include <EntityScriptingInterface.h>
#include <EntityTree.h>
#include <QJsonDocument>
#include <QRegularExpression>
#include <QThread>

namespace overte::e2e {
// A separate bounded original source: real API returns, actual Tree map birth/
// removal, and independently observed weak destruction. No ownership setter or
// supplied entity ID, event floor, reset, tree mutation or queue drain exists.
class IOSCreateEntitiesObservation {
public:
    IOSCreateEntitiesObservation() { _clock.start(); }
    QVariantMap read(const QString& request,const QString& run,EntityScriptingInterface* entities) {
        auto app=QCoreApplication::instance();
        if (!app || QThread::currentThread()!=app->thread() || !QCoreApplication::arguments().contains("--testScript")
                || _sequence>=1000000000 || !QRegularExpression("^ios-[a-f0-9]{32}$").match(request).hasMatch()
                || !QRegularExpression("^[a-f0-9]{32}$").match(run).hasMatch() || !entities || !entities->getEntityTree()) { return {}; }
        const auto before=clock();const auto tree=entities->getEntityTree();
        const QVariantMap source{{"calls",CreateEntityObservation::instance().snapshot()},{"tree",tree->featureEntityLifetimes()}};
        const auto after=clock();
        if (source.value("calls").toMap().isEmpty() || source.value("tree").toMap().isEmpty()
                || QJsonDocument::fromVariant(source).toJson(QJsonDocument::Compact).size()>1040000) { return {}; }
        return {{"iosCreateEntitiesVersion",1},{"requestId",request},{"runId",run},{"instance",_instance},
            {"sequence",static_cast<double>(++_sequence)},{"processId",static_cast<double>(QCoreApplication::applicationPid())},
            {"clockDomain","native-main-create-entities"},{"clockBefore",before},{"clockAfter",after},{"source",source}};
    }
private:
    QVariantMap clock() const { return {{"epochMs",static_cast<double>(QDateTime::currentMSecsSinceEpoch())},
        {"monotonicMs",static_cast<double>(_clock.elapsed())}}; }
    const QString _instance {QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')};
    quint64 _sequence {0};QElapsedTimer _clock;
};
} // namespace overte::e2e
#endif
