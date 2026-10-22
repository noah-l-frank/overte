// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include <QtCore/qglobal.h>
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include "IOSWorldWebTrace.h"
#include "../../tests/device/native/IOSTabletSourcesObservation.h"

namespace overte::ios::tablet_web_trace {
using Function=std::function<QVariantMap(const QVariantMap&)>;
struct Provider final:Function { using Function::Function; };
inline const char* providerProperty() { return "_overteE2EIOSTabletWebProviderV1"; }
inline const char* domProviderProperty() { return "_overteE2EIOSTabletWebDOMProviderV1"; }
inline bool command(const QVariantMap& value) {
    auto original=value;
    if (QJsonObject::fromVariantMap(value).value("action")!=QJsonValue("feature-ios-tablet-web")) { return false; }
    original["action"]="feature-ios-tablet-sources";return overte::e2e::tablet_sources::command(original);
}
inline bool domCommand(const QVariantMap& value) {
    auto original=value;
    if (QJsonObject::fromVariantMap(value).value("action")!=QJsonValue("feature-ios-tablet-web-dom")) { return false; }
    original["action"]="feature-ios-tablet-web";return command(original);
}
// The native view supplies its immutable source-input association, established
// during its actual policy grant. Query parameters cannot introduce ownership.
inline QString rootFor(const QVariantMap& identity) {
    if (identity.value("surface")!="tablet") { return {}; }
    const auto source=identity.value("source").toMap();const auto keys=source.keys();
    if (QSet<QString>(keys.begin(),keys.end())!=QSet<QString>{"root","navigation","fixtureUrl","carrier","binding"}) { return {}; }
    const QRegularExpression identifier("\\A[0-9a-f]{32}\\z");
    if (!identifier.match(source.value("root").toString()).hasMatch() || !identifier.match(source.value("navigation").toString()).hasMatch()) { return {}; }
    const auto json=QJsonObject::fromVariantMap(source);
    if (!(json.value("carrier").isNull() && json.value("binding").isNull())
            && !(identifier.match(json.value("carrier").toString()).hasMatch() && identifier.match(json.value("binding").toString()).hasMatch())) { return {}; }
    const auto root=source.value("fixtureUrl").toString();const QUrl url(root,QUrl::StrictMode);
    if (!url.isValid() || root.size()>512 || (url.scheme()!="http" && url.scheme()!="https") || url.host().isEmpty()
            || !url.userInfo().isEmpty() || url.hasQuery() || url.hasFragment() || url.toString(QUrl::FullyEncoded)!=root
            || !QRegularExpression("\\A/feature-fixture/v1/runs/[0-9a-f]{32}/\\z").match(url.path()).hasMatch()) { return {}; }
    return root;
}
// Reuse only the source-neutral monotonic clock/counter container, with an
// independent actual Tablet instance. World events/DTOs remain unchanged.
using State=world_web_trace::State;
inline State& state() { static State original;return original; }
inline quint64 event(const QVariantMap& identity,const QString& kind,const QVariantMap& detail={}) {
    if (!world_web_trace::enabled() || rootFor(identity).isEmpty()) { return 0; }
    auto& actual=state();QMutexLocker guard(&actual.mutex);
    if (!world_web_trace::mainThread() || actual.events.size()>=4096 || actual.eventSequence>=9007199254740991ULL
            || QJsonDocument(QJsonObject::fromVariantMap(detail)).toJson(QJsonDocument::Compact).size()>32768) { actual.complete=false;return 0; }
    const auto stamp=world_web_trace::clock(actual);const auto ordinal=++actual.eventSequence;
    actual.events.push_back(QVariantMap{{"sequence",static_cast<qulonglong>(ordinal)},{"eventId",world_web_trace::nonce()},
        {"kind",kind},{"clock",stamp},{"identity",identity},{"detail",detail}});return ordinal;
}
inline QVariantMap observe(const QVariantMap& query) {
    if (!world_web_trace::enabled() || !world_web_trace::mainThread() || !command(query)) { return {}; }
    auto& actual=state();QMutexLocker guard(&actual.mutex);const auto before=world_web_trace::clock(actual);
    QVariantList events;const auto root=query.value("fixtureUrl").toString();
    for (const auto& entry:actual.events) { if (rootFor(entry.toMap().value("identity").toMap())==root) { events.push_back(entry); } }
    if (actual.sequence>=9007199254740991ULL) { actual.complete=false;return {}; }
    const auto after=world_web_trace::clock(actual);
    QVariantMap result{{"iosTabletWebVersion",1},{"commandId",query.value("commandId")},{"runId",query.value("runId")},{"fixtureUrl",root},
        {"instance",actual.instance},{"sequence",static_cast<qulonglong>(++actual.sequence)},{"processId",QCoreApplication::applicationPid()},
        {"clockDomain","native-main-ios-tablet-web"},{"clockBefore",before},{"clockAfter",after},{"complete",actual.complete},
        {"eventSequence",static_cast<qulonglong>(actual.eventSequence)},{"events",events}};
    if (QJsonDocument(QJsonObject::fromVariantMap(result)).toJson(QJsonDocument::Compact).size()>2097152) { actual.complete=false;return {}; }
    return result;
}
} // namespace overte::ios::tablet_web_trace
Q_DECLARE_METATYPE(overte::ios::tablet_web_trace::Provider)
#endif
