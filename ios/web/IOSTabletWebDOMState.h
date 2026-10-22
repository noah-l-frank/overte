// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include <QtCore/qglobal.h>
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include "IOSTabletWebTrace.h"
#include <QHash>
#include <QPointer>
#include <memory>
namespace overte::ios::tablet_web_dom {
struct Read {
    QVariantMap command,packet,identity,presentation;
    QPointer<QObject> owner;
    std::weak_ptr<void> callbackCapture;
    bool issued { false };
};
struct State {
    world_web_trace::State clock;
    QHash<QString,std::shared_ptr<Read>> reads;
    qint64 storedBytes { 0 };
};
inline State& state() { static State actual;return actual; }
inline QVariantMap packet(const std::shared_ptr<Read>& read,const QString& status,const QVariantMap& source={}) {
    auto& actual=state().clock;
    if (!read || !world_web_trace::enabled() || !world_web_trace::mainThread()) { return {}; }
    const auto now=world_web_trace::clock(actual);
    if (!actual.complete) { return {}; }
    const auto& query=read->command;
    const auto before=read->packet.isEmpty() ? now : read->packet.value("clockBefore").toMap();
    const auto sequence=read->packet.isEmpty() ? ++actual.sequence : read->packet.value("sequence").toULongLong();
    if (!sequence || sequence>9007199254740991ULL) { actual.complete=false;return {}; }
    return {{"iosTabletWebDOMNativeVersion",1},{"commandId",query.value("commandId")},{"runId",query.value("runId")},
        {"fixtureUrl",query.value("fixtureUrl")},{"instance",actual.instance},{"sequence",static_cast<qulonglong>(sequence)},
        {"processId",QCoreApplication::applicationPid()},{"clockDomain","native-main-ios-tablet-web-dom"},
        {"clockBefore",before},{"clockAfter",now},{"status",status},{"source",source}};
}
inline bool store(const std::shared_ptr<Read>& read,const QVariantMap& value) {
    if (!read || value.isEmpty()) { return false; }
    auto& actual=state();
    const auto oldBytes=QJsonDocument(QJsonObject::fromVariantMap(read->packet)).toJson(QJsonDocument::Compact).size();
    const auto newBytes=QJsonDocument(QJsonObject::fromVariantMap(value)).toJson(QJsonDocument::Compact).size();
    const auto total=actual.storedBytes-(read->packet.isEmpty() ? 0 : oldBytes)+newBytes;
    if (newBytes>2097152 || total<0 || total>64*1024*1024) { actual.clock.complete=false;return false; }
    read->packet=value;actual.storedBytes=total;return true;
}
inline std::shared_ptr<Read> begin(const QVariantMap& query) {
    if (!world_web_trace::enabled() || !world_web_trace::mainThread() || !tablet_web_trace::domCommand(query)) { return {}; }
    auto& actual=state();const auto id=query.value("commandId").toString();
    const auto old=actual.reads.value(id);
    if (old) { return QJsonObject::fromVariantMap(old->command)==QJsonObject::fromVariantMap(query) ? old : nullptr; }
    if (actual.reads.size()>=4096 || !actual.clock.complete) { actual.clock.complete=false;return {}; }
    auto read=std::make_shared<Read>();read->command=query;store(read,packet(read,"pending"));
    if (read->packet.isEmpty()) { return {}; }actual.reads.insert(id,read);return read;
}
inline bool pending(const std::shared_ptr<Read>& read) {
    return read && read->packet.value("status")=="pending";
}
inline void failed(const std::shared_ptr<Read>& read) {
    if (pending(read)) { store(read,packet(read,"unavailable")); }
}
inline bool fresh(const std::shared_ptr<Read>& read) {
    if (!pending(read)) { return false; }
    const auto now=world_web_trace::clock(state().clock);const auto before=read->packet.value("clockBefore").toMap();
    if (!state().clock.complete || now.value("epochMs").toLongLong()-before.value("epochMs").toLongLong()>=1500
            || now.value("monotonicMs").toLongLong()-before.value("monotonicMs").toLongLong()>=1500) { failed(read);return false; }
    return true;
}
// Only terminal original reads are replayed as cached results. Pending polls
// retain the same original acquisition/query clock, never start another JS read.
} // namespace overte::ios::tablet_web_dom
#endif
