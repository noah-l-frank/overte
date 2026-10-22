// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include <QtCore/qglobal.h>
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include "IOSTabletWebTrace.h"
#include "IOSWebClosureTrace.h"
#include <QJsonArray>
#include <QJsonParseError>
#include <QScopeGuard>
#include <map>
#include <cmath>
#include <memory>

namespace overte::ios::tablet_web_deferred {
using Function=std::function<QVariantMap(const QVariantMap&)>;
struct Provider final:Function { using Function::Function; };
inline const char* providerProperty() { return "_overteE2EIOSTabletWebDeferredProviderV1"; }
inline const char* faultProviderProperty() { return "_overteE2EIOSTabletWebDeferProviderV1"; }
// Only the original native callsite supplies identity, arguments and closure.
// Commands can schedule the next real parity callback; they cannot supply it.
struct Record {
    QString id,run,fixture,armCommand,deliveryCommand,discardCommand;QVariantMap identity,armed,captured,delivering,returned,unwound,discarded,expired,overdue;
    QString envelope,nonce,frame,sha;bool mainFrame{false};quint64 generation{0};
    std::function<void()> callback;std::weak_ptr<void> lifetime;
};
struct State {
    const QString instance{world_web_trace::nonce()};QElapsedTimer timer;
    qint64 epoch{0},mono{0};quint64 sequence{0},commandSequence{0};bool complete{true};QString failure;
    QList<std::shared_ptr<Record>> records;std::map<QString,std::pair<QVariantMap,QVariantMap>> commands;
    State() { timer.start(); }
};
inline State& state() { static auto* actual=new State;return *actual; }
inline void fail(const QString& reason) { auto& actual=state();actual.complete=false;if (actual.failure.isEmpty()) { actual.failure=reason; } }
inline QVariantMap clock() {
    auto& actual=state();const auto epoch=QDateTime::currentMSecsSinceEpoch(),mono=actual.timer.elapsed();
    if (epoch<=0 || mono<0 || epoch<actual.epoch || mono<actual.mono || (actual.epoch && qAbs(epoch-actual.epoch-mono+actual.mono)>250)) { fail("clock-discontinuity"); }
    actual.epoch=epoch;actual.mono=mono;return {{"epochMs",epoch},{"monotonicMs",mono}};
}
inline bool enabled() { return overte::e2e::tablet_sources::enabled() && overte::e2e::tablet_sources::mainThread(); }
inline bool query(const QVariantMap& input,bool operation=false) {
    auto original=input;
    if (QJsonObject::fromVariantMap(input).value("action")!=QJsonValue(operation ? "feature-ios-tablet-web-defer" : "feature-ios-tablet-web-deferred")) { return false; }
    if (operation) {
        const auto value=QJsonObject::fromVariantMap(input).value("operation");
        if (value!=QJsonValue("arm") && value!=QJsonValue("deliver") && value!=QJsonValue("discard")) { return false; }original.remove("operation");
        if (value!=QJsonValue("arm")) {
            if (!QRegularExpression("\\A[0-9a-f]{32}\\z").match(QJsonObject::fromVariantMap(input).value("recordId").toString()).hasMatch()) { return false; }
            original.remove("recordId");
        }
    }
    original["action"]="feature-ios-tablet-sources";return overte::e2e::tablet_sources::command(original);
}
inline void sweep() {
    for (const auto& row:state().records) {
        if (!row->captured.isEmpty() && row->lifetime.expired() && row->expired.isEmpty()) { row->expired=clock(); }
        if (!row->armed.isEmpty() && row->discarded.isEmpty() && row->returned.isEmpty() && row->unwound.isEmpty()
                && row->overdue.isEmpty() && state().timer.elapsed()-row->armed.value("monotonicMs").toLongLong()>=30000) {
            row->overdue=clock();fail("hold-deadline-exceeded");
            // In particular, do NOT clear a captured callback on timeout. An
            // explicit issued-once deliver/discard retains cleanup ownership.
        }
    }
}
inline bool parityEnvelope(const QString& raw,int originalMethod) {
    const auto bytes=raw.toUtf8();if (originalMethod<0 || bytes.isEmpty() || bytes.size()>4096) { return false; }
    QJsonParseError error;const auto document=QJsonDocument::fromJson(bytes,&error);
    if (error.error!=QJsonParseError::NoError || !document.isObject()) { return false; }
    const auto outer=document.object();const auto keys=outer.keys();auto expected=QSet<QString>{"type","object","method","args"};
    if (outer.contains("id")) { expected.insert("id");const auto id=outer.value("id");if (!id.isDouble() || id.toDouble()<0 || id.toDouble()>9007199254740991.0 || std::floor(id.toDouble())!=id.toDouble()) { return false; } }
    if (QSet<QString>(keys.begin(),keys.end())!=expected || outer.value("type")!=QJsonValue(6) || outer.value("object")!=QJsonValue("eventBridge")) { return false; }
    const auto method=outer.value("method");
    if (method!=QJsonValue(originalMethod) && method!=QJsonValue("emitWebEvent") && method!=QJsonValue("emitWebEvent(QVariant)")) { return false; }
    const auto args=outer.value("args");if (!args.isArray() || args.toArray().size()!=1 || !args.toArray()[0].isString()) { return false; }
    const auto packet=QJsonDocument::fromJson(args.toArray()[0].toString().toUtf8(),&error);
    if (error.error!=QJsonParseError::NoError || !packet.isObject()) { return false; }
    const auto body=packet.object();const auto fields=body.keys();const auto seq=body.value("sequence");
    return QSet<QString>(fields.begin(),fields.end())==QSet<QString>{"contract","action","sequence"}
        && body.value("contract")==QJsonValue("overte-web-parity-v1") && body.value("action")==QJsonValue("echo")
        && seq.isDouble() && seq.toDouble()>=1 && seq.toDouble()<=1000000 && std::floor(seq.toDouble())==seq.toDouble();
}
inline std::shared_ptr<Record> pending(const QString& fixture) {
    std::shared_ptr<Record> selected;
    for (const auto& row:state().records) {
        if (row->fixture==fixture && row->discarded.isEmpty() && row->returned.isEmpty() && row->unwound.isEmpty()
                && (row->overdue.isEmpty() || !row->captured.isEmpty())) {
            if (selected) { fail("multiple-pending-holds");return {}; }selected=row;
        }
    }return selected;
}
inline bool occupied() {
    for (const auto& row:state().records) {
        if (row->callback || !row->lifetime.expired()
                || (row->captured.isEmpty() && row->discarded.isEmpty() && row->overdue.isEmpty())) { return true; }
    }return false;
}
inline QVariantMap receipt(const QVariantMap& command,const QString& status,const QString& record={}) {
    auto& actual=state();const auto found=actual.commands.find(command.value("commandId").toString());
    const auto old=found==actual.commands.end() ? QVariantMap() : found->second.second;
    return {{"iosTabletWebDeferReceiptVersion",1},{"command",command},{"instance",actual.instance},
        {"sequence",old.isEmpty() ? QVariant::fromValue<qulonglong>(actual.commandSequence) : old.value("sequence")},
        {"issued",old.isEmpty() ? QVariant(clock()) : old.value("issued")},
        {"completed",status=="issued" ? QVariant() : QVariant(clock())},
        {"status",status},{"record",record.isEmpty() ? QVariant() : QVariant(record)}};
}
inline QVariantMap command(const QVariantMap& input,const QVariantMap& actualInlineIdentity={}) {
    if (!enabled() || !query(input,true)) { return {}; }auto& actual=state();
    const auto commandId=input.value("commandId").toString();const auto found=actual.commands.find(commandId);
    if (found!=actual.commands.end()) { if (found->second.first!=input) { fail("command-nonce-rewritten");return {}; }return found->second.second; }
    if (actual.commands.size()>=4096) { fail("command-capacity");return {}; }
    // Claim the actual native command BEFORE touching the held responsibility.
    ++actual.commandSequence;actual.commands.emplace(commandId,std::make_pair(input,receipt(input,"issued")));sweep();
    const auto operation=input.value("operation").toString(),fixture=input.value("fixtureUrl").toString();auto row=pending(fixture);
    QVariantMap result;
    if (operation=="arm") {
        const auto source=actualInlineIdentity.value("source").toMap();
        if (!actual.complete || occupied() || actual.records.size()>=128 || tablet_web_trace::rootFor(actualInlineIdentity)!=fixture
                || source.value("carrier").isNull() || source.value("binding").isNull()) { result=receipt(input,"refused"); }
        else {
            row=std::make_shared<Record>();row->id=world_web_trace::nonce();row->run=input.value("runId").toString();row->fixture=fixture;
            row->identity=actualInlineIdentity;row->armCommand=commandId;row->armed=clock();actual.records.push_back(row);result=receipt(input,"armed",row->id);
        }
    } else if (!row || row->id!=input.value("recordId").toString()) { result=receipt(input,"refused"); }
    else if (operation=="discard") {
        // This retires only the actual fault-owned closure. It neither closes
        // the product view nor claims native input/resource/UI drainage.
        row->discardCommand=commandId;row->discarded=clock();row->callback={};sweep();result=receipt(input,"discarded",row->id);
    } else if (row->captured.isEmpty() || !row->callback) { result=receipt(input,"refused",row->id); }
    else {
        row->deliveryCommand=commandId;auto original=std::move(row->callback);row->delivering=clock();bool returned=false;
        const auto finish=qScopeGuard([row,&returned] {
            if (returned) { row->returned=clock(); }else { fail("held-callback-exception"); }row->unwound=clock();
        });
        original();returned=true;result=receipt(input,"delivered",row->id);
        // original's actual capture is released on scope exit, after the body
        // returns. sweep in a later read observes the separate weak death.
    }
    actual.commands[commandId].second=result;return result;
}
inline bool intercept(const QVariantMap& actualIdentity,quint64 actualGeneration,const QString& envelope,const QString& nonce,
        const QUrl& frame,bool mainFrame,int originalMethod,const feature_closures::ContextPointer& originalContext,std::function<void()> original) {
    if (!enabled()) { return false; }sweep();const auto fixture=tablet_web_trace::rootFor(actualIdentity);auto row=pending(fixture);
    if (!row || !row->captured.isEmpty() || !row->overdue.isEmpty() || !parityEnvelope(envelope,originalMethod)) { return false; }
    if (row->identity!=actualIdentity || actualGeneration!=actualIdentity.value("grant").toULongLong() || !mainFrame
            || actualIdentity.value("nonce")!=nonce || actualIdentity.value("url")!=frame.toString(QUrl::FullyEncoded) || !original || !originalContext) {
        fail("held-source-changed");return false;
    }
    // This lifetime token and the actual neutral JavaScript context lease are
    // captured ONLY by the held original closure, never by a snapshot/reader.
    auto lifetime=std::make_shared<char>(0);row->lifetime=lifetime;
    const auto lease=feature_closures::retain(originalContext,feature_closures::Kind::JavaScript);
    if (!lease) { fail("held-context-unavailable");return false; }
    const auto captured=clock();
    if (captured.value("monotonicMs").toLongLong()-row->armed.value("monotonicMs").toLongLong()>=30000) { row->overdue=captured;fail("hold-deadline-exceeded");return false; }
    row->envelope=envelope;row->nonce=nonce;row->frame=frame.toString(QUrl::FullyEncoded);row->mainFrame=mainFrame;row->generation=actualGeneration;
    row->sha=QString::fromLatin1(QCryptographicHash::hash(envelope.toUtf8(),QCryptographicHash::Sha256).toHex());row->captured=captured;
    row->callback=[original=std::move(original),lifetime,lease] { original(); };return true;
}
inline QVariantMap observe(const QVariantMap& input) {
    if (!enabled() || !query(input)) { return {}; }auto& actual=state();const auto before=clock();sweep();QVariantList rows,commands;
    for (const auto& row:actual.records) {
        if (row->fixture!=input.value("fixtureUrl")) { continue; }
        QVariantMap value{{"id",row->id},{"identity",row->identity},{"armCommand",row->armCommand},
            {"deliveryCommand",row->deliveryCommand.isEmpty() ? QVariant() : QVariant(row->deliveryCommand)},
            {"discardCommand",row->discardCommand.isEmpty() ? QVariant() : QVariant(row->discardCommand)},
            {"armed",row->armed},{"bufferPending",static_cast<bool>(row->callback)},{"callbackAlive",!row->lifetime.expired()}};
        for (const auto& item:std::initializer_list<std::pair<const char*,QVariantMap>>{{"captured",row->captured},{"delivering",row->delivering},
                {"returned",row->returned},{"finally",row->unwound},{"discarded",row->discarded},{"expired",row->expired},{"overdue",row->overdue}}) {
            value[item.first]=item.second.isEmpty() ? QVariant() : QVariant(item.second);
        }
        value["original"]=row->captured.isEmpty() ? QVariant() : QVariant(QVariantMap{{"envelope",row->envelope},{"envelopeSha256",row->sha},
            {"nonce",row->nonce},{"frame",row->frame},{"mainFrame",row->mainFrame},{"generation",static_cast<qulonglong>(row->generation)}});
        rows.push_back(value);
    }
    for (const auto& entry:actual.commands) { if (entry.second.first.value("fixtureUrl")==input.value("fixtureUrl")) { commands.push_back(entry.second.second); } }
    if (actual.sequence>=9007199254740991ULL) { fail("query-capacity");return {}; }
    QVariantMap value{{"iosTabletWebDeferredVersion",1},{"commandId",input.value("commandId")},{"runId",input.value("runId")},{"fixtureUrl",input.value("fixtureUrl")},
        {"instance",actual.instance},{"sequence",static_cast<qulonglong>(++actual.sequence)},{"processId",QCoreApplication::applicationPid()},
        {"clockDomain","native-main-ios-tablet-web-deferred"},{"clockBefore",before},{"clockAfter",clock()},{"complete",actual.complete},
        {"failure",actual.failure.isEmpty() ? QVariant() : QVariant(actual.failure)},{"commandSequence",static_cast<qulonglong>(actual.commandSequence)},{"records",rows},{"commands",commands}};
    if (QJsonDocument(QJsonObject::fromVariantMap(value)).toJson(QJsonDocument::Compact).size()>2097152) { fail("packet-capacity");return {}; }return value;
}
} // namespace overte::ios::tablet_web_deferred
Q_DECLARE_METATYPE(overte::ios::tablet_web_deferred::Provider)
#endif
