// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include "WebRuntimeBridge.h"
#include <QDateTime>
#include <QElapsedTimer>
#include <QMutex>
#include <QMutexLocker>
#include <QCryptographicHash>
#include <QJsonDocument>
#include <memory>
namespace overte::e2e {
inline bool picoWorldCurrentDocumentCommand(const QVariantMap& input) {
    const auto object=QJsonObject::fromVariantMap(input);const auto keys=object.keys();
    if (QSet<QString>(keys.begin(),keys.end())!=QSet<QString>{"schemaVersion","commandId","action","runId","fixtureUrl","operation","ownerToken"}
        || object.value("action")!=QJsonValue("pico-world-web") || object.value("operation")!=QJsonValue("observe-current-document")
        || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(object.value("ownerToken").toString()).hasMatch()) return false;
    auto base=input;base.remove("operation");base.remove("ownerToken");base.insert("action","feature-web-runtime-observe");
    return webRuntimeCommand(base);
}
class PicoCurrentClock final {
    static QElapsedTimer start(){QElapsedTimer timer;timer.start();return timer;}
public:
    const QElapsedTimer timer{start()};
    const qint64 epoch{QDateTime::currentMSecsSinceEpoch()};
    const qint64 monotonic{timer.msecsSinceReference()};
    bool fresh()const {const auto delta=QDateTime::currentMSecsSinceEpoch()-epoch;
        return timer.isValid() && timer.isMonotonic() && epoch>0 && delta>=-250 && delta<=1500 && timer.elapsed()>=0 && timer.elapsed()<=1500;}
    qint64 nowMonotonic()const {QElapsedTimer current;current.start();return current.msecsSinceReference();}
};
using PicoCurrentAnchor=std::shared_ptr<const PicoCurrentClock>;
// One exported owner in picoOpenXR; interface calls the same pre-queue factory.
Q_DECL_EXPORT PicoCurrentAnchor picoCurrentAnchor(const QVariantMap& command);
using PicoCurrentProvider=std::function<QVariantMap(const QVariantMap&,PicoCurrentAnchor)>;
inline const char* picoCurrentDocumentProperty(){return "_overteE2EPicoWorldCurrentDocumentProviderV1";}
}
Q_DECLARE_METATYPE(overte::e2e::PicoCurrentProvider)
#endif
