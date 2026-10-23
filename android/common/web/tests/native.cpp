// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#include "NativeWebViewItem.h"
#include <QFile>
#include <QGuiApplication>
#include <QWheelEvent>
#include <QTouchEvent>
#include <QTouchDevice>
#include <QKeyEvent>
#include <QQuickWindow>
#include <QQuickRenderControl>
#include <QJsonDocument>
#include <QJsonArray>
#include <QTemporaryDir>
#include <QQmlEngine>
#include <QQmlComponent>
#include <QQmlFileSelector>
#include <QDir>
#include <memory>
#include <limits>
#include <cassert>
#include <cstdio>
#include <jni.h>
extern "C" void Java_org_overte_web_EmbeddedWebView_nativeInputFocus(JNIEnv*, jclass, jlong, jlong, jlong, jboolean);
extern "C" void Java_org_overte_web_EmbeddedWebView_nativeInitialize(JNIEnv*, jclass);
extern "C" jlong Java_org_overte_web_EmbeddedWebView_nativeLifecycleRevision(JNIEnv*, jclass, jlong);
extern "C" jlong Java_org_overte_web_EmbeddedWebView_nativeGeneration(JNIEnv*, jclass, jlong);
extern "C" void Java_org_overte_web_EmbeddedWebView_nativeResumeRequest(JNIEnv*, jclass, jlong, jlong, jlong, jstring);
extern "C" void Java_org_overte_web_EmbeddedWebView_nativeCreated(JNIEnv*, jclass, jlong, jlong, jboolean);
#include "inline-backend-tests.h"
class Probe : public NativeWebViewItem {
public: using NativeWebViewItem::touchEvent; using NativeWebViewItem::touchUngrabEvent; using NativeWebViewItem::inputMethodQuery; using NativeWebViewItem::wheelEvent; using NativeWebViewItem::keyPressEvent; using NativeWebViewItem::inputMethodEvent;
    mutable int enabledQueries { 0 };
    QVariant inputMethodQuery(Qt::InputMethodQuery query) const override {
        if (query == Qt::ImEnabled) ++enabledQueries;
        return NativeWebViewItem::inputMethodQuery(query);
    }
};
int main(int argc, char** argv) {
    qputenv("QT_QUICK_BACKEND", "software");
    QGuiApplication app(argc, argv);
    {
        // Compare the native editor contract with a real Qt text control:
        // rendered preedit is separate from committed surrounding text.
        QQmlEngine engine;
        QQmlComponent component(&engine);
        component.setData("import QtQuick 2.15; TextInput { width:240; height:80; text:'ab' }", QUrl());
        std::unique_ptr<QObject> object(component.create());
        auto* reference = qobject_cast<QQuickItem*>(object.get()); assert(reference);
        QQuickWindow window; window.resize(240,80); window.show(); window.requestActivate();
        reference->setParentItem(window.contentItem()); reference->forceActiveFocus();
        reference->setProperty("cursorPosition",1); QCoreApplication::processEvents();
        QInputMethodEvent preedit("XY", {{QInputMethodEvent::Cursor,1,1,QVariant()}});
        QCoreApplication::sendEvent(reference,&preedit);
        assert(reference->property("text").toString()=="ab");
        assert(reference->property("preeditText").toString()=="XY");
        QInputMethodQueryEvent query(Qt::ImQueryInput | Qt::ImAbsolutePosition | Qt::ImTextBeforeCursor | Qt::ImTextAfterCursor);
        QCoreApplication::sendEvent(reference,&query);
        assert(query.value(Qt::ImSurroundingText).toString()=="ab");
        assert(query.value(Qt::ImCursorPosition).toInt()==1 && query.value(Qt::ImAnchorPosition).toInt()==1);
        assert(query.value(Qt::ImAbsolutePosition).toInt()==1);
        assert(query.value(Qt::ImTextBeforeCursor).toString()=="a" && query.value(Qt::ImTextAfterCursor).toString()=="b");
        QInputMethodEvent commit; commit.setCommitString("Z"); QCoreApplication::sendEvent(reference,&commit);
        assert(reference->property("text").toString()=="aZb" && reference->property("cursorPosition").toInt()==2);
        reference->setProperty("text","abc");
        assert(QMetaObject::invokeMethod(reference,"select",Q_ARG(int,1),Q_ARG(int,2)));
        QInputMethodEvent empty;
        QCoreApplication::sendEvent(reference,&empty);
        assert(reference->property("text").toString()=="abc" && reference->property("selectedText").toString()=="b");
        QInputMethodEvent selectionOnly(QString(),{{QInputMethodEvent::Selection,0,1,QVariant()}});
        QCoreApplication::sendEvent(reference,&selectionOnly);
        assert(reference->property("text").toString()=="abc" && reference->property("selectedText").toString()=="a");
        reference->setParentItem(nullptr);
        puts("PASS: actual Qt TextInput renders preedit separately from committed surrounding text and native cursor offsets");
    }
    // Exercise actual native frame ingestion, Qt texture painting and premultiplied BGRA.
    QQuickRenderControl control; QQuickWindow raster(&control); raster.resize(8,8); raster.setColor(Qt::transparent);
    Probe pixels; pixels.setParentItem(raster.contentItem()); pixels.setSize(QSizeF(8,8));
    pixels.acceptForeground(true); pixels.setSourceIdentity("pixel-fixture");
    pixels.setUrl("https://one.test/frame"); pixels.componentComplete();
    auto pixelGrant = pixels.generation(); pixels.acceptPage(pixelGrant,1,QUrl("https://one.test/frame"));
    const unsigned char bgra[] = {0,0,255,255, 0,128,0,128, 255,0,0,255, 255,255,255,255};
    pixels.acceptFrame(pixelGrant,1,bgra,sizeof(bgra),2,2);
    control.initialize(nullptr); control.polishItems(); control.sync(); control.render();
    QImage painted = control.grab(); assert(!painted.isNull());
    assert(painted.pixelColor(1,1).red() > 240 && painted.pixelColor(1,1).blue() < 10);
    assert(painted.pixelColor(6,1).green() > 240 && painted.pixelColor(6,1).alpha() >= 120 && painted.pixelColor(6,1).alpha() <= 136);
    assert(painted.pixelColor(1,6).blue() > 240 && painted.pixelColor(1,6).red() < 10);
    const unsigned char rejected[] = {0,0,0,255};
    pixels.acceptFrame(pixelGrant+1,1,rejected,sizeof(rejected),1,1);
    pixels.acceptFrame(pixelGrant,2,rejected,sizeof(rejected),1,1);
    control.polishItems(); control.sync(); control.render();
    assert(control.grab().pixelColor(1,1).red() > 240);
    pixels.setUrl("https://one.test/replacement");
    control.polishItems(); control.sync(); control.render();
    assert(control.grab().pixelColor(1,1).alpha() == 0);
    pixels.setParentItem(nullptr); control.invalidate();
    std::puts("PASS: actual native frame ingestion and Qt scene graph pixels preserve BGRA/row orientation/premultiplied alpha; stale source/page frames rejected");
    QQuickItem transformed; transformed.setPosition(QPointF(10, 20)); transformed.setWidth(300); transformed.setHeight(200);
    NativeWebViewItem geometry(&transformed); geometry.setPosition(QPointF(5, 48)); geometry.setWidth(100); geometry.setHeight(70);
    auto plain = geometry.sceneBounds(); assert(plain.size() == QSizeF(100, 70));
    transformed.setScale(2); auto scaled = geometry.sceneBounds(); assert(scaled.size() == QSizeF(200, 140));
    transformed.setRotation(90); auto rotated = geometry.sceneBounds(); assert(qAbs(rotated.width() - 140) < .001 && qAbs(rotated.height() - 200) < .001);
    transformed.setRotation(0); transformed.setScale(1); transformed.setClip(true);
    geometry.setPosition(QPointF(5, 48)); transformed.setWidth(80); transformed.setHeight(90);
    assert(geometry.sceneBounds().size() == QSizeF(100, 70));
    assert(geometry.sceneClipBounds() == QRectF(15, 68, 75, 42));
    transformed.setScale(2);
    assert(geometry.sceneClipBounds().size() == QSizeF(150, 84));
    transformed.setClip(false); assert(geometry.sceneClipBounds() == geometry.sceneBounds());
    transformed.setClip(true); geometry.setY(1000); assert(geometry.sceneClipBounds().isEmpty());
    Probe item; item.acceptForeground(true); item.setSourceIdentity("fixture-owned-surface");
    item.setUrl("https://one.test/document"); item.componentComplete();
    auto grant = item.generation(); assert(grant);
    item.acceptPage(grant, 1, QUrl("https://one.test/document"));
    assert(item.allowsFileChooser(grant, 1, QUrl("https://one.test/document")));
    assert(!item.allowsFileChooser(grant+1, 1, QUrl("https://one.test/document")));
    assert(!item.allowsFileChooser(grant, 2, QUrl("https://one.test/document")));
    assert(!item.allowsFileChooser(grant, 1, QUrl("https://other.test/document")));
    Probe tablet; tablet.acceptForeground(true); tablet.setSurface(NativeWebViewItem::Tablet);
    tablet.setPresentation(NativeWebViewItem::Texture); tablet.setSourceIdentity("fixture-tablet");
    tablet.setUrl("https://one.test/document"); tablet.componentComplete();
    auto tabletGrant = tablet.generation(); tablet.acceptPage(tabletGrant, 1, QUrl("https://one.test/document"));
    assert(tablet.allowsFileChooser(tabletGrant, 1, QUrl("https://one.test/document")));
    assert(!tablet.allowsFileChooser(tabletGrant, 2, QUrl("https://one.test/document")));
    assert(!tablet.allowsFileChooser(tabletGrant, 1, QUrl("https://one.test/other")));
    tablet.setVisible(false); assert(!tablet.allowsFileChooser(tabletGrant, 1, QUrl("https://one.test/document")));
    auto send = [&](quint64 generation, quint64 page, const QUrl& origin, bool main, const QByteArray& payload) {
        return item.acceptMessage(generation, page, QUrl("https://one.test/document"), origin, main, "editor", payload);
    };
    assert(!send(grant, 1, QUrl("https://foreign.test"), true, "{}"));
    assert(!send(grant, 1, QUrl("https://one.test"), false, "{}"));
    assert(!send(grant, 2, QUrl("https://one.test"), true, "{}"));
    assert(!send(grant, 1, QUrl("https://one.test"), true, QByteArray(65537, 'x')));
    assert(send(grant, 1, QUrl("https://one.test"), true,
        R"({"active":true,"text":"hello world","cursor":5,"anchor":0,"kind":"text"})"));
    QCoreApplication::processEvents();
    assert(item.inputMethodQuery(Qt::ImSurroundingText).toString() == "hello world");
    assert(item.editorFocused() && !item.editorNumeric() && !item.editorPassword());
    assert(item.inputMethodQuery(Qt::ImCurrentSelection).toString() == "hello");
    assert(send(grant, 1, QUrl("https://one.test"), true,
        R"({"active":true,"sensitive":true,"text":"must-never-be-retained","cursor":3,"anchor":0})"));
    QCoreApplication::processEvents(); assert(item.inputMethodQuery(Qt::ImSurroundingText).toString().isEmpty());
    assert(item.editorFocused() && item.editorPassword());
    assert(send(grant, 1, QUrl("https://one.test"), true,
        R"({"active":true,"sensitive":true,"text":"must-never-be-retained","length":4,"cursor":4,"anchor":4,"absoluteCursor":4})"));
    QCoreApplication::processEvents();
    assert(item.inputMethodQuery(Qt::ImSurroundingText).toString() == QString(4, QChar(0x2022)));
    assert(item.inputMethodQuery(Qt::ImCursorPosition).toInt() == 4);
    assert(item.inputMethodQuery(Qt::ImAbsolutePosition).toInt() == 4);
    assert(item.inputMethodQuery(Qt::ImCurrentSelection).toString().isEmpty());
    QJsonObject initialization; auto* transport = item.findChild<NativeWebTransport*>(); assert(transport);
    QObject::connect(transport, &NativeWebTransport::outbound, [&](const QJsonObject& message) { if (message.value("type").toInt() == 10) initialization = message; });
    auto channel = [&](const QJsonObject& object) { return item.acceptMessage(grant, 1, QUrl("https://one.test/document"), QUrl("https://one.test"), true, "channel", QJsonDocument(object).toJson(QJsonDocument::Compact)); };
    assert(channel({{"type", 3}, {"id", 0}})); QCoreApplication::processEvents();
    assert(initialization.value("data").toObject().contains("eventBridge"));
    auto* bridge = item.findChild<NativeSurfaceBridge*>(); assert(bridge);
    int received = 0; QObject::connect(&item, &NativeWebViewItem::webEventReceived, [&](const QVariant& message) { assert(message.toString() == "safe event"); ++received; });
    assert(channel({{"type", 6}, {"object", "eventBridge"}, {"method", bridge->metaObject()->indexOfMethod("emitWebEvent(QVariant)")}, {"args", QJsonArray { "safe event" }}, {"id", 1}}));
    QCoreApplication::processEvents(); assert(received == 1);
    assert(!channel({{"type", 6}, {"object", "eventBridge"}, {"method", bridge->metaObject()->indexOfMethod("deleteLater()")}, {"args", QJsonArray {}}, {"id", 2}}));
    assert(!channel({{"type", 6}, {"object", "eventBridge"}, {"method", "forwardScriptEvent"}, {"args", QJsonArray { "injected signal" }}}));
    assert(!item.runJavaScript("1 + 2")); // Missing native provider cannot report successful execution.
    assert(item.emitScriptEvent("authorized event"));
    assert(!item.emitScriptEvent(QString(65536, QChar(0))));
    assert(!channel({{"type", 9}, {"object", "eventBridgeWrapper"}, {"property", 0}, {"value", "foreign bridge"}}));
    assert(item.allowsNavigation(grant, QUrl("https://foreign.test/page"), true, "POST"));
    assert(!item.allowsNavigation(grant, QUrl("file:///private/anything"), true, "GET"));
    item.acceptPage(grant, 2, QUrl("https://foreign.test/page"));
    item.acceptState(grant, 2, QUrl("https://foreign.test/page"), false, true, false, true, 0);
    QCoreApplication::processEvents(); assert(item.errorText().isEmpty() && !item.warningText().isEmpty());
    const QUrl foreignDocument("https://foreign.test/page"), foreignOrigin("https://foreign.test");
    auto foreign = [&](quint64 generation, quint64 page, const QUrl& document, const QUrl& origin, bool main, const QString& type, const QByteArray& payload) {
        return item.acceptMessage(generation, page, document, origin, main, type, payload);
    };
    assert(item.allowsFileChooser(grant, 2, foreignDocument));
    assert(!item.allowsFileChooser(grant, 1, QUrl("https://one.test/document")));
    assert(item.allowsEditorDocument(grant, 2, foreignDocument));
    assert(!item.allowsBridgeDocument(grant, 2, foreignDocument));
    assert(!item.emitScriptEvent("foreign event") && !item.runJavaScript("foreign script"));
    const QByteArray editorState = R"({"active":true,"text":"foreign document input","cursor":7,"anchor":0,"kind":"email"})";
    assert(foreign(grant, 2, foreignDocument, foreignOrigin, true, "editor", editorState));
    QCoreApplication::processEvents();
    assert(item.editorFocused() && item.inputMethodQuery(Qt::ImSurroundingText).toString() == "foreign document input");
    assert(item.inputMethodQuery(Qt::ImCurrentSelection).toString() == "foreign");
    assert(!foreign(grant, 2, foreignDocument, foreignOrigin, true, "channel", R"({"type":3,"id":0})"));
    assert(!foreign(grant, 2, foreignDocument, QUrl("https://one.test"), true, "editor", editorState));
    assert(!foreign(grant, 2, foreignDocument, foreignOrigin, false, "editor", editorState));
    assert(!foreign(grant, 1, foreignDocument, foreignOrigin, true, "editor", editorState));
    assert(!foreign(grant, 2, QUrl("https://foreign.test/another"), foreignOrigin, true, "editor", editorState));
    assert(!foreign(grant, 2, foreignDocument, foreignOrigin, true, "editor", QByteArray(65537, 'x')));
    assert(foreign(grant, 2, foreignDocument, foreignOrigin, true, "editor", editorState));
    item.acceptPage(grant, 3, QUrl("https://third.test/page"));
    QCoreApplication::processEvents(); assert(!item.editorFocused()); // A queued old document cannot restore focus.
    const QUrl thirdDocument("https://third.test/page"), thirdOrigin("https://third.test");
    assert(foreign(grant, 3, thirdDocument, thirdOrigin, true, "editor", editorState));
    QCoreApplication::processEvents(); assert(item.editorFocused());
    item.acceptForeground(false);
    assert(!foreign(grant, 3, thirdDocument, thirdOrigin, true, "editor", editorState));
    QCoreApplication::processEvents(); assert(!item.editorFocused());
    item.acceptForeground(true); grant = item.generation();
    assert(foreign(grant, 3, thirdDocument, thirdOrigin, true, "editor", editorState));
    QCoreApplication::processEvents(); assert(item.editorFocused());
    assert(!send(grant, 1, QUrl("https://one.test"), true, "{}"));
    item.setVisible(false); assert(!item.allowsFileChooser(grant,3,thirdDocument)); assert(!item.editorFocused() && !item.editorPassword()); assert(!item.generation()); assert(!item.emitScriptEvent("hidden event"));
    assert(!foreign(grant, 3, thirdDocument, thirdOrigin, true, "editor", editorState));
    item.setVisible(true); assert(item.generation() != grant);
    assert(!send(grant, 2, QUrl("https://one.test"), true, "{}"));
    item.setSourceIdentity("replacement-source");
    assert(!item.allowsFileChooser(grant, 3, thirdDocument));
    assert(!foreign(grant, 3, thirdDocument, thirdOrigin, true, "editor", editorState));
    QTemporaryDir root, outside; assert(root.isValid() && outside.isValid());
    QFile doc(root.filePath("page.html")); assert(doc.open(QFile::WriteOnly)); doc.write("test"); doc.close();
    QFile secret(outside.filePath("private.txt")); assert(secret.open(QFile::WriteOnly)); secret.write("private"); secret.close();
    assert(QFile::link(secret.fileName(), root.filePath("escape.txt")));
    using overte::android::web::NativeResourceMapping;
    NativeResourceMapping mapping(root.path(), 77);
    auto source = QUrl::fromLocalFile(doc.fileName()); auto browser = mapping.toBrowser(source);
    assert(browser.host() == "overte-embedded.invalid"); assert(mapping.toSource(browser) == source);
    QDir(root.path()).mkdir("nested");
    QUrl alias = QUrl::fromLocalFile(root.filePath("nested/../page.html")); assert(!mapping.accepts(alias));
    assert(QFile::link(doc.fileName(), root.filePath("alias.html")));
    QUrl internalAlias = QUrl::fromLocalFile(root.filePath("alias.html"));
    assert(mapping.accepts(internalAlias)); assert(mapping.toSource(mapping.toBrowser(internalAlias)) == source);
    assert(mapping.toSource(QUrl("https://overte-embedded.invalid/78/page.html")).isEmpty());
    assert(mapping.toSource(QUrl("https://overte-embedded.invalid/77/%2e%2e/private.txt")).isEmpty());
    assert(mapping.toSource(QUrl("https://overte-embedded.invalid/77/escape.txt")).isEmpty());
    assert(!mapping.accepts(QUrl::fromLocalFile(secret.fileName())));
    if (argc > 1) { QFile script(":/qtwebchannel/qwebchannel.js"), output(argv[1]);
        assert(script.open(QFile::ReadOnly)); assert(output.open(QFile::WriteOnly)); output.write(script.readAll()); }
    if (argc > 2) {
        QQmlEngine engine; QQmlComponent component(&engine, QUrl::fromLocalFile(argv[2]));
        assert(component.isReady()); std::unique_ptr<QObject> adapter(component.create()); assert(adapter);
        adapter->setProperty("surface", "tablet"); adapter->setProperty("userAgent", "host-test-agent");
        auto views = adapter->findChildren<NativeWebViewItem*>(); assert(views.size() == 1);
        assert(views[0]->surface() == NativeWebViewItem::Tablet);
        assert(views[0]->presentation() == NativeWebViewItem::NativeOverlay);
        adapter->setProperty("presentation", "texture");
        assert(views[0]->presentation() == NativeWebViewItem::Texture);
        adapter->setProperty("presentation", "auto");
        assert(views[0]->presentation() == NativeWebViewItem::NativeOverlay);
        assert(views[0]->userAgent() == "host-test-agent");
        assert(views[0]->hasFocus());
        auto* reloadOffer = adapter->findChild<QObject*>("EmbeddedWebReloadGET"); assert(reloadOffer);
        views[0]->acceptForeground(true); views[0]->setSourceIdentity("qml-reload-owner");
        views[0]->setUrl("https://reload.test/page");
        views[0]->acceptSuspended(views[0]->lifecycleRevision(),QUrl("https://reload.test/page"),false,false,0);
        QCoreApplication::processEvents();
        assert(views[0]->reloadRequired() && reloadOffer->property("visible").toBool());
        assert(reloadOffer->metaObject()->indexOfMethod("requestReload()") >= 0);
        auto reloadRevision = views[0]->lifecycleRevision();
        assert(QMetaObject::invokeMethod(reloadOffer,"requestReload",Qt::DirectConnection));
        QCoreApplication::processEvents(); assert(views[0]->lifecycleRevision() > reloadRevision);
        std::puts("PASS: actual Android QML fallback exposes an explicit GET reload action and invokes production native reload; no browser restoration claimed");
        adapter->setProperty("surface", "world-entity");
        assert(views[0]->presentation() == NativeWebViewItem::Texture);
        assert(adapter->metaObject()->indexOfMethod("emitScriptEvent(QVariant)") >= 0);
        assert(adapter->metaObject()->indexOfMethod("goForward()") >= 0);
        engine.addImportPath(QFileInfo(QString::fromLocal8Bit(argv[2])).absoluteDir().absoluteFilePath("../.."));
        QQmlFileSelector selector(&engine); selector.setExtraSelectors({ "android" });
        QQmlComponent module(&engine);
        module.setData("import QtQuick 2.7\nimport controls 1.0 as Controls\nControls.AndroidEmbeddedWebBackend { surface: \"tablet\"; presentation: \"texture\" }", QUrl());
        if (!module.isReady()) qWarning() << module.errors();
        assert(module.isReady()); std::unique_ptr<QObject> exported(module.create()); assert(exported);
        auto* exportedView = exported->findChild<NativeWebViewItem*>(); assert(exportedView);
        assert(exportedView->surface() == NativeWebViewItem::Tablet && exportedView->presentation() == NativeWebViewItem::Texture);
    }
    if (argc > 3) {
        JavaVM* machine = nullptr; JNIEnv* env = nullptr;
        QByteArray classpath = "-Djava.class.path=" + QByteArray(argv[3]);
        JavaVMOption option; option.optionString = classpath.data();
        JavaVMInitArgs settings {}; settings.version = JNI_VERSION_1_8; settings.nOptions = 1; settings.options = &option;
        assert(JNI_CreateJavaVM(&machine, reinterpret_cast<void**>(&env), &settings) == JNI_OK);
        auto boundary = env->FindClass("org/overte/web/WebLifecycleBoundary"); assert(boundary);
        JNINativeMethod methods[] = {
            { const_cast<char*>("revision"), const_cast<char*>("(J)J"), reinterpret_cast<void*>(qEnvironmentVariableIsSet("OVERTE_TEST_OLD_ACTIVE_VISIBILITY") ? Java_org_overte_web_EmbeddedWebView_nativeGeneration : Java_org_overte_web_EmbeddedWebView_nativeLifecycleRevision) },
            { const_cast<char*>("active"), const_cast<char*>("(J)J"), reinterpret_cast<void*>(Java_org_overte_web_EmbeddedWebView_nativeGeneration) },
            { const_cast<char*>("resume"), const_cast<char*>("(JJJLjava/lang/String;)V"), reinterpret_cast<void*>(Java_org_overte_web_EmbeddedWebView_nativeResumeRequest) },
            { const_cast<char*>("created"), const_cast<char*>("(JJZ)V"), reinterpret_cast<void*>(Java_org_overte_web_EmbeddedWebView_nativeCreated) }
        };
        assert(env->RegisterNatives(boundary, methods, 4) == JNI_OK);
        Java_org_overte_web_EmbeddedWebView_nativeInitialize(env, boundary);
        {
            Probe wheel; wheel.setSize(QSizeF(100,80)); wheel.acceptForeground(true);
            wheel.setSourceIdentity("wheel-owned-source"); wheel.setUrl("https://owned.test/page"); wheel.componentComplete();
            QCoreApplication::processEvents(); const auto grant=wheel.generation(); const QUrl foreign("https://foreign.test/page");
            wheel.acceptPage(grant,2,foreign); assert(wheel.allowsEditorDocument(grant,2,foreign));
            assert(!wheel.allowsBridgeDocument(grant,2,foreign) && !wheel.runJavaScript("forbidden"));
            auto number=[&](const char* name){return env->GetStaticIntField(boundary,env->GetStaticFieldID(boundary,name,"I"));};
            auto real=[&](const char* name){return env->GetStaticFloatField(boundary,env->GetStaticFieldID(boundary,name,"F"));};
            const auto before=number("wheels"), scripts=number("evaluations");
            QWheelEvent angle(QPointF(20,30),QPointF(20,30),QPoint(),QPoint(60,120),Qt::NoButton,Qt::NoModifier,Qt::NoScrollPhase,false);
            wheel.wheelEvent(&angle); assert(angle.isAccepted() && number("wheels")==before+1);
            assert(env->GetStaticLongField(boundary,env->GetStaticFieldID(boundary,"wheelHandle","J"))
                ==env->GetStaticLongField(boundary,env->GetStaticFieldID(boundary,"handle","J")));
            assert(real("wheelX")==20 && real("wheelY")==30 && real("wheelAngleX")==60 && real("wheelAngleY")==120);
            assert(!env->GetStaticBooleanField(boundary,env->GetStaticFieldID(boundary,"wheelPixelMode","Z")));
            assert(env->GetStaticLongField(boundary,env->GetStaticFieldID(boundary,"wheelGrant","J"))==jlong(grant));
            assert(env->GetStaticLongField(boundary,env->GetStaticFieldID(boundary,"wheelPage","J"))==2);
            auto document=static_cast<jstring>(env->GetStaticObjectField(boundary,env->GetStaticFieldID(boundary,"wheelDocument","Ljava/lang/String;")));
            const auto* text=env->GetStringUTFChars(document,nullptr);assert(QByteArray(text)==foreign.toEncoded());env->ReleaseStringUTFChars(document,text);env->DeleteLocalRef(document);
            QWheelEvent pixel(QPointF(25,35),QPointF(25,35),QPoint(4,-9),QPoint(0,120),Qt::NoButton,Qt::NoModifier,Qt::ScrollUpdate,false);
            wheel.wheelEvent(&pixel); assert(pixel.isAccepted() && number("wheels")==before+2);
            assert(real("wheelPixelX")==4 && real("wheelPixelY")==-9);
            assert(env->GetStaticBooleanField(boundary,env->GetStaticFieldID(boundary,"wheelPixelMode","Z")));
            assert(number("evaluations")==scripts && !wheel.hasActiveFocus());
            wheel.acceptForeground(false);wheel.wheelEvent(&angle);assert(!angle.isAccepted() && number("wheels")==before+2);
            wheel.acceptForeground(true);QCoreApplication::processEvents();wheel.setVisible(false);wheel.wheelEvent(&pixel);
            assert(!pixel.isAccepted() && number("wheels")==before+2);
            wheel.setVisible(true);QCoreApplication::processEvents();wheel.setUrl("https://replacement.test/page");wheel.wheelEvent(&angle);
            assert(!angle.isAccepted() && number("wheels")==before+2);
            assert(!env->ExceptionCheck());
            puts("PASS: actual QWheelEvent reaches private JNI with document/grant/page/position/horizontal/pixel intent; foreign bridge remains denied and inactive input rejects");
        }
        {
            Probe touch; touch.setSize(QSizeF(100,80)); touch.acceptForeground(true);
            touch.setSourceIdentity("world-touch-source"); touch.setSurface(NativeWebViewItem::WorldEntity);
            touch.setUrl("https://owned.test/touch"); touch.componentComplete(); QCoreApplication::processEvents();
            auto number=[&](const char* name){return env->GetStaticIntField(boundary,env->GetStaticFieldID(boundary,name,"I"));};
            auto real=[&](const char* name){return env->GetStaticFloatField(boundary,env->GetStaticFieldID(boundary,name,"F"));};
            QTouchDevice device; device.setType(QTouchDevice::TouchScreen); device.setCapabilities(QTouchDevice::Position);
            auto send=[&](QEvent::Type type, Qt::TouchPointState state, QPointF position) {
                QTouchEvent::TouchPoint point(7); point.setState(state); point.setPos(position);
                QTouchEvent event(type,&device,Qt::NoModifier,state,{point}); event.ignore();
                touch.touchEvent(&event); assert(event.isAccepted());
            };
            const auto hoverBefore=number("pointers");
            QTouchEvent::TouchPoint hovering(7); hovering.setState(Qt::TouchPointStationary); hovering.setPos({20,30});
            QTouchEvent hoverBegin(QEvent::TouchBegin,&device,Qt::NoModifier,Qt::TouchPointStationary,{hovering});
            hoverBegin.ignore(); touch.touchEvent(&hoverBegin);
            assert(!hoverBegin.isAccepted() && number("pointers")==hoverBefore);
            send(QEvent::TouchUpdate,Qt::TouchPointPressed,{20,30});
            assert(number("pointers")==hoverBefore+1 && number("pointerAction")==0);
            send(QEvent::TouchUpdate,Qt::TouchPointReleased,{20,30});
            send(QEvent::TouchUpdate,Qt::TouchPointPressed,{25,35});
            assert(number("pointers")==hoverBefore+3 && number("pointerAction")==0);
            send(QEvent::TouchUpdate,Qt::TouchPointReleased,{25,35});
            const auto before=number("pointers");
            send(QEvent::TouchBegin,Qt::TouchPointPressed,{20,30});
            assert(number("pointers")==before+1 && number("pointerAction")==0 && real("pointerX")==20 && real("pointerY")==30);
            send(QEvent::TouchUpdate,Qt::TouchPointMoved,{25,35});
            assert(number("pointers")==before+2 && number("pointerAction")==2);
            send(QEvent::TouchEnd,Qt::TouchPointReleased,{25,35});
            assert(number("pointers")==before+3 && number("pointerAction")==1);
            send(QEvent::TouchBegin,Qt::TouchPointPressed,{10,15});
            QTouchEvent canceled(QEvent::TouchCancel,&device);touch.touchEvent(&canceled);
            assert(canceled.isAccepted() && number("pointers")==before+5 && number("pointerAction")==3);
            send(QEvent::TouchBegin,Qt::TouchPointPressed,{10,15});touch.touchUngrabEvent();
            assert(number("pointers")==before+7 && number("pointerAction")==3);
            QTouchEvent orphan(QEvent::TouchUpdate,&device);touch.touchEvent(&orphan);
            assert(number("pointers")==before+7 && !env->ExceptionCheck());
            // Entity surfaces deliver to a real QQuickWindow, which chooses the
            // item and transforms the point before invoking its touch handler.
            QQuickWindow touchWindow; touchWindow.resize(100,80);
            touch.setParentItem(touchWindow.contentItem()); touchWindow.show();
            QCoreApplication::processEvents();
            auto windowSend=[&](QEvent::Type type, Qt::TouchPointState state, QPointF position) {
                QTouchEvent::TouchPoint point(1); point.setState(state);
                point.setPos(position); point.setScreenPos(position);
                QTouchEvent event(type,&device,Qt::NoModifier,state,{point});
                event.setWindow(&touchWindow); event.setTarget(touchWindow.contentItem());
                event.ignore(); QCoreApplication::sendEvent(&touchWindow,&event);
                QCoreApplication::processEvents();
            };
            const auto windowBefore=number("pointers");
            windowSend(QEvent::TouchBegin,Qt::TouchPointPressed,{20,30});
            assert(number("pointers")==windowBefore+1 && number("pointerAction")==0
                && real("pointerX")==20 && real("pointerY")==30);
            windowSend(QEvent::TouchEnd,Qt::TouchPointReleased,{20,30});
            assert(number("pointers")==windowBefore+2 && number("pointerAction")==1);
            const auto hoverWindowBefore=number("pointers");
            windowSend(QEvent::TouchBegin,Qt::TouchPointStationary,{20,30});
            assert(number("pointers")==hoverWindowBefore);
            windowSend(QEvent::TouchUpdate,Qt::TouchPointPressed,{20,30});
            assert(number("pointers")==hoverWindowBefore+1 && number("pointerAction")==0);
            windowSend(QEvent::TouchUpdate,Qt::TouchPointReleased,{20,30});
            windowSend(QEvent::TouchUpdate,Qt::TouchPointPressed,{25,35});
            assert(number("pointers")==hoverWindowBefore+3 && number("pointerAction")==0);
            windowSend(QEvent::TouchUpdate,Qt::TouchPointReleased,{25,35});
            touch.setParentItem(nullptr); touchWindow.hide();
            // The Java texture backend clamps the requested scene size. Its
            // input coordinates must not be clamped again from a captured frame.
            touch.setSize(QSizeF(4000,3000));
            touch.acceptPage(touch.generation(),1,QUrl("https://owned.test/touch"));
            QByteArray clampedPixels(2048*1536*4, char(255));
            touch.acceptFrame(touch.generation(),1,
                reinterpret_cast<const unsigned char*>(clampedPixels.constData()),clampedPixels.size(),2048,1536);
            send(QEvent::TouchBegin,Qt::TouchPointPressed,{2000,1500});
            assert(real("pointerX")==2000 && real("pointerY")==1500);
            send(QEvent::TouchEnd,Qt::TouchPointReleased,{2000,1500});
            QQuickItem scaledParent; scaledParent.setScale(2);
            touch.setParentItem(&scaledParent);
            send(QEvent::TouchBegin,Qt::TouchPointPressed,{500,400});
            assert(real("pointerX")==1000 && real("pointerY")==800);
            send(QEvent::TouchEnd,Qt::TouchPointReleased,{500,400});
            touch.setParentItem(nullptr);
            puts("PASS: actual Qt touch press/move/release/cancel/ungrab reaches private pointer JNI; orphan input cannot leave a pressed pointer");
        }
        {
            QQuickWindow window; window.resize(240,120); window.show(); window.requestActivate();
            Probe cursor; cursor.setParentItem(window.contentItem()); cursor.setSize(QSizeF(200,100));
            cursor.acceptForeground(true); cursor.setSourceIdentity("cursor-owned-source");
            const QUrl document("https://cursor.test/page"); cursor.setUrl(document.toString()); cursor.componentComplete();
            cursor.forceActiveFocus(); QCoreApplication::processEvents(); assert(cursor.hasActiveFocus());
            const auto grant=cursor.generation(); cursor.acceptPage(grant,1,document);
            QImage frame(100,50,QImage::Format_ARGB32_Premultiplied); frame.fill(Qt::white);
            cursor.acceptFrame(grant,1,frame.constBits(),frame.sizeInBytes(),frame.width(),frame.height());
            const QByteArray state=R"({"active":true,"text":"abcdef","cursor":5,"anchor":1,"kind":"text",
                "x":10,"y":5,"width":60,"height":20,"caret":{"x":20,"y":6,"width":1,"height":12},
                "anchorCaret":{"x":30,"y":7,"width":1,"height":12}})";
            assert(cursor.acceptMessage(grant,1,document,QUrl("https://cursor.test"),true,"editor",state));
            QCoreApplication::processEvents();
            assert(cursor.inputMethodQuery(Qt::ImCursorRectangle).toRectF()==QRectF(40,12,2,24));
            assert(cursor.inputMethodQuery(Qt::ImAnchorRectangle).toRectF()==QRectF(60,14,2,24));
            for (const auto* kind : {"textarea", "contenteditable"}) {
                auto multiline = QJsonDocument::fromJson(state).object();
                multiline["kind"] = QString::fromLatin1(kind);
                assert(cursor.acceptMessage(grant,1,document,QUrl("https://cursor.test"),true,"editor",
                    QJsonDocument(multiline).toJson(QJsonDocument::Compact)));
                QCoreApplication::processEvents();
                assert(cursor.inputMethodQuery(Qt::ImHints).toInt() & Qt::ImhMultiLine);
            }
            assert(cursor.acceptMessage(grant,1,document,QUrl("https://cursor.test"),true,"editor",state));
            QCoreApplication::processEvents();
            assert(!(cursor.inputMethodQuery(Qt::ImHints).toInt() & Qt::ImhMultiLine));
            const auto count=[&]{return env->GetStaticIntField(boundary,env->GetStaticFieldID(boundary,"edits","I"));};
            const auto before=count();
            bool accepted = false;
            assert(QMetaObject::invokeMethod(&cursor,"moveInputCursorToPoint",Qt::DirectConnection,
                Q_RETURN_ARG(bool,accepted),Q_ARG(QPointF,QPointF(50,30)),Q_ARG(int,1)) && accepted && count()==before+1);
            auto encoded=static_cast<jstring>(env->GetStaticObjectField(boundary,env->GetStaticFieldID(boundary,"lastEdit","Ljava/lang/String;")));
            const auto* bytes=env->GetStringUTFChars(encoded,nullptr);
            const auto command=QJsonDocument::fromJson(QByteArray(bytes)).object();
            env->ReleaseStringUTFChars(encoded,bytes);env->DeleteLocalRef(encoded);
            assert(command.value("action")=="point" && command.value("x").toDouble()==25 && command.value("y").toDouble()==15
                && command.value("handle").toInt()==1);
            assert(cursor.inputMethodQuery(Qt::ImCursorPosition).toInt()==5); // Await actual browser acknowledgement.
            assert(!cursor.moveInputCursorToPoint(QPointF(-1,0),1));
            assert(!cursor.moveInputCursorToPoint(QPointF(std::numeric_limits<double>::quiet_NaN(),5),1));
            assert(count()==before+1);
            for (int handle : {2,3}) {
                assert(cursor.moveInputCursorToPoint(QPointF(50,30),handle));
                auto value=static_cast<jstring>(env->GetStaticObjectField(boundary,env->GetStaticFieldID(boundary,"lastEdit","Ljava/lang/String;")));
                const auto* text=env->GetStringUTFChars(value,nullptr);
                assert(QJsonDocument::fromJson(QByteArray(text)).object().value("handle").toInt()==handle);
                env->ReleaseStringUTFChars(value,text);env->DeleteLocalRef(value);
            }
            assert(!cursor.moveInputCursorToPoint(QPointF(50,30),0));
            assert(!cursor.moveInputCursorToPoint(QPointF(50,30),4));
            assert(count()==before+3);
            cursor.setEnabled(false);assert(!cursor.moveInputCursorToPoint(QPointF(50,30),1));cursor.setEnabled(true);
            cursor.setVisible(false);assert(!cursor.moveInputCursorToPoint(QPointF(50,30),1));
            assert(count()==before+3 && !env->ExceptionCheck());
            cursor.setParentItem(nullptr);
            puts("PASS: real Qt/JNI cursor point converts to CSS, keeps actual caret/anchor rectangles and rejects invalid/inactive input without guessing an index");
        }
        {
            QQuickWindow window; window.resize(240,120); window.show(); window.requestActivate();
            Probe input; input.setParentItem(window.contentItem()); input.setSize(QSizeF(240,120));
            input.acceptForeground(true); input.setSourceIdentity("synchronous-query-source");
            const QUrl document("https://input.test/page");input.setUrl(document.toString());input.componentComplete();
            input.forceActiveFocus();QCoreApplication::processEvents();assert(input.hasActiveFocus());
            const auto grant=input.generation();input.acceptPage(grant,1,document);
            assert(input.acceptMessage(grant,1,document,QUrl("https://input.test"),true,"editor",
                R"({"active":true,"text":"ab","cursor":1,"anchor":1,"absoluteCursor":1,"kind":"textarea","editor":"1","sequence":0})"));
            QCoreApplication::processEvents();
            QInputMethodEvent commit;commit.setCommitString("Z");input.inputMethodEvent(&commit);assert(commit.isAccepted());
            // Qt's Android input context queries again before a WebView callback can run.
            assert(input.inputMethodQuery(Qt::ImSurroundingText).toString()=="aZb" && "Accepted native commit must be visible to immediate Qt queries before the browser acknowledgement");
            assert(input.inputMethodQuery(Qt::ImCursorPosition).toInt()==2);
            assert(input.inputMethodQuery(Qt::ImTextBeforeCursor).toString()=="aZ");
            assert(input.inputMethodQuery(Qt::ImTextAfterCursor).toString()=="b");
            auto packet = [&] {
                auto value=static_cast<jstring>(env->GetStaticObjectField(boundary,env->GetStaticFieldID(boundary,"lastEdit","Ljava/lang/String;")));
                const auto* chars=env->GetStringChars(value,nullptr);
                const auto object=QJsonDocument::fromJson(QString::fromUtf16(reinterpret_cast<const ushort*>(chars),env->GetStringLength(value)).toUtf8()).object();
                env->ReleaseStringChars(value,chars);env->DeleteLocalRef(value);return object;
            };
            auto acknowledge = [&](const QString& text,int cursor,int anchor,const QString& owner,double sequence,bool sensitive=false,int absolute=-1) {
                const QJsonObject state{{"active",true},{"editor",owner},{"sequence",sequence},{"kind",sensitive?"password":"textarea"},
                    {"text",sensitive?QString():text},{"length",text.size()},{"sensitive",sensitive},{"cursor",cursor},{"anchor",anchor},
                    {"absoluteCursor",absolute<0?cursor:absolute}};
                assert(input.acceptMessage(grant,1,document,QUrl("https://input.test"),true,"editor",QJsonDocument(state).toJson(QJsonDocument::Compact)));
                QCoreApplication::processEvents();
            };
            const double firstSequence=packet().value("sequence").toDouble();assert(firstSequence>0 && packet().value("editor")=="1");
            commit.setCommitString("W");input.inputMethodEvent(&commit);const double secondSequence=packet().value("sequence").toDouble();
            assert(secondSequence>firstSequence && input.inputMethodQuery(Qt::ImSurroundingText).toString()=="aZWb");
            acknowledge("aZb",2,2,"1",firstSequence);
            assert(input.inputMethodQuery(Qt::ImSurroundingText).toString()=="aZWb" && input.inputMethodQuery(Qt::ImCursorPosition).toInt()==3);
            acknowledge("ab",1,1,"1",0);
            assert(input.inputMethodQuery(Qt::ImSurroundingText).toString()=="aZWb");
            acknowledge("PAGE!",5,5,"1",secondSequence); // A page formatter is authoritative.
            assert(input.inputMethodQuery(Qt::ImSurroundingText).toString()=="PAGE!");
            commit.setCommitString("!");input.inputMethodEvent(&commit);const double oldOwnerSequence=packet().value("sequence").toDouble();
            acknowledge("other",5,5,"2",0);acknowledge("PAGE!!",6,6,"1",oldOwnerSequence);
            assert(input.inputMethodQuery(Qt::ImSurroundingText).toString()=="other");
            acknowledge("abc",2,1,"3",0);
            commit.setCommitString(QString::fromUtf8("漢😀"));input.inputMethodEvent(&commit);
            assert(input.inputMethodQuery(Qt::ImSurroundingText).toString()==QString::fromUtf8("a漢😀c"));
            assert(input.inputMethodQuery(Qt::ImCursorPosition).toInt()==4);
            QKeyEvent backspace(QEvent::KeyPress,Qt::Key_Backspace,Qt::NoModifier);input.keyPressEvent(&backspace);
            assert(input.inputMethodQuery(Qt::ImSurroundingText).toString()==QString::fromUtf8("a漢c"));
            assert(input.inputMethodQuery(Qt::ImCursorPosition).toInt()==2);
            acknowledge("ab",1,1,"4",0,true);
            commit.setCommitString(QString::fromUtf8("secret😀"));input.inputMethodEvent(&commit);
            assert(packet().value("commit").toString()==QString::fromUtf8("secret😀")); // Only the outgoing edit carries typed input.
            assert(input.inputMethodQuery(Qt::ImSurroundingText).toString()==QString(10,QChar(0x2022)));
            acknowledge("ab",1,1,"4",0,true); // Replay retains lengths, never password characters.
            assert(input.inputMethodQuery(Qt::ImSurroundingText).toString()==QString(10,QChar(0x2022)));
            acknowledge("ab",1,1,"5",0);
            QInputMethodEvent preedit("XY",{{QInputMethodEvent::Cursor,1,1,QVariant()}});input.inputMethodEvent(&preedit);
            assert(input.inputMethodQuery(Qt::ImSurroundingText).toString()=="ab" && input.inputMethodQuery(Qt::ImCursorPosition).toInt()==1);
            commit.setCommitString("Z");input.inputMethodEvent(&commit);
            assert(input.inputMethodQuery(Qt::ImSurroundingText).toString()=="aZb" && input.inputMethodQuery(Qt::ImCursorPosition).toInt()==2);
            acknowledge("ab",1,1,"6",0,false,10001);commit.setCommitString("Z");input.inputMethodEvent(&commit);
            assert(input.inputMethodQuery(Qt::ImAbsolutePosition).toInt()==10002);
            QInputMethodEvent selected(QString(),{{QInputMethodEvent::Selection,0,2,QVariant()}});input.inputMethodEvent(&selected);
            assert(input.inputMethodQuery(Qt::ImCurrentSelection).toString()=="aZ");
            acknowledge("a",1,1,"7",0);commit.setCommitString(QString(16384,'x'));input.inputMethodEvent(&commit);
            assert(input.inputMethodQuery(Qt::ImAbsolutePosition).toInt()==16385 && input.inputMethodQuery(Qt::ImSurroundingText).toString().size()<=16384);
            acknowledge("",0,0,"8",0);commit.setCommitString("a");input.inputMethodEvent(&commit);
            const double canceledSequence=packet().value("sequence").toDouble();commit.setCommitString("b");input.inputMethodEvent(&commit);
            const double followingSequence=packet().value("sequence").toDouble();
            assert(input.inputMethodQuery(Qt::ImSurroundingText).toString()=="ab");
            acknowledge("",0,0,"8",canceledSequence); // The page canceled the first edit; retain the later intent.
            assert(input.inputMethodQuery(Qt::ImSurroundingText).toString()=="b" && input.inputMethodQuery(Qt::ImCursorPosition).toInt()==1);
            acknowledge("b",1,1,"8",followingSequence);assert(input.inputMethodQuery(Qt::ImSurroundingText).toString()=="b");
            acknowledge("",0,0,"9",0);commit.setCommitString("now-private");input.inputMethodEvent(&commit);
            acknowledge("",0,0,"9",0,true); // A page can make the same field sensitive while input is pending.
            assert(input.inputMethodQuery(Qt::ImSurroundingText).toString()==QString(11,QChar(0x2022)));
            acknowledge("abc",2,1,"10",0);
            QInputMethodEvent empty;
            input.inputMethodEvent(&empty);
            assert(empty.isAccepted());
            assert(input.inputMethodQuery(Qt::ImSurroundingText).toString()=="abc" && "An empty IME update must preserve selected text, as real Qt TextInput does");
            assert(input.inputMethodQuery(Qt::ImCurrentSelection).toString()=="b");
            QInputMethodEvent selectionOnly(QString(),{{QInputMethodEvent::Selection,0,1,QVariant()}});
            input.inputMethodEvent(&selectionOnly);
            assert(selectionOnly.isAccepted() && input.inputMethodQuery(Qt::ImSurroundingText).toString()=="abc");
            assert(input.inputMethodQuery(Qt::ImCurrentSelection).toString()=="a");
            acknowledge("ab",1,1,"11",0);
            QInputMethodEvent pendingPreedit("XY",{}); input.inputMethodEvent(&pendingPreedit);
            commit.setCommitString("Z"); input.inputMethodEvent(&commit);
            const double rejectedCommitSequence=packet().value("sequence").toDouble();
            QInputMethodEvent finishPendingComposition; input.inputMethodEvent(&finishPendingComposition);
            // The page cancels the commit, so its old preedit still exists.
            // The later empty update must remain queued to finish that preedit.
            const QJsonObject canceledComposition{{"active",true},{"editor","11"},{"sequence",rejectedCommitSequence},
                {"kind","textarea"},{"text","ab"},{"cursor",1},{"anchor",1},{"absoluteCursor",1},{"composing",true}};
            assert(input.acceptMessage(grant,1,document,QUrl("https://input.test"),true,"editor",
                QJsonDocument(canceledComposition).toJson(QJsonDocument::Compact)));
            QCoreApplication::processEvents();
            QKeyEvent followingNewline(QEvent::KeyPress,Qt::Key_Return,Qt::NoModifier);
            input.keyPressEvent(&followingNewline);
            assert(input.inputMethodQuery(Qt::ImSurroundingText).toString()=="a\nb" && "Finishing a pending composition must survive page cancellation of an earlier commit");
            input.acceptForeground(false);QCoreApplication::processEvents();
            assert(!input.editorFocused() && input.inputMethodQuery(Qt::ImSurroundingText).toString().isEmpty());
            input.setParentItem(nullptr);
            puts("PASS: actual accepted Qt/JNI commit updates immediate surrounding/cursor queries while browser delivery is delayed");
        }
        Probe wire; wire.setSize(QSizeF(100,100)); wire.acceptForeground(true);
        wire.setSourceIdentity("wire-owned-source"); wire.setUrl("https://wire.test/page"); wire.componentComplete();
        QCoreApplication::processEvents();
        assert(!env->ExceptionCheck());
        auto field = [&](const char* name) { return env->GetStaticLongField(boundary, env->GetStaticFieldID(boundary,name,"J")); };
        const auto handle = field("handle"); const auto before = wire.generation(); assert(handle > 0 && before > 0);
        const QUrl wireDocument("https://wire.test/page");
        const auto birth = field("creationRevision");
        wire.acceptPage(before,1,wireDocument); QCoreApplication::processEvents();
        const QByteArray inputState = R"({"active":true,"text":"typed","cursor":5,"anchor":5})";
        assert(wire.acceptMessage(before,1,wireDocument,QUrl("https://wire.test"),true,"editor",inputState));
        Java_org_overte_web_EmbeddedWebView_nativeInputFocus(env,boundary,handle,birth,wire.lifecycleRevision(),false);
        QCoreApplication::processEvents(); assert(!wire.editorFocused());
        assert(wire.generation() == before && wire.allowsEditorDocument(before,1,wireDocument));
        assert(!wire.acceptMessage(before,1,wireDocument,QUrl("https://wire.test"),true,"editor",inputState));
        Java_org_overte_web_EmbeddedWebView_nativeInputFocus(env,boundary,handle,birth,wire.lifecycleRevision(),true);
        assert(wire.acceptMessage(before,1,wireDocument,QUrl("https://wire.test"),true,"editor",inputState));
        Java_org_overte_web_EmbeddedWebView_nativeInputFocus(env,boundary,handle,birth,wire.lifecycleRevision(),false);
        Java_org_overte_web_EmbeddedWebView_nativeInputFocus(env,boundary,handle,birth,wire.lifecycleRevision(),true);
        QCoreApplication::processEvents(); assert(!wire.editorFocused()); // A queued old focus state cannot survive lose/regain.
        assert(wire.acceptMessage(before,1,wireDocument,QUrl("https://wire.test"),true,"editor",inputState));
        Java_org_overte_web_EmbeddedWebView_nativeInputFocus(env,boundary,handle,birth+1,wire.lifecycleRevision(),false);
        QCoreApplication::processEvents(); assert(wire.editorFocused()); // A stale instance cannot revoke current input.
        std::puts("PASS: actual Qt/JNI focus-only revocation rejects queued old editors without changing active document/bridge generation");
        const auto hiddenBefore=env->GetStaticIntField(boundary,env->GetStaticFieldID(boundary,"hidden","I"));
        wire.setVisible(false); assert(!wire.generation());
        assert(!env->ExceptionCheck());
        assert(field("hiddenRevision") == jlong(wire.lifecycleRevision()) && field("hiddenRevision") != jlong(before));
        assert(field("hiddenActive") == 0);
        assert(env->GetStaticIntField(boundary,env->GetStaticFieldID(boundary,"hidden","I")) == hiddenBefore+1);
        wire.setVisible(true); assert(wire.generation() > before);
        wire.acceptSuspended(wire.lifecycleRevision(),QUrl("https://wire.test/page"),true,false,field("creationRevision"));
        QCoreApplication::processEvents(); assert(wire.reloadRequired() && !wire.warningText().isEmpty());
        int count = env->GetStaticIntField(boundary,env->GetStaticFieldID(boundary,"creates","I"));
        wire.setVisible(false); wire.setVisible(true); QCoreApplication::processEvents();
        assert(env->GetStaticIntField(boundary,env->GetStaticFieldID(boundary,"creates","I")) == count);
        wire.requestResume(wire.lifecycleRevision()-1,QUrl("https://wire.test/reloaded"),field("creationRevision"));
        QCoreApplication::processEvents(); assert(wire.reloadRequired());
        wire.reload(); QCoreApplication::processEvents(); QCoreApplication::processEvents();
        assert(!wire.reloadRequired());
        assert(env->GetStaticIntField(boundary,env->GetStaticFieldID(boundary,"creates","I")) == count+1);
        auto loaded = static_cast<jstring>(env->GetStaticObjectField(boundary,env->GetStaticFieldID(boundary,"loadedUrl","Ljava/lang/String;")));
        const char* url = env->GetStringUTFChars(loaded,nullptr); assert(QByteArray(url) == "https://wire.test/page");
        env->ReleaseStringUTFChars(loaded,url); env->DeleteLocalRef(loaded);
        wire.acceptForeground(false); assert(!wire.generation() && wire.lifecycleRevision() > 0);
        auto delayed = env->GetStaticFieldID(boundary,"delayCreated","Z");
        env->SetStaticBooleanField(boundary,delayed,true);
        Probe pending; pending.setSize(QSizeF(100,100)); pending.acceptForeground(true);
        pending.setSourceIdentity("delayed-source"); pending.setUrl("https://wire.test/old"); pending.componentComplete();
        const auto oldHandle = field("handle"); const auto oldRevision = field("creationRevision");
        pending.setUrl("https://wire.test/new");
        env->SetStaticBooleanField(boundary,delayed,false);
        Java_org_overte_web_EmbeddedWebView_nativeCreated(env,boundary,oldHandle,oldRevision,true);
        QCoreApplication::processEvents(); QCoreApplication::processEvents();
        loaded = static_cast<jstring>(env->GetStaticObjectField(boundary,env->GetStaticFieldID(boundary,"loadedUrl","Ljava/lang/String;")));
        url = env->GetStringUTFChars(loaded,nullptr); assert(QByteArray(url) == "https://wire.test/new");
        env->ReleaseStringUTFChars(loaded,url); env->DeleteLocalRef(loaded);
        const auto freshRevision = pending.lifecycleRevision(); assert(freshRevision > oldRevision);
        Java_org_overte_web_EmbeddedWebView_nativeCreated(env,boundary,oldHandle,oldRevision,false);
        QCoreApplication::processEvents(); assert(pending.lifecycleRevision() == freshRevision && !env->ExceptionCheck());
        std::puts("PASS: actual Qt hide event crosses JVM/JNI into production lifecycle dispatcher after active grant becomes0; Android WebView/Looper represented, not DOM/audio");
        {
            QQuickWindow window; window.resize(100,80); window.show(); window.requestActivate();
            Probe key; key.setParentItem(window.contentItem()); key.setSize(QSizeF(100,80)); key.acceptForeground(true);
            key.setSourceIdentity("key-owned-source"); key.setUrl("https://owned.test/key"); key.componentComplete();
            QCoreApplication::processEvents(); const auto grant=key.generation(); const QUrl document("https://foreign.test/key");
            key.acceptPage(grant,1,document); key.forceActiveFocus(); QCoreApplication::processEvents(); assert(key.hasActiveFocus());
            assert(QGuiApplication::focusObject() == &key && !key.editorFocused());
            key.enabledQueries = 0;
            assert(key.acceptMessage(grant,1,document,QUrl("https://foreign.test"),true,"editor",
                R"({"active":true,"text":"typed","cursor":5,"anchor":5,"kind":"text"})"));
            QCoreApplication::processEvents(); assert(key.editorFocused() && !key.allowsBridgeDocument(grant,1,document));
            assert(key.enabledQueries > 0 && "First asynchronous DOM focus must refresh Qt input-method acceptance");
            auto count=[&]{return env->GetStaticIntField(boundary,env->GetStaticFieldID(boundary,"edits","I"));};
            auto command=[&]{auto value=static_cast<jstring>(env->GetStaticObjectField(boundary,env->GetStaticFieldID(boundary,"lastEdit","Ljava/lang/String;")));
                const auto* bytes=env->GetStringUTFChars(value,nullptr);auto object=QJsonDocument::fromJson(bytes).object();
                env->ReleaseStringUTFChars(value,bytes);env->DeleteLocalRef(value);return object;};
            const auto before=count();
            QKeyEvent enter(QEvent::KeyPress,Qt::Key_Enter,Qt::NoModifier,QString());key.keyPressEvent(&enter);
            assert(enter.isAccepted() && count()==before+1 && command().value("action")=="enter" && !command().value("shift").toBool());
            QKeyEvent shifted(QEvent::KeyPress,Qt::Key_Return,Qt::ShiftModifier,"\r");key.keyPressEvent(&shifted);
            assert(shifted.isAccepted() && count()==before+2 && command().value("action")=="enter" && command().value("shift").toBool());
            for(auto modifier:{Qt::ControlModifier,Qt::AltModifier,Qt::MetaModifier}) {
                QKeyEvent modified(QEvent::KeyPress,Qt::Key_Return,modifier,"\r");key.keyPressEvent(&modified);assert(!modified.isAccepted() && count()==before+2);
            }
            key.enabledQueries = 0;
            assert(key.acceptMessage(grant,1,document,QUrl("https://foreign.test"),true,"editor", R"({"active":false})"));
            QCoreApplication::processEvents();
            assert(!key.editorFocused() && key.enabledQueries > 0 && "DOM blur must refresh Qt input-method acceptance");
            key.acceptForeground(false);QCoreApplication::processEvents();key.keyPressEvent(&enter);
            assert(!enter.isAccepted() && count()==before+2 && !env->ExceptionCheck());
            puts("PASS: actual foreign-page Qt Return/keypad Enter reaches private edit JNI as enter+shift, including empty text; modifiers and inactive input reject");
        }
        runInlineBackendTests(env,boundary,QString::fromLocal8Bit(argv[2]));
    }
    return 0;
}
