// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include <InlineHtmlDocument.h>
#include <QQmlContext>
#include <QQmlProperty>
#include <QVariantMap>
#include <thread>
extern "C" jlong Java_org_overte_web_EmbeddedWebView_nativeBeginResourceLoad(JNIEnv*, jclass, jlong, jlong, jlong, jlong, jstring);
extern "C" jboolean Java_org_overte_web_EmbeddedWebView_nativeBindResourcePage(JNIEnv*, jclass, jlong, jlong, jlong, jlong, jlong, jlong, jstring);
extern "C" jboolean Java_org_overte_web_EmbeddedWebView_nativeResourceCurrent(JNIEnv*, jclass, jlong, jlong, jlong, jlong, jlong);
extern "C" jobject Java_org_overte_web_EmbeddedWebView_nativeRequest(JNIEnv*, jclass, jlong, jlong, jlong, jlong, jlong, jstring, jboolean, jstring);
extern "C" void Java_org_overte_web_EmbeddedWebView_nativeForeground(JNIEnv*, jclass, jboolean);

static void runInlineBackendTests(JNIEnv* env, jclass boundary, const QString& backendPath) {
    using overte::web::InlineHtmlDocumentOwner;
    auto field = [&](const char* name) { return env->GetStaticLongField(boundary, env->GetStaticFieldID(boundary,name,"J")); };
    auto count = [&] { return env->GetStaticIntField(boundary,env->GetStaticFieldID(boundary,"creates","I")); };
    auto jstringFor = [&](const QString& value) { return env->NewString(reinterpret_cast<const jchar*>(value.utf16()),value.size()); };
    auto responseType = env->FindClass("org/overte/web/WebResourceLease$Response");
    if (!responseType) env->ExceptionDescribe();
    assert(responseType); // The real production response carrier, never an API substitute.
    auto actionField = env->GetFieldID(responseType,"action","I");
    auto bytesField = env->GetFieldID(responseType,"bytes","[B");
    auto charsetField = env->GetFieldID(responseType,"charset","Ljava/lang/String;");
    assert(actionField && bytesField && charsetField);
    auto responseAction = [&](jobject response) { return response ? env->GetIntField(response,actionField) : 0; };
    auto responseBytes = [&](jobject response) {
        auto array = static_cast<jbyteArray>(env->GetObjectField(response,bytesField)); assert(array);
        QByteArray result(env->GetArrayLength(array),char(0));
        env->GetByteArrayRegion(array,0,result.size(),reinterpret_cast<jbyte*>(result.data())); env->DeleteLocalRef(array); return result;
    };
    Java_org_overte_web_EmbeddedWebView_nativeForeground(env,boundary,true);
    QCoreApplication::processEvents(); QCoreApplication::processEvents();
    QQmlEngine engine;
    engine.addImportPath(QFileInfo(backendPath).absoluteDir().absoluteFilePath("../.."));
    QQmlFileSelector selector(&engine); selector.setExtraSelectors({"android"});
    QQmlContext ownerContext(engine.rootContext()), nested(&ownerContext), foreignContext(engine.rootContext());
    const QString raw = "data:text/html;charset=windows-1252,%3Cp%3E%00%80%FF.qml#anchor";
    const QString script = "https://script.test/a%2Fname.js?literal=%2f";
    InlineHtmlDocumentOwner owner;
    const auto document = owner.issue(&ownerContext,"inline-owner",raw,script);
    ownerContext.setContextProperty("nativeInlineHtmlDocument",QVariant::fromValue(document));
    ownerContext.setContextProperty("nativeWebSourceIdentity","inline-owner");
    QQmlComponent component(&engine);
    component.setData("import QtQuick 2.7\nimport controls 1.0 as Controls\nItem { width: 100; height: 100; property alias content: page; Controls.EmbeddedWebView { id: page; anchors.fill: parent; url: authored; scriptUrl: approvedScript } }",QUrl());
    ownerContext.setContextProperty("authored",raw); ownerContext.setContextProperty("approvedScript",script);
    assert(component.isReady()); const auto before = count();
    std::unique_ptr<QObject> root(component.create(&nested));
    if (!root) qWarning() << component.errors(); assert(root);
    QCoreApplication::processEvents();
    auto* view = root->findChild<NativeWebViewItem*>(); assert(view);
    assert(view->generation() && view->url() == raw && view->scriptUrl() == script);
    assert(count() == before+1); // Full tuple authorized before the single first native creation.
    auto handle = field("handle"), birth = field("creationRevision"); auto grant = view->generation();
    const auto transport = document.transportURL(); auto transportString = jstringFor(transport.toString(QUrl::FullyEncoded));
    auto get = jstringFor("GET"), head = jstringFor("HEAD");
    const auto load = Java_org_overte_web_EmbeddedWebView_nativeBeginResourceLoad(env,boundary,handle,birth,grant,1,transportString); assert(load);
    auto response = Java_org_overte_web_EmbeddedWebView_nativeRequest(env,boundary,handle,birth,grant,load,1,transportString,true,get);
    assert(responseAction(response) == 1 && responseBytes(response) == QByteArray::fromHex("3c703e0080ff2e716d6c"));
    auto charset = static_cast<jstring>(env->GetObjectField(response,charsetField));
    const char* encoding = env->GetStringUTFChars(charset,nullptr); assert(QByteArray(encoding) == "windows-1252");
    env->ReleaseStringUTFChars(charset,encoding); env->DeleteLocalRef(charset); env->DeleteLocalRef(response);
    assert(Java_org_overte_web_EmbeddedWebView_nativeBindResourcePage(env,boundary,handle,birth,grant,load,1,2,transportString));
    response = Java_org_overte_web_EmbeddedWebView_nativeRequest(env,boundary,handle,birth,grant,load,1,transportString,true,head);
    assert(responseAction(response) == 1 && responseBytes(response).isEmpty()); env->DeleteLocalRef(response);
    view->acceptPage(grant,2,transport);
    QUrl origin = transport; origin.setPath(""); origin.setFragment({});
    assert(view->allowsBridgeDocument(grant,2,transport));
    assert(view->acceptMessage(grant,2,transport,origin,true,"editor","{}"));
    assert(!view->acceptMessage(grant,2,transport,origin,false,"editor","{}"));
    assert(!view->acceptMessage(grant,2,transport,QUrl("http://other.overte-inline.invalid"),true,"editor","{}"));
    QUrl wrongPath=transport; wrongPath.setPath("/copied.html");
    assert(!view->acceptMessage(grant,2,wrongPath,origin,true,"channel",R"({"type":3,"id":0})"));
    view->acceptState(grant,2,transport,true,false,false,true,0); QCoreApplication::processEvents();
    assert(view->currentUrl() == raw); // Exact authored source stays distinct from transport.
    // Actual scene graph clears the revoked document's previously visible pixels.
    QQuickRenderControl control; QQuickWindow window(&control); window.resize(8,8); window.setColor(Qt::transparent);
    // Observe the native texture itself; the shared error overlay would otherwise mask it.
    assert(QQmlProperty(view,"anchors.fill").write(QVariant::fromValue<QQuickItem*>(nullptr)));
    view->setParentItem(window.contentItem()); view->setSize(QSizeF(8,8));
    const unsigned char red[] = {0,0,255,255}; view->acceptFrame(grant,2,red,sizeof(red),1,1);
    QCoreApplication::processEvents();
    control.initialize(nullptr); control.polishItems(); control.sync(); control.render();
    assert(control.grab().pixelColor(1,1).red() > 240);
    // Resource IO actually enters JNI on a foreign JVM-attached thread and never pumps Qt.
    std::atomic<bool> ioPassed { false }; JavaVM* machine=nullptr; assert(env->GetJavaVM(&machine)==JNI_OK);
    std::thread io([&] {
        JNIEnv* threadEnv=nullptr; assert(machine->AttachCurrentThread(reinterpret_cast<void**>(&threadEnv),nullptr)==JNI_OK);
        auto u=threadEnv->NewStringUTF(transport.toEncoded().constData()), verb=threadEnv->NewStringUTF("GET");
        auto r=Java_org_overte_web_EmbeddedWebView_nativeRequest(threadEnv,nullptr,handle,birth,grant,load,1,u,true,verb);
        assert(r); auto type=threadEnv->GetObjectClass(r); auto action=threadEnv->GetFieldID(type,"action","I");
        ioPassed.store(r && threadEnv->GetIntField(r,action)==1 && !threadEnv->ExceptionCheck());
        threadEnv->DeleteLocalRef(r); threadEnv->DeleteLocalRef(type); threadEnv->DeleteLocalRef(u); threadEnv->DeleteLocalRef(verb); machine->DetachCurrentThread();
    }); io.join(); assert(ioPassed.load());
    owner.revoke();
    assert(!Java_org_overte_web_EmbeddedWebView_nativeResourceCurrent(env,boundary,handle,birth,grant,load,1));
    assert(!view->generation() && !view->allowsBridgeDocument(grant,2,transport));
    control.polishItems(); control.sync(); control.render(); assert(control.grab().pixelColor(1,1).alpha()==0);
    view->setParentItem(nullptr); control.invalidate();
    response=Java_org_overte_web_EmbeddedWebView_nativeRequest(env,boundary,handle,birth,grant,load,1,transportString,true,get);
    assert(responseAction(response)==0); if(response)env->DeleteLocalRef(response);
    root.reset();
    // Real nested QML rejects forged, stale, wrong-script and unrelated-context carriers before creation.
    const auto rejectedBefore=count();
    ownerContext.setContextProperty("nativeInlineHtmlDocument",QVariantMap{{"bytes","forged"}});
    std::unique_ptr<QObject> forged(component.create(&nested)); assert(forged && !forged->findChild<NativeWebViewItem*>()->generation()); forged.reset();
    ownerContext.setContextProperty("nativeInlineHtmlDocument",QVariant::fromValue(document));
    std::unique_ptr<QObject> stale(component.create(&nested)); assert(stale && !stale->findChild<NativeWebViewItem*>()->generation()); stale.reset();
    InlineHtmlDocumentOwner nextOwner; const auto next=nextOwner.issue(&ownerContext,"inline-owner",raw,script);
    ownerContext.setContextProperty("nativeInlineHtmlDocument",QVariant::fromValue(next));
    ownerContext.setContextProperty("approvedScript",script+"#changed");
    std::unique_ptr<QObject> wrongScript(component.create(&nested)); assert(wrongScript && !wrongScript->findChild<NativeWebViewItem*>()->generation()); wrongScript.reset();
    foreignContext.setContextProperty("nativeInlineHtmlDocument",QVariant::fromValue(next));
    foreignContext.setContextProperty("nativeWebSourceIdentity","inline-owner"); foreignContext.setContextProperty("authored",raw); foreignContext.setContextProperty("approvedScript",script);
    std::unique_ptr<QObject> foreign(component.create(&foreignContext)); assert(foreign && !foreign->findChild<NativeWebViewItem*>()->generation());
    assert(count()==rejectedBefore);
    assert(!env->ExceptionCheck());
    env->DeleteLocalRef(transportString); env->DeleteLocalRef(get); env->DeleteLocalRef(head); env->DeleteLocalRef(responseType);
    puts("PASS: real nested shared/Android QML initial descriptor, exact JNI bytes/charset/HEAD, foreign-thread resource IO, inline frame-origin negatives, semantic URL, synchronous revoke/scene clear, forged/stale/foreign/script rejection");
}
