// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// One owned recorder. Product commands/predicates/delivery are not changed.
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
struct PicoCurrentConsumptionAccess {
    static QVariantMap snapshot(NativeWebViewItem* item,const QVariantList& documents){return item->featurePicoCurrentSnapshot(documents);}
    static QVariantMap editor(NativeWebViewItem* item){
        if(item->_sensitive)return {{"sensitive",true}};
        return {{"text",item->_editorText},{"cursor",item->_cursor},{"anchor",item->_anchor},
            {"absoluteCursor",item->_surroundingStart+item->_cursor},{"kind",item->_editorKind},{"sensitive",false},
            {"focused",item->hasActiveFocus() && item->_editorActive},{"enabled",item->inputMethodQuery(Qt::ImEnabled)}};
    }
};
namespace {
using ConsumeAnchor=overte::e2e::PicoCurrentAnchor;
struct ConsumeAttempt;
struct ConsumeQuery {QVariantMap command,packet;ConsumeAnchor clock;std::shared_ptr<ConsumeAttempt> attempt;bool failed{false};};
struct ConsumeScope {
    QString instance{QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')};quint64 sequence{0};
    QHash<QString,std::shared_ptr<ConsumeAttempt>> attempts;QHash<QString,std::shared_ptr<ConsumeQuery>> queries;
};
struct ConsumeAttempt {
    QString run,root,owner,nonce,control,reason;ConsumeAnchor clock;std::shared_ptr<PicoCurrentInputQuery> focus;
    QPointer<NativeWebViewItem> item;QPointer<QQmlContext> context;QPointer<QQuickWindow> window;
    QSharedPointer<QObject> receiver;QPointer<QObject> receiverWeak;QVariantList frames;QVector<QByteArray> callbackOriginals;
    std::weak_ptr<ConsumeScope> scope;bool terminal{false},abandoned{false};
};
enum ConsumeStackKind{ConsumeTrigger,ConsumeKeyboard,ConsumeApplication,ConsumeNative,ConsumeJni};
struct ConsumeStack {
    ConsumeStackKind kind;std::shared_ptr<ConsumeAttempt> attempt;QPointer<QObject> keyboard;QEvent* event{nullptr};
    QString id,origin,requested,keyEntity;int keyType{-1};QVariantMap raw;
};
QMutex consumeMutex;QHash<QString,std::shared_ptr<ConsumeScope>> consumeScopes;
QHash<QString,std::weak_ptr<ConsumeAttempt>> consumeEventOwners;
QHash<QObject*,QPair<QPointer<QObject>,QString>> consumeKeyboards;
QHash<quint64,ConsumeStack> consumeStack;quint64 consumeNextToken{0};std::atomic<quint64> consumeRawBytes{0};
bool consumeGui(){return featureEnabled() && QCoreApplication::instance() && QThread::currentThread()==QCoreApplication::instance()->thread();}
QString consumeId(){return QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');}
QVariant consumeNull(){return QVariant();}
bool consumeReserve(qsizetype bytes){
    if(bytes<0 || bytes>16384)return false;quint64 old=consumeRawBytes.load();
    while(old+quint64(bytes)<=16*1024*1024){if(consumeRawBytes.compare_exchange_weak(old,old+quint64(bytes)))return true;}return false;
}
void consumeFail(const std::shared_ptr<ConsumeAttempt>& a,const QString& reason){
    if(a && a->reason.isEmpty())a->reason=reason;if(a && reason!="encoding-unavailable")a->terminal=true;
}
QVariantMap consumeLife(const std::shared_ptr<ConsumeAttempt>& a){
    return {{"itemAlive",bool(a->item)},{"contextAlive",bool(a->context)},{"windowAlive",bool(a->window)},
        {"receiverAlive",bool(a->receiverWeak)},{"activeAttempt",!a->terminal && a->reason.isEmpty()}};
}
QVariantMap consumeSnapshot(const std::shared_ptr<ConsumeAttempt>& a){
    if(!consumeGui() || !a || !a->item || !a->context || !a->context->isValid() || !a->window)return {};
    if(a->item->thread()!=QThread::currentThread() || a->context->thread()!=QThread::currentThread()
        || a->window->thread()!=QThread::currentThread() || a->item->window()!=a->window
        || QQmlEngine::contextForObject(a->item)!=a->context)return {};
    return PicoCurrentConsumptionAccess::snapshot(a->item,a->focus->document->documents);
}
bool consumeCurrent(const std::shared_ptr<ConsumeAttempt>& a,bool encodingOriginal=false){
    if(!consumeGui() || !a)return false;
    if(a->abandoned){consumeFail(a,"incomplete-dispatch");return false;}
    if(!a->reason.isEmpty() && !(encodingOriginal && a->reason=="encoding-unavailable"))return false;
    if(QGuiApplication::applicationState()!=Qt::ApplicationActive){consumeFail(a,"authority-changed");return false;}
    const auto age=a->clock->nowMonotonic()-a->clock->monotonic;
    if(age<0 || age>5000){consumeFail(a,"expired");return false;}
    const auto original=a->focus->packet.value("source").toMap(),snapshot=consumeSnapshot(a);
    if(snapshot.isEmpty()){consumeFail(a,"weak-unavailable");return false;}
    const auto scope=worldWebScopes.constFind(a->run);
    if(scope==worldWebScopes.cend() || scope->retired || !scope->complete || scope->tablet || scope->reference
        || scope->token!=a->owner || scope->root!=a->root || scope->documents!=a->focus->document->documents){consumeFail(a,"source-changed");return false;}
    if(snapshot.value("finish")!=original.value("originalFinish") || picoCurrentSemantic(snapshot.value("native").toMap())
        !=picoCurrentSemantic(original.value("authorityAfter").toMap().value("native").toMap())){consumeFail(a,"authority-changed");return false;}
    const auto editor=PicoCurrentConsumptionAccess::editor(a->item);
    if(editor.value("sensitive")==true || editor.value("focused")!=true || editor.value("enabled")!=true
        || editor.value("kind")!=(a->control=="foreign" ? "url" : "text")){consumeFail(a,"authority-changed");return false;}
    return true;
}
void consumeFrame(const std::shared_ptr<ConsumeAttempt>& a,const QString& id,const QString& kind,const QString& origin,const QVariantMap& raw){
    if(!consumeGui() || !a)return;const auto bytes=QJsonDocument::fromVariant(raw).toJson(QJsonDocument::Compact);
    if(a->frames.size()>=16){consumeFail(a,"event-overrun");return;}
    if(bytes.size()>8192 || !consumeReserve(bytes.size())){consumeFail(a,"raw-overrun");return;}
    a->frames.append(QVariantMap{{"sequence",a->frames.size()+1},{"eventId",id},{"kind",kind},{"origin",origin},
        {"epochMs",QDateTime::currentMSecsSinceEpoch()},{"monotonicMs",a->clock->nowMonotonic()},{"raw",QString::fromUtf8(bytes)}});
}
QString consumeU16(const QString& value){
    QByteArray raw;raw.reserve(value.size()*2);for(const auto c:value){raw.append(char(c.unicode()>>8));raw.append(char(c.unicode()&255));}return QString::fromLatin1(raw.toHex());
}
bool consumeWellFormed(const QString& value){
    for(int i=0;i<value.size();++i){const auto c=value.at(i);
        if(c.isHighSurrogate()){if(i+1>=value.size() || !value.at(++i).isLowSurrogate())return false;}
        else if(c.isLowSurrogate())return false;}return true;
}
std::shared_ptr<ConsumeAttempt> consumeForEntity(const QString& entity){
    if(!consumeGui())return {};
    for(const auto& scope:consumeScopes)for(const auto& a:scope->attempts){
        if(a->terminal || a->reason.size())continue;
        const auto native=a->focus->packet.value("source").toMap().value("authorityAfter").toMap().value("native").toMap();
        if(native.value("sourceIdentity")=="web-entity:"+entity && consumeCurrent(a))return a;
    }return {};
}
quint64 consumeToken(ConsumeStack value){
    if(consumeNextToken>=9007199254740991ULL || consumeStack.size()>=64){consumeFail(value.attempt,"event-overrun");return 0;}
    const auto token=++consumeNextToken;consumeStack.insert(token,std::move(value));return token;
}
ConsumeStack* consumeEvent(QEvent* event){
    quint64 latest=0;ConsumeStack* found=nullptr;for(auto it=consumeStack.begin();it!=consumeStack.end();++it)
        if(it->event==event && it.key()>latest && it->kind!=ConsumeTrigger){latest=it.key();found=&it.value();}return found;
}
QVariantMap consumePacket(const std::shared_ptr<ConsumeQuery>& q,const QString& status,const QVariantMap& source={}){
    std::shared_ptr<ConsumeScope> scope;
    {QMutexLocker hold(&consumeMutex);scope=consumeScopes.value(q->command.value("runId").toString());}
    if(!scope || scope->sequence>=9007199254740991ULL)return {};
    return {{"picoWorldCurrentConsumptionVersion",1},{"commandId",q->command.value("commandId")},{"runId",q->command.value("runId")},
        {"ownerToken",q->command.value("ownerToken")},{"instance",scope->instance},{"sequence",qulonglong(++scope->sequence)},
        {"processId",QCoreApplication::applicationPid()},{"requestedEpochMs",q->clock->epoch},{"requestedMonotonicMs",q->clock->monotonic},
        {"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()},{"capturedMonotonicMs",q->clock->nowMonotonic()},{"status",status},{"source",source}};
}
QVariantMap consumeRead(const std::shared_ptr<ConsumeQuery>& q){
    const auto a=q->attempt;const auto before=consumeSnapshot(a);consumeCurrent(a);
    const int cursor=q->command.value("afterSequence").toInt();
    if(q->command.value("operation")=="observe-current-consumption" && cursor>a->frames.size())consumeFail(a,"incomplete-dispatch");
    const auto focus=a->focus->packet;QVariant frame;
    if(q->command.value("operation")=="observe-current-consumption" && cursor<a->frames.size())frame=a->frames[cursor];
    const auto after=consumeSnapshot(a);
    if(!before.isEmpty() && !after.isEmpty() && picoCurrentSemantic(before.value("native").toMap())!=picoCurrentSemantic(after.value("native").toMap()))consumeFail(a,"authority-changed");
    if(a->reason.isEmpty() && q->command.value("operation")=="observe-current-consumption" && frame.isNull() && !a->terminal)return consumePacket(q,"pending");
    QVariantMap source{{"attemptReference",QVariantMap{{"nonce",a->nonce},{"itemInstance",focus.value("source").toMap().value("authorityAfter").toMap().value("native").toMap().value("itemInstance")},
            {"sourceInstance",focus.value("instance")}}},
        {"focusReference",QVariantMap{{"commandId",focus.value("commandId")},{"instance",focus.value("instance")},{"sequence",focus.value("sequence")}}},
        {"nativeBefore",before.isEmpty() ? consumeNull() : QVariant(before)},{"nativeAfter",after.isEmpty() ? consumeNull() : QVariant(after)},
        {"lifetime",consumeLife(a)},{"frame",frame},{"availableFrames",a->frames.size()},{"terminal",a->terminal}};
    if(!a->reason.isEmpty())source.insert("reason",a->reason);
    auto packet=consumePacket(q,a->reason.isEmpty() ? "ready" : "unavailable",source);
    if(!q->clock->fresh() || QJsonDocument::fromVariant(packet).toJson(QJsonDocument::Compact).size()>65536)return {};
    q->failed=!a->reason.isEmpty();q->packet=packet;return packet;
}
}

QVariantMap NativeWebViewItem::featurePicoWorldCurrentConsumption(const QVariantMap& command,ConsumeAnchor anchor){
    if(!consumeGui() || !overte::e2e::picoWorldCurrentConsumptionCommand(command))return {};
    const auto original=overte::e2e::picoCurrentConsumptionAnchor(command);if(!anchor)anchor=original;
    if(!anchor || anchor!=original || !anchor->fresh())return {};
    const auto run=command.value("runId").toString(),id=command.value("commandId").toString();
    std::shared_ptr<ConsumeScope> scope;
    {QMutexLocker hold(&consumeMutex);
        if(!consumeScopes.contains(run) && consumeScopes.size()>=32)return {};
        scope=consumeScopes.value(run);if(!scope){scope=std::make_shared<ConsumeScope>();consumeScopes.insert(run,scope);}}
    auto query=scope->queries.value(id);
    if(query){if(query->command!=command)return {};if(query->failed)return query->packet;
        if(query->attempt && !consumeCurrent(query->attempt))return consumeRead(query);
        return query->packet.isEmpty() ? consumeRead(query) : query->packet;}
    if(scope->queries.size()>=4096)return {};
    if(picoCurrentLookup(run,id) || picoCurrentInputLookup(run,id))return {};
    for(const auto& world:worldWebScopes)if(world.originalCommands.contains(id))return {};
    std::shared_ptr<ConsumeAttempt> attempt;
    if(command.value("operation")=="arm-current-consumption"){
        const auto focus=picoCurrentInputLookup(run,command.value("focusNonce").toString());
        if(!focus || focus->status!="ready" || focus->command.value("operation")!="observe-current-focus" || !focus->clock->fresh()
            || focus->command.value("ownerToken")!=command.value("ownerToken") || focus->command.value("fixtureUrl")!=command.value("fixtureUrl")
            || scope->attempts.size()>=128)return {};
        for(const auto& old:scope->attempts)if(old->item==focus->item && !old->terminal){consumeCurrent(old,true);if(!old->terminal)return {};}
        attempt=std::make_shared<ConsumeAttempt>();attempt->run=run;attempt->root=command.value("fixtureUrl").toString();attempt->owner=command.value("ownerToken").toString();
        attempt->nonce=id;attempt->control=focus->command.value("control").toString();attempt->clock=anchor;attempt->focus=focus;
        attempt->item=focus->item;attempt->context=focus->context;attempt->window=focus->window;attempt->scope=scope;
        if(!consumeCurrent(attempt))return {};
        attempt->receiver=QSharedPointer<QObject>(new QObject(),[](QObject* receiver){receiver->deleteLater();});attempt->receiverWeak=attempt->receiver.data();
        scope->attempts.insert(id,attempt);
    }else{
        attempt=scope->attempts.value(command.value("attemptNonce").toString());
        if(!attempt || attempt->owner!=command.value("ownerToken") || attempt->root!=command.value("fixtureUrl"))return {};
    }
    query=std::make_shared<ConsumeQuery>();query->command=command;query->clock=anchor;query->attempt=attempt;scope->queries.insert(id,query);
    return consumeRead(query);
}

namespace overte::e2e {
PicoCurrentTraceScope picoCurrentTraceTrigger(QObject* keyboard,const QString& keyEntity,int keyType){
    if(!consumeGui() || !keyboard || keyboard->thread()!=QThread::currentThread())return {};
    try{ConsumeStack e;e.kind=ConsumeTrigger;e.keyboard=keyboard;e.keyEntity=keyEntity;e.keyType=keyType;return PicoCurrentTraceScope(consumeToken(std::move(e)));}catch(...){return {};}
}
PicoCurrentTraceScope picoCurrentTraceKeyboard(QObject* keyboard,QEvent* event,const QString& requested){
    if(!consumeGui() || !keyboard || keyboard->thread()!=QThread::currentThread() || !event
        || (event->type()!=QEvent::KeyPress && event->type()!=QEvent::KeyRelease))return {};
    try{
        const auto a=consumeForEntity(requested);if(!a)return {};const auto key=static_cast<QKeyEvent*>(event);
        ConsumeStack e;e.kind=ConsumeKeyboard;e.attempt=a;e.keyboard=keyboard;e.event=event;e.id=consumeId();e.origin="keyboard-dispatch";e.requested=requested;
        quint64 latest=0;for(auto it=consumeStack.begin();it!=consumeStack.end();++it)if(it->kind==ConsumeTrigger && it->keyboard==keyboard && it.key()>latest){
            latest=it.key();e.keyEntity=it->keyEntity;e.keyType=it->keyType;e.origin="vr-key";}
        if(!consumeKeyboards.contains(keyboard) || consumeKeyboards.value(keyboard).first!=keyboard){
            if(!consumeKeyboards.contains(keyboard) && consumeKeyboards.size()>=32){consumeFail(a,"event-overrun");return {};}
            consumeKeyboards.insert(keyboard,{QPointer<QObject>(keyboard),consumeId()});}
        QVariantMap raw{{"keyboardObject",consumeKeyboards.value(keyboard).second},{"keyEntity",e.keyEntity.isEmpty() ? consumeNull() : QVariant(e.keyEntity)},
            {"keyType",e.keyType<0 ? consumeNull() : QVariant(e.keyType)},{"eventType",event->type()==QEvent::KeyPress ? "press" : "release"},
            {"key",key->key()},{"modifiers",int(key->modifiers())},{"textUtf16Hex",consumeU16(key->text())},{"requestedEntity",requested}};
        if(!consumeWellFormed(key->text()))consumeFail(a,"encoding-unavailable");
        consumeFrame(a,e.id,"keyboard-event",e.origin,raw);return PicoCurrentTraceScope(consumeToken(std::move(e)));
    }catch(...){return {};}
}
PicoCurrentTraceScope picoCurrentTraceApplication(QEvent* event,const QString& focused,QObject* handler,std::function<QString()> after){
    if(!consumeGui() || !event)return {};
    try{
        const auto previous=consumeEvent(event);const auto a=previous ? previous->attempt : consumeForEntity(focused);if(!a || !consumeCurrent(a,true))return {};
        ConsumeStack e;e.kind=ConsumeApplication;e.attempt=a;e.event=event;e.id=previous ? previous->id : consumeId();e.origin=previous ? previous->origin : "qt-key";
        e.raw={{"eventType",event->type()==QEvent::KeyPress ? "press" : "release"},{"requestedEntity",previous ? QVariant(previous->requested) : consumeNull()},
            {"focusedBefore",focused},{"handlerMatchesWindow",handler && handler==a->window},{"focusItemMatches",a->window && a->window->activeFocusItem()==a->item}};
        return PicoCurrentTraceScope(consumeToken(std::move(e)),std::move(after));
    }catch(...){return {};}
}
PicoCurrentTraceScope picoCurrentTraceNative(QObject* object,QEvent* event){
    if(!consumeGui() || !object || object->thread()!=QThread::currentThread() || !event)return {};
    try{
        auto* item=qobject_cast<NativeWebViewItem*>(object);if(!item)return {};
        const auto previous=consumeEvent(event);std::shared_ptr<ConsumeAttempt> a;
        for(const auto& scope:consumeScopes)for(const auto& candidate:scope->attempts)if(candidate->item==item && !candidate->terminal && consumeCurrent(candidate,true))a=candidate;
        if(!a)return {};ConsumeStack e;e.kind=ConsumeNative;e.attempt=a;e.event=event;
        e.id=previous && previous->attempt==a ? previous->id : consumeId();e.origin=event->type()==QEvent::InputMethod ? "qt-ime" : (previous && previous->attempt==a ? previous->origin : "qt-key");
        e.raw={{"authority",consumeSnapshot(a).value("native")},{"editor",PicoCurrentConsumptionAccess::editor(item)},
            {"eventType",event->type()==QEvent::InputMethod ? "ime" : "key-press"},{"key",consumeNull()},{"modifiers",consumeNull()},
            {"textUtf16Hex",consumeNull()},{"commitUtf16Hex",consumeNull()},{"preeditUtf16Hex",consumeNull()},
            {"replacementStart",consumeNull()},{"replacementLength",consumeNull()},{"attributes",QVariantList()}};
        if(event->type()==QEvent::KeyPress){const auto key=static_cast<QKeyEvent*>(event);e.raw.insert("key",key->key());e.raw.insert("modifiers",int(key->modifiers()));e.raw.insert("textUtf16Hex",consumeU16(key->text()));
            if(!consumeWellFormed(key->text()))consumeFail(a,"encoding-unavailable");}
        else if(event->type()==QEvent::InputMethod){const auto ime=static_cast<QInputMethodEvent*>(event);QVariantList attributes;
            for(const auto& attribute:ime->attributes())attributes.append(QVariantMap{{"type",int(attribute.type)},{"start",attribute.start},{"length",attribute.length}});
            e.raw.insert("commitUtf16Hex",consumeU16(ime->commitString()));e.raw.insert("preeditUtf16Hex",consumeU16(ime->preeditString()));
            e.raw.insert("replacementStart",ime->replacementStart());e.raw.insert("replacementLength",ime->replacementLength());e.raw.insert("attributes",attributes);
            if(!consumeWellFormed(ime->commitString()) || !consumeWellFormed(ime->preeditString()))consumeFail(a,"encoding-unavailable");
        }else return {};
        return PicoCurrentTraceScope(consumeToken(std::move(e)));
    }catch(...){return {};}
}
PicoCurrentTraceScope picoCurrentTraceJni(void* environment,const void* arguments){
    if(!consumeGui() || !environment || !arguments)return {};
    try{
        quint64 latest=0;ConsumeStack* native=nullptr;
        for(auto it=consumeStack.begin();it!=consumeStack.end();++it)if(it->kind==ConsumeNative && it.key()>latest){latest=it.key();native=&it.value();}
        if(!native || !consumeCurrent(native->attempt,true))return {};auto* env=static_cast<JNIEnv*>(environment);const auto args=static_cast<const jvalue*>(arguments);
        if(env->ExceptionCheck() || !args[3].l || !args[4].l)return {};
        const auto url=string(env,static_cast<jstring>(args[3].l)),command=string(env,static_cast<jstring>(args[4].l));
        if(env->ExceptionCheck()){env->ExceptionClear();consumeFail(native->attempt,"encoding-unavailable");return {};}
        const auto snapshot=consumeSnapshot(native->attempt).value("native").toMap();
        if(QString::number(args[0].j)!=snapshot.value("handle").toString() || quint64(args[1].j)!=snapshot.value("grant").toULongLong()
            || quint64(args[2].j)!=snapshot.value("page").toULongLong() || url!=snapshot.value("url").toString())return {};
        ConsumeStack e=*native;e.kind=ConsumeJni;e.event=nullptr;e.raw={{"handle",QString::number(args[0].j)},{"creation",snapshot.value("creation")},
            {"grant",qulonglong(args[1].j)},{"page",qulonglong(args[2].j)},{"url",url},{"sourceIdentity",snapshot.value("sourceIdentity")},
            {"commandUtf16Hex",consumeU16(command)},{"commandUtf8Hex",QString::fromLatin1(command.toUtf8().toHex())}};
        if(!consumeWellFormed(command))consumeFail(e.attempt,"encoding-unavailable");
        consumeFrame(e.attempt,e.id,"jni-command",e.origin,e.raw);
        {QMutexLocker hold(&consumeMutex);consumeEventOwners.insert(e.id,e.attempt);}
        return PicoCurrentTraceScope(consumeToken(std::move(e)));
    }catch(...){return {};}
}
void picoCurrentTraceEnd(quint64 token,const QString& focusedAfter){
    if(!consumeGui())return;const auto found=consumeStack.find(token);if(found==consumeStack.end())return;const auto value=found.value();consumeStack.erase(found);
    if(value.kind==ConsumeApplication){auto raw=value.raw;raw.insert("handled",value.event && value.event->isAccepted());raw.insert("focusedAfter",focusedAfter.isEmpty() ? consumeNull() : QVariant(focusedAfter));
        consumeFrame(value.attempt,value.id,"application-target",value.origin,raw);}
    if(value.kind==ConsumeNative){auto raw=value.raw;raw.insert("accepted",value.event && value.event->isAccepted());consumeFrame(value.attempt,value.id,"native-input",value.origin,raw);}
}
void picoCurrentTraceAbandon(quint64 token)noexcept{
    if(!QCoreApplication::instance() || QThread::currentThread()!=QCoreApplication::instance()->thread())return;
    const auto found=consumeStack.find(token);if(found==consumeStack.end())return;
    if(found->attempt){found->attempt->terminal=true;found->attempt->abandoned=true;}consumeStack.erase(found);
}
}

extern "C" JNIEXPORT jstring JNICALL Java_org_overte_web_EmbeddedWebView_nativePicoConsumptionId(JNIEnv* env,jclass,jlong handle,jlong grant,jlong page,jstring url,jstring command){
    if(!consumeGui() || !url || !command || env->ExceptionCheck())return nullptr;
    try{
        const auto document=string(env,url),data=string(env,command);if(env->ExceptionCheck()){env->ExceptionClear();return nullptr;}
        quint64 latest=0;const ConsumeStack* found=nullptr;
        for(auto it=consumeStack.cbegin();it!=consumeStack.cend();++it)if(it->kind==ConsumeJni && it.key()>latest){latest=it.key();found=&it.value();}
        if(!found || !consumeCurrent(found->attempt,true))return nullptr;const auto raw=found->raw;
        if(raw.value("handle").toString()!=QString::number(handle) || raw.value("grant").toULongLong()!=quint64(grant)
            || raw.value("page").toULongLong()!=quint64(page) || raw.value("url").toString()!=document
            || raw.value("commandUtf16Hex").toString()!=consumeU16(data))return nullptr;
        Jni jni;return jni.string(found->id);
    }catch(...){return nullptr;}
}
extern "C" JNIEXPORT void JNICALL Java_org_overte_web_EmbeddedWebView_nativePicoConsumptionEvent(JNIEnv* env,jclass,jstring event,jstring stage,jstring result){
    if(!featureEnabled() || !event || !stage || !result || env->GetStringLength(event)!=32 || env->GetStringLength(stage)>16 || env->GetStringLength(result)>8192)return;
    try{
        const auto id=string(env,event),kind=string(env,stage);const auto raw=string(env,result).toUtf8();
        if((kind!="java-entry" && kind!="java-consume") || raw.size()>8192)return;
        std::shared_ptr<ConsumeAttempt> a;QSharedPointer<QObject> receiver;
        {QMutexLocker hold(&consumeMutex);a=consumeEventOwners.value(id).lock();if(!a || a->callbackOriginals.size()>=4 || !consumeReserve(raw.size()))return;
            a->callbackOriginals.append(raw);receiver=a->receiver;}
        if(!receiver)return;
        QMetaObject::invokeMethod(receiver.data(),[a,id,kind,raw]{
            if(!consumeGui())return;const auto document=QJsonDocument::fromJson(raw);const auto value=document.object();
            if(!document.isObject()){consumeFail(a,"encoding-unavailable");return;}
            const QSet<QString> common{"handle","grant","page","url","commandUtf16Hex","commandUtf8Hex"};auto fields=common;
            if(kind=="java-entry")fields.unite(QSet<QString>{"isMainThread","capturedEpochMs","capturedElapsedMs"});
            else fields.unite(QSet<QString>{"before","after"});
            const auto keys=value.keys();bool strict=QSet<QString>(keys.begin(),keys.end())==fields
                && value.value("handle").isString() && value.value("url").isString()
                && value.value("commandUtf16Hex").isString() && value.value("commandUtf8Hex").isString();
            for(const auto& key:{"grant","page"})strict=strict && value.value(key).isDouble()
                && picoCurrentInteger(value.value(key),1);
            if(kind=="java-entry")strict=strict && value.value("isMainThread").isBool()
                && picoCurrentInteger(value.value("capturedEpochMs"),1) && picoCurrentInteger(value.value("capturedElapsedMs"));
            else strict=strict && picoCurrentJava(value.value("before").toObject()) && picoCurrentJava(value.value("after").toObject());
            if(!strict)consumeFail(a,"encoding-unavailable");
            QVariantMap command;QString origin;
            for(const auto& frame:a->frames){const auto row=frame.toMap();if(row.value("eventId")==id && row.value("kind")=="jni-command"){
                command=QJsonDocument::fromJson(row.value("raw").toString().toUtf8()).object().toVariantMap();origin=row.value("origin").toString();}}
            bool matches=!command.isEmpty();
            for(const auto& key:{"handle","grant","page","url","commandUtf16Hex","commandUtf8Hex"})matches=matches && value.value(key).toVariant()==command.value(key);
            if(!matches)consumeFail(a,"encoding-unavailable");
            consumeCurrent(a,true);consumeFrame(a,id,kind,origin,value.toVariantMap());
            if(kind=="java-consume")a->terminal=true;
        },Qt::QueuedConnection);
    }catch(...){/* Product Java dispatch remains independent of recorder availability. */}
}
#else
#if defined(OVERTE_E2E_FEATURE_TESTS)
QVariantMap NativeWebViewItem::featurePicoWorldCurrentConsumption(const QVariantMap&,overte::e2e::PicoCurrentAnchor){return {};}
#endif
extern "C" JNIEXPORT jstring JNICALL Java_org_overte_web_EmbeddedWebView_nativePicoConsumptionId(JNIEnv*,jclass,jlong,jlong,jlong,jstring,jstring){return nullptr;}
extern "C" JNIEXPORT void JNICALL Java_org_overte_web_EmbeddedWebView_nativePicoConsumptionEvent(JNIEnv*,jclass,jstring,jstring,jstring){}
#endif
