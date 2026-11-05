// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// E2E-only once dispatch via the ORIGINAL normal Qt IME provider. No setter.
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
#include <exception>
namespace {
struct PicoCurrentImeAttempt {
    QVariantMap command,packet;QByteArray originalCommand;
    overte::e2e::PicoCurrentAnchor clock;std::shared_ptr<PicoCurrentInputQuery> focus;
    QString instance;quint64 sequence{0};bool issued{false},terminal{false};
    QVariant issuedEpoch,issuedMonotonic;QVariantMap before,after;std::exception_ptr failure;
};
struct PicoCurrentImeScope {
    QString instance{QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')};quint64 sequence{0};
    QHash<QString,std::shared_ptr<PicoCurrentImeAttempt>> attempts;
    QHash<QString,QString> focusOwners;
};
QHash<QString,std::shared_ptr<PicoCurrentImeScope>> picoCurrentImeScopes;
QVariantMap picoCurrentImePacket(const std::shared_ptr<PicoCurrentImeAttempt>& a,const QString& status,
        const QString& reason={},bool accepted=false) {
    const auto& c=a->command;QVariantMap source;
    if(status!="pending") {
        QVariantMap dispatch{{"issued",a->issued},{"acceptedQt",accepted},{"issuedEpochMs",a->issuedEpoch},
            {"issuedMonotonicMs",a->issuedMonotonic}};
        source={{"reason",reason},{"dispatch",dispatch},{"nativeBefore",a->before},{"nativeAfter",a->after}};
        if(a->focus && a->focus->document) {
            const auto f=a->focus->packet,d=a->focus->document->packet;
            source.insert("focusReference",QVariantMap{{"commandId",f.value("commandId")},{"instance",f.value("instance")},{"sequence",f.value("sequence")}});
            source.insert("documentReference",QVariantMap{{"commandId",d.value("commandId")},{"instance",d.value("instance")},{"sequence",d.value("sequence")}});
            source.insert("originalFinish",a->focus->document->admission.value("finish"));
        }
    }
    return {{"picoWorldCurrentImeVersion",1},{"commandId",c.value("commandId")},{"runId",c.value("runId")},
        {"ownerToken",c.value("ownerToken")},{"documentNonce",c.value("documentNonce")},{"focusNonce",c.value("focusNonce")},
        {"instance",a->instance},{"sequence",qulonglong(a->sequence)},{"processId",QCoreApplication::applicationPid()},
        {"requestedEpochMs",a->clock->epoch},{"requestedMonotonicMs",a->clock->monotonic},
        {"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()},{"capturedMonotonicMs",a->clock->nowMonotonic()},
        {"status",status},{"source",source}};
}
}
QVariantMap NativeWebViewItem::featurePicoWorldCurrentIme(const QVariantMap& command,overte::e2e::PicoCurrentAnchor anchor) {
    if(!featureEnabled() || !overte::e2e::picoWorldCurrentImeCommand(command) || !QCoreApplication::instance()
        || QThread::currentThread()!=QCoreApplication::instance()->thread())return {};
    const auto original=overte::e2e::picoCurrentImeAnchor(command);if(!anchor)anchor=original;
    if(!anchor || anchor!=original || !anchor->fresh())return {};
    const auto run=command.value("runId").toString(),id=command.value("commandId").toString();
    const auto raw=QJsonDocument::fromVariant(command).toJson(QJsonDocument::Compact);
    auto scope=picoCurrentImeScopes.value(run);
    if(scope && scope->attempts.contains(id)) {
        const auto attempt=scope->attempts.value(id);
        return attempt->originalCommand==raw ? attempt->packet : QVariantMap();
    }
    if(picoCurrentLookup(run,id) || picoCurrentInputLookup(run,id))return {};
    for(const auto& old:worldWebScopes)if(old.originalCommands.contains(id))return {};
    if(!scope) {
        if(picoCurrentImeScopes.size()>=32)return {};
        scope=std::make_shared<PicoCurrentImeScope>();picoCurrentImeScopes.insert(run,scope);
    }
    if(scope->attempts.size()>=128 || scope->sequence>=9007199254740991ULL)return {};
    // First typed outcome is strong/sticky even if focus resolution fails.
    // A later appearing query cannot adopt this same input nonce.
    auto a=std::make_shared<PicoCurrentImeAttempt>();a->command=command;a->originalCommand=raw;a->clock=anchor;
    a->instance=scope->instance;a->sequence=++scope->sequence;scope->attempts.insert(id,a);
    const auto finish=[a](const QString& reason,bool accepted=false) {
        const auto actualReason=reason.isEmpty() && !a->clock->fresh() ? QStringLiteral("expired") : reason;
        a->terminal=true;a->packet=picoCurrentImePacket(a,actualReason.isEmpty() ? "ready" : "unavailable",actualReason,accepted);
        return a->packet;
    };
    a->packet=picoCurrentImePacket(a,"pending");
    const auto focus=picoCurrentInputLookup(run,command.value("focusNonce").toString());
    if(!focus || !focus->document || focus->status!="ready" || focus->command.value("operation")!="observe-current-focus"
        || focus->command.value("documentNonce")!=command.value("documentNonce")
        || focus->command.value("control")!=command.value("control")
        || focus->command.value("ownerToken")!=command.value("ownerToken") || focus->command.value("fixtureUrl")!=command.value("fixtureUrl"))return finish("focus-unavailable");
    a->focus=focus;
    const auto retained=focus->packet.value("source").toMap();const auto expectedEditor=retained.value("nativeEditor").toMap();
    const auto valid=[a,focus,retained,expectedEditor] {
        if(!a->clock->fresh() || !focus->clock->fresh() || !focus->document->clock->fresh() || !picoCurrentInputDocument(focus)
            || QGuiApplication::applicationState()!=Qt::ApplicationActive)return false;
        const auto item=focus->item;
        if(!item || !item->window() || item->_surface!=WorldEntity || item->_presentation!=Texture
            || !item->isVisible() || !item->isEnabled() || !item->hasActiveFocus()
            || item->window()->activeFocusItem()!=item || item->_editorText.size()>512)return false;
        const bool enabled=item->inputMethodQuery(Qt::ImEnabled).toBool();if(!item)return false;
        const QVariantMap editor{{"text",item->_editorText},{"cursor",item->_cursor},{"anchor",item->_anchor},
            {"absoluteCursor",item->_surroundingStart+item->_cursor},{"kind",item->_editorKind},{"sensitive",item->_sensitive},
            {"focused",item->hasActiveFocus() && item->_editorActive},{"enabled",enabled}};
        if(editor!=expectedEditor || !enabled || item->_sensitive || !item->_editorActive || item->_surroundingStart
            || item->_editorKind!=(a->command.value("control").toString()=="foreign" ? "url" : "text"))return false;
        const auto snapshot=item->featurePicoCurrentSnapshot(focus->document->documents);
        if(!item || snapshot.isEmpty() || snapshot.value("finish")!=retained.value("originalFinish")
            || picoCurrentSemantic(snapshot.value("native").toMap())!=picoCurrentSemantic(retained.value("authorityAfter").toMap().value("native").toMap()))return false;
        const auto now=QDateTime::currentMSecsSinceEpoch();QList<qint64> epochs;
        for(const auto packet:{focus->document->packet,focus->packet}) {
            epochs.append(packet.value("requestedEpochMs").toLongLong());epochs.append(packet.value("capturedEpochMs").toLongLong());
            const auto source=packet.value("source").toMap();
            for(const auto side:{"authorityBefore","authorityAfter"})for(const auto kind:{"native","java"})
                epochs.append(source.value(side).toMap().value(kind).toMap().value("capturedEpochMs").toLongLong());
        }
        epochs.append(focus->document->packet.value("source").toMap().value("dom").toMap().value("capturedEpochMs").toLongLong());
        for(const auto epoch:epochs)if(epoch<=0 || now-epoch< -250 || now-epoch>1500)return false;
        return true;
    };
    if(!valid())return finish("source-changed");
    const auto item=focus->item;
    const auto wrapper=QJsonDocument::fromJson(retained.value("focusRaw").toString().toUtf8());
    const auto quoted=QJsonDocument::fromJson('['+wrapper.object().value("geometryRaw").toString().toUtf8()+']');
    QJsonDocument parsed;
    if(quoted.isArray() && quoted.array().size()==1 && quoted.array()[0].isString())parsed=QJsonDocument::fromJson(quoted.array()[0].toString().toUtf8());
    if(!item || !wrapper.isObject() || !parsed.isObject())return finish("focus-unavailable");
    const auto point=overte::e2e::picoBrowserPoint(parsed.object().toVariantMap(),focus->command.value("commandId").toString(),run,
        focus->document->admission.value("native").toMap().value("url").toString(),command.value("control").toString(),
        QDateTime::currentMSecsSinceEpoch(),QSizeF(item->width(),item->height()));
    const auto geometry=parsed.object().toVariantMap();
    const auto imageCurrent=[focus,geometry] {
        const auto current=focus->item;if(!current)return false;
        const auto viewport=geometry.value("viewport").toMap();
        QMutexLocker lock(&current->_mutex);
        return !current->_image.isNull() && viewport.value("width").toDouble()>0 && viewport.value("height").toDouble()>0
            && std::abs(double(current->_image.width())/current->_image.height()
                -viewport.value("width").toDouble()/viewport.value("height").toDouble())<=0.02;
    };
    const auto property=qApp->property(overte::e2e::picoWorldWebTextProperty());
    if(!point || property.userType()!=qMetaTypeId<overte::e2e::PicoWorldWebTextProvider>())return finish("provider-unavailable");
    const auto provider=property.value<overte::e2e::PicoWorldWebTextProvider>();
    if(!provider || !valid() || !imageCurrent())return finish("source-changed");
    a->before=item->featurePicoCurrentSnapshot(focus->document->documents);
    if(a->before.isEmpty() || !valid() || !imageCurrent())return finish("source-changed");
    const auto focusId=command.value("focusNonce").toString();
    if(scope->focusOwners.contains(focusId))return finish("focus-already-issued");
    scope->focusOwners.insert(focusId,id);
    a->issued=true;a->issuedEpoch=QDateTime::currentMSecsSinceEpoch();a->issuedMonotonic=anchor->nowMonotonic();
    bool accepted=false;
    try {
        accepted=provider(item.data(),*point,command.value("text").toString(),parsed.object().value("capturedEpochMs").toVariant().toLongLong());
    } catch(...) {a->failure=std::current_exception();return finish("dispatch-unknown");}
    // Editor text may change due to the ORIGINAL normal event. Do not demand
    // that post-input editor equals the pre-input focus or invent its effect.
    if(!item || !anchor->fresh() || !focus->clock->fresh() || QGuiApplication::applicationState()!=Qt::ApplicationActive
        || !picoCurrentInputDocument(focus))return finish("source-changed-after-dispatch",accepted);
    a->after=item->featurePicoCurrentSnapshot(focus->document->documents);
    if(a->after.isEmpty() || a->after.value("finish")!=a->before.value("finish")
        || picoCurrentSemantic(a->after.value("native").toMap())!=picoCurrentSemantic(a->before.value("native").toMap()))return finish("source-changed-after-dispatch",accepted);
    return finish(QString(),accepted);
}
#else
#if defined(OVERTE_E2E_FEATURE_TESTS)
QVariantMap NativeWebViewItem::featurePicoWorldCurrentIme(const QVariantMap&,overte::e2e::PicoCurrentAnchor){return {};}
#endif
#endif
