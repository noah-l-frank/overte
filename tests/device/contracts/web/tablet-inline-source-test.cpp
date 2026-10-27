// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#include "NativeInlineHtmlSource.h"
#include "EmbeddedWebPolicy.h"
#include <QGuiApplication>
#include <QQmlComponent>
#include <QQmlContext>
#include <QQmlEngine>
#include <QJSValue>
#include <QQmlFileSelector>
#include <QTimer>
#include <cassert>
#include <memory>
#include <iostream>

// Native surface/window selection and the scene UI are explicit boundaries;
// the complete actual TabletProxy navigation body below is never reproduced.
namespace hifi::scripting { void setLocalAccessSafeThread(bool) {} }
struct WindowBoundary { QQuickItem* item {}; QQuickItem* asQuickItem() { return item; } };
class TabletProxy : public QObject {
public:
    enum class State { Uninitialized, Web };
    QString _name { "system" };
    bool _toolbarMode { false }, _initialScreen { false };
    QQuickItem* _qmlTabletRoot {};
    WindowBoundary* _desktopWindow {};
    State _state { State::Uninitialized };
    QVariant _currentPathLoaded;
    std::pair<QVariant, State> _initialPath;
    std::pair<QVariant, bool> _initialWebPathParams;
    void loadHTMLSourceOnTopImpl(const QString&, const QString&, bool, bool);
};
#include "production-tablet-native-loader.inc"

static QVariant nativeCarrier(QVariant value) {
    if (value.userType() == qMetaTypeId<QJSValue>()) { value = value.value<QJSValue>().toVariant(); }
    return value;
}
static bool carrierSupplied(QVariant value) {
    value = nativeCarrier(value);
    // A typed empty/stale carrier is explicitly supplied and must be denied.
    return value.userType() == qMetaTypeId<overte::web::InlineHtmlDocument>() ||
        (value.isValid() && !value.isNull());
}
static overte::web::InlineHtmlDocument descriptor(QVariant value) {
    return nativeCarrier(value).value<overte::web::InlineHtmlDocument>();
}

// The real QML property/constructor boundary, with only the OS browser
// substituted. Session ownership, context ancestry and revocation use production
// classes. This endpoint does not claim Android/WK navigation or device parity.
class NativeEndpoint : public QQuickItem {
    Q_OBJECT
    Q_PROPERTY(QString url READ url WRITE setUrl NOTIFY urlChanged)
    Q_PROPERTY(QString scriptUrl READ scriptUrl WRITE setScriptUrl NOTIFY scriptUrlChanged)
    Q_PROPERTY(QString sourceIdentity READ sourceIdentity WRITE setSourceIdentity NOTIFY sourceIdentityChanged)
    Q_PROPERTY(QVariant inlineDocument READ inlineDocument WRITE setInlineDocument NOTIFY inlineDocumentChanged)
public:
    QString _url, _script, _identity;
    QVariant _document;
    overte::web::EmbeddedWebSession session;
    bool complete { false }, validAtCompletion { false };
    int bootstrapCount { 0 }, revokeCount { 0 };
    QMetaObject::Connection revocation;
    QString acceptedToken;
    QString url() const { return _url; }
    QString scriptUrl() const { return _script; }
    QString sourceIdentity() const { return _identity; }
    QVariant inlineDocument() const { return _document; }
    void setUrl(const QString& value) { _url = value; emit urlChanged(); refresh(); }
    void setScriptUrl(const QString& value) { _script = value; emit scriptUrlChanged(); refresh(); }
    void setSourceIdentity(const QString& value) { _identity = value; emit sourceIdentityChanged(); refresh(); }
    void setInlineDocument(const QVariant& value) { _document = value; emit inlineDocumentChanged(); refresh(); }
    void refresh() {
        if (!complete) { return; }
        session.close();
        QObject::disconnect(revocation);
        if (!carrierSupplied(_document)) {
            session.open(QUrl(_url), overte::web::Surface::Tablet, _identity);
            return;
        }
        const auto document = descriptor(_document);
        auto* context = qmlContext(this);
        while (context && context != document.context()) { context = context->parentContext(); }
        if (!context || !session.openInline(document, context, _url,
                overte::web::Surface::Tablet, _identity, _script)) { return; }
        if (acceptedToken != document.token()) { acceptedToken = document.token(); ++bootstrapCount; }
        revocation = document.onRevoked(this, [this] { ++revokeCount; session.close(); });
    }
    void componentComplete() override {
        QQuickItem::componentComplete(); complete = true; refresh();
        validAtCompletion = session.active();
    }
signals:
    void urlChanged();
    void scriptUrlChanged();
    void sourceIdentityChanged();
    void inlineDocumentChanged();
};

static NativeEndpoint* worldEndpoint(QObject* world) {
    // Loader can retain a retired QObject until deferred deletion. Observe its
    // current production item, never a stale descendant found by tree order.
    auto* item = nativeCarrier(world->property("item")).value<QObject*>();
    return item ? item->findChild<NativeEndpoint*>() : nullptr;
}

// Surface acquisition is the explicit host boundary. Both real ordering modes
// are exercised: page completeCreate before or after the native callback. The
// native backend must be fully configured at its own componentComplete in both.
class SurfaceBoundary : public QObject {
    Q_OBJECT
public:
    QQmlEngine* engine {};
    QString stage;
    bool deferCallbacks { false }, completeBeforeCallback { false };
    struct Pending { QQmlComponent* component; QPointer<QQuickItem> item, parent; QJSValue callback; };
    std::vector<Pending> pending;
    Q_INVOKABLE void load(const QString& source, QQuickItem* parent, QJSValue callback) {
        auto* component = new QQmlComponent(engine, QUrl::fromLocalFile(stage + "/" + source), this);
        auto* item = qobject_cast<QQuickItem*>(component->beginCreate(qmlContext(parent)));
        if (!item) { std::cerr << component->errorString().toStdString(); std::abort(); }
        Pending request { component, item, parent, callback };
        if (deferCallbacks) { pending.push_back(request); }
        else { finish(request); }
    }
    void finish(Pending request) {
        if (completeBeforeCallback) { request.component->completeCreate(); }
        request.callback.call({ engine->newQObject(request.item) });
        if (request.item) {
            QQmlEngine::setObjectOwnership(request.item, QQmlEngine::JavaScriptOwnership);
            request.item->setParentItem(request.parent); request.item->setParent(request.parent);
        }
        if (!completeBeforeCallback) { request.component->completeCreate(); }
        request.component->deleteLater();
    }
    void flush() {
        auto requests = pending; pending.clear();
        for (const auto& request : requests) { finish(request); }
    }
signals:
    void qmlLoadFailed(QObject* parent, int generation);
};

int main(int argc, char** argv) {
    QGuiApplication application(argc, argv);
    assert(argc == 2);
    qmlRegisterType<NativeEndpoint>("TestNative", 1, 0, "NativeEndpoint");
    QQmlEngine engine;
    engine.addImportPath(QString::fromLocal8Bit(argv[1]));
    SurfaceBoundary surface;
    surface.engine = &engine; surface.stage = QString::fromLocal8Bit(argv[1]);
    engine.rootContext()->setContextProperty("QmlSurface", &surface);
    engine.rootContext()->setContextProperty("HMD", QVariant::fromValue(engine.evaluate("({ active: false })")));
    engine.rootContext()->setContextProperty("Tablet", QVariant::fromValue(engine.evaluate(
        "({ getTablet: function() { return { tabletShown:false, hideAndroidTablet:function(){}, "
        "gotoHomeScreen:function(){}, loadQMLSource:function(){} }; } })")));
    engine.rootContext()->setContextProperty("eventBridge", static_cast<QObject*>(nullptr));
    QQmlContext context(engine.rootContext()), foreignContext(engine.rootContext());
    QQmlComponent component(&engine);
    component.setData("import QtQuick 2.7\nItem { Item { objectName: 'container'; "
                      "Item { objectName: 'page' } } }", QUrl());
    std::unique_ptr<QQuickItem> root(qobject_cast<QQuickItem*>(component.create(&context)));
    std::unique_ptr<QQuickItem> foreignRoot(qobject_cast<QQuickItem*>(component.create(&foreignContext)));
    assert(root && foreignRoot);
    auto* page = root->findChild<QQuickItem*>("page");
    auto* container = root->findChild<QQuickItem*>("container");
    assert(page && container && qmlContext(page));
    const QByteArray html("<!doctype html><input value='original'><script>window.answer=42</script>"
                          "<video controls src='http://media.example/original.mp4'></video>");
    const QString source = "data:text/html;charset=UTF-8," + QString::fromLatin1(QUrl::toPercentEncoding(html));
    const QString script("https://scripts.example/%2fsource-owned.js?raw=%2b+%2f#exact%2f");
    QObject owner;
    auto* request = new NativeInlineHtmlSource(root.get(), "system", source, script, &owner);
    assert(!carrierSupplied(request->document()));
    assert(!request->bind(root.get()));
    QObject notAPage;
    assert(!request->bind(&notAPage));
    assert(!request->bind(foreignRoot->findChild<QQuickItem*>("page")));
    assert(request->bind(page));
    auto first = descriptor(request->document());
    assert(first.currentFor(qmlContext(page), request->sourceIdentity(), source));
    assert(first.bytes() == html && first.scriptURL() == script);
    const auto token = first.token();
    assert(request->bind(page) && descriptor(request->document()).token() == token);
    overte::web::EmbeddedWebSession session;
    assert(session.openInline(first, qmlContext(page), source, overte::web::Surface::Tablet,
                              request->sourceIdentity(), script));
    engine.rootContext()->setContextProperty("nativeRequest", request);
    QQmlComponent carrier(&engine);
    carrier.setData("import QtQml 2.15\nQtObject { property var forwarded: nativeRequest.document }", QUrl());
    std::unique_ptr<QObject> forwarded(carrier.create());
    assert(forwarded && descriptor(forwarded->property("forwarded")).current());
    // QObject dynamic properties cannot replace the native approved tuple.
    request->setProperty("source", "data:text/html,forged");
    request->setProperty("sourceIdentity", "forged-owner");
    assert(request->bind(page));
    assert(descriptor(request->document()).bytes() == html);
    assert(request->sourceIdentity().startsWith("tablet:system:"));
    container->setParentItem(foreignRoot.get());
    assert(!first.current() && !session.active());
    assert(!descriptor(forwarded->property("forwarded")).current());
    container->setParentItem(root.get());
    assert(request->bind(page));
    auto replacement = descriptor(request->document());
    assert(replacement.current() && replacement.token() != token);
    // Visual reparenting alone does not transfer a foreign QML context grant.
    auto* foreignPage = foreignRoot->findChild<QQuickItem*>("page");
    assert(foreignPage);
    foreignPage->setParentItem(root.get());
    assert(!request->bind(foreignPage) && !replacement.current());
    assert(request->bind(page));
    auto dying = descriptor(request->document());
    delete page;
    assert(!dying.current() && !descriptor(request->document()).current());
    assert(!carrierSupplied(request->document()));
    assert(!descriptor(forwarded->property("forwarded")).current());

    QQmlComponent nextComponent(&engine);
    nextComponent.setData("import QtQuick 2.7\nItem {}", QUrl());
    // A component created beside the tablet's QML context is still foreign,
    // even if QQuickItem visual parenting is changed afterward.
    std::unique_ptr<QQuickItem> siblingPage(qobject_cast<QQuickItem*>(nextComponent.create(&context)));
    assert(siblingPage); siblingPage->setParentItem(root.get());
    assert(!request->bind(siblingPage.get()));
    std::unique_ptr<QQuickItem> nextPage(qobject_cast<QQuickItem*>(nextComponent.create(qmlContext(root.get()))));
    assert(nextPage); nextPage->setParentItem(root.get());
    assert(request->bind(nextPage.get()));
    auto hidden = descriptor(request->document());
    nextPage->setVisible(false);
    assert(!hidden.current());
    nextPage->setVisible(true);
    assert(request->bind(nextPage.get()));
    auto retired = descriptor(request->document());
    request->retire();
    assert(!retired.current() && !request->bind(nextPage.get()));
    auto* rootBound = new NativeInlineHtmlSource(root.get(), "system", source, script, &owner);
    assert(rootBound->bind(nextPage.get()));
    auto closedRoot = descriptor(rootBound->document());
    nextPage->setParentItem(nullptr); // Page detachment also revokes immediately.
    assert(!closedRoot.current());
    nextPage->setParentItem(root.get());
    assert(rootBound->bind(nextPage.get()));
    closedRoot = descriptor(rootBound->document());
    root.reset();
    assert(!closedRoot.current());
    {
        auto ancestor = std::make_unique<QQmlContext>(engine.rootContext());
        QQmlComponent child(&engine);
        child.setData("import QtQuick 2.7\nItem { Item { objectName: 'child' } }", QUrl());
        std::unique_ptr<QQuickItem> contextRoot(qobject_cast<QQuickItem*>(child.create(ancestor.get())));
        auto* childPage = contextRoot->findChild<QQuickItem*>("child");
        auto* contextRequest = new NativeInlineHtmlSource(contextRoot.get(), "ancestor", source, script, &owner);
        assert(contextRequest->bind(childPage));
        const auto contextDocument = descriptor(contextRequest->document());
        ancestor.reset();
        assert(!contextDocument.current() && !descriptor(contextRequest->document()).current());
    }
    QQmlComponent unissued(&engine);
    unissued.setData("import QtQml 2.15\nNativeInlineHtmlSource {}", QUrl());
    assert(unissued.isError()); // No QML constructor issues a native source.
    for (const auto& worldEntry : { QString("Web3DSurface.qml"),
                                    QString("+android_interface/Web3DSurface.qml") }) {
      for (const auto& worldSource : { source, QString("data:text/html,<p>hello</p>.qml"),
                                     QString("DATA:text/html,last.qml#fragment"),
                                     QString("data:text/html,<p>hello</p>#document.qml") }) {
        // Complete generic World caller into the same native constructor.
        QQmlContext worldContext(engine.rootContext());
        overte::web::InlineHtmlDocumentOwner worldOwner;
        const auto worldDocument = worldOwner.issue(&worldContext, "world-owner", worldSource, script);
        worldContext.setContextProperty("nativeWebSourceIdentity", "world-owner");
        worldContext.setContextProperty("nativeInlineHtmlDocument", QVariant::fromValue(worldDocument));
        QQmlComponent worldComponent(&engine, QUrl::fromLocalFile(surface.stage + "/" + worldEntry));
        std::unique_ptr<QObject> world(worldComponent.beginCreate(&worldContext));
        assert(world); world->setProperty("scriptUrl", script); world->setProperty("url", worldSource);
        worldComponent.completeCreate();
        auto* endpoint = worldEndpoint(world.get());
        if (!endpoint || !endpoint->validAtCompletion || !endpoint->session.active()) {
            std::cerr << "World route failed: " << worldEntry.toStdString() << " source="
                      << worldSource.toStdString() << " endpoint=" << static_cast<bool>(endpoint)
                      << " complete=" << (endpoint && endpoint->validAtCompletion)
                      << " active=" << (endpoint && endpoint->session.active()) << std::endl;
        }
        assert(endpoint && endpoint->validAtCompletion && endpoint->session.active());
        assert(endpoint->_url == worldSource && endpoint->_script == script && endpoint->bootstrapCount == 1);
        worldOwner.revoke();
        assert(!endpoint->session.active() && endpoint->revokeCount == 1);
      }
    }
    {
        // An initially unset native QVariant legitimately reads as JS undefined.
        // A later real descriptor must still cross the required property.
        QQmlContext pageContext(engine.rootContext());
        QQmlComponent viewComponent(&engine, QUrl::fromLocalFile(surface.stage + "/controls/EmbeddedWebView.qml"));
        std::unique_ptr<QObject> view(viewComponent.beginCreate(&pageContext));
        assert(view); view->setProperty("url", "https://ordinary.example/start");
        viewComponent.completeCreate();
        auto* endpoint = view->findChild<NativeEndpoint*>(); assert(endpoint);
        assert(endpoint->validAtCompletion && endpoint->session.active());
        assert(!carrierSupplied(endpoint->inlineDocument()));
        overte::web::InlineHtmlDocumentOwner sourceOwner;
        const auto value = sourceOwner.issue(&pageContext, "later-source", source, script);
        view->setProperty("sourceIdentity", "later-source"); view->setProperty("scriptUrl", script);
        view->setProperty("inlineDocument", QVariant::fromValue(value)); view->setProperty("url", source);
        assert(endpoint->session.active() && descriptor(endpoint->inlineDocument()).current());
        assert(endpoint->bootstrapCount == 1);
        view->setProperty("inlineDocument", QVariantMap { { "token", value.token() } });
        assert(!endpoint->session.active());
        view->setProperty("inlineDocument", QVariant::fromValue(value));
        assert(endpoint->session.active() && endpoint->bootstrapCount == 1);
        const auto generation = endpoint->session.generation();
        sourceOwner.revoke();
        assert(!endpoint->session.active() && endpoint->revokeCount == 1);
        assert(!endpoint->session.allowsBridge(generation, value.transportURL(), true, 10));
    }
    {
        // Complete ordinary World startup and inline -> ordinary replacement.
        // Absence crosses the actual production aliases into the native property.
        QQmlContext worldContext(engine.rootContext());
        overte::web::InlineHtmlDocumentOwner worldOwner;
        worldContext.setContextProperty("nativeWebSourceIdentity", "ordinary-world-owner");
        worldContext.setContextProperty("nativeInlineHtmlDocument", QVariant());
        QQmlComponent component(&engine, QUrl::fromLocalFile(surface.stage + "/Web3DSurface.qml"));
        std::unique_ptr<QObject> world(component.beginCreate(&worldContext));
        assert(world); world->setProperty("url", "https://ordinary.example/initial");
        component.completeCreate();
        auto* endpoint = worldEndpoint(world.get());
        assert(endpoint && endpoint->validAtCompletion && endpoint->session.active());
        assert(!carrierSupplied(endpoint->inlineDocument()) && !endpoint->session.inlineDocument());
        const auto issued = worldOwner.issue(&worldContext, "ordinary-world-owner", source, script);
        worldContext.setContextProperty("nativeInlineHtmlDocument", QVariant::fromValue(issued));
        world->setProperty("scriptUrl", script); world->setProperty("url", source);
        endpoint = worldEndpoint(world.get());
        assert(endpoint && endpoint->validAtCompletion && endpoint->session.inlineDocument());
        worldOwner.revoke();
        assert(!issued.current() && !endpoint->session.active());
        worldContext.setContextProperty("nativeInlineHtmlDocument", QVariant());
        world->setProperty("url", "https://ordinary.example/replacement");
        endpoint = worldEndpoint(world.get());
        assert(endpoint && endpoint->validAtCompletion && endpoint->session.active());
        assert(!carrierSupplied(endpoint->inlineDocument()) && !endpoint->session.inlineDocument());
        // Never reinterpret a deliberately supplied typed-unissued/stale carrier
        // as absence, even when the URL is otherwise an ordinary HTTPS URL.
        endpoint->setInlineDocument(QVariant::fromValue(overte::web::InlineHtmlDocument()));
        assert(!endpoint->session.active());
        endpoint->setInlineDocument(QVariant::fromValue(issued));
        assert(!endpoint->session.active());
        endpoint->setInlineDocument(QVariant());
        assert(endpoint->session.active() && !endpoint->session.inlineDocument());
    }
    for (bool completeBefore : { false, true }) {
      surface.completeBeforeCallback = completeBefore;
      for (const auto& kind : { QString("Tablet"), QString("Window") }) {
        QQmlComponent routing(&engine, QUrl::fromLocalFile(QString::fromLocal8Bit(argv[1]) + "/hifi/tablet/" + kind + "Root.qml"));
        std::unique_ptr<QQuickItem> routedRoot(qobject_cast<QQuickItem*>(routing.create()));
        if (!routedRoot) { std::cerr << kind.toStdString() << " root status " << routing.status() << ": "
                                   << routing.errorString().toStdString(); }
        assert(routedRoot);
        auto* loader = routedRoot->findChild<QObject*>("loader");
        assert(loader);
        const auto routedPage = [&] { return qobject_cast<QQuickItem*>(loader->property("item").value<QObject*>()); };
        TabletProxy proxy;
        WindowBoundary window { routedRoot.get() };
        if (kind == "Tablet") { proxy._qmlTabletRoot = routedRoot.get(); }
        else { proxy._toolbarMode = true; proxy._desktopWindow = &window; }
        proxy.loadHTMLSourceOnTopImpl(source, script, false, false);
        QCoreApplication::processEvents(); QCoreApplication::processEvents();
        auto* page = routedPage(); assert(page);
        auto original = descriptor(page->property("inlineDocument"));
        assert(original.currentFor(qmlContext(page), page->property("sourceIdentity").toString(), source));
        assert(original.bytes() == html && original.scriptURL() == script);
        assert(page->property("url").toString() == source && page->property("scriptURL").toString() == script);
        auto* endpoint = page->findChild<NativeEndpoint*>();
        assert(endpoint && endpoint->validAtCompletion && endpoint->session.active());
        assert(endpoint->_url == source && endpoint->_script == script);
        assert(endpoint->bootstrapCount == 1);
        assert(proxy._state == TabletProxy::State::Web && proxy._currentPathLoaded.toString() == source);
        if (kind == "Window") { assert(routedRoot->property("shown").toBool()); }
        const QString secondSource("data:text/html,second-native-request");
        proxy.loadHTMLSourceOnTopImpl(secondSource, QString(), true, false);
        assert(!original.current());
        assert(!endpoint->session.active() && endpoint->revokeCount == 1);
        QCoreApplication::processEvents(); QCoreApplication::processEvents();
        auto second = descriptor(routedPage()->property("inlineDocument"));
        assert(second.current() && second.bytes() == "second-native-request");
        if (kind == "Tablet") {
            assert(routedRoot->property("currentApp").toInt() == 1);
            assert(QMetaObject::invokeMethod(routedRoot.get(), "returnToPreviousApp"));
            assert(!second.current());
            assert(routedRoot->property("currentApp").toInt() == 0); // Return never appends a duplicate app.
            QCoreApplication::processEvents(); QCoreApplication::processEvents();
            auto restored = descriptor(routedPage()->property("inlineDocument"));
            assert(restored.current() && restored.bytes() == html && restored.token() != original.token());
        }
        surface.deferCallbacks = true;
        proxy.loadHTMLSourceOnTopImpl("data:text/html,obsolete-callback", QString(), false, false);
        proxy.loadHTMLSourceOnTopImpl("data:text/html,current-callback", QString(), false, false);
        surface.flush();
        surface.deferCallbacks = false;
        QCoreApplication::processEvents(); QCoreApplication::processEvents();
        auto current = descriptor(routedPage()->property("inlineDocument"));
        assert(current.current() && current.bytes() == "current-callback");
        assert(routedPage()->property("url").toString() == "data:text/html,current-callback");
        if (kind == "Window") {
            NativeInlineHtmlSource* sameSource = nullptr;
            const auto identity = routedPage()->property("sourceIdentity").toString();
            for (auto* candidate : proxy.findChildren<NativeInlineHtmlSource*>()) {
                if (candidate->sourceIdentity() == identity) { sameSource = candidate; }
            }
            assert(sameSource);
            assert(QMetaObject::invokeMethod(routedRoot.get(), "loadWebBase",
                Q_ARG(QVariant, QVariant("data:text/html,current-callback")), Q_ARG(QVariant, QVariant(QString())),
                Q_ARG(QVariant, QVariant::fromValue(static_cast<QObject*>(sameSource)))));
            assert(!current.current());
            QCoreApplication::processEvents(); QCoreApplication::processEvents();
            auto rebound = descriptor(routedPage()->property("inlineDocument"));
            assert(rebound.current() && rebound.token() != current.token());
            current = rebound;
        }
        assert(QMetaObject::invokeMethod(routedRoot.get(), "loadSource", Q_ARG(QVariant, QVariant("hifi/tablet/TabletHome.qml"))));
        assert(!current.current());
        assert(!descriptor(routedPage()->property("inlineDocument")).current());
        proxy.loadHTMLSourceOnTopImpl(source, script, false, false);
        QCoreApplication::processEvents(); QCoreApplication::processEvents();
        auto closed = descriptor(routedPage()->property("inlineDocument")); assert(closed.current());
        assert(QMetaObject::invokeMethod(routedRoot.get(), "setShown", Q_ARG(QVariant, QVariant(false))));
        assert(!closed.current());
    }
      }
    qInfo("PASS actual native tablet source and TabletProxy navigation, complete production Tablet/Window roots and nested aliases into native componentComplete, real context/visual lifetime and descriptor binding, app-stack return without duplicates, stale load callbacks and retirement; OS browser and device media remain separate");
}

#include "tablet-inline-source-test.moc"
