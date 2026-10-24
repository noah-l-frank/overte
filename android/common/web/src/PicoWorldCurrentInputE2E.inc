// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Read-only current-authority geometry/focus. No old handler is reused as input.
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
namespace {
struct PicoCurrentInputQuery;
struct PicoCurrentInputScope {
    QString instance{QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')};quint64 sequence{0};
    QHash<QString,std::shared_ptr<PicoCurrentInputQuery>> queries;
};
struct PicoCurrentInputQuery {
    QVariantMap command,before,packet;QByteArray raw;QVector<QByteArray> originals;
    std::shared_ptr<PicoCurrentQuery> document;overte::e2e::PicoCurrentAnchor clock;
    QPointer<NativeWebViewItem> item;QPointer<QQmlContext> context;QPointer<QQuickWindow> window;
    QPointer<QObject> receiverWeak;QSharedPointer<QObject> receiver;
    QString status{"pending"};std::weak_ptr<PicoCurrentInputScope> scope;bool issued{false};
};
QMutex picoCurrentInputMutex;
QHash<QString,std::shared_ptr<PicoCurrentInputScope>> picoCurrentInputs;
std::shared_ptr<PicoCurrentInputQuery> picoCurrentInputLookup(const QString& run,const QString& id){
    QMutexLocker guard(&picoCurrentInputMutex);const auto scope=picoCurrentInputs.value(run);return scope ? scope->queries.value(id) : nullptr;
}
QVariantMap picoCurrentInputPacket(const std::shared_ptr<PicoCurrentInputQuery>& query,const QString& status,const QVariantMap& source={}){
    const auto scope=query->scope.lock();if(!scope || scope->sequence>=9007199254740991ULL)return {};
    return {{"picoWorldCurrentInputVersion",1},{"commandId",query->command.value("commandId")},{"runId",query->command.value("runId")},
        {"ownerToken",query->command.value("ownerToken")},{"documentNonce",query->command.value("documentNonce")},
        {"instance",scope->instance},{"sequence",qulonglong(++scope->sequence)},{"processId",QCoreApplication::applicationPid()},
        {"requestedEpochMs",query->clock->epoch},{"requestedMonotonicMs",query->clock->monotonic},
        {"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()},{"capturedMonotonicMs",query->clock->nowMonotonic()},
        {"status",status},{"source",source}};
}
void picoCurrentInputUnavailable(const std::shared_ptr<PicoCurrentInputQuery>& query){
    query->status="unavailable";query->packet=picoCurrentInputPacket(query,"unavailable");
    QMutexLocker guard(&picoCurrentInputMutex);query->receiver.clear();
}
bool picoCurrentInputDocument(const std::shared_ptr<PicoCurrentInputQuery>& query){
    if(!QCoreApplication::instance() || QThread::currentThread()!=QCoreApplication::instance()->thread())return false;
    const auto doc=query->document;if(!doc || !doc->clock->fresh() || doc->status!="ready" || !doc->owner || doc->owner!=query->item)return false;
    const auto& command=query->command;const auto found=worldWebScopes.constFind(command.value("runId").toString());
    return doc->command.value("commandId")==command.value("documentNonce") && doc->command.value("runId")==command.value("runId")
        && doc->command.value("ownerToken")==command.value("ownerToken") && doc->command.value("fixtureUrl")==command.value("fixtureUrl")
        && found!=worldWebScopes.cend() && !found->retired && found->complete && !found->tablet && !found->reference && found->surface=="world"
        && found->token==command.value("ownerToken") && found->root==command.value("fixtureUrl") && found->documents==doc->documents
        && query->context && query->context->isValid() && query->window
        && query->context->thread()==QThread::currentThread() && query->window->thread()==QThread::currentThread()
        && QQmlEngine::contextForObject(query->item)==query->context && query->item->window()==query->window
        && query->context->contextProperty("nativeWebSourceIdentity").toString()==doc->admission.value("native").toMap().value("sourceIdentity");
}
}
QVariantMap NativeWebViewItem::featurePicoWorldCurrentInput(const QVariantMap& command,overte::e2e::PicoCurrentAnchor anchor){
    if(!featureEnabled() || !overte::e2e::picoWorldCurrentInputCommand(command) || !QCoreApplication::instance()
        || QThread::currentThread()!=QCoreApplication::instance()->thread())return {};
    const auto original=overte::e2e::picoCurrentInputAnchor(command);if(!anchor)anchor=original;if(!anchor || anchor!=original)return {};
    const auto run=command.value("runId").toString(),id=command.value("commandId").toString();
    auto query=picoCurrentInputLookup(run,id);
    if(query){
        if(query->command!=command)return {};
        if(query->status=="unavailable")return query->packet;
        const auto item=query->item;
        const auto snapshot=item ? item->featurePicoCurrentSnapshot(query->document->documents) : QVariantMap();
        if(!query->clock->fresh() || !picoCurrentInputDocument(query) || snapshot.isEmpty()
            || snapshot.value("finish")!=query->document->admission.value("finish")
            || picoCurrentSemantic(snapshot.value("native").toMap())!=picoCurrentSemantic(query->document->admission.value("native").toMap()))picoCurrentInputUnavailable(query);
        return query->status=="pending" ? picoCurrentInputPacket(query,"pending") : query->packet;
    }
    if(picoCurrentLookup(run,id))return {};
    for(const auto& scope:worldWebScopes)if(scope.originalCommands.contains(id))return {};
    const auto doc=picoCurrentLookup(run,command.value("documentNonce").toString());if(!doc)return {};
    query=std::make_shared<PicoCurrentInputQuery>();query->command=command;query->clock=anchor;query->document=doc;query->item=doc->owner;
    if(query->item){query->context=QQmlEngine::contextForObject(query->item);query->window=query->item->window();}
    if(!picoCurrentInputDocument(query))return {};
    {QMutexLocker guard(&picoCurrentInputMutex);
        if(!picoCurrentInputs.contains(run) && picoCurrentInputs.size()>=32)return {};
        auto scope=picoCurrentInputs.value(run);if(!scope){scope=std::make_shared<PicoCurrentInputScope>();picoCurrentInputs.insert(run,scope);}
        if(scope->queries.size()>=128)return {};query->scope=scope;scope->queries.insert(id,query);}
    if(!anchor->fresh()){picoCurrentInputUnavailable(query);return query->packet;}
    const auto receiver=QSharedPointer<QObject>(new QObject(),[](QObject* object){object->deleteLater();});query->receiverWeak=receiver.data();
    {QMutexLocker guard(&picoCurrentInputMutex);query->receiver=receiver;}
    const bool posted=QMetaObject::invokeMethod(receiver.data(),[query,run,id]{
        if(!QCoreApplication::instance() || QThread::currentThread()!=QCoreApplication::instance()->thread() || !featureEnabled())return;
        const auto item=query->item;
        if(query->status!="pending" || !query->clock->fresh() || !picoCurrentInputDocument(query) || !item || item->thread()!=QThread::currentThread()){
            picoCurrentInputUnavailable(query);return;}
        query->before=item->featurePicoCurrentSnapshot(query->document->documents);
        if(query->before.isEmpty() || query->before.value("finish")!=query->document->admission.value("finish")
            || picoCurrentSemantic(query->before.value("native").toMap())!=picoCurrentSemantic(query->document->admission.value("native").toMap())){
            picoCurrentInputUnavailable(query);return;}
        const auto native=query->before.value("native").toMap();Jni jni;if(!jni.env){picoCurrentInputUnavailable(query);return;}
        const auto jr=jni.string(run),ji=jni.string(id),js=jni.string(native.value("sourceUrl").toString()),jc=jni.string(query->command.value("control").toString());
        bool sent=false;query->issued=true;
        if(jr && ji && js && jc){jvalue args[8];args[0].j=native.value("handle").toString().toLongLong();args[1].j=native.value("creation").toULongLong();
            args[2].j=native.value("grant").toULongLong();args[3].j=native.value("page").toULongLong();args[4].l=jr;args[5].l=ji;args[6].l=js;args[7].l=jc;
            sent=call("featurePicoCurrentInputRead","(JJJJLjava/lang/String;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;)V",args);}
        for(auto value:{jr,ji,js,jc})if(value)jni.env->DeleteLocalRef(value);
        if(!sent)picoCurrentInputUnavailable(query);
    },Qt::QueuedConnection);
    if(!posted)picoCurrentInputUnavailable(query);
    return query->status=="pending" ? picoCurrentInputPacket(query,"pending") : query->packet;
}
void NativeWebViewItem::acceptFeaturePicoWorldCurrentInput(qint64 handle,quint64 creation,quint64 grant,quint64 page,
        const QString& run,const QString& request,const QByteArray& raw){
    if(!featureEnabled() || raw.size()>16384)return;const auto query=picoCurrentInputLookup(run,request);if(!query)return;
    QSharedPointer<QObject> receiver;
    {QMutexLocker guard(&picoCurrentInputMutex);if(query->originals.size()>=4)return;query->originals.append(raw);receiver=query->receiver;}
    if(!receiver)return;
    QMetaObject::invokeMethod(receiver.data(),[query,handle,creation,grant,page,run,request,raw]{
        if(!QCoreApplication::instance() || QThread::currentThread()!=QCoreApplication::instance()->thread() || !featureEnabled())return;
        if(query->status!="pending" || !query->issued)return;
        const auto item=query->item;
        if(!query->clock->fresh() || !picoCurrentInputDocument(query) || !item || item->thread()!=QThread::currentThread()){
            picoCurrentInputUnavailable(query);return;}
        const auto after=item->featurePicoCurrentSnapshot(query->document->documents),before=query->before.value("native").toMap();
        if(after.isEmpty() || after.value("finish")!=query->document->admission.value("finish")
            || picoCurrentSemantic(after.value("native").toMap())!=picoCurrentSemantic(before)
            || before.value("handle").toString()!=QString::number(handle) || before.value("creation").toULongLong()!=creation
            || before.value("grant").toULongLong()!=grant || before.value("page").toULongLong()!=page){picoCurrentInputUnavailable(query);return;}
        const auto wrapper=QJsonDocument::fromJson(raw);const auto object=wrapper.object();
        if(!wrapper.isObject() || !picoCurrentKeys(object,{"before","geometryRaw","after"}) || !object.value("geometryRaw").isString()
            || object.value("geometryRaw").toString().toUtf8().size()>8192 || !picoCurrentJava(object.value("before").toObject())
            || !picoCurrentJava(object.value("after").toObject())){picoCurrentInputUnavailable(query);return;}
        const auto javaBefore=object.value("before").toObject().toVariantMap(),javaAfter=object.value("after").toObject().toVariantMap();
        if(picoCurrentSemantic(javaBefore)!=picoCurrentSemantic(javaAfter) || !picoCurrentJoins(before,javaBefore)
            || !picoCurrentJoins(after.value("native").toMap(),javaAfter)){picoCurrentInputUnavailable(query);return;}
        const auto quoted=QJsonDocument::fromJson('['+object.value("geometryRaw").toString().toUtf8()+']');QJsonDocument parsed;
        if(quoted.isArray() && quoted.array().size()==1 && quoted.array()[0].isString())parsed=QJsonDocument::fromJson(quoted.array()[0].toString().toUtf8());
        const auto geometry=parsed.object().toVariantMap(),native=after.value("native").toMap();
        const auto point=overte::e2e::picoBrowserPoint(geometry,request,run,before.value("url").toString(),query->command.value("control").toString(),
            QDateTime::currentMSecsSinceEpoch(),QSizeF(item->width(),item->height()));
        const auto originalDOM=query->document->packet.value("source").toMap().value("dom").toMap();
        if(!parsed.isObject() || !point || geometry.value("instance")!=originalDOM.value("instance")
            || geometry.value("sequence").toULongLong()<=originalDOM.value("sequence").toULongLong()
            || geometry.value("document")!=originalDOM.value("document") || !item->isVisible() || !item->isEnabled()
            || item->_presentation!=Texture || !item->window() || QGuiApplication::applicationState()!=Qt::ApplicationActive){picoCurrentInputUnavailable(query);return;}
        {QMutexLocker guard(&item->_mutex);const auto viewport=geometry.value("viewport").toMap();
            if(item->_image.isNull() || std::abs(double(item->_image.width())/item->_image.height()-viewport.value("width").toDouble()/viewport.value("height").toDouble())>0.02){
                picoCurrentInputUnavailable(query);return;}}
        const auto a=javaBefore.value("capturedEpochMs").toLongLong(),b=javaAfter.value("capturedEpochMs").toLongLong();
        const auto ge=geometry.value("capturedEpochMs").toLongLong();
        if(a<before.value("capturedEpochMs").toLongLong()-250 || b<a || b>native.value("capturedEpochMs").toLongLong()+250
            || ge<a-250 || ge>b+250 || javaAfter.value("capturedElapsedMs").toLongLong()<javaBefore.value("capturedElapsedMs").toLongLong()
            || javaAfter.value("capturedElapsedMs").toLongLong()-javaBefore.value("capturedElapsedMs").toLongLong()>1500){picoCurrentInputUnavailable(query);return;}
        const auto docPacket=query->document->packet;
        QVariantMap source{{"documentReference",QVariantMap{{"commandId",docPacket.value("commandId")},{"instance",docPacket.value("instance")},{"sequence",docPacket.value("sequence")}}},
            {"originalFinish",query->document->admission.value("finish")},{"authorityBefore",QVariantMap{{"native",before},{"java",javaBefore}}},
            {"authorityAfter",QVariantMap{{"native",native},{"java",javaAfter}}}};
        if(query->command.value("operation")=="measure-current-ray"){
            const auto property=qApp->property(overte::e2e::picoWorldWebRayProperty());
            if(property.userType()!=qMetaTypeId<overte::e2e::PicoWorldWebRayProvider>()){picoCurrentInputUnavailable(query);return;}
            const auto provider=property.value<overte::e2e::PicoWorldWebRayProvider>();const auto ray=provider ? provider(item,*point) : QVariantMap();
            if(ray.isEmpty()){picoCurrentInputUnavailable(query);return;}source.insert("geometryRaw",QString::fromUtf8(raw));source.insert("worldRay",ray);
        }else{
            const auto editor=geometry.value("editor").toMap();
            if(item->_editorText.size()>512){picoCurrentInputUnavailable(query);return;}
            const QVariantMap nativeEditor{{"text",item->_editorText},{"cursor",item->_cursor},{"anchor",item->_anchor},
                {"absoluteCursor",item->_surroundingStart+item->_cursor},{"kind",item->_editorKind},{"sensitive",item->_sensitive},
                {"focused",item->hasActiveFocus() && item->_editorActive},{"enabled",item->inputMethodQuery(Qt::ImEnabled)}};
            if(item->_sensitive || nativeEditor.value("focused")!=editor.value("focused") || (editor.value("focused")==true
                && (!nativeEditor.value("enabled").toBool() || item->_surroundingStart || item->_editorKind!=(query->command.value("control")=="foreign" ? "url" : "text")
                    || item->_editorText!=editor.value("text").toString() || item->_cursor!=editor.value("cursor").toInt() || item->_anchor!=editor.value("anchor").toInt()))){
                picoCurrentInputUnavailable(query);return;}
            source.insert("focusRaw",QString::fromUtf8(raw));source.insert("nativeEditor",nativeEditor);
        }
        // The provider/Qt editor queries above may have run arbitrary existing
        // code. Reacquire the actual final authority, not a copied bookend.
        if(!item){picoCurrentInputUnavailable(query);return;}
        const auto final=item->featurePicoCurrentSnapshot(query->document->documents);
        if(!query->clock->fresh() || !picoCurrentInputDocument(query) || final.isEmpty() || final.value("finish")!=after.value("finish")
            || picoCurrentSemantic(final.value("native").toMap())!=picoCurrentSemantic(native)){picoCurrentInputUnavailable(query);return;}
        const auto epoch=QDateTime::currentMSecsSinceEpoch();
        const QList<qint64> captured{before.value("capturedEpochMs").toLongLong(),native.value("capturedEpochMs").toLongLong(),a,b,ge};
        for(const auto value:captured)if(epoch-value< -250 || epoch-value>1500){picoCurrentInputUnavailable(query);return;}
        if(source.contains("worldRay")){const auto value=source.value("worldRay").toMap().value("capturedEpochMs").toLongLong();
            if(epoch-value< -250 || epoch-value>1500){picoCurrentInputUnavailable(query);return;}}
        query->raw=raw;auto packet=picoCurrentInputPacket(query,"ready",source);
        if(!query->clock->fresh() || QJsonDocument::fromVariant(packet).toJson(QJsonDocument::Compact).size()>65536){picoCurrentInputUnavailable(query);return;}
        query->packet=packet;query->status="ready";QMutexLocker guard(&picoCurrentInputMutex);query->receiver.clear();
    },Qt::QueuedConnection);
}
#else
#if defined(OVERTE_E2E_FEATURE_TESTS)
QVariantMap NativeWebViewItem::featurePicoWorldCurrentInput(const QVariantMap&,overte::e2e::PicoCurrentAnchor){return {};}
void NativeWebViewItem::acceptFeaturePicoWorldCurrentInput(qint64,quint64,quint64,quint64,const QString&,const QString&,const QByteArray&){}
#endif
#endif
extern "C" JNIEXPORT void JNICALL Java_org_overte_web_EmbeddedWebView_nativePicoCurrentInputResult(JNIEnv* env,jclass,jlong handle,jlong creation,jlong grant,jlong page,
        jstring run,jstring request,jstring raw){
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
    if(!run || !request || !raw || env->GetStringLength(run)!=32 || env->GetStringLength(request)!=32 || env->GetStringLength(raw)>16384)return;
    NativeWebViewItem::acceptFeaturePicoWorldCurrentInput(handle,creation,grant,page,string(env,run),string(env,request),string(env,raw).toUtf8());
#else
    Q_UNUSED(env);Q_UNUSED(handle);Q_UNUSED(creation);Q_UNUSED(grant);Q_UNUSED(page);Q_UNUSED(run);Q_UNUSED(request);Q_UNUSED(raw);
#endif
}
