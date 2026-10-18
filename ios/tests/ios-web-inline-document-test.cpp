// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Real Qt contexts, production native binding/session/epoch and property bodies.
// UIKit/WK loading, rule compilation, networking and video are NOT simulated.
#include <QGuiApplication>
#include <QQmlComponent>
#include <QQmlEngine>
#include <QQmlAbstractUrlInterceptor>
#include <QQuickItem>
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
class IOSWebView : public QQuickItem {
    Q_OBJECT
#include "production-properties.inc"
public:
    struct Private { QString originalSource, originalScript; QUrl url, scriptUrl; QVariant inlineCarrier; };
    std::unique_ptr<Private> _private { std::make_unique<Private>() };
    int revocations { 0 };
    QString url() const;
    void setUrl(const QString&);
    QString scriptUrl() const;
    void setScriptUrl(const QString&);
    QVariant inlineDocument() const;
    void setInlineDocument(const QVariant&);
    void scheduleOpen() { ++revocations; } // Explicit native lifecycle boundary.
signals:
    void urlChanged();
    void configurationChanged();
    void inlineDocumentChanged();
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

class IOSBackendSelector : public QQmlAbstractUrlInterceptor {
public:
    QString apiRoot, iosRoot;
    QUrl intercept(const QUrl& url, DataType type) override {
        if (type == QmlFile && url == QUrl::fromLocalFile(apiRoot + "/interface/resources/qml/controls/EmbeddedWebBackend.qml")) {
            return QUrl::fromLocalFile(iosRoot + "/interface/resources/qml/controls/+ios/EmbeddedWebBackend.qml");
        }
        return url;
    }
};

int main(int argc, char** argv) {
    QGuiApplication app(argc, argv);
    assert(argc == 3);
    const QString apiRoot = QString::fromLocal8Bit(argv[1]), iosRoot = QString::fromLocal8Bit(argv[2]);
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
    for (const char* name : {"url", "scriptUrl", "inlineDocument"}) {
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
    std::cout << "PASS independent iOS native property/binding/session/epoch/namespace checks" << std::endl;
    document = owner.issue(&issuer, identity, source, script);
    // Execute the exact SHA-bound common wrapper through the real selected
    // iOS backend. The interceptor selects a URL, never copies parent source.
    qmlRegisterType<IOSWebView>("IOSInlineProperties", 1, 0, "NativeProperties");
    qmlRegisterType(QUrl::fromLocalFile(iosRoot + "/ios/tests/qml/InlineNativeBoundary.qml"),
        "Overte.iOS", 1, 0, "IOSWebView");
    IOSBackendSelector selector; selector.apiRoot = apiRoot; selector.iosRoot = iosRoot;
#if QT_VERSION >= QT_VERSION_CHECK(6, 0, 0)
    engine.addUrlInterceptor(&selector);
#else
    engine.setUrlInterceptor(&selector);
#endif
    QQmlComponent sharedWrapper(&engine, QUrl::fromLocalFile(apiRoot + "/interface/resources/qml/controls/EmbeddedWebView.qml"));
    if (!sharedWrapper.isReady()) { std::cerr << sharedWrapper.errorString().toStdString(); std::abort(); }
    QVariantMap initial {{"url", source}, {"scriptUrl", script}, {"sourceIdentity", identity},
        {"inlineDocument", QVariant::fromValue(document)}, {"width", 640}, {"height", 480}};
    std::unique_ptr<QObject> surface(sharedWrapper.createWithInitialProperties(initial, &issuer));
    if (!surface) { std::cerr << sharedWrapper.errorString().toStdString(); std::abort(); }
    auto* backend = qobject_cast<IOSWebView*>(surface->property("backend").value<QObject*>());
    assert(backend && backend->url() == source && backend->scriptUrl() == script);
    assert(!backend->property("bridgeAvailable").toBool());
    ios::IOSInlineDocumentBinding callerBinding;
    assert(callerBinding.bind(backend->inlineDocument(), backend, backend->property("sourceIdentity").toString(),
        backend->url(), backend->scriptUrl()));
    assert(callerBinding.context() == &issuer && callerBinding.current(backend));

    owner.revoke();
    assert(!callerBinding.current(backend));
    surface->setProperty("inlineDocument", QVariant::fromValue(web::InlineHtmlDocument{}));
    assert(!callerBinding.current(backend));
    surface.reset();
#if QT_VERSION >= QT_VERSION_CHECK(6, 0, 0)
    engine.removeUrlInterceptor(&selector);
#else
    engine.setUrlInterceptor(nullptr);
#endif
    std::cout << "PASS Qt " << qVersion() << " actual inline context ancestry, exact source/charset/bytes, property setters, revocation, epoch and compiled-rule input (WK execution not performed)\n";
}
