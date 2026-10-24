// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Separate read-only source. Legacy DOM/Browser commands and finished fields
// are never modified by this observer.
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
namespace {
struct PicoCurrentQuery;
struct PicoCurrentScope {
    QString token,root,instance{QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')};
    quint64 sequence{0};QHash<QString,std::shared_ptr<PicoCurrentQuery>> queries;
};
struct PicoCurrentQuery {
    QVariantMap command,admission,before,packet;QVariantList documents;
    QByteArray raw;QVector<QByteArray> originals;
    overte::e2e::PicoCurrentAnchor clock;
    QPointer<NativeWebViewItem> owner;QPointer<QObject> receiverWeak;
    QSharedPointer<QObject> receiver;
    std::weak_ptr<PicoCurrentScope> scope;
    QString status{"pending"};bool javaIssued{false};
};
QMutex picoCurrentMutex;
QHash<QString,std::shared_ptr<PicoCurrentScope>> picoCurrentScopes;
std::shared_ptr<PicoCurrentQuery> picoCurrentLookup(const QString& run,const QString& id) {
    QMutexLocker guard(&picoCurrentMutex);const auto scope=picoCurrentScopes.value(run);
    return scope ? scope->queries.value(id) : nullptr;
}
QVariantMap picoCurrentSemantic(QVariantMap value) {
    value.remove("capturedEpochMs");value.remove("capturedMonotonicMs");value.remove("capturedElapsedMs");return value;
}
void picoCurrentCloseReceiver(const std::shared_ptr<PicoCurrentQuery>& query) {
    QMutexLocker guard(&picoCurrentMutex);query->receiver.clear();
}
QVariantMap picoCurrentPacket(const std::shared_ptr<PicoCurrentQuery>& query,const QString& status,const QVariantMap& source={}) {
    const auto scope=query->scope.lock();if(!scope || scope->sequence>=9007199254740991ULL)return {};
    return {{"picoWorldCurrentDocumentVersion",1},{"commandId",query->command.value("commandId")},{"runId",query->command.value("runId")},
        {"ownerToken",scope->token},{"instance",scope->instance},{"sequence",qulonglong(++scope->sequence)},
        {"processId",QCoreApplication::applicationPid()},{"requestedEpochMs",query->clock->epoch},
        {"requestedMonotonicMs",query->clock->monotonic},{"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()},
        {"capturedMonotonicMs",query->clock->nowMonotonic()},{"status",status},{"source",source}};
}
void picoCurrentUnavailable(const std::shared_ptr<PicoCurrentQuery>& query) {
    query->status="unavailable";query->packet=picoCurrentPacket(query,"unavailable");picoCurrentCloseReceiver(query);
}
bool picoCurrentKeys(const QJsonObject& value,const QSet<QString>& expected) {
    const auto keys=value.keys();return QSet<QString>(keys.begin(),keys.end())==expected;
}
bool picoCurrentInteger(const QJsonValue& value,qint64 minimum=0) {
    const auto number=value.toDouble(-1);return value.isDouble() && std::isfinite(number) && number>=minimum && number<=9007199254740991. && number==qint64(number);
}
bool picoCurrentJava(const QJsonObject& value) {
    if(!picoCurrentKeys(value,{"handle","creation","grant","page","url","sourceUrl","ownerCurrent","active","foreground","windowFocused",
            "destroyed","closing","loading","capturedEpochMs","capturedElapsedMs"})
        || !QRegularExpression("\\A[1-9][0-9]{0,18}\\z").match(value.value("handle").toString()).hasMatch())return false;
    for(const auto& key:QStringList{"creation","grant","page","capturedEpochMs"})if(!picoCurrentInteger(value.value(key),1))return false;
    if(!picoCurrentInteger(value.value("capturedElapsedMs")))return false;
    for(const auto& key:QStringList{"ownerCurrent","active","foreground","windowFocused"})if(value.value(key)!=QJsonValue(true))return false;
    for(const auto& key:QStringList{"destroyed","closing","loading"})if(value.value(key)!=QJsonValue(false))return false;
    return value.value("url").isString() && value.value("sourceUrl").isString();
}
bool picoCurrentJoins(const QVariantMap& native,const QVariantMap& java) {
    for(const auto& key:QStringList{"handle","creation","grant","page","url","sourceUrl"}) {
        if(QJsonValue::fromVariant(native.value(key))!=QJsonValue::fromVariant(java.value(key)))return false;
    }
    return true;
}
}

QVariantMap NativeWebViewItem::featurePicoCurrentSnapshot(const QVariantList& documents) const {
    if(!featureEnabled() || !QCoreApplication::instance() || QThread::currentThread()!=QCoreApplication::instance()->thread()
        || thread()!=QThread::currentThread() || _surface!=WorldEntity)return {};
    QVariantMap authority,finish;quint64 finishedGrant,finishedPage;QUrl finishedDocument;
    {
        QMutexLocker guard(&_mutex);
        if(!QRegularExpression("\\Aweb-entity:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\\z").match(_sourceIdentity).hasMatch() || !_created || !_sourceAuthorized || !_session.active() || _suspendedDocument || _loading || _inlineProvided || !_page || !_creationRevision)return {};
        authority={{"handle",QString::number(_handle)},{"itemInstance",_featureWebInstance},{"creation",qulonglong(_creationRevision)},
            {"grant",qulonglong(_session.generation())},{"page",qulonglong(_page)},{"url",_document.toString(QUrl::FullyEncoded)},
            {"sourceUrl",_session.url().toString(QUrl::FullyEncoded)},{"sourceIdentity",_sourceIdentity},
            {"created",true},{"authorized",true},{"sessionActive",true},{"suspended",false},{"loading",false}};
        finishedGrant=_featureWebFinishedGrant;finishedPage=_featureWebFinishedPage;finishedDocument=_featureWebFinishedDocument;
    }
    if(!isVisible() || !isEnabled() || !allowsEditorDocument(authority.value("grant").toULongLong(),authority.value("page").toULongLong(),QUrl(authority.value("url").toString()))
        || !finishedGrant || finishedPage!=authority.value("page").toULongLong() || finishedDocument.toString(QUrl::FullyEncoded)!=authority.value("url"))return {};
    QSet<QString> keys;qint64 lastFinish=0;
    if(documents.size()>256)return {};
    for(const auto& entry:documents) {
        const auto row=entry.toMap();const auto json=QJsonObject::fromVariantMap(row);const auto key=worldWebKey(row);
        if(!picoCurrentKeys(json,{"handle","creation","grant","page","url","finishedEpochMs"}) || keys.contains(key)
            || !QRegularExpression("\\A[1-9][0-9]{0,18}\\z").match(json.value("handle").toString()).hasMatch()
            || !picoCurrentInteger(json.value("creation"),1) || !picoCurrentInteger(json.value("grant"),1)
            || !picoCurrentInteger(json.value("page"),1) || !json.value("url").isString()
            || !picoCurrentInteger(json.value("finishedEpochMs"),1) || row.value("finishedEpochMs").toLongLong()<lastFinish)return {};
        keys.insert(key);lastFinish=row.value("finishedEpochMs").toLongLong();
        if(row.value("handle")==authority.value("handle") && row.value("creation")==authority.value("creation")
            && row.value("grant").toULongLong()==finishedGrant && row.value("page").toULongLong()==finishedPage && row.value("url")==finishedDocument.toString(QUrl::FullyEncoded)) {
            if(!finish.isEmpty())return {};finish=row;
        }
    }
    if(finish.isEmpty() || lastFinish>QDateTime::currentMSecsSinceEpoch()+250)return {};
    QElapsedTimer captured;captured.start();authority.insert("capturedMonotonicMs",captured.msecsSinceReference());
    authority.insert("capturedEpochMs",QDateTime::currentMSecsSinceEpoch());
    return {{"native",authority},{"finish",finish}};
}

QVariantMap NativeWebViewItem::featurePicoWorldCurrentDocument(const QVariantMap& command,overte::e2e::PicoCurrentAnchor anchor) {
    if(!featureEnabled() || !overte::e2e::picoWorldCurrentDocumentCommand(command) || !QCoreApplication::instance()
        || QThread::currentThread()!=QCoreApplication::instance()->thread())return {};
    const auto originalAnchor=overte::e2e::picoCurrentAnchor(command);
    if(!anchor)anchor=originalAnchor;if(!anchor || anchor!=originalAnchor)return {};
    const auto run=command.value("runId").toString(),id=command.value("commandId").toString();
    auto found=worldWebScopes.find(run);if(found==worldWebScopes.end())return {};
    const auto& original=found.value();
    if(original.retired || !original.complete || original.tablet || original.reference || original.surface!="world"
        || original.token!=command.value("ownerToken") || original.root!=command.value("fixtureUrl"))return {};
    auto query=picoCurrentLookup(run,id);
    if(query) {
        if(query->command!=command)return {};
        if(!query->clock->fresh() || !query->owner)picoCurrentUnavailable(query);
        if(query->status=="ready") {
            const auto item=query->owner;
            const auto current=item ? item->featurePicoCurrentSnapshot(original.documents) : QVariantMap();
            if(current.isEmpty() || original.documents!=query->documents || current.value("finish")!=query->admission.value("finish")
                || picoCurrentSemantic(current.value("native").toMap())!=picoCurrentSemantic(query->admission.value("native").toMap()))picoCurrentUnavailable(query);
        }
        auto result=query->status=="pending" ? picoCurrentPacket(query,"pending") : query->packet;
        if(!query->clock->fresh() && query->status!="unavailable"){picoCurrentUnavailable(query);result=query->packet;}
        return result;
    }
    // No legacy nonce can become this new callback's authority.
    for(const auto& value:worldWebScopes)if(value.originalCommands.contains(id))return {};
    std::shared_ptr<PicoCurrentScope> scope;
    {
        QMutexLocker guard(&picoCurrentMutex);scope=picoCurrentScopes.value(run);
        if(!scope) {
            if(picoCurrentScopes.size()>=32)return {};
            scope=std::make_shared<PicoCurrentScope>();scope->root=original.root;scope->token=original.token;picoCurrentScopes.insert(run,scope);
        }
        if(scope->queries.size()>=128 || scope->root!=original.root || scope->token!=original.token)return {};
    }
    query=std::make_shared<PicoCurrentQuery>();query->command=command;query->clock=anchor;query->scope=scope;query->documents=original.documents;
    {
        QMutexLocker guard(&picoCurrentMutex);scope->queries.insert(id,query);
    }
    if(!anchor->fresh() || query->documents.size()>256){picoCurrentUnavailable(query);return query->packet;}
    QList<QPointer<NativeWebViewItem>> candidates;
    {QMutexLocker guard(&registryMutex);if(registry.size()>128){picoCurrentUnavailable(query);return query->packet;}for(auto* item:registry)candidates.append(item);}
    for(const auto& item:candidates) {
        if(!item || item->thread()!=QThread::currentThread()){picoCurrentUnavailable(query);return query->packet;}
        QString source;{QMutexLocker guard(&item->_mutex);source=item->_session.url().toString(QUrl::FullyEncoded);}
        if(!source.startsWith(original.root+"tickets/"))continue;
        if(query->owner || item->_surface!=WorldEntity){picoCurrentUnavailable(query);return query->packet;}
        query->owner=item;
    }
    if(!query->owner){picoCurrentUnavailable(query);return query->packet;}
    query->admission=query->owner->featurePicoCurrentSnapshot(query->documents);
    if(query->admission.isEmpty()){picoCurrentUnavailable(query);return query->packet;}
    const auto receiver=QSharedPointer<QObject>(new QObject(),[](QObject* value){value->deleteLater();});
    query->receiverWeak=receiver.data();
    {QMutexLocker guard(&picoCurrentMutex);query->receiver=receiver;}
    const bool posted=QMetaObject::invokeMethod(receiver.data(),[query,run,id] {
        if(!QCoreApplication::instance() || QThread::currentThread()!=QCoreApplication::instance()->thread() || !featureEnabled())return;
        if(query->status!="pending" || !query->clock->fresh()){picoCurrentUnavailable(query);return;}
        const auto item=query->owner;const auto found=worldWebScopes.constFind(run);
        if(!item || item->thread()!=QThread::currentThread() || found==worldWebScopes.cend() || found->retired || !found->complete
            || found->documents!=query->documents || found->token!=query->command.value("ownerToken")){picoCurrentUnavailable(query);return;}
        query->before=item->featurePicoCurrentSnapshot(found->documents);
        if(query->before.isEmpty() || query->before.value("finish")!=query->admission.value("finish")
            || picoCurrentSemantic(query->before.value("native").toMap())!=picoCurrentSemantic(query->admission.value("native").toMap())){picoCurrentUnavailable(query);return;}
        Jni jni;if(!jni.env){picoCurrentUnavailable(query);return;}
        const auto native=query->before.value("native").toMap();
        const auto request=jni.string(id),runValue=jni.string(run),source=jni.string(native.value("sourceUrl").toString());
        bool sent=false;query->javaIssued=true;
        if(request && runValue && source) {
            jvalue args[7];args[0].j=native.value("handle").toString().toLongLong();args[1].j=native.value("creation").toULongLong();
            args[2].j=native.value("grant").toULongLong();args[3].j=native.value("page").toULongLong();args[4].l=runValue;args[5].l=request;args[6].l=source;
            sent=call("featurePicoCurrentDocumentRead","(JJJJLjava/lang/String;Ljava/lang/String;Ljava/lang/String;)V",args);
        }
        if(request)jni.env->DeleteLocalRef(request);if(runValue)jni.env->DeleteLocalRef(runValue);if(source)jni.env->DeleteLocalRef(source);
        if(!sent)picoCurrentUnavailable(query);
    },Qt::QueuedConnection);
    if(!posted)picoCurrentUnavailable(query);
    return query->status=="pending" ? picoCurrentPacket(query,"pending") : query->packet;
}

void NativeWebViewItem::acceptFeaturePicoWorldCurrentDocument(qint64 handle,quint64 creation,quint64 grant,quint64 page,
        const QString& run,const QString& request,const QByteArray& raw) {
    if(!featureEnabled() || raw.size()>16384)return;
    const auto query=picoCurrentLookup(run,request);if(!query)return;
    QSharedPointer<QObject> receiver;
    {QMutexLocker guard(&picoCurrentMutex);
        if(query->originals.size()>=4)return;query->originals.append(raw);receiver=query->receiver;}
    if(!receiver)return;
    QMetaObject::invokeMethod(receiver.data(),[query,handle,creation,grant,page,run,request,raw] {
        if(!QCoreApplication::instance() || QThread::currentThread()!=QCoreApplication::instance()->thread() || !featureEnabled())return;
        if(query->status!="pending" || !query->javaIssued)return;
        const auto item=query->owner;const auto scope=worldWebScopes.constFind(run);
        if(!query->clock->fresh() || !item || item->thread()!=QThread::currentThread() || scope==worldWebScopes.cend() || scope->retired || !scope->complete
            || scope->documents!=query->documents || scope->token!=query->command.value("ownerToken")){picoCurrentUnavailable(query);return;}
        const auto after=item->featurePicoCurrentSnapshot(scope->documents),before=query->before.value("native").toMap();
        if(after.isEmpty() || after.value("finish")!=query->admission.value("finish")
            || picoCurrentSemantic(after.value("native").toMap())!=picoCurrentSemantic(before)
            || before.value("handle").toString()!=QString::number(handle) || before.value("creation").toULongLong()!=creation
            || before.value("grant").toULongLong()!=grant || before.value("page").toULongLong()!=page){picoCurrentUnavailable(query);return;}
        const auto transaction=QJsonDocument::fromJson(raw);const auto object=transaction.object();
        if(!transaction.isObject() || !picoCurrentKeys(object,{"before","domRaw","after"}) || !object.value("domRaw").isString()
            || !picoCurrentJava(object.value("before").toObject()) || !picoCurrentJava(object.value("after").toObject())){picoCurrentUnavailable(query);return;}
        const auto javaBefore=object.value("before").toObject().toVariantMap(),javaAfter=object.value("after").toObject().toVariantMap();
        if(picoCurrentSemantic(javaBefore)!=picoCurrentSemantic(javaAfter) || !picoCurrentJoins(before,javaBefore)
            || !picoCurrentJoins(after.value("native").toMap(),javaAfter)){picoCurrentUnavailable(query);return;}
        const auto quoted=QJsonDocument::fromJson('['+object.value("domRaw").toString().toUtf8()+']');QJsonDocument parsed;
        if(quoted.isArray() && quoted.array().size()==1 && quoted.array()[0].isString())parsed=QJsonDocument::fromJson(quoted.array()[0].toString().toUtf8());
        const auto dom=parsed.object(),document=dom.value("document").toObject();
        if(!parsed.isObject() || !picoCurrentKeys(dom,{"webDOMVersion","requestId","instance","sequence","capturedEpochMs","document","editor","attempts","echoes"})
            || dom.value("webDOMVersion")!=QJsonValue(1) || dom.value("requestId")!=QJsonValue(request)
            || document.value("runId")!=QJsonValue(run) || document.value("href")!=QJsonValue(before.value("url").toString())
            || document.value("readyState")!=QJsonValue("complete") || !picoCurrentInteger(dom.value("capturedEpochMs"),1)
            || !picoCurrentInteger(dom.value("sequence"),1) || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(dom.value("instance").toString()).hasMatch()){
            picoCurrentUnavailable(query);return;}
        const auto nativeAfter=after.value("native").toMap();const auto begin=before.value("capturedEpochMs").toLongLong(),end=nativeAfter.value("capturedEpochMs").toLongLong();
        const auto ja=javaBefore.value("capturedEpochMs").toLongLong(),jb=javaAfter.value("capturedEpochMs").toLongLong();
        const auto de=dom.value("capturedEpochMs").toDouble();
        if(ja<begin-250 || jb<ja || jb>end+250 || de<ja-250 || de>jb+250
            || javaAfter.value("capturedElapsedMs").toLongLong()<javaBefore.value("capturedElapsedMs").toLongLong()
            || javaAfter.value("capturedElapsedMs").toLongLong()-javaBefore.value("capturedElapsedMs").toLongLong()>1500){picoCurrentUnavailable(query);return;}
        query->raw=raw;
        const QVariantMap source{{"authorityBefore",QVariantMap{{"native",before},{"java",javaBefore}}},
            {"originalFinish",query->admission.value("finish")},{"domRaw",QString::fromUtf8(raw)},{"dom",dom.toVariantMap()},
            {"authorityAfter",QVariantMap{{"native",nativeAfter},{"java",javaAfter}}},{"documents",query->documents}};
        auto packet=picoCurrentPacket(query,"ready",source);
        if(!query->clock->fresh() || QJsonDocument::fromVariant(packet).toJson(QJsonDocument::Compact).size()>65536){picoCurrentUnavailable(query);return;}
        query->packet=packet;query->status="ready";picoCurrentCloseReceiver(query);
    },Qt::QueuedConnection);
}
#else
#if defined(OVERTE_E2E_FEATURE_TESTS)
QVariantMap NativeWebViewItem::featurePicoWorldCurrentDocument(const QVariantMap&,overte::e2e::PicoCurrentAnchor){return {};}
QVariantMap NativeWebViewItem::featurePicoCurrentSnapshot(const QVariantList&)const{return {};}
void NativeWebViewItem::acceptFeaturePicoWorldCurrentDocument(qint64,quint64,quint64,quint64,const QString&,const QString&,const QByteArray&){}
#endif
#endif

extern "C" JNIEXPORT jboolean JNICALL Java_org_overte_web_EmbeddedWebView_nativePicoCurrentDocumentEnabled(JNIEnv*,jclass) {
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
    return featureEnabled();
#else
    return false;
#endif
}
extern "C" JNIEXPORT void JNICALL Java_org_overte_web_EmbeddedWebView_nativePicoCurrentDocumentResult(JNIEnv* env,jclass,jlong handle,jlong creation,jlong grant,jlong page,
        jstring run,jstring request,jstring raw) {
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
    if(!run || !request || !raw || env->GetStringLength(run)!=32 || env->GetStringLength(request)!=32 || env->GetStringLength(raw)>16384)return;
    NativeWebViewItem::acceptFeaturePicoWorldCurrentDocument(handle,creation,grant,page,string(env,run),string(env,request),string(env,raw).toUtf8());
#else
    Q_UNUSED(env);Q_UNUSED(handle);Q_UNUSED(creation);Q_UNUSED(grant);Q_UNUSED(page);Q_UNUSED(run);Q_UNUSED(request);Q_UNUSED(raw);
#endif
}
