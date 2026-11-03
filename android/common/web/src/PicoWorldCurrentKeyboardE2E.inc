// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Passive composition over an existing current-focus original and actual UI.
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
namespace {
struct PicoCurrentKeyboardQuery {QVariantMap command,packet,observedKeyboard;overte::e2e::PicoCurrentAnchor clock;};
struct PicoCurrentKeyboardScope {
    QString instance{QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')};quint64 sequence{0};
    QHash<QString,std::shared_ptr<PicoCurrentKeyboardQuery>> queries;
};
QHash<QString,std::shared_ptr<PicoCurrentKeyboardScope>> picoCurrentKeyboards;
quint64 picoCurrentKeyboardReservations{0};
}
namespace overte::e2e {
QVariantMap picoObserveCurrentKeyboard(const QVariantMap& command,PicoCurrentAnchor anchor,QObject* keyboardObject,const std::function<QVariantMap()>& capture){
    if(!consumeGui() || !picoWorldCurrentKeyboardCommand(command) || !capture || !keyboardObject
        || keyboardObject->thread()!=QThread::currentThread())return {};
    const QPointer<QObject> originalKeyboard(keyboardObject);
    const auto original=picoCurrentKeyboardAnchor(command);if(!anchor || anchor!=original)return {};
    const auto run=command.value("runId").toString(),id=command.value("commandId").toString();
    auto scope=picoCurrentKeyboards.value(run);
    if(scope && scope->queries.contains(id)){
        const auto query=scope->queries.value(id);
        if(query->command!=command)return {};
        // A completed original is historical. Never rerun capture or renew its
        // requested/captured clocks when the caller repeats its nonce.
        return query->packet;
    }
    if(!scope){if(picoCurrentKeyboards.size()>=32)return {};scope=std::make_shared<PicoCurrentKeyboardScope>();picoCurrentKeyboards.insert(run,scope);}
    if(scope->queries.size()>=128 || scope->sequence>=9007199254740991ULL || picoCurrentKeyboardReservations>=256)return {};
    // Reserve a full maximal literal BEFORE the actual callback. No mid-literal
    // capacity failure can discard a newly measured Keyboard original.
    ++picoCurrentKeyboardReservations;
    auto query=std::make_shared<PicoCurrentKeyboardQuery>();query->command=command;query->clock=anchor;scope->queries.insert(id,query);
    auto packet=[&](const QVariantMap& source){
        query->packet={{"picoWorldCurrentKeyboardVersion",1},{"commandId",id},{"runId",run},{"ownerToken",command.value("ownerToken")},
            {"focusNonce",command.value("focusNonce")},{"instance",scope->instance},{"sequence",qulonglong(++scope->sequence)},
            {"processId",QCoreApplication::applicationPid()},{"requestedEpochMs",anchor->epoch},{"requestedMonotonicMs",anchor->monotonic},
            {"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()},{"capturedMonotonicMs",anchor->nowMonotonic()},
            {"status",source.isEmpty() ? "unavailable" : "ready"},{"source",source}};
        return query->packet;
    };
    if(!anchor->fresh())return packet({});
    const auto focus=picoCurrentInputLookup(run,command.value("focusNonce").toString());
    if(!focus || focus->status!="ready" || !focus->clock->fresh() || !picoCurrentInputDocument(focus)
        || focus->command.value("operation")!="observe-current-focus" || focus->command.value("control")!="text"
        || focus->command.value("ownerToken")!=command.value("ownerToken") || focus->command.value("fixtureUrl")!=command.value("fixtureUrl"))return packet({});
    const auto item=focus->item;if(!item)return packet({});
    const auto before=PicoCurrentConsumptionAccess::snapshot(item,focus->document->documents);
    const auto editor=PicoCurrentConsumptionAccess::editor(item);
    if(before.isEmpty() || editor.value("focused")!=QVariant(true) || editor.value("enabled")!=QVariant(true)
        || before.value("finish")!=focus->document->admission.value("finish")
        || picoCurrentSemantic(before.value("native").toMap())!=picoCurrentSemantic(focus->before.value("native").toMap())
        || !anchor->fresh() || !focus->clock->fresh())return packet({});
    const auto keyboard=capture();query->observedKeyboard=keyboard; // Retain even a subsequently refused capture.
    if(!item || !originalKeyboard || originalKeyboard->thread()!=QThread::currentThread()
        || !anchor->fresh() || !focus->clock->fresh() || !picoCurrentInputDocument(focus))return packet({});
    const auto after=PicoCurrentConsumptionAccess::snapshot(item,focus->document->documents);
    const auto editorAfter=PicoCurrentConsumptionAccess::editor(item);
    if(keyboard.isEmpty() || after.isEmpty() || before.value("finish")!=after.value("finish")
        || picoCurrentSemantic(before.value("native").toMap())!=picoCurrentSemantic(after.value("native").toMap())
        || editor!=editorAfter || !anchor->fresh())return packet({});
    const QVariantMap source{{"focusReference",QVariantMap{{"commandId",focus->packet.value("commandId")},
        {"instance",focus->packet.value("instance")},{"sequence",focus->packet.value("sequence")}}},
        {"nativeBefore",before},{"nativeAfter",after},{"nativeEditor",editorAfter},{"keyboard",keyboard}};
    if(QJsonDocument::fromVariant(source).toJson(QJsonDocument::Compact).size()>62000)return packet({});
    const auto result=packet(source);
    if(!anchor->fresh() || !focus->clock->fresh())return packet({});
    return result;
}
}
#endif
