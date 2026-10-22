// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Included only by NativeWebViewItem.cpp. Default-off instrumentation; no
// navigation, authority, DOM or feature-state setters are added to the product.
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PHONE_INTERFACE)
namespace {
struct WorldWebScope {
    bool reference{false};QString surface{"world"};
    QString root,token,instance{QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')};
    QVariantList documents,requests,replies;QVariantMap dom;
    bool complete{true},retired{false};quint64 sequence{0};qint64 epoch{0};
    QVariantMap input,receipt,lastCommand,lastPacket;QElapsedTimer timer;
};
QHash<QString,WorldWebScope> worldWebScopes;
QString worldWebKey(const QVariantMap& row) {
    return row.value("handle").toString()+":"+row.value("creation").toString()+":"+row.value("grant").toString()+":"+row.value("page").toString();
}
QVariantMap worldWebPacket(const QVariantMap& command,WorldWebScope& scope,const QString& status,const QVariantMap& source={}) {
    const auto now=QDateTime::currentMSecsSinceEpoch();
    if (now<=0 || now<scope.epoch || scope.sequence>=9007199254740991ULL || !scope.complete) { return {}; }
    scope.epoch=now;
    QVariantMap packet{{"phoneWorldWebVersion",1},{"commandId",command.value("commandId")},{"runId",command.value("runId")},
        {"ownerToken",scope.token},{"instance",scope.instance},{"sequence",static_cast<qulonglong>(++scope.sequence)},
        {"processId",QCoreApplication::applicationPid()},{"capturedEpochMs",now},{"status",status},{"source",source}};
    if (command.value("operation")!="input") { scope.lastCommand=command;scope.lastPacket=packet; }
    return packet;
}
}
void NativeWebViewItem::featureWorldWebRecord(const QString& kind,const QVariant& value) {
    if (!featureEnabled() || thread()!=QThread::currentThread()) { return; }
    QString source,document;quint64 grant,page;
    { QMutexLocker guard(&_mutex);source=_session.url().toString(QUrl::FullyEncoded);document=_document.toString(QUrl::FullyEncoded);
      grant=_session.generation();page=_page; }
    for (auto scope=worldWebScopes.begin();scope!=worldWebScopes.end();++scope) {
        if ((!scope->reference && _surface!=WorldEntity) || scope->retired || !(scope->reference ? source==scope->root+"index.html" : source.startsWith(scope->root+"tickets/")) || !grant || !page) { continue; }
        QVariantMap identity{{"handle",QString::number(_handle)},{"creation",static_cast<qulonglong>(_creationRevision)},
            {"grant",static_cast<qulonglong>(grant)},{"page",static_cast<qulonglong>(page)},{"url",document}};
        const auto key=worldWebKey(identity);const auto now=QDateTime::currentMSecsSinceEpoch();
        if (now<=0 || now<scope->epoch) { scope->complete=false;return; }
        if (kind=="documents") {
            bool found=false;
            for (const auto& row:scope->documents) { if (worldWebKey(row.toMap())==key) { found=true;break; } }
            if (found) { continue; } // Actual duplicate completion is not another load.
            if (scope->documents.size()>=256) { scope->complete=false;return; }
            identity.insert("finishedEpochMs",now);scope->documents.append(identity);
        } else if (kind=="dom") {
            const auto packet=value.toMap(),original=scope->dom.value(key).toMap();
            if (!original.isEmpty()) {
                const auto before=original.value("source").toMap().value("dom").toMap();
                const auto after=packet.value("source").toMap().value("dom").toMap();
                if (before.value("instance")!=after.value("instance")) { scope->complete=false;return; }
                for (const auto& history:QStringList{"attempts","echoes"}) {
                    const auto a=before.value(history).toList(),b=after.value(history).toList();
                    if (b.size()<a.size()) { scope->complete=false;return; }
                    for (int index=0;index<a.size();++index) { if (a[index]!=b[index]) { scope->complete=false;return; } }
                }
            }
            if (scope->dom.size()>=256 && !scope->dom.contains(key)) { scope->complete=false;return; }
            scope->dom.insert(key,packet); // Original source timestamps are preserved.
        } else if (kind=="requests" || kind=="replies") {
            if (value.userType()!=QMetaType::QString || value.toString().size()>4096) { continue; }
            const auto raw=QJsonDocument::fromJson(value.toString().toUtf8());
            if (!raw.isObject()) { continue; }const auto packet=raw.object();
            const auto sequence=packet.value("sequence").toDouble(-1);
            if (packet.value("contract")!="overte-web-parity-v1" || packet.value("action")!="echo"
                    || sequence<1 || sequence>1000000 || sequence!=int(sequence)) { continue; }
            auto& rows=kind=="requests" ? scope->requests : scope->replies;
            if (rows.size()>=128) { scope->complete=false;return; }
            identity.insert("message",value);identity.insert("capturedEpochMs",now);rows.append(identity);
        } else { scope->complete=false;return; }
    }
}
QVariantMap NativeWebViewItem::featurePhoneWorldWeb(const QVariantMap& command) {
    if (!featureEnabled() || !overte::e2e::phoneWorldWebCommand(command) || !QCoreApplication::instance()
            || QThread::currentThread()!=QCoreApplication::instance()->thread()) { return {}; }
    const auto run=command.value("runId").toString(),operation=command.value("operation").toString();
    if (!worldWebScopes.contains(run)) {
        if (operation!="reserve" || worldWebScopes.size()>=32) { return {}; }
        WorldWebScope scope;scope.root=command.value("fixtureUrl").toString();scope.reference=command.value("action")=="phone-web-reference";
        scope.surface=scope.reference ? command.value("surface").toString() : "world";scope.token=command.value("ownerToken").toString();
        worldWebScopes.insert(run,scope);
    }
    auto& scope=worldWebScopes[run];
    if (scope.root!=command.value("fixtureUrl") || scope.token!=command.value("ownerToken") || !scope.complete
            || scope.reference!=(command.value("action")=="phone-web-reference")
            || (scope.reference && scope.surface!=command.value("surface"))) { return {}; }
    if (operation!="input" && scope.lastCommand.value("commandId")==command.value("commandId")) {
        if (scope.lastCommand!=command) { return {}; }
        if (scope.lastPacket.value("status")=="ready" || scope.lastPacket.value("status")=="unavailable") { return scope.lastPacket; }
    }
    QList<QPointer<NativeWebViewItem>> original;
    { QMutexLocker guard(&registryMutex);if (registry.size()>128) { return {}; }for (auto* item:registry) { original.append(item); } }
    QPointer<NativeWebViewItem> selected;int owned=0;
    for (const auto& item:original) {
        if (!item || item->thread()!=QThread::currentThread()) { return {}; }
        QString source;{ QMutexLocker guard(&item->_mutex);source=item->_session.url().toString(QUrl::FullyEncoded); }
        const bool matches=scope.reference ? source==scope.root+"index.html" : source.startsWith(scope.root+"tickets/");
        if (!matches) { continue; }++owned;
        if (item->_surface!=(scope.surface=="world" ? WorldEntity : Tablet)) { continue; }
        if (selected) { return {}; }selected=item;
    }
    if (operation=="reserve") {
        // A reservation cannot adopt an already existing owned world view.
        if (owned || scope.retired || !scope.documents.isEmpty()) { return {}; }
        return worldWebPacket(command,scope,"ready",{{"reserved",true}});
    }
    if (operation=="retire") {
        if (!scope.input.isEmpty() && scope.receipt.value("status")=="pending" && scope.timer.isValid() && scope.timer.elapsed()>=4000) {
            scope.receipt=worldWebPacket(scope.input,scope,"unavailable"); // An expired input is never an effect.
        }
        if (owned || (!scope.input.isEmpty() && scope.receipt.value("status")=="pending")) { return {}; }
        scope.input.clear();scope.receipt.clear();scope.timer.invalidate();
        scope.retired=true;scope.documents.clear();scope.requests.clear();scope.replies.clear();scope.dom.clear();
        return worldWebPacket(command,scope,"ready",{{"retired",true}});
    }
    if (operation=="input") {
        if (scope.retired) { return {}; }
        if (!scope.input.isEmpty() && scope.input.value("commandId")==command.value("commandId")) {
            if (scope.input!=command) { return {}; }
            if (scope.receipt.value("status")=="pending" && scope.timer.elapsed()>=4000) { scope.receipt=worldWebPacket(command,scope,"unavailable"); }
            return scope.receipt;
        }
        if (scope.receipt.value("status")=="pending" || !selected) { return {}; }
        quint64 grant,page;QUrl document;
        { QMutexLocker guard(&selected->_mutex);grant=selected->_session.generation();page=selected->_page;document=selected->_document; }
        if (command.value("handle")!=QString::number(selected->_handle) || command.value("creation").toULongLong()!=selected->_creationRevision
                || command.value("grant").toULongLong()!=grant || command.value("page").toULongLong()!=page
                || !selected->allowsEditorDocument(grant,page,document)) { return {}; }
        scope.input=command;scope.timer.start();scope.receipt=worldWebPacket(command,scope,"pending");
        Jni jni;if (!jni.env) { scope.receipt=worldWebPacket(command,scope,"unavailable");return scope.receipt; }
        const auto id=jni.string(command.value("commandId").toString()),control=jni.string(command.value("control").toString()),text=jni.string(command.value("text").toString());
        bool posted=false;
        if (id && control && text) { jvalue args[6];args[0].j=selected->_handle;args[1].j=grant;args[2].j=page;args[3].l=id;args[4].l=control;args[5].l=text;
            posted=call("featureWorldInput","(JJJLjava/lang/String;Ljava/lang/String;Ljava/lang/String;)V",args); }
        if (id) jni.env->DeleteLocalRef(id);if (control) jni.env->DeleteLocalRef(control);if (text) jni.env->DeleteLocalRef(text);
        if (!posted) scope.receipt=worldWebPacket(command,scope,"unavailable");
        return scope.receipt;
    }
    QVariantMap current;
    if (selected) {
        if (scope.retired) { return {}; }
        if (scope.reference) {
            quint64 grant,page;QString source;QUrl document;bool inlineLease;
            { QMutexLocker guard(&selected->_mutex);grant=selected->_session.generation();page=selected->_page;
              document=selected->_document;source=selected->_session.url().toString(QUrl::FullyEncoded);
              inlineLease=selected->_inlineProvided && selected->_inlineDocument.current(); }
            if (!selected->allowsEditorDocument(grant,page,document) || selected->_featureWebFinishedGrant!=grant
                    || selected->_featureWebFinishedPage!=page || selected->_featureWebFinishedDocument!=document) {
                return worldWebPacket(command,scope,"pending");
            }
            QVariantMap view{{"handle",QString::number(selected->_handle)},{"creation",static_cast<qulonglong>(selected->_creationRevision)},
                {"grant",static_cast<qulonglong>(grant)},{"page",static_cast<qulonglong>(page)},{"url",document.toString(QUrl::FullyEncoded)},
                {"nativeFinished",true},{"httpErrorStatus",selected->_featureWebHTTPGrant==grant && selected->_featureWebHTTPPage==page ? selected->_featureWebHTTPStatus : 0},
                {"inlineLease",inlineLease},{"sourceUrl",source},{"sourceIdentity",selected->_sourceIdentity}};
            current={{"nativeView",view}};
        } else {
        auto request=QVariantMap{{"schemaVersion",1},{"commandId",command.value("commandId")},{"action","feature-web-dom-observe"},
            {"runId",run},{"surface","world"},{"fixtureUrl",scope.root}};
        const auto packet=selected->featureWebDOMRequest(request);
        if (packet.value("status")!="ready") { return worldWebPacket(command,scope,packet.value("status").toString()); }
        current=packet;
        }
    }
    return worldWebPacket(command,scope,"ready",{{"retired",scope.retired},{"documents",scope.documents},
        {"requests",scope.requests},{"replies",scope.replies},{"domHistory",scope.dom},{"current",current}});
}
void NativeWebViewItem::acceptFeatureWorldWebInput(const QString& request,bool delivered) {
    if (!featureEnabled() || !QCoreApplication::instance()) { return; }
    QMetaObject::invokeMethod(QCoreApplication::instance(),[request,delivered] {
        for (auto scope=worldWebScopes.begin();scope!=worldWebScopes.end();++scope) {
            if (scope->input.value("commandId")!=request || scope->receipt.value("status")!="pending") { continue; }
            scope->receipt=worldWebPacket(scope->input,*scope,delivered && scope->timer.elapsed()<4000 ? "ready" : "unavailable",
                delivered ? QVariantMap{{"delivered",true}} : QVariantMap());
        }
    },Qt::QueuedConnection);
}
extern "C" JNIEXPORT void JNICALL Java_org_overte_web_EmbeddedWebView_nativeFeatureWorldInput(JNIEnv* env,jclass,jstring request,jboolean delivered) {
    if (!request || env->GetStringLength(request)!=32) { return; }
    NativeWebViewItem::acceptFeatureWorldWebInput(string(env,request),delivered);
}
#else
#if defined(OVERTE_E2E_FEATURE_TESTS)
QVariantMap NativeWebViewItem::featurePhoneWorldWeb(const QVariantMap&) { return {}; }
void NativeWebViewItem::acceptFeatureWorldWebInput(const QString&,bool) {}
void NativeWebViewItem::featureWorldWebRecord(const QString&,const QVariant&) {}
#endif
#endif
