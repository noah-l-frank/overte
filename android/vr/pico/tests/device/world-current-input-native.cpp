// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Reuse original test assembly/provider bodies; run only this source boundary.
#define main original_browser_contract_main
#include "current-browser-assembly.inc"
#undef main
// Include the unchanged complete original TU so this test can passively inspect
// its existing E2E finish inventory without adding a product accessor.
#include "NativeWebViewItem.cpp"

struct CurrentSurface {QQuickWindow* window{};QQuickWindow* getWindow(){return window;}};
struct WebEntityRenderer {float _dpi{40};std::shared_ptr<CurrentSurface> _webSurface=std::make_shared<CurrentSurface>();void handlePointerEventAsMouse(const PointerEvent&);};
struct RayPick {static glm::vec2 projectOntoXYPlane(const glm::vec3&,const glm::vec3&,const glm::quat&,const glm::vec3&,const glm::vec3&,bool);};
#include "current-renderer-raypick.inc"
int main(int argc,char**argv) {
    CurrentAppBoundary app(argc,argv);assert(argc>=2);
    const auto caseIndex=QCoreApplication::arguments().indexOf("--current-input-case");
    const QString selectedCase=caseIndex>=0 ? QCoreApplication::arguments().value(caseIndex+1) : "positive";
    const std::string path=std::string("-Djava.class.path=")+argv[1];JavaVMOption option{const_cast<char*>(path.c_str()),nullptr};
    JavaVMInitArgs config{JNI_VERSION_1_8,1,&option,JNI_FALSE};JavaVM* machine=nullptr;JNIEnv* env=nullptr;
    assert(JNI_CreateJavaVM(&machine,reinterpret_cast<void**>(&env),&config)==JNI_OK);
    auto javaClass=env->FindClass("org/overte/web/EmbeddedWebView");assert(javaClass);
    Java_org_overte_web_EmbeddedWebView_nativeInitialize(env,javaClass);Java_org_overte_web_EmbeddedWebView_nativeForeground(env,javaClass,true);
    const auto count=[&](const char*name){auto field=env->GetStaticFieldID(javaClass,name,"I");assert(field);return env->GetStaticIntField(javaClass,field);};
    const auto field=[&](const char*name){auto id=env->GetStaticFieldID(javaClass,name,"J");assert(id);return env->GetStaticLongField(javaClass,id);};
    const auto record=[&](const QString& name,const QVariantMap& value) {
        QFile output(QString::fromUtf8(argv[1])+"/"+name+".json");assert(output.open(QIODevice::WriteOnly|QIODevice::NewOnly));
        assert(output.setPermissions(QFileDevice::ReadOwner|QFileDevice::WriteOwner));
        const auto raw=QJsonDocument::fromVariant(value).toJson(QJsonDocument::Compact);assert(output.write(raw)==raw.size());output.close();
    };
    const auto javaText=[&](const char* name) {
        const auto field=env->GetStaticFieldID(javaClass,name,"Ljava/lang/String;");assert(field);
        auto raw=static_cast<jstring>(env->GetStaticObjectField(javaClass,field));if(!raw)return QString();
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
        const QVariantMap dom{{"webDOMVersion",1},{"requestId",beforeRequest.value("commandId")},{"instance",javaText("modelDOMInstance")},{"sequence",1},
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
        Java_org_overte_web_EmbeddedWebView_nativeForeground(env,javaClass,false);events();
        const auto hiddenGrant=item->generation();assert(hiddenGrant!=grant);
        Java_org_overte_web_EmbeddedWebView_nativeForeground(env,javaClass,true);events();
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
        const unsigned char frame[640*480*4]={};item->acceptFrame(returnedGrant,1,frame,sizeof(frame),640,480);events();
        QQmlEngine engine;auto context=std::make_unique<QQmlContext>(engine.rootContext());QQmlEngine::setContextForObject(item.get(),context.get());
        context->setContextProperty("nativeWebSourceIdentity",item->property("sourceIdentity"));currentEntities.props.url=url;
        installWorldWebRayProvider();
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
            auto currentDom=dom;currentDom.insert("requestId",query->command.value("commandId"));currentDom.insert("sequence",count("modelDOMSequence"));
            currentDom.insert("capturedEpochMs",QDateTime::currentMSecsSinceEpoch());
            // Explicit WebView/DOM recorder seam; same actual DOM identity and
            // complete original read bytes, no HTTP request or load callback.
            const QVariantMap wrapper{{"before",java},{"domRaw",QString::fromUtf8(quoted(currentDom))},{"after",java}};
            return QJsonDocument::fromVariant(wrapper).toJson(QJsonDocument::Compact);
        };
        const auto deliver=[&](const std::shared_ptr<PicoCurrentQuery>& query,const QByteArray& raw,quint64 callbackGrant) {
            auto jr=env->NewStringUTF(run.toUtf8().constData()),ji=env->NewStringUTF(query->command.value("commandId").toString().toUtf8().constData());
            auto body=env->NewStringUTF(raw.constData());
            Java_org_overte_web_EmbeddedWebView_nativePicoCurrentDocumentResult(env,javaClass,handle,creation,callbackGrant,1,jr,ji,body);
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
        int geometrySequence=100;
        const auto inputCommand=[&](const QVariantMap& doc,const QString& op){auto value=command(op);
            value.insert("documentNonce",doc.value("commandId"));value.insert("control","text");return value;};
        const auto geometryTransaction=[&](const std::shared_ptr<PicoCurrentInputQuery>& query){
            const auto native=query->before.value("native").toMap();assert(!native.isEmpty());
            QVariantMap java;for(const auto& key:QStringList{"handle","creation","grant","page","url","sourceUrl"})java.insert(key,native.value(key));
            for(const auto& key:QStringList{"ownerCurrent","active","foreground","windowFocused"})java.insert(key,true);
            for(const auto& key:QStringList{"destroyed","closing","loading"})java.insert(key,false);
            QElapsedTimer timer;timer.start();java.insert("capturedEpochMs",QDateTime::currentMSecsSinceEpoch());java.insert("capturedElapsedMs",timer.msecsSinceReference());
            const auto focusedField=env->GetStaticFieldID(javaClass,"modelFocused","Z");assert(focusedField);
            const bool focused=env->GetStaticBooleanField(javaClass,focusedField);
            const auto doc=query->document->packet.value("source").toMap().value("dom").toMap();
            const QVariantMap geometry{{"webGeometryVersion",1},{"requestId",query->command.value("commandId")},{"instance",doc.value("instance")},
                {"sequence",count("modelDOMSequence")},{"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()},{"document",doc.value("document")},{"control","text"},
                {"editor",QVariantMap{{"focused",focused},{"text",""},{"cursor",0},{"anchor",0}}},
                {"viewport",QVariantMap{{"width",640},{"height",480},{"scale",1},{"offsetLeft",0},{"offsetTop",0}}},
                {"rect",QVariantMap{{"x",80},{"y",60},{"width",160},{"height",80}}},{"center",QVariantMap{{"x",160},{"y",100}}},
                {"hit",true},{"enabled",true},{"connected",true}};
            return QJsonDocument::fromVariant(QVariantMap{{"before",java},{"geometryRaw",QString::fromUtf8(quoted(geometry))},{"after",java}}).toJson(QJsonDocument::Compact);
        };
        const auto readInput=[&](const QVariantMap& cmd,const QString& fault=QString()){
            auto pending=NativeWebViewItem::featurePicoWorldCurrentInput(cmd);assert(pending.value("status")=="pending");events();
            const auto query=picoCurrentInputLookup(run,cmd.value("commandId").toString());assert(query && query->issued);
            const auto raw=geometryTransaction(query);
            if(fault=="foreign"){
                const auto before=count("currentInputReads");auto unknown=cmd;unknown.insert("commandId",nonce());unknown.insert("documentNonce",nonce());
                assert(NativeWebViewItem::featurePicoWorldCurrentInput(unknown).isEmpty());
                auto collision=cmd;collision.insert("control","bridge");assert(NativeWebViewItem::featurePicoWorldCurrentInput(collision).isEmpty());
                NativeWebViewItem::acceptFeaturePicoWorldCurrentInput(handle,creation,returnedGrant,1,run,nonce(),raw);events();
                assert(query->originals.isEmpty() && count("currentInputReads")==before);
                assert(NativeWebViewItem::featurePicoWorldCurrentInput(cmd).value("status")=="pending");
            }
            if(fault=="grant"){Java_org_overte_web_EmbeddedWebView_nativeForeground(env,javaClass,false);events();Java_org_overte_web_EmbeddedWebView_nativeForeground(env,javaClass,true);events();assert(item->generation()!=returnedGrant);}
            if(fault=="page"){item->acceptPage(returnedGrant,2,QUrl(url));events();}
            if(fault=="source"){item->setUrl(fixture+"tickets/"+nonce()+"/index.html");events();}
            if(fault=="death" || fault=="recreate"){
                item.reset();events();
                if(fault=="recreate"){
                    item=std::make_unique<BrowserItem>(&root);item->setSize(QSizeF(640,480));item->setSurface(NativeWebViewItem::WorldEntity);
                    item->setSourceIdentity("web-entity:12345678-1234-1234-1234-123456789abc");item->setUrl(url);item->componentComplete();events();
                    const auto birth=field("birth");assert(field("handle")!=handle && birth>0);record("current-input-recreation-lineage",{{"oldHandle",qlonglong(handle)},{"newHandle",qlonglong(field("handle"))},{"oldCreationRevision",qlonglong(creation)},{"newCreationRevision",qlonglong(birth)}});item->acceptCreated(true,birth);events();
                    const auto grant=item->generation();item->acceptPage(grant,1,QUrl(url));events();item->acceptFrame(grant,1,frame,sizeof(frame),640,480);events();
                    auto ju=env->NewStringUTF(url.toUtf8().constData());Java_org_overte_web_EmbeddedWebView_nativeFeatureFinished(env,javaClass,field("handle"),grant,1,ju);env->DeleteLocalRef(ju);events();
                    assert(worldWebScopes.value(run).documents.size()==2);
                }
            }
            if(fault=="context")context.reset();
            if(fault=="window")root.setParentItem(nullptr);
            if(fault=="late")events(1550);
            QQuickItem overlay(&root);overlay.setSize(QSizeF(640,480));overlay.setZ(100);overlay.setVisible(fault=="overlay");
            auto jr=env->NewStringUTF(run.toUtf8().constData()),ji=env->NewStringUTF(cmd.value("commandId").toString().toUtf8().constData()),jb=env->NewStringUTF(raw.constData());
            const auto callbackNative=query->before.value("native").toMap();
            Java_org_overte_web_EmbeddedWebView_nativePicoCurrentInputResult(env,javaClass,callbackNative.value("handle").toString().toLongLong(),
                callbackNative.value("creation").toULongLong(),callbackNative.value("grant").toULongLong(),callbackNative.value("page").toULongLong(),jr,ji,jb);
            env->DeleteLocalRef(jr);env->DeleteLocalRef(ji);env->DeleteLocalRef(jb);events();
            return NativeWebViewItem::featurePicoWorldCurrentInput(cmd);
        };
        if(selectedCase!="positive"){
            const auto cmd=inputCommand(retained,"measure-current-ray");const int beforePointers=count("pointers");
            const auto result=readInput(cmd,selectedCase);const auto query=picoCurrentInputLookup(run,cmd.value("commandId").toString());
            record("current-input-counter",{{"case",selectedCase},{"request",cmd},{"packet",result},{"pointers",count("pointers")-beforePointers},
                {"geometryQueries",count("currentInputReads")},{"rawOriginals",query->originals.size()},
                {"documentOriginal",QVariantMap{{"request",retainedCommand},{"raw",QString::fromUtf8(QJsonDocument::fromVariant(retained).toJson(QJsonDocument::Compact))}}}});
            assert(result.value("status")== (selectedCase=="foreign" ? "ready" : "unavailable"));
            assert(count("pointers")==beforePointers && count("currentInputReads")==1 && query->originals.size()==1);
            const auto repeated=NativeWebViewItem::featurePicoWorldCurrentInput(cmd);events();
            assert(repeated==result && count("currentInputReads")==1);
            if(selectedCase=="recreate"){
                QQmlEngine::setContextForObject(item.get(),context.get());
                const auto docCommand=requestCurrent();auto pending=NativeWebViewItem::featurePicoWorldCurrentDocument(docCommand);assert(pending.value("status")=="pending");events();
                const auto freshDocQuery=picoCurrentLookup(run,docCommand.value("commandId").toString());assert(freshDocQuery && freshDocQuery->javaIssued);
                auto wrapper=QJsonDocument::fromJson(transaction(freshDocQuery)).object();
                auto quotedDOM=QJsonDocument::fromJson('['+wrapper.value("domRaw").toString().toUtf8()+']');auto originalDOM=QJsonDocument::fromJson(quotedDOM.array()[0].toString().toUtf8()).object();
                originalDOM.insert("instance",javaText("modelDOMInstance"));wrapper.insert("domRaw",QString::fromUtf8(quoted(originalDOM.toVariantMap())));
                const auto actual=freshDocQuery->before.value("native").toMap();
                NativeWebViewItem::acceptFeaturePicoWorldCurrentDocument(actual.value("handle").toString().toLongLong(),actual.value("creation").toULongLong(),actual.value("grant").toULongLong(),1,
                    run,docCommand.value("commandId").toString(),QJsonDocument(wrapper).toJson(QJsonDocument::Compact));events();
                const auto doc=NativeWebViewItem::featurePicoWorldCurrentDocument(docCommand);assert(doc.value("status")=="ready");
                assert(doc.value("source").toMap().value("dom").toMap().value("instance")!=retained.value("source").toMap().value("dom").toMap().value("instance"));
                assert(doc.value("source").toMap().value("authorityBefore").toMap().value("native").toMap().value("itemInstance")
                    !=retained.value("source").toMap().value("authorityBefore").toMap().value("native").toMap().value("itemInstance"));
                const auto newCommand=inputCommand(doc,"measure-current-ray");const auto newRay=readInput(newCommand);assert(newRay.value("status")=="ready");
                record("current-input-recreated",{{"request",newCommand},{"packet",newRay},{"documentOriginal",QVariantMap{{"request",docCommand},
                    {"raw",QString::fromUtf8(QJsonDocument::fromVariant(doc).toJson(QJsonDocument::Compact))}}}});
            }
            item.reset();events();assert(!query->receiverWeak);assert(machine->DestroyJavaVM()==JNI_OK);
            puts("PASS original CurrentInput disjoint counter, full raw retained, zero pointer and no repeated query");return 0;
        }
        const auto rayCommand=inputCommand(retained,"measure-current-ray");const auto ray=readInput(rayCommand);
        record("current-input-ray",{{"request",rayCommand},{"packet",ray},{"documentOriginal",QVariantMap{{"request",retainedCommand},{"raw",QString::fromUtf8(QJsonDocument::fromVariant(retained).toJson(QJsonDocument::Compact))}}}});
        assert(ray.value("status")=="ready");
        const auto rayOriginal=ray.value("source").toMap().value("worldRay").toMap();const auto world=rayOriginal.value("worldPoint").toList();
        const glm::vec3 point(world[0].toFloat(),world[1].toFloat(),world[2].toFloat());
        const auto projected=RayPick::projectOntoXYPlane(point,currentEntities.props.getPosition(),currentEntities.props.getRotation(),
            currentEntities.props.getDimensions(),currentEntities.props.getRegistrationPoint(),true);
        WebEntityRenderer renderer;renderer._webSurface->window=&window;
        const int beforePointers=count("pointers");
        renderer.handlePointerEventAsMouse(PointerEvent(PointerEvent::Press,1,projected,PointerEvent::PrimaryButton,PointerEvent::PrimaryButton,Qt::NoModifier));
        renderer.handlePointerEventAsMouse(PointerEvent(PointerEvent::Release,1,projected,PointerEvent::PrimaryButton,PointerEvent::NoButtons,Qt::NoModifier));events();
        assert(count("pointers")==beforePointers+2 && item->hasActiveFocus());
        const auto focusedField=env->GetStaticFieldID(javaClass,"modelFocused","Z");assert(focusedField && env->GetStaticBooleanField(javaClass,focusedField));
        // Explicit Android editor/DOM model boundary consumes the actual JNI
        // pointer, not the requested focus or a controller publication ACK.
        Java_org_overte_web_EmbeddedWebView_nativeInputFocus(env,javaClass,handle,creation,returnedGrant,env->GetStaticBooleanField(javaClass,focusedField));events();
        const QVariantMap publishedEditor{{"active",bool(env->GetStaticBooleanField(javaClass,focusedField))},{"text",javaText("modelText")},
            {"cursor",0},{"anchor",0},{"absoluteCursor",0},{"kind","text"}};
        assert(item->acceptMessage(returnedGrant,1,QUrl(url),QUrl("http://127.0.0.1"),true,"editor",QJsonDocument::fromVariant(publishedEditor).toJson(QJsonDocument::Compact)));events();
        const auto focusedDocCommand=requestCurrent();auto focusedDocQuery=startCurrent(focusedDocCommand);
        auto focusedWrapper=QJsonDocument::fromJson(transaction(focusedDocQuery)).object();
        auto quotedDOM=QJsonDocument::fromJson('['+focusedWrapper.value("domRaw").toString().toUtf8()+']');auto focusedDOM=QJsonDocument::fromJson(quotedDOM.array()[0].toString().toUtf8()).object();
        auto editor=focusedDOM.value("editor").toObject();editor.insert("focused",bool(env->GetStaticBooleanField(javaClass,focusedField)));focusedDOM.insert("editor",editor);
        focusedWrapper.insert("domRaw",QString::fromUtf8(quoted(focusedDOM.toVariantMap())));
        deliver(focusedDocQuery,QJsonDocument(focusedWrapper).toJson(QJsonDocument::Compact),returnedGrant);
        const auto focusedDoc=NativeWebViewItem::featurePicoWorldCurrentDocument(focusedDocCommand);assert(focusedDoc.value("status")=="ready");
        const auto focusCommand=inputCommand(focusedDoc,"observe-current-focus");const auto focus=readInput(focusCommand);
        record("current-input-focus",{{"request",focusCommand},{"packet",focus},{"documentOriginal",QVariantMap{{"request",focusedDocCommand},{"raw",QString::fromUtf8(QJsonDocument::fromVariant(focusedDoc).toJson(QJsonDocument::Compact))}}}});
        assert(focus.value("status")=="ready" && focus.value("source").toMap().value("nativeEditor").toMap().value("focused")==true);
        assert(focusedDoc.value("source").toMap().value("dom").toMap().value("editor").toMap().value("focused")==true);
        record("current-input-proof",{{"pointers",count("pointers")-beforePointers},{"geometryQueries",count("currentInputReads")},
            {"nativeFocused",item->hasActiveFocus()},{"seams","Android DOM/editor and entity/avatar/HMD dependencies; no OpenXR device/mapper execution"}});
        item.reset();events();
    }
    assert(machine->DestroyJavaVM()==JNI_OK);
    puts("PASS actual current-authority ray -> original projection/renderer/Qt/JNI pointer -> native focus and fresh readonly DOM");
}
