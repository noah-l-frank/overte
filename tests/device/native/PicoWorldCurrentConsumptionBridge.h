// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include "PicoWorldCurrentDocumentBridge.h"
#include <utility>
class QEvent;
namespace overte::e2e {
inline bool picoWorldCurrentConsumptionCommand(const QVariantMap& input){
    const auto object=QJsonObject::fromVariantMap(input);const auto operation=object.value("operation").toString();
    const bool arm=operation=="arm-current-consumption",observe=operation=="observe-current-consumption";
    if(!arm && !observe)return false;
    auto fields=QSet<QString>{"schemaVersion","commandId","action","runId","fixtureUrl","operation","ownerToken"};
    fields.insert(arm ? "focusNonce" : "attemptNonce");if(observe)fields.insert("afterSequence");
    const auto keys=object.keys();if(QSet<QString>(keys.begin(),keys.end())!=fields)return false;
    const auto reference=object.value(arm ? "focusNonce" : "attemptNonce");
    if(!reference.isString() || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(reference.toString()).hasMatch()
        || reference==object.value("commandId"))return false;
    if(observe){const auto after=object.value("afterSequence");
        if(!after.isDouble() || after.toDouble()<0 || after.toDouble()>16 || after.toDouble()!=after.toInt())return false;}
    auto base=input;base.remove("focusNonce");base.remove("attemptNonce");base.remove("afterSequence");
    base.insert("operation","observe-current-document");return picoWorldCurrentDocumentCommand(base);
}
Q_DECL_EXPORT PicoCurrentAnchor picoCurrentConsumptionAnchor(const QVariantMap& command);
struct PicoCurrentConsumptionProvider {
    std::function<QVariantMap(const QVariantMap&,PicoCurrentAnchor)> observe;
    explicit operator bool()const{return bool(observe);}
    QVariantMap operator()(const QVariantMap& command,PicoCurrentAnchor anchor)const{return observe ? observe(command,std::move(anchor)) : QVariantMap();}
};
inline const char* picoCurrentConsumptionProperty(){return "_overteE2EPicoWorldCurrentConsumptionProviderV1";}

// Each scope ends on the same synchronous native stack as its actual QEvent.
// Only the one picoOpenXR implementation owns state; no inline registry exists.
Q_DECL_EXPORT void picoCurrentTraceEnd(quint64 token,const QString& focusedAfter);
Q_DECL_EXPORT void picoCurrentTraceAbandon(quint64 token)noexcept;
struct PicoCurrentTraceScope {
    quint64 token{0};std::function<QString()> after;
    PicoCurrentTraceScope()=default;
    explicit PicoCurrentTraceScope(quint64 value,std::function<QString()> capture={}):token(value),after(std::move(capture)){}
    PicoCurrentTraceScope(const PicoCurrentTraceScope&)=delete;
    PicoCurrentTraceScope& operator=(const PicoCurrentTraceScope&)=delete;
    PicoCurrentTraceScope(PicoCurrentTraceScope&& other)noexcept:token(std::exchange(other.token,0)),after(std::move(other.after)){}
    ~PicoCurrentTraceScope(){if(token){try{picoCurrentTraceEnd(token,after ? after() : QString());}
        catch(...){picoCurrentTraceAbandon(token);}}}
};
Q_DECL_EXPORT PicoCurrentTraceScope picoCurrentTraceTrigger(QObject* keyboard,const QString& keyEntity,int keyType);
Q_DECL_EXPORT PicoCurrentTraceScope picoCurrentTraceKeyboard(QObject* keyboard,QEvent* event,const QString& requestedEntity);
Q_DECL_EXPORT PicoCurrentTraceScope picoCurrentTraceApplication(QEvent* event,const QString& focused,QObject* handler,std::function<QString()> after);
Q_DECL_EXPORT PicoCurrentTraceScope picoCurrentTraceNative(QObject* item,QEvent* event);
// JNI types stay in their actual original NativeWebViewItem translation unit.
Q_DECL_EXPORT PicoCurrentTraceScope picoCurrentTraceJni(void* environment,const void* originalArguments);
}
Q_DECLARE_METATYPE(overte::e2e::PicoCurrentConsumptionProvider)
#endif
