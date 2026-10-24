// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Reuse original test assembly/provider bodies; run only this source boundary.
#define main original_browser_contract_main
#include "pico-browser-originals.cpp"
#undef main
// Include the unchanged complete original TU so this test can passively inspect
// its existing E2E finish inventory without adding a product accessor.
#include "NativeWebViewItem.cpp"

int main(int argc,char**argv) {
    QGuiApplication app(argc,argv);assert(argc>=2);
    const std::string path=std::string("-Djava.class.path=")+argv[1];JavaVMOption option{const_cast<char*>(path.c_str()),nullptr};
    JavaVMInitArgs config{JNI_VERSION_1_8,1,&option,JNI_FALSE};JavaVM* machine=nullptr;JNIEnv* env=nullptr;
    assert(JNI_CreateJavaVM(&machine,reinterpret_cast<void**>(&env),&config)==JNI_OK);
    auto java=env->FindClass("org/overte/web/EmbeddedWebView");assert(java);
    Java_org_overte_web_EmbeddedWebView_nativeInitialize(env,java);Java_org_overte_web_EmbeddedWebView_nativeForeground(env,java,true);
    const auto count=[&](const char*name){auto field=env->GetStaticFieldID(java,name,"I");assert(field);return env->GetStaticIntField(java,field);};
    const auto field=[&](const char*name){auto id=env->GetStaticFieldID(java,name,"J");assert(id);return env->GetStaticLongField(java,id);};
    const auto record=[&](const QString& name,const QVariantMap& value) {
        QFile output(QString::fromUtf8(argv[1])+"/"+name+".json");assert(output.open(QIODevice::WriteOnly|QIODevice::NewOnly));
        assert(output.setPermissions(QFileDevice::ReadOwner|QFileDevice::WriteOwner));
        const auto raw=QJsonDocument::fromVariant(value).toJson(QJsonDocument::Compact);assert(output.write(raw)==raw.size());output.close();
    };
    const auto javaText=[&](const char* name) {
        const auto field=env->GetStaticFieldID(java,name,"Ljava/lang/String;");assert(field);
        auto raw=static_cast<jstring>(env->GetStaticObjectField(java,field));if(!raw)return QString();
        const auto chars=env->GetStringUTFChars(raw,nullptr);assert(chars);const auto value=QString::fromUtf8(chars);
        env->ReleaseStringUTFChars(raw,chars);env->DeleteLocalRef(raw);return value;
    };
    {
        QQuickWindow window;window.resize(640,480);window.show();window.requestActivate();events();
        QQuickItem root(window.contentItem());root.setSize(QSizeF(640,480));
        const QString run(32,'1'),owner(32,'2'),fixture="http://127.0.0.1/feature-fixture/v1/runs/"+run+"/",url=fixture+"tickets/"+QString(32,'3')+"/index.html";
        auto command=[&](const QString&op){return QVariantMap{{"schemaVersion",1},{"commandId",nonce()},{"action","pico-world-web"},
            {"runId",run},{"fixtureUrl",fixture},{"operation",op},{"ownerToken",owner}};};
        assert(NativeWebViewItem::featurePicoBrowser(command("reserve")).value("status")=="ready");
        auto item=std::make_unique<BrowserItem>(&root);item->setSize(QSizeF(640,480));item->setSurface(NativeWebViewItem::WorldEntity);
        item->setSourceIdentity("web-entity:12345678-1234-1234-1234-123456789abc");item->setUrl(url);item->componentComplete();events();
        const auto handle=field("handle"),creation=field("birth");const auto grant=item->generation();assert(handle && creation && grant);
        item->acceptCreated(true,creation);events();item->acceptPage(grant,1,QUrl(url));events();
        // Exactly one original finished event. Neither foreground callback nor
        // the explicit Java recorder below dispatches another finished event.
        item->acceptFeatureWebFinished(grant,1,QUrl(url));events();
        const auto beforeRequest=command("observe");
        const auto beforePending=NativeWebViewItem::featurePicoBrowser(beforeRequest);
        assert(beforePending.value("status")=="pending" && count("worldReads")==1);
        const QVariantMap dom{{"webDOMVersion",1},{"requestId",beforeRequest.value("commandId")},{"instance",QString(32,'4')},{"sequence",1},
            {"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()},
            {"document",QVariantMap{{"runId",run},{"href",url},{"responseId",QString(32,'5')},{"readyState","complete"}}},
            {"editor",QVariantMap{{"text",""},{"focused",false}}},{"attempts",QVariantList{}},{"echoes",QVariantList{}}};
        item->acceptFeatureWebDOM(grant,1,QUrl(url),beforeRequest.value("commandId").toString(),quoted(dom));events();
        const auto before=NativeWebViewItem::featurePicoBrowser(beforeRequest);record("initial-finished-original",{{"request",beforeRequest},{"packet",before},{"javaWorldQueries",javaText("worldQueries")}});assert(before.value("status")=="ready");
        const auto source=before.value("source").toMap(),current=source.value("current").toMap().value("source").toMap().value("nativeView").toMap();
        const auto documents=source.value("documents").toList();assert(documents.size()==1);
        const auto finished=documents[0].toMap();assert(finished.value("creation").toULongLong()==quint64(creation)
            && finished.value("grant").toULongLong()==grant && finished.value("page").toULongLong()==1 && finished.value("url")==url
            && finished.value("finishedEpochMs").toLongLong()>0);
        assert(current.value("nativeFinished")==true);
        Java_org_overte_web_EmbeddedWebView_nativeForeground(env,java,false);events();
        const auto hiddenGrant=item->generation();assert(hiddenGrant!=grant);
        Java_org_overte_web_EmbeddedWebView_nativeForeground(env,java,true);events();
        const auto returnedGrant=item->generation();record("original-foreground-grants",{{"initial",qulonglong(grant)},{"hidden",qulonglong(hiddenGrant)},{"returned",qulonglong(returnedGrant)}});assert(returnedGrant!=hiddenGrant && returnedGrant!=grant);
        assert(item->allowsEditorDocument(returnedGrant,1,QUrl(url)) && field("birth")==creation && field("handle")==handle);
        // The native runtime snapshot independently acquires the actual live
        // current-grant/page/creation, not a requested finished-event value.
        const QVariantMap runtimeRequest{{"schemaVersion",1},{"commandId",nonce()},{"action","feature-web-runtime-observe"},{"runId",run},{"fixtureUrl",fixture}};
        assert(NativeWebViewItem::featureWebRuntimeObservation(runtimeRequest).value("status")=="pending");
        const QVariantMap javaAck{{"commandId",runtimeRequest.value("commandId")},{"complete",true}}; // Explicit Java inventory seam; not a full runtime DTO.
        NativeWebViewItem::acceptFeatureWebRuntime(runtimeRequest.value("commandId").toString(),QJsonDocument::fromVariant(javaAck).toJson(QJsonDocument::Compact));events();
        const auto runtime=NativeWebViewItem::featureWebRuntimeObservation(runtimeRequest);record("actual-current-native-runtime",{{"request",runtimeRequest},{"packet",runtime},{"javaRuntimeQueries",javaText("runtimeQueries")}});assert(runtime.value("status")=="ready");
        const auto native=runtime.value("source").toMap().value("nativeAfter").toMap();const auto views=native.value("views").toList();assert(views.size()==1);
        const auto view=views[0].toMap();assert(view.value("created")==true && view.value("sessionActive")==true
            && view.value("creation").toULongLong()==quint64(creation) && view.value("page").toULongLong()==1
            && view.value("grant").toULongLong()==returnedGrant && view.value("documentSha256")==QString::fromLatin1(QCryptographicHash::hash(url.toUtf8(),QCryptographicHash::Sha256).toHex()));
        const int reads=count("worldReads");const auto created=field("birth");
        const auto afterRequest=command("observe"),after=NativeWebViewItem::featurePicoBrowser(afterRequest);record("fresh-resume-pending-original",{{"request",afterRequest},{"packet",after},{"javaWorldQueries",javaText("worldQueries")}});
        assert(after.value("status")=="pending" && count("worldReads")==reads && field("birth")==created);
        const auto repeated=NativeWebViewItem::featurePicoBrowser(afterRequest);record("repeated-pending-original",{{"request",afterRequest},{"packet",repeated},{"javaWorldQueries",javaText("worldQueries")}});
        assert(repeated.value("status")=="pending" && repeated.value("commandId")==after.value("commandId")
            && repeated.value("sequence").toULongLong()>after.value("sequence").toULongLong()
            && repeated.value("capturedEpochMs").toLongLong()>=after.value("capturedEpochMs").toLongLong() && count("worldReads")==reads);
        const auto historical=NativeWebViewItem::featurePicoBrowser(beforeRequest);
        const auto retainedFinishHistory=worldWebScopes.value(run).documents;
        record("historical-finished-original",{{"request",beforeRequest},{"packet",historical},{"retainedFinishHistory",retainedFinishHistory}});
        // The native bounded cache intentionally prunes old observation replies;
        // its original finish event history remains unchanged, not retimed.
        assert(historical.isEmpty());assert(retainedFinishHistory==documents);
        // A fresh native world measurement is also unavailable. The ordinary
        // calibrated Reload hit cannot borrow the old grant's geometry.
        auto measure=command("measure-ray");measure.insert("handle",QString::number(handle));measure.insert("creation",qulonglong(creation));
        measure.insert("grant",qulonglong(returnedGrant));measure.insert("page",1);measure.insert("control","reload");
        assert(picoBrowserCommand(measure));const auto measured=NativeWebViewItem::featurePicoBrowser(measure);
        record("unavailable-normal-reload-geometry",{{"request",measure},{"packet",measured},{"javaGeometryQueries",count("geometryReads")}});
        assert(measured.isEmpty());assert(count("geometryReads")==0);
        const QVariantMap proof{{"beforeRequest",beforeRequest},{"before",before},{"hiddenGrant",qulonglong(hiddenGrant)},
            {"returnedGrant",qulonglong(returnedGrant)},{"runtimeRequest",runtimeRequest},{"runtime",runtime},
            {"afterRequest",afterRequest},{"after",after},{"historicalCacheReply",historical},{"retainedFinishHistory",retainedFinishHistory},{"worldReads",reads},{"geometryReads",count("geometryReads")},
            {"finishedEventsDelivered",1},{"reloadsDelivered",0}};
        record("retained-resume-originals",proof);

        // New read-only channel runs after the unchanged retained-page counter.
        const auto requestCurrent=[&](){return command("observe-current-document");};
        const auto startCurrent=[&](const QVariantMap& cmd) {
            const auto value=NativeWebViewItem::featurePicoWorldCurrentDocument(cmd);assert(value.value("status")=="pending");
            events();return picoCurrentLookup(run,cmd.value("commandId").toString());
        };
        int domSequence=1;
        const auto transaction=[&](const std::shared_ptr<PicoCurrentQuery>& query) {
            const auto native=query->before.value("native").toMap();assert(!native.isEmpty());
            QElapsedTimer timer;timer.start();
            QVariantMap java;
            for(const auto& key:QStringList{"handle","creation","grant","page","url","sourceUrl"})java.insert(key,native.value(key));
            for(const auto& key:QStringList{"ownerCurrent","active","foreground","windowFocused"})java.insert(key,true);
            for(const auto& key:QStringList{"destroyed","closing","loading"})java.insert(key,false);
            java.insert("capturedEpochMs",QDateTime::currentMSecsSinceEpoch());java.insert("capturedElapsedMs",timer.msecsSinceReference());
            auto currentDom=dom;currentDom.insert("requestId",query->command.value("commandId"));currentDom.insert("sequence",++domSequence);
            currentDom.insert("capturedEpochMs",QDateTime::currentMSecsSinceEpoch());
            // Explicit WebView/DOM recorder seam; same actual DOM identity and
            // complete original read bytes, no HTTP request or load callback.
            const QVariantMap wrapper{{"before",java},{"domRaw",QString::fromUtf8(quoted(currentDom))},{"after",java}};
            return QJsonDocument::fromVariant(wrapper).toJson(QJsonDocument::Compact);
        };
        const auto deliver=[&](const std::shared_ptr<PicoCurrentQuery>& query,const QByteArray& raw,quint64 callbackGrant) {
            auto jr=env->NewStringUTF(run.toUtf8().constData()),ji=env->NewStringUTF(query->command.value("commandId").toString().toUtf8().constData());
            auto body=env->NewStringUTF(raw.constData());
            Java_org_overte_web_EmbeddedWebView_nativePicoCurrentDocumentResult(env,java,handle,creation,callbackGrant,1,jr,ji,body);
            env->DeleteLocalRef(jr);env->DeleteLocalRef(ji);env->DeleteLocalRef(body);events();
        };
        const auto retainedCommand=requestCurrent();auto retainedQuery=startCurrent(retainedCommand);assert(retainedQuery && retainedQuery->javaIssued);
        const int currentReads=count("currentReads");assert(currentReads==1);
        const auto pendingAgain=NativeWebViewItem::featurePicoWorldCurrentDocument(retainedCommand);events();
        assert(pendingAgain.value("status")=="pending" && count("currentReads")==currentReads);
        const auto retainedRaw=transaction(retainedQuery);deliver(retainedQuery,retainedRaw,returnedGrant);
        const auto retained=NativeWebViewItem::featurePicoWorldCurrentDocument(retainedCommand);
        record("current-retained",{{"request",retainedCommand},{"packet",retained}});assert(retained.value("status")=="ready");
        const auto retainedSource=retained.value("source").toMap();
        assert(retainedSource.value("originalFinish").toMap()==finished && retainedSource.value("documents").toList()==documents);
        assert(retainedSource.value("authorityBefore").toMap().value("native").toMap().value("grant").toULongLong()==returnedGrant);
        assert(retainedSource.value("originalFinish").toMap().value("grant").toULongLong()==grant && returnedGrant!=grant);
        assert(retainedSource.value("dom").toMap().value("instance")==dom.value("instance"));
        assert(retainedSource.value("domRaw")==QString::fromUtf8(retainedRaw));
        const auto readyAgain=NativeWebViewItem::featurePicoWorldCurrentDocument(retainedCommand);events();
        assert(readyAgain==retained && count("currentReads")==currentReads && worldWebScopes.value(run).documents==documents);
        const auto byteCommand=requestCurrent();auto byteQuery=startCurrent(byteCommand);
        auto byteWrapper=QJsonDocument::fromJson(transaction(byteQuery)).object();
        auto innerQuoted=QJsonDocument::fromJson('['+byteWrapper.value("domRaw").toString().toUtf8()+']');
        auto byteDOM=QJsonDocument::fromJson(innerQuoted.array()[0].toString().toUtf8()).object();
        auto byteEditor=byteDOM.value("editor").toObject();byteEditor.insert("text",QString(512,QChar(0x4e2d)));byteDOM.insert("editor",byteEditor);
        QJsonArray byteEchoes;
        for(int i=1;i<=27;++i){
            const QVariantMap message{{"contract","overte-web-parity-v1"},{"action","echo"},{"sequence",i},{"surface","world"}};
            byteEchoes.append(QJsonObject{{"sequence",i},{"surface","world"},
                {"message",QString::fromUtf8(QJsonDocument::fromVariant(message).toJson(QJsonDocument::Compact))},
                {"receivedEpochMs",double(byteQuery->clock->epoch)},{"observedEpochMs",double(byteQuery->clock->epoch)}});
        }
        byteDOM.insert("echoes",byteEchoes);const auto originalQuoted=QString::fromUtf8(quoted(byteDOM.toVariantMap()));
        byteWrapper.insert("domRaw",originalQuoted);const auto byteRaw=QJsonDocument(byteWrapper).toJson(QJsonDocument::Compact);
        record("current-utf8-input",{{"domOriginal",byteDOM.toVariantMap()},{"domRaw",originalQuoted},
            {"innerUtf16Units",originalQuoted.size()},{"innerUtf8Bytes",originalQuoted.toUtf8().size()},{"transactionBytes",byteRaw.size()}});
        assert(originalQuoted.size()<=8192 && originalQuoted.toUtf8().size()>8192 && byteRaw.size()<16384);
        deliver(byteQuery,byteRaw,returnedGrant);
        const auto bytePacket=NativeWebViewItem::featurePicoWorldCurrentDocument(byteCommand);
        record("current-utf8-cap",{{"request",byteCommand},{"packet",bytePacket},{"domOriginal",byteDOM.toVariantMap()},
            {"innerUtf16Units",originalQuoted.size()},{"innerUtf8Bytes",originalQuoted.toUtf8().size()},{"transactionBytes",byteRaw.size()}});
        assert(bytePacket.value("status")=="unavailable" && byteQuery->originals.size()==1 && byteQuery->originals[0]==byteRaw);
        assert(count("currentReads")==currentReads+1); // no resample after rejected original
        if(QCoreApplication::arguments().contains("--current-document-byte-cap")){
            item.reset();events();assert(machine->DestroyJavaVM()==JNI_OK);
            puts("PASS actual Pico current-document UTF8 byte cap without another DOM read");return 0;
        }
        auto foreign=retainedCommand;foreign.insert("ownerToken",nonce());assert(NativeWebViewItem::featurePicoWorldCurrentDocument(foreign).isEmpty());
        auto foreignNonce=nonce();NativeWebViewItem::acceptFeaturePicoWorldCurrentDocument(handle,creation,returnedGrant,1,run,foreignNonce,retainedRaw);events();
        assert(!picoCurrentLookup(run,foreignNonce) && retainedQuery->originals.size()==1);
        const auto staleCommand=requestCurrent();auto staleQuery=startCurrent(staleCommand);deliver(staleQuery,transaction(staleQuery),grant);
        const auto stale=NativeWebViewItem::featurePicoWorldCurrentDocument(staleCommand);record("current-stale-grant",{{"request",staleCommand},{"packet",stale}});assert(stale.value("status")=="unavailable");
        assert(!staleQuery->originals.isEmpty());
        // An actual new original finished callback is distinguished, never
        // manufactured by current-document observation itself.
        auto finishedUrl=env->NewStringUTF(url.toUtf8().constData());
        Java_org_overte_web_EmbeddedWebView_nativeFeatureFinished(env,java,handle,returnedGrant,1,finishedUrl);
        env->DeleteLocalRef(finishedUrl);events();
        const auto newCommand=requestCurrent();auto newQuery=startCurrent(newCommand);deliver(newQuery,transaction(newQuery),returnedGrant);
        const auto newFinish=NativeWebViewItem::featurePicoWorldCurrentDocument(newCommand);record("current-new-finish",{{"request",newCommand},{"packet",newFinish}});
        assert(newFinish.value("status")=="ready" && worldWebScopes.value(run).documents.size()==2);
        assert(newFinish.value("source").toMap().value("originalFinish").toMap().value("grant").toULongLong()==returnedGrant);
        assert(!retainedQuery->receiverWeak); // actual deferred-delete occurred
        const auto lateCommand=requestCurrent();auto lateQuery=startCurrent(lateCommand);const auto lateRaw=transaction(lateQuery);
        events(1550);deliver(lateQuery,lateRaw,returnedGrant);
        const auto late=NativeWebViewItem::featurePicoWorldCurrentDocument(lateCommand);record("current-late",{{"request",lateCommand},{"packet",late}});
        assert(late.value("status")=="unavailable");
        const auto deadCommand=requestCurrent();auto deadQuery=startCurrent(deadCommand);const auto deadRaw=transaction(deadQuery);
        item.reset();events();deliver(deadQuery,deadRaw,returnedGrant);
        const auto dead=NativeWebViewItem::featurePicoWorldCurrentDocument(deadCommand);record("current-dead",{{"request",deadCommand},{"packet",dead}});
        assert(dead.value("status")=="unavailable" && !deadQuery->owner && !deadQuery->receiverWeak);
        record("current-proof",{{"retainedGrant",qulonglong(returnedGrant)},{"finishGrant",qulonglong(grant)},
            {"legacyDOMReads",count("worldReads")},{"currentDOMReads",count("currentReads")},{"originalFinishEvents",2},
            {"reloads",0},{"sameDOM",true},{"foreignNonceQueryCreated",false}});

    }
    assert(machine->DestroyJavaVM()==JNI_OK);
    puts("PASS actual Pico current-document retained/new finish, nonce, stale, weak death and late original clocks");
}
