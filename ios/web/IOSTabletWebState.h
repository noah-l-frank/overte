// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include <QtCore/qglobal.h>
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include "IOSTabletWebTrace.h"
#include <QPointer>

namespace overte::ios::tablet_web_state {
using Function=std::function<QVariantMap(const QVariantMap&)>;
struct Provider final:Function {using Function::Function;};
inline const char* providerProperty() {return "_overteE2EIOSTabletWebStateProviderV1";}
inline bool command(const QVariantMap& value) {
    if (QJsonObject::fromVariantMap(value).value("action")!=QJsonValue("feature-ios-tablet-web-state")) {return false;}
    auto original=value;original["action"]="feature-ios-tablet-web";return tablet_web_trace::command(original);
}
struct Owner {
    QString id,handle,fixture;QVariantMap source,firstObserved,expired;QPointer<QObject> object;
};
struct State {
    const QString instance{world_web_trace::nonce()};QElapsedTimer timer;qint64 epoch{0},mono{0};quint64 sequence{0};bool complete{true};
    QList<std::shared_ptr<Owner>> owners;
    State() {timer.start();}
};
inline State& state() {static State actual;return actual;}
inline QVariantMap clock(State& actual) {
    const auto epoch=QDateTime::currentMSecsSinceEpoch(),mono=actual.timer.elapsed();
    if (epoch<=0 || mono<0 || epoch<actual.epoch || mono<actual.mono || (actual.epoch && qAbs(epoch-actual.epoch-mono+actual.mono)>250)) {actual.complete=false;}
    actual.epoch=epoch;actual.mono=mono;return {{"epochMs",epoch},{"monotonicMs",mono}};
}
// Registration is an observation of an existing native object and its actual
// historical SourceStamp. Each source association is immutable; multiple
// observations can share the same actual weak QObject. Neither firstObserved
// nor sourceCurrent=false is an allocation birth or weak expiry. The read
// query cannot introduce a source association.
inline void observed(QObject* object,const QVariantMap& identity) {
    const auto fixture=tablet_web_trace::rootFor(identity);if (!object || fixture.isEmpty()) {return;}
    const auto source=identity.value("source").toMap();
    auto& actual=state();for (const auto& row:actual.owners) {
        if (row->object==object && row->fixture==fixture && QJsonObject::fromVariantMap(row->source)==QJsonObject::fromVariantMap(source)) {return;}
    }
    if (actual.owners.size()>=1024) {actual.complete=false;return;}
    auto row=std::make_shared<Owner>();row->id=world_web_trace::nonce();row->handle=identity.value("handle").toString();row->fixture=fixture;
    row->source=source;row->object=object;row->firstObserved=clock(actual);actual.owners.push_back(row);
}
} // namespace overte::ios::tablet_web_state
Q_DECLARE_METATYPE(overte::ios::tablet_web_state::Provider)
#endif
