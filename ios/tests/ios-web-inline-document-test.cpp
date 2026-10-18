// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Real Qt contexts, production native binding/session/epoch and property bodies.
// UIKit/WK loading, rule compilation, networking and video are NOT simulated.
#include <QGuiApplication>
#include <QQmlComponent>
#include <QQmlEngine>
#include <QQmlFileSelector>
#include <QFileSelector>
#include <CapabilityProfile.h>
#include <QQuickItem>
#include <QQuickPaintedItem>
#include <QPainter>
#include <QInputMethod>
#include <QTimer>
#include <QUuid>
#include <QJsonDocument>
#include <QRegularExpression>
#include <QMetaProperty>
#include <cassert>
#include <iostream>
#include <memory>
#include "../web/IOSInlineDocument.h"
#include "../web/IOSWebDocumentEpoch.h"
#include <EmbeddedWebPolicy.h>
using namespace overte;

// Only the native item construction/teardown boundary is replaced. Property
// declarations and complete getter/setter bodies come from IOSWebView itself.
class IOSWebView : public QQuickPaintedItem {
    Q_OBJECT
#include "production-properties.inc"
public:
    struct Private {
        QString originalSource, originalScript; QUrl url, scriptUrl; QVariant inlineCarrier;
        QString identity, surface { QStringLiteral("tablet") }, documentRoot;
        web::EmbeddedWebSession policy;
        ios::IOSInlineDocumentBinding inlineBinding;
        QMetaObject::Connection inlineRevocationConnection, snapshotConnection;
        ios::IOSWebDocumentEpoch document;
        QImage image;
        QString error;
        QUrl bridgeFrame;
        bool background { true }, inputActive { false }, presentation { false }, bridgeReady { false }, loading { false };
        struct SnapshotBoundary { int detaches {0}; void detach() { ++detaches; } } snapshot;
        QTimer deadline;
        std::uint64_t generation { 0 };
        bool inlineMode { false };
    };
    std::unique_ptr<Private> _private { std::make_unique<Private>() };
    int revocations { 0 }, nativeStops { 0 };
    bool configuredAtCompletion { false }, sourceOpenedAtCompletion { false };
    QString url() const;
    void setUrl(const QString&);
    QString scriptUrl() const;
    void setScriptUrl(const QString&);
    QVariant inlineDocument() const;
    void setInlineDocument(const QVariant&);
    bool observeInlineDocument();
    bool openSource();
    bool active() const { return _private->generation && _private->policy.active(); } // Explicit native-window boundary.
    void setLoading(bool);
    void retireDocumentPresentation();
    bool beginDocumentNavigation(const QUrl&);
    void acceptDocumentImage(std::uint64_t, std::uint64_t, const QImage&);
    void acceptInputResult(std::uint64_t, std::uint64_t, bool);
    void prepareDocument(const QUrl& frame) { beginDocumentNavigation(frame); } // WK script installation boundary.
    void paint(QPainter*) override;
    QVariant inputMethodQuery(Qt::InputMethodQuery) const override;
    void fail(const QString& error) { _private->error = error; stop(); }
    QString surface() const;
    void setSurface(const QString&);
    QString sourceIdentity() const;
    void setSourceIdentity(const QString&);
    void scheduleOpen() {
        ++revocations; // Explicit unopened WK replacement boundary.
        _private->policy.close(); _private->generation = 0;
        QObject::disconnect(_private->inlineRevocationConnection); _private->inlineRevocationConnection = {};
        _private->inlineBinding.clear();
    }
    void stop() {
        ++nativeStops; // Actual subscription stops at this explicit WK boundary.
        _private->policy.close(); _private->generation = 0;
        QObject::disconnect(_private->inlineRevocationConnection); _private->inlineRevocationConnection = {};
        _private->inlineBinding.clear();
    }
protected:
    void componentComplete() override {
        QQuickPaintedItem::componentComplete();
        ios::IOSInlineDocumentBinding initial;
        configuredAtCompletion = initial.bind(inlineDocument(), this, sourceIdentity(), url(), scriptUrl());
        sourceOpenedAtCompletion = openSource(); // Execute production policy selection, then stop before WK.
    }
signals:
    void urlChanged();
    void configurationChanged();
    void inlineDocumentChanged();
    void frameChanged();
    void bridgeAvailableChanged();
    void loadingChanged();
};
struct IOSWebViewNative {
    static bool current(IOSWebView*, std::uint64_t);
    static void started(IOSWebView*, std::uint64_t);
    static void prepareNavigation(IOSWebView*, std::uint64_t, const QUrl&, const QUrl&, bool);
};
#include "inline-test.moc"
#include "production-properties-methods.inc"

static std::unique_ptr<QObject> createObject(QQmlEngine& engine, QQmlContext* context) {
    QQmlComponent component(&engine);
    component.setData("import QtQml 2.15\nQtObject { property QtObject endpoint: QtObject {} }", QUrl());
    auto root = std::unique_ptr<QObject>(component.create(context));
    if (!root) { std::cerr << component.errorString().toStdString(); std::abort(); }
    QQmlEngine::setObjectOwnership(root.get(), QQmlEngine::CppOwnership);
    return root;
}
static QObject* endpoint(QObject* root) { return root->property("endpoint").value<QObject*>(); }

int main(int argc, char** argv) {
    QGuiApplication app(argc, argv);
    assert(argc == 2);
    const QString iosRoot = QString::fromLocal8Bit(argv[1]);
    qmlRegisterType<IOSWebView>("IOSInlineProperties", 1, 0, "NativeProperties");
    QQmlEngine engine;
    QQmlContext issuer(engine.rootContext()), sibling(engine.rootContext());
    auto root = createObject(engine, &issuer), foreign = createObject(engine, &sibling);
    auto* native = endpoint(root.get()); assert(native);
    assert(qmlContext(native) != &issuer); // Actual component child context.
    const QString source = "DaTa:TEXT/HTML;charset=windows-1252,%3Ctitle%3E%E9%2b%3C/title%3E#frag";
    const QString script = "https://Scripts.example/app%2f.js?q=%7e#source";
    const QString identity = "world-entity:source-owner";
    web::InlineHtmlDocumentOwner owner;
    auto document = owner.issue(&issuer, identity, source, script);
    assert(document.current());
    ios::IOSInlineDocumentBinding binding;
    assert(binding.bind(QVariant::fromValue(document), native, identity, source, script));
    assert(binding.context() == &issuer && binding.current(native));
    assert(document.bytes() == QByteArray::fromHex("3c7469746c653ee92b3c2f7469746c653e"));
    assert(document.charset() == "windows-1252");
    const auto bytes = document.bytes();
    web::EmbeddedWebSession session;
    const auto generation = session.openInline(document, binding.context(), source, web::Surface::WorldEntity, identity, script);
    assert(generation && session.active());
    const auto transport = document.transportURL();
    assert(session.allowsInlineResponse(generation, transport, true, "GET"));
    assert(session.allowsInlineResponse(generation, transport, true, "HEAD"));
    assert(!session.allowsInlineResponse(generation, transport, false, "GET"));
    assert(!session.allowsInlineResponse(generation, transport, true, "POST"));
    QUrl other(transport); other.setQuery("forged=1");
    assert(!session.allowsInlineResponse(generation, other, true, "GET"));
    assert(!session.allowsNavigation(generation, QUrl(source), true, "GET"));
    assert(session.allowsNavigation(generation, QUrl("https://remote.example/app"), true, "GET"));
    assert(!session.allowsBridge(generation, QUrl("https://remote.example/app"), true, 1));
    assert(!session.allowsBridge(generation, transport, false, 1));
    ios::IOSWebDocumentEpoch epoch;
    assert(epoch.begin(generation, transport, "native-nonce"));
    assert(epoch.accepts(generation, "native-nonce", transport, true));
    assert(session.allowsBridge(generation, transport, true, 1));
    assert(!epoch.accepts(generation, "old-nonce", transport, true));
    assert(!epoch.accepts(generation, "native-nonce", QUrl("about:blank"), true));
    assert(!epoch.accepts(generation, "native-nonce", QUrl(), true));

    ios::IOSInlineDocumentBinding denied;
    assert(!denied.bind(QVariantMap{{"token", document.token()}}, native, identity, source, script));
    assert(!denied.bind(document.token(), native, identity, source, script));
    assert(!denied.bind(QVariant::fromValue(document), endpoint(foreign.get()), identity, source, script));
    // Changing QObject ownership does not change real QML context ancestry.
    foreign->setParent(&issuer);
    assert(!denied.bind(QVariant::fromValue(document), endpoint(foreign.get()), identity, source, script));
    foreign->setParent(nullptr);
    QQmlEngine otherEngine;
    auto otherRoot = createObject(otherEngine, otherEngine.rootContext());
    assert(!denied.bind(QVariant::fromValue(document), endpoint(otherRoot.get()), identity, source, script));
    assert(!denied.bind(QVariant::fromValue(document), native, identity + "-other", source, script));
    assert(!denied.bind(QVariant::fromValue(document), native, identity, QUrl(source).toString(), script));
    assert(!denied.bind(QVariant::fromValue(document), native, identity, source, QUrl(script).toString()));

    IOSWebView item;
    QQmlEngine::setObjectOwnership(&item, QQmlEngine::CppOwnership);
    for (const char* name : {"url", "scriptUrl", "inlineDocument", "surface", "sourceIdentity"}) {
        const auto index = item.metaObject()->indexOfProperty(name);
        assert(index >= 0); // JavaScript must never fall back to a dynamic property.
        const auto property = item.metaObject()->property(index);
        assert(property.isWritable());
        assert(QByteArray(property.typeName()) == (QByteArray(name) == "inlineDocument" ? "QVariant" : "QString"));
    }
    engine.globalObject().setProperty("nativeItem", engine.newQObject(&item));
    const auto literal = [](const QString& value) {
        return QString::fromUtf8(QJsonDocument(QJsonArray{value}).toJson(QJsonDocument::Compact)) + "[0]";
    };
    assert(!engine.evaluate("nativeItem.url = " + literal(source)).isError());
    assert(!engine.evaluate("nativeItem.scriptUrl = " + literal(script)).isError());
    assert(item.url() == source && item.scriptUrl() == script);
    assert(item._private->url.toString() != source && item._private->scriptUrl.toString() != script);
    assert(item.revocations == 2);
    item.setUrl(source); item.setScriptUrl(script);
    assert(item.revocations == 2); // Exact repeat does not replace a lifetime.
    IOSWebView normalized;
    normalized.setUrl(source); normalized.setScriptUrl(script);
    normalized.setUrl(QUrl(source).toString()); normalized.setScriptUrl(QUrl(script).toString());
    assert(normalized.revocations == 4); // URL-equivalent strings are distinct authored sources.
    assert(normalized._private->url == item._private->url && normalized._private->scriptUrl == item._private->scriptUrl);
    assert(normalized.url() != item.url() && normalized.scriptUrl() != item.scriptUrl());
    item.setInlineDocument(QVariant::fromValue(document)); assert(item.revocations == 3);
    std::cout << "PASS real Qt native QString source/script properties, unchanged exact source/script literals and descriptor replacement invalidation" << std::endl;

    owner.revoke();
    assert(!document.current() && !binding.current(native) && !session.active());
    assert(!session.allowsBridge(generation, transport, true, 1));
    item.setInlineDocument(QVariant::fromValue(web::InlineHtmlDocument{}));
    assert(item.revocations == 4); // Invalid replacement must not compare equal to a dead descriptor.
    document = owner.issue(&issuer, identity, source, script);
    assert(document.bytes() == bytes && document.transportURL() != transport);
    assert(binding.bind(QVariant::fromValue(document), native, identity, source, script));
    const auto next = session.openInline(document, binding.context(), source, web::Surface::Tablet, identity, script);
    assert(next > generation && !session.allowsBridge(generation, document.transportURL(), true, 1));
    session.setForeground(false); assert(!session.active());
    session.setForeground(true); assert(session.active());
    assert(!session.allowsBridge(next, document.transportURL(), true, 1));
    assert(epoch.begin(session.generation(), document.transportURL(), "restored-native-nonce"));
    assert(!epoch.accepts(session.generation(), "native-nonce", document.transportURL(), true));

    ios::IOSInlineNavigation expected;
    expected.issued(next, document.transportURL(), document.token());
    assert(expected.consume(next, document.transportURL(), document.token()));
    assert(!expected.consume(next, document.transportURL(), document.token()));
    expected.issued(next, document.transportURL(), document.token());
    assert(!expected.consume(generation, document.transportURL(), document.token()));
    assert(!expected.consume(next, document.transportURL(), document.token()));
    expected.issued(next, document.transportURL(), document.token()); expected.clear();
    assert(!expected.consume(next, document.transportURL(), document.token()));

    const auto rules = QJsonDocument::fromJson(ios::iosInlineNamespaceRules().toUtf8()).array();
    assert(rules.size() == 1);
    const auto trigger = rules[0].toObject()["trigger"].toObject();
    assert(!trigger.contains("resource-type") && !trigger.contains("load-type"));
    assert(rules[0].toObject()["action"].toObject()["type"] == "block");
    const QRegularExpression blocked(trigger["url-filter"].toString(), QRegularExpression::CaseInsensitiveOption);
    assert(blocked.isValid());
    for (const QString url : {"http://overte-inline.invalid", "http://a.overte-inline.invalid/index.html",
            "https://USER:secret@a.b.overte-inline.invalid.:8443/asset", "HTTP://A.OVERTE-INLINE.INVALID./",
            "ws://a.overte-inline.invalid/socket", "wss://overte-inline.invalid:443/socket",
            "http://a.overte-inline.invalid.../file", "http://user@overte-inline.invalid/"}) {
        assert(blocked.match(url).hasMatch());
    }
    for (const QString url : {"https://outside.example/path/overte-inline.invalid", "http://overte-inline.invalid.example/path",
            "http://outside.example/?q=overte-inline.invalid", "http://overte-inline.invalid@outside.example/",
            "http://not-overte-inline.invalid/"}) { assert(!blocked.match(url).hasMatch()); }

    auto transient = std::make_unique<QQmlContext>(engine.rootContext());
    auto transientRoot = createObject(engine, transient.get());
    auto dying = owner.issue(transient.get(), identity, source, script);
    assert(binding.bind(QVariant::fromValue(dying), endpoint(transientRoot.get()), identity, source, script));
    transient.reset();
    assert(!dying.current() && !binding.current(endpoint(transientRoot.get())));
    QQmlComponent observedComponent(&engine);
    observedComponent.setData("import IOSInlineProperties 1.0\nNativeProperties {}", QUrl());
    auto observed = std::unique_ptr<IOSWebView>(qobject_cast<IOSWebView*>(observedComponent.create(&issuer)));
    assert(observed);
    QQmlEngine::setObjectOwnership(observed.get(), QQmlEngine::CppOwnership);
    const auto observe = [&](const web::InlineHtmlDocument& current, std::uint64_t nativeGeneration) {
        auto& state = *observed->_private;
        state.generation = nativeGeneration; state.inlineMode = true;
        assert(state.inlineBinding.bind(QVariant::fromValue(current), observed.get(), identity, source, script));
        assert(observed->observeInlineDocument());
    };
    web::InlineHtmlDocumentOwner observedOwner;
    auto observedDocument = observedOwner.issue(&issuer, identity, source, script);
    observe(observedDocument, 1);
    observedOwner.revoke();
    assert(observed->nativeStops == 1 && !observed->_private->generation); // Before processEvents.
    assert(!observed->observeInlineDocument()); // Dead authority never subscribes.
    observedDocument = observedOwner.issue(&issuer, identity, source, script);
    observe(observedDocument, 2);
    auto invalidReplacement = observedOwner.issue(&issuer, identity, "data:text/html;base64,%%%%", script);
    assert(!invalidReplacement.current() && observed->nativeStops == 2);
    web::InlineHtmlDocumentOwner retiredOwner, currentOwner;
    const auto retired = retiredOwner.issue(&issuer, identity, source, script);
    observe(retired, 3);
    const auto current = currentOwner.issue(&issuer, identity, source, script);
    observe(current, 4); // Replaces and disconnects the retired subscription.
    retiredOwner.revoke();
    assert(observed->nativeStops == 2 && observed->_private->generation == 4);
    currentOwner.revoke(); assert(observed->nativeStops == 3);
    auto mortalOwner = std::make_unique<web::InlineHtmlDocumentOwner>();
    const auto mortal = mortalOwner->issue(&issuer, identity, source, script);
    observe(mortal, 5); mortalOwner.reset();
    assert(observed->nativeStops == 4 && !mortal.current());
    auto dyingContext = std::make_unique<QQmlContext>(engine.rootContext());
    auto dyingObserved = std::unique_ptr<IOSWebView>(qobject_cast<IOSWebView*>(observedComponent.create(dyingContext.get())));
    assert(dyingObserved);
    QQmlEngine::setObjectOwnership(dyingObserved.get(), QQmlEngine::CppOwnership);
    web::InlineHtmlDocumentOwner dyingOwner;
    const auto dyingDocument = dyingOwner.issue(dyingContext.get(), identity, source, script);
    dyingObserved->_private->generation = 5; dyingObserved->_private->inlineMode = true;
    assert(dyingObserved->_private->inlineBinding.bind(QVariant::fromValue(dyingDocument), dyingObserved.get(), identity, source, script));
    assert(dyingObserved->observeInlineDocument());
    dyingContext.reset(); assert(dyingObserved->nativeStops == 1 && !dyingDocument.current());
    std::cout << "PASS actual native revocation subscription: synchronous source/invalid-replacement/context teardown and retired subscription isolation (WK stop boundary unopened)" << std::endl;
    // Execute actual document navigation, result sinks, paint and input-query
    // bodies. Only the active native window and WK script/capture are boundaries.
    IOSWebView navigating;
    navigating.setWidth(32); navigating.setHeight(32);
    navigating._private->deadline.setInterval(30000);
    const QUrl firstPage("https://navigation.example/first"), fragment("https://navigation.example/first#part"),
        nextPage("https://navigation.example/next");
    const auto navigationGeneration = navigating._private->policy.open(firstPage, web::Surface::WorldEntity, "navigation-world");
    navigating._private->generation = navigationGeneration;
    IOSWebViewNative::prepareNavigation(&navigating, navigationGeneration, QUrl(), firstPage, true);
    const auto oldEpoch = navigating._private->document.epoch();
    QImage oldImage(32, 32, QImage::Format_RGBA8888); oldImage.fill(Qt::red);
    navigating.acceptDocumentImage(navigationGeneration, oldEpoch, oldImage);
    navigating.acceptInputResult(navigationGeneration, oldEpoch, true);
    assert(navigating.inputMethodQuery(Qt::ImEnabled).toBool());
    const auto painted = [&] {
        QImage pixels(32, 32, QImage::Format_RGBA8888); pixels.fill(Qt::transparent);
        QPainter painter(&pixels); navigating.paint(&painter); painter.end(); return pixels;
    };
    assert(painted().pixelColor(16, 16) == QColor(Qt::red));
    IOSWebViewNative::prepareNavigation(&navigating, navigationGeneration, firstPage, fragment, true);
    assert(navigating._private->document.epoch() == oldEpoch);
    assert(painted().pixelColor(16, 16) == QColor(Qt::red) && navigating.inputMethodQuery(Qt::ImEnabled).toBool());
    IOSWebViewNative::prepareNavigation(&navigating, navigationGeneration, fragment, nextPage, true);
    const auto newEpoch = navigating._private->document.epoch();
    assert(newEpoch > oldEpoch && navigating._private->image.isNull());
    assert(!navigating.inputMethodQuery(Qt::ImEnabled).toBool());
    IOSWebViewNative::started(&navigating, navigationGeneration);
    assert(navigating._private->loading && painted().pixelColor(16, 16) == QColor(Qt::white));
    navigating.acceptDocumentImage(navigationGeneration, oldEpoch, oldImage);
    navigating.acceptInputResult(navigationGeneration, oldEpoch, true);
    assert(navigating._private->image.isNull() && !navigating.inputMethodQuery(Qt::ImEnabled).toBool());
    QImage newImage(32, 32, QImage::Format_RGBA8888); newImage.fill(Qt::blue);
    navigating.acceptDocumentImage(navigationGeneration, newEpoch, newImage);
    navigating.acceptInputResult(navigationGeneration, newEpoch, true);
    assert(painted().pixelColor(16, 16) == QColor(Qt::blue) && navigating.inputMethodQuery(Qt::ImEnabled).toBool());
    IOSWebViewNative::prepareNavigation(&navigating, navigationGeneration, nextPage, QUrl("https://foreign.example/frame"), false);
    navigating.acceptDocumentImage(navigationGeneration + 1, newEpoch, oldImage);
    navigating.acceptInputResult(navigationGeneration + 1, newEpoch, false);
    assert(painted().pixelColor(16, 16) == QColor(Qt::blue) && navigating.inputMethodQuery(Qt::ImEnabled).toBool());
    std::cout << "PASS actual document navigation/paint/input: real navigation retires old pixels and edits, stale image/input results deny, new document recovers, fragments/subframes preserve state (WK unopened)" << std::endl;
    std::cout << "PASS independent iOS native property/binding/session/epoch/namespace checks" << std::endl;
    document = owner.issue(&issuer, identity, source, script);
    // Execute the actual inherited wrapper through the real product selectors;
    // only the UIKit/WK type is substituted at its registered native boundary.
    qmlRegisterType(QUrl::fromLocalFile(iosRoot + "/ios/tests/qml/InlineNativeBoundary.qml"),
        "Overte.iOS", 1, 0, "IOSWebView");
    engine.addImportPath(iosRoot + "/interface/resources/qml");
    QQmlFileSelector platformSelector(&engine);
    QStringList profile;
    for (const auto& item : ui::profileSelectors(ui::Product::IOS, true)) {
        profile.append(QString::fromStdString(item));
    }
    platformSelector.setExtraSelectors(profile);
    assert(platformSelector.selector()->select(iosRoot + "/interface/resources/qml/controls/EmbeddedWebBackend.qml").contains("/+ios/"));
    assert(platformSelector.selector()->select(iosRoot + "/interface/resources/qml/controls/FlickableWebViewCore.qml").contains("/+ios/"));
    QQmlComponent sharedWrapper(&engine, QUrl::fromLocalFile(iosRoot + "/interface/resources/qml/controls/EmbeddedWebView.qml"));
    if (!sharedWrapper.isReady()) { std::cerr << sharedWrapper.errorString().toStdString(); std::abort(); }
    QVariantMap initial {{"url", source}, {"scriptUrl", script}, {"sourceIdentity", identity},
        {"inlineDocument", QVariant::fromValue(document)}, {"width", 640}, {"height", 480}};
    std::unique_ptr<QObject> surface(sharedWrapper.createWithInitialProperties(initial, &issuer));
    if (!surface) { std::cerr << sharedWrapper.errorString().toStdString(); std::abort(); }
    auto* backend = qobject_cast<IOSWebView*>(surface->property("backend").value<QObject*>());
    assert(backend && backend->url() == source && backend->scriptUrl() == script);
    assert(backend->configuredAtCompletion && backend->sourceOpenedAtCompletion);
    assert(!backend->property("bridgeAvailable").toBool());
    ios::IOSInlineDocumentBinding callerBinding;
    assert(callerBinding.bind(backend->inlineDocument(), backend, backend->property("sourceIdentity").toString(),
        backend->url(), backend->scriptUrl()));
    assert(callerBinding.context() == &issuer && callerBinding.current(backend));

    // The actual selected +ios Flickable -> NativeFlickable -> EmbeddedWebView
    // chain must also deliver its descriptor before native completion.
    std::unique_ptr<QObject> nested;
    {
        QQmlComponent nestedComponent(&engine, QUrl::fromLocalFile(iosRoot + "/interface/resources/qml/controls/FlickableWebViewCore.qml"));
        if (!nestedComponent.isReady()) { std::cerr << nestedComponent.errorString().toStdString(); std::abort(); }
        QVariantMap nestedInitial = initial;
        nestedInitial.remove("scriptUrl"); nestedInitial.insert("userScriptUrl", script);
        nested.reset(nestedComponent.createWithInitialProperties(nestedInitial, &issuer));
        if (!nested) { std::cerr << nestedComponent.errorString().toStdString(); std::abort(); }
        auto* nestedWrapper = nested->property("webViewCore").value<QObject*>();
        auto* nestedNative = qobject_cast<IOSWebView*>(nestedWrapper->property("backend").value<QObject*>());
        assert(nestedNative && nestedNative->configuredAtCompletion);
        ios::IOSInlineDocumentBinding nestedBinding;
        assert(nestedBinding.bind(nestedNative->inlineDocument(), nestedNative, identity, source, script));
        assert(nestedBinding.context() == &issuer);
    }
    // An initially undefined native QVariant must remain assignable on the
    // ordinary-page -> inline transition, including an explicit clear first.
    QVariantMap ordinaryInitial = initial;
    ordinaryInitial.insert("url", "https://ordinary.example/page"); ordinaryInitial.remove("inlineDocument");
    std::unique_ptr<QObject> ordinary(sharedWrapper.createWithInitialProperties(ordinaryInitial, &issuer));
    assert(ordinary);
    auto* transitioned = qobject_cast<IOSWebView*>(ordinary->property("backend").value<QObject*>());
    assert(transitioned && !transitioned->configuredAtCompletion && transitioned->sourceOpenedAtCompletion);
    assert(transitioned->_private->policy.active() && !transitioned->_private->inlineMode);
    assert(transitioned->_private->policy.url() == QUrl("https://ordinary.example/page"));
    assert(transitioned->inlineDocument().userType() != qMetaTypeId<web::InlineHtmlDocument>());
    assert(ordinary->setProperty("inlineDocument", QVariant()));
    assert(ordinary->setProperty("inlineDocument", QVariant::fromValue(document)));
    assert(ordinary->setProperty("url", source));
    ios::IOSInlineDocumentBinding transitionBinding;
    assert(transitionBinding.bind(transitioned->inlineDocument(), transitioned, identity, source, script));
    assert(transitioned->openSource() && transitioned->_private->inlineMode);
    const auto oldGeneration = transitioned->_private->generation;
    const auto oldTransport = document.transportURL();
    assert(transitioned->_private->policy.allowsBridge(oldGeneration, oldTransport, true, 1));
    owner.revoke();
    assert(!transitioned->_private->policy.active() && !transitioned->_private->generation);
    assert(ordinary->setProperty("inlineDocument", QVariant()));
    assert(ordinary->setProperty("url", "https://ordinary.example/restored"));
    assert(transitioned->openSource() && !transitioned->_private->inlineMode);
    assert(transitioned->_private->policy.url() == QUrl("https://ordinary.example/restored"));
    assert(!transitioned->_private->policy.allowsBridge(oldGeneration, oldTransport, true, 1));
    // Supplying an opaque empty/stale grant or a forged map/string must never
    // silently downgrade an unauthorized request into ordinary HTTPS policy.
    for (const auto& supplied : {QVariant::fromValue(web::InlineHtmlDocument{}), QVariant::fromValue(document),
            QVariant(QVariantMap{{"token", "forged"}}), QVariant(QString("forged")), QVariant(QString())}) {
        assert(ordinary->setProperty("inlineDocument", supplied));
        assert(!transitioned->openSource());
        assert(!transitioned->_private->policy.active());
    }
    // Both native undefined and the actual QML null carriers remain absence;
    // they permit ordinary HTTPS but never grant data HTML source authority.
    for (const auto& absent : {QVariant(), QVariant::fromValue(nullptr), QVariant::fromValue(static_cast<QObject*>(nullptr)),
            QVariant::fromValue(QJSValue(QJSValue::NullValue)), QVariant::fromValue(QJSValue(QJSValue::UndefinedValue))}) {
        assert(!ios::iosInlineCarrierSupplied(absent));
        assert(ordinary->setProperty("inlineDocument", absent));
        assert(transitioned->openSource() && transitioned->_private->policy.active());
    }
    assert(ordinary->setProperty("url", source));
    assert(!transitioned->openSource() && !transitioned->_private->policy.active());
    std::cout << "PASS actual selected iOS source opening: ordinary HTTPS, inline revocation, absent-carrier restoration and supplied-carrier denial (WK unopened)" << std::endl;
    ordinary.reset(); nested.reset();
    owner.revoke();
    assert(!callerBinding.current(backend));
    surface->setProperty("inlineDocument", QVariant::fromValue(web::InlineHtmlDocument{}));
    assert(!callerBinding.current(backend));
    surface.reset();
    std::cout << "PASS Qt " << qVersion() << " actual inline context ancestry, exact source/charset/bytes, property setters, revocation, epoch and compiled-rule input (WK execution not performed)\n";
}
