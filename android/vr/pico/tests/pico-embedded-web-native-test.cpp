// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#include "NativeWebViewItem.h"
#include "InlineHtmlDocument.h"
#include <QGuiApplication>
#include <QQuickWindow>
#include <QQmlEngine>
#include <QQmlContext>
#include <QQmlComponent>
#include <QQmlFileSelector>
#include <QPointer>
#include <QJsonDocument>
#include <QMouseEvent>
#include <QHoverEvent>
#include <QEventLoop>
#include <QTimer>
#include <QQuickItemGrabResult>
#include <cassert>
#include <memory>
#include <cstdio>

// Existing legacy JNI creation is tested separately. This boundary lets the
// real legacy Canvas/QML participate without loading an Android VM on the host.
class LegacyBoundary : public QQuickItem {
    Q_OBJECT
    Q_PROPERTY(QString url MEMBER url)
    Q_PROPERTY(QString scriptUrl MEMBER scriptUrl)
    Q_PROPERTY(QString userAgent MEMBER userAgent)
    Q_PROPERTY(bool useBackground MEMBER useBackground)
    Q_PROPERTY(QString frameSource READ frameSource)
    Q_PROPERTY(bool rendering READ rendering NOTIFY renderingChanged)
public:
    QString url, scriptUrl, userAgent;
    bool useBackground = true;
    QString frameSource() const { return {}; }
    bool rendering() const { return false; }
signals:
    void renderingChanged();
};
class BridgeBoundary : public QObject {
    Q_OBJECT
public:
    QStringList messages;
    Q_INVOKABLE void emitWebEvent(const QVariant& value) { messages << value.toString(); }
};
class KeyboardBoundary : public QObject {
    Q_OBJECT
    Q_PROPERTY(bool use3DKeyboard MEMBER use3DKeyboard)
    Q_PROPERTY(bool raised MEMBER raised)
    Q_PROPERTY(bool password MEMBER password)
public:
    bool use3DKeyboard = true, raised = false, password = false;
};
int main(int argc, char** argv) {
    qInstallMessageHandler([](QtMsgType, const QMessageLogContext&, const QString& message) {
        std::fprintf(stderr, "%s\n", qPrintable(message));
    });
    QGuiApplication app(argc, argv);
    qmlRegisterType<LegacyBoundary>("Overte.Pico", 1, 0, "PicoWebView");
    qmlRegisterModule("TabletScriptingInterface", 1, 0);
    qmlRegisterModule("Hifi", 1, 0);
    QQmlEngine engine;
    QQmlFileSelector selector(&engine);
    selector.setExtraSelectors({ "android_picoInterface", "android" });
    engine.addImportPath(argv[1]);
    BridgeBoundary bridge;
    KeyboardBoundary keyboard;
    engine.rootContext()->setContextProperty("eventBridge", &bridge);
    engine.rootContext()->setContextProperty("KeyboardScriptingInterface", &keyboard);
    QQuickWindow window;
    window.setWidth(640); window.setHeight(480); window.show();
    auto create = [&](const QString& file, QQmlContext* context = nullptr) {
        QQmlComponent component(&engine, QUrl::fromLocalFile(QString(argv[1]) + file));
        if (!component.isReady()) qFatal("%s", qPrintable(component.errorString()));
        auto* object = component.create(context ? context : engine.rootContext());
        if (!object) qFatal("%s", qPrintable(component.errorString()));
        return object;
    };
    std::unique_ptr<QObject> adapter(create("/controls/EmbeddedWebBackend.qml"));
    auto* view = adapter->findChild<NativeWebViewItem*>(); assert(view);
    auto* adapterItem = qobject_cast<QQuickItem*>(adapter.get());
    adapterItem->setParentItem(window.contentItem()); adapterItem->setWidth(640); adapterItem->setHeight(480);
    adapter->setProperty("surface", "tablet");
    assert(view->surface() == NativeWebViewItem::Tablet);
    assert(view->presentation() == NativeWebViewItem::Texture);
    adapter->setProperty("sourceIdentity", "pico-owned-tablet");
    view->acceptForeground(true);
    adapter->setProperty("url", "https://pico.test/form");
    auto grant = view->generation(); assert(grant);
    view->acceptPage(grant, 1, QUrl("https://pico.test/form"));
    assert(view->allowsFileChooser(grant, 1, QUrl("https://pico.test/form")));
    assert(!view->allowsFileChooser(grant, 2, QUrl("https://pico.test/form")));
    assert(!view->allowsFileChooser(grant, 1, QUrl("https://foreign.test/form")));
    view->forceActiveFocus();
    auto editor = [&](const QByteArray& value) {
        assert(view->acceptMessage(grant, 1, QUrl("https://pico.test/form"), QUrl("https://pico.test"), true, "editor", value));
        QCoreApplication::processEvents();
    };
    editor(R"({"active":true,"kind":"number","sensitive":true,"cursor":0,"anchor":0})");
    assert(bridge.messages.last() == "_RAISE_KEYBOARD_NUMERIC_PASSWORD");
    assert(adapter->property("editorFocused").toBool());
    assert(adapter->property("editorNumeric").toBool());
    assert(adapter->property("editorPassword").toBool());
    assert(view->width() == 640 && view->height() == 480);
    assert(view->acceptHoverEvents());
    for (auto type : { QEvent::HoverEnter, QEvent::HoverMove, QEvent::HoverLeave }) {
        QHoverEvent event(type, QPointF(42, 60), QPointF(40, 58));
        QCoreApplication::sendEvent(view, &event); assert(event.isAccepted());
    }
    auto pointer = [&](QEvent::Type type, Qt::MouseButton button, Qt::MouseButtons buttons, bool accepted) {
        QMouseEvent event(type, QPointF(42, 60), button, buttons, Qt::NoModifier);
        QCoreApplication::sendEvent(view, &event); assert(event.isAccepted() == accepted);
    };
    pointer(QEvent::MouseMove, Qt::NoButton, Qt::LeftButton, false);
    pointer(QEvent::MouseButtonRelease, Qt::LeftButton, Qt::NoButton, false);
    pointer(QEvent::MouseButtonPress, Qt::LeftButton, Qt::LeftButton, true);
    pointer(QEvent::MouseMove, Qt::NoButton, Qt::LeftButton, true);
    pointer(QEvent::MouseButtonPress, Qt::LeftButton, Qt::LeftButton, true);
    pointer(QEvent::MouseButtonRelease, Qt::LeftButton, Qt::NoButton, true);
    pointer(QEvent::MouseMove, Qt::NoButton, Qt::LeftButton, false);
    pointer(QEvent::MouseButtonPress, Qt::LeftButton, Qt::LeftButton, true);
    view->grabMouse(); assert(window.mouseGrabberItem() == view);
    view->ungrabMouse(); assert(window.mouseGrabberItem() != view);
    pointer(QEvent::MouseMove, Qt::NoButton, Qt::LeftButton, false);
    pointer(QEvent::MouseButtonRelease, Qt::LeftButton, Qt::NoButton, false);
    QImage frame(4, 4, QImage::Format_ARGB32); frame.fill(QColor(220, 40, 60));
    view->acceptFrame(grant, 1, frame.constBits(), frame.sizeInBytes(), frame.width(), frame.height());
    QEventLoop paint; QTimer::singleShot(80, &paint, &QEventLoop::quit); paint.exec();
    auto capture = view->grabToImage(); assert(capture);
    if (capture->image().isNull()) {
        QEventLoop ready;
        QObject::connect(capture.data(), &QQuickItemGrabResult::ready, &ready, &QEventLoop::quit);
        QTimer::singleShot(2000, &ready, &QEventLoop::quit); ready.exec();
    }
    auto rendered = capture->image(); assert(!rendered.isNull());
    auto color = rendered.pixelColor(100, 100);
    assert(color.red() == 220 && color.green() == 40 && color.blue() == 60);
    qInfo("PASS actual Qt scene renders Pico-selected native WebView texture pixels");
    std::unique_ptr<QObject> isolated(create("/controls/EmbeddedWebBackend.qml"));
    auto* isolatedItem=qobject_cast<QQuickItem*>(isolated.get());
    isolatedItem->setParentItem(window.contentItem());isolatedItem->setWidth(640);isolatedItem->setHeight(480);
    isolated->setProperty("sourceIdentity", "pico-owned-second-world");
    isolated->setProperty("url", "https://pico.test/isolated");
    auto* isolatedView=isolated->findChild<NativeWebViewItem*>();assert(isolatedView && isolatedView!=view);
    isolatedView->acceptForeground(true);const auto isolatedGrant=isolatedView->generation();assert(isolatedGrant);
    isolatedView->acceptPage(isolatedGrant,1,QUrl("https://pico.test/isolated"));
    QImage isolatedFrame(4,4,QImage::Format_ARGB32);isolatedFrame.fill(QColor(20,210,70));
    isolatedView->acceptFrame(isolatedGrant,1,isolatedFrame.constBits(),isolatedFrame.sizeInBytes(),4,4);
    isolatedItem->setVisible(false);QCoreApplication::processEvents();
    assert(!isolatedView->generation() && view->generation()==grant);
    assert(view->editorFocused() && !isolatedView->editorFocused());
    isolated.reset();assert(view->generation()==grant);
    qInfo("PASS selected Pico native surfaces isolate frame, editor and hide state; browser media is a device boundary");
    assert(!view->acceptMessage(grant, 1, QUrl("https://pico.test/form"), QUrl("https://foreign.test"), true, "editor", "{}"));
    view->acceptForeground(false); QCoreApplication::processEvents();
    assert(bridge.messages.last() == "_LOWER_KEYBOARD");
    assert(!adapter->property("editorFocused").toBool());
    assert(!view->generation());
    assert(!view->allowsFileChooser(grant, 1, QUrl("https://pico.test/form")));
    view->acceptForeground(true); QCoreApplication::processEvents();
    auto resumedGrant = view->generation(); assert(resumedGrant && resumedGrant != grant);
    assert(view->allowsFileChooser(resumedGrant, 1, QUrl("https://pico.test/form")));
    assert(!view->allowsFileChooser(grant, 1, QUrl("https://pico.test/form")));
    adapter->setProperty("surface", "world-entity");
    assert(view->surface() == NativeWebViewItem::WorldEntity && view->presentation() == NativeWebViewItem::Texture);
    assert(!view->allowsFileChooser(view->generation(), 1, QUrl("https://pico.test/form")));
    adapter.reset();

    std::unique_ptr<QObject> world(create("/Web3DSurface.qml"));
    auto* worldItem = qobject_cast<QQuickItem*>(world.get()); assert(worldItem);
    worldItem->setParentItem(window.contentItem()); worldItem->setWidth(640); worldItem->setHeight(480);
    world->setProperty("scriptUrl", "https://pico.test/client.js");
    world->setProperty("userAgent", "pico-fixture");
    world->setProperty("url", "https://pico.test/page"); QCoreApplication::processEvents();
    QPointer<NativeWebViewItem> common = world->findChild<NativeWebViewItem*>(); assert(common);
    assert(common->presentation() == NativeWebViewItem::Texture);
    assert(common->scriptUrl() == "https://pico.test/client.js");
    assert(common->userAgent() == "pico-fixture");
    world->setProperty("keyboardRaised", true); world->setProperty("passwordField", true);
    assert(keyboard.raised && keyboard.password);
    world->setProperty("keyboardRaised", false); assert(!keyboard.raised && !keyboard.password);
    keyboard.use3DKeyboard = false;
    world->setProperty("punctuationMode", true); world->setProperty("keyboardRaised", true);
    auto* panel = world->findChild<QQuickItem*>("keyboard"); assert(panel);
    assert(panel->height() == 250 && panel->isVisible());
    assert(panel->property("numeric").toBool() && panel->property("password").toBool());
    assert(common->height() == 230);
    world->setProperty("keyboardRaised", false); assert(common->height() == 480);
    const QString inlineSource = "data:text/html;charset=UTF-8,<input value='inline+%2f'>.qml#Authored";
    world->setProperty("url", inlineSource);
    QCoreApplication::sendPostedEvents(nullptr, QEvent::DeferredDelete); QCoreApplication::processEvents();
    common = world->findChild<NativeWebViewItem*>();
    assert(common && !world->findChild<LegacyBoundary*>());
    assert(common->url() == inlineSource && !common->generation()); // No descriptor, no authority.
    overte::web::InlineHtmlDocumentOwner inlineOwner;
    const auto descriptor = inlineOwner.issue(engine.rootContext(), "pico:inline:world", inlineSource,
        "https://pico.test/client.js");
    assert(descriptor.current());
    engine.rootContext()->setContextProperty("nativeWebSourceIdentity", "pico:inline:world");
    engine.rootContext()->setContextProperty("nativeInlineHtmlDocument", QVariant::fromValue(descriptor));
    common->acceptForeground(true); QCoreApplication::processEvents();
    assert(common->url() == inlineSource && common->generation());
    assert(common->property("inlineDocument").value<overte::web::InlineHtmlDocument>().token() == descriptor.token());
    const auto inlineGrant = common->generation();
    const auto inlineTransport = descriptor.transportURL();
    inlineOwner.revoke(); // Revoke without a QML assignment or event-loop turn.
    assert(!common->generation());
    assert(!common->allowsFileChooser(inlineGrant, 1, inlineTransport));
    assert(!common->acceptMessage(inlineGrant, 1, inlineTransport, inlineTransport, true, "editor", "{}"));
    // A typed but unissued carrier must remain denied even for HTTPS.
    // Ordinary World navigation clears the context carrier before the URL.
    engine.rootContext()->setContextProperty("nativeInlineHtmlDocument",
        QVariant::fromValue(overte::web::InlineHtmlDocument()));
    world->setProperty("url", "https://pico.test/next");
    QCoreApplication::sendPostedEvents(nullptr, QEvent::DeferredDelete); QCoreApplication::processEvents();
    auto* nextWorld = world->findChild<NativeWebViewItem*>(); assert(nextWorld);
    nextWorld->acceptForeground(true); assert(!nextWorld->generation());
    engine.rootContext()->setContextProperty("nativeInlineHtmlDocument", QVariant());
    QCoreApplication::processEvents(); assert(nextWorld->generation());
    assert(!world->findChild<LegacyBoundary*>());
    world.reset();
    std::unique_ptr<QObject> physicalWorld(create("/+android_picoInterface/Web3DSurface.qml"));
    auto* physicalItem = qobject_cast<QQuickItem*>(physicalWorld.get()); assert(physicalItem);
    physicalItem->setParentItem(window.contentItem()); physicalItem->setWidth(640); physicalItem->setHeight(480);
    physicalWorld->setProperty("url", "https://pico.test/physical"); QCoreApplication::processEvents();
    assert(physicalWorld->findChild<NativeWebViewItem*>());
    physicalWorld->setProperty("url", "data:text/html,<p>physical inline</p>");
    QCoreApplication::processEvents(); QCoreApplication::sendPostedEvents(nullptr,QEvent::DeferredDelete);
    auto* physicalNative = physicalWorld->findChild<NativeWebViewItem*>(); assert(physicalNative);
    assert(!physicalWorld->findChild<LegacyBoundary*>() && !physicalNative->generation());
    // The direct physical selector entry must also preserve data bodies that
    // look like a QML filename and reject caller-supplied maps as authority.
    physicalWorld->setProperty("url", "data:text/html,<p>physical inline</p>.qml");
    QCoreApplication::processEvents(); QCoreApplication::sendPostedEvents(nullptr,QEvent::DeferredDelete);
    physicalNative = physicalWorld->findChild<NativeWebViewItem*>(); assert(physicalNative);
    assert(physicalNative->url().endsWith(".qml"));
    physicalNative->setProperty("inlineDocument", QVariantMap{{"html", "forged"}});
    assert(!physicalNative->generation());
    physicalWorld.reset();
    std::unique_ptr<QObject> tablet(create("/controls/TabletWebScreen.qml"));
    auto* tabletItem = qobject_cast<QQuickItem*>(tablet.get()); assert(tabletItem);
    tabletItem->setParentItem(window.contentItem()); tabletItem->setWidth(640); tabletItem->setHeight(480);
    tablet->setProperty("url", "https://pico.test/tablet"); QCoreApplication::processEvents();
    auto* tabletView = tablet->findChild<NativeWebViewItem*>(); assert(tabletView);
    assert(tabletView->surface() == NativeWebViewItem::Tablet);
    assert(tabletView->presentation() == NativeWebViewItem::Texture);
    tabletView->acceptForeground(true); auto tabletGrant = tabletView->generation(); assert(tabletGrant);
    tabletView->acceptPage(tabletGrant, 1, QUrl("https://pico.test/tablet")); tabletView->forceActiveFocus();
    assert(tabletView->acceptMessage(tabletGrant, 1, QUrl("https://pico.test/tablet"), QUrl("https://pico.test"), true, "editor",
        R"({"active":true,"kind":"text","text":"tablet input","cursor":12,"anchor":12})"));
    QCoreApplication::processEvents(); assert(tabletView->editorFocused());
    tablet->setProperty("keyboardRaised", true);
    assert(tabletView->editorFocused()); // Raising the QML keyboard must retain the real editor.
    assert(tabletView->height() == 182); // Existing keyboard (250) + native navigation (48).
    tablet->setProperty("keyboardRaised", false);
    assert(!tabletView->editorFocused() && tabletView->height() == 432);
    {
        auto context=std::make_unique<QQmlContext>(engine.rootContext());
        QQmlContext foreignContext(engine.rootContext());
        auto owner=std::make_unique<overte::web::InlineHtmlDocumentOwner>();
        const QString source="data:text/html,<p>owner+%2f</p>.qml#Case";
        const QString script="https://pico.test/script%2f.js?literal=+";
        auto foreign=owner->issue(&foreignContext,"pico:bound-context",source,script);
        context->setContextProperty("nativeWebSourceIdentity","pico:bound-context");
        context->setContextProperty("nativeInlineHtmlDocument",QVariant::fromValue(foreign));
        std::unique_ptr<QObject> bound(create("/+android_picoInterface/Web3DSurface.qml",context.get()));
        qobject_cast<QQuickItem*>(bound.get())->setParentItem(window.contentItem());
        bound->setProperty("scriptUrl",script);bound->setProperty("url",source);
        QCoreApplication::processEvents();
        auto* native=bound->findChild<NativeWebViewItem*>();assert(native);
        native->acceptForeground(true);assert(!native->generation()); // A sibling context cannot authorize this page.
        auto valid=owner->issue(context.get(),"pico:bound-context",source,script);
        context->setContextProperty("nativeInlineHtmlDocument",QVariant::fromValue(valid));
        QCoreApplication::processEvents();assert(native->generation());
        assert(native->url()==source && native->scriptUrl()==script);
        owner.reset();assert(!native->generation()); // Owner death is synchronous.
        overte::web::InlineHtmlDocumentOwner contextOwner;
        auto renewed=contextOwner.issue(context.get(),"pico:bound-context",source,script);
        context->setContextProperty("nativeInlineHtmlDocument",QVariant::fromValue(renewed));
        QCoreApplication::processEvents();assert(native->generation());
        context.reset();assert(!native->generation()); // Context death retires the still-live native item.
    }
    qInfo("PASS Pico selected native Texture world/tablet, editor/keyboard and lifecycle routing");
}
#include "pico-embedded-web-native-test.moc"
