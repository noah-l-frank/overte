// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#include "InlineHtmlDocument.h"
#include "EmbeddedWebPolicy.h"
#include <QCoreApplication>
#include <QQmlComponent>
#include <QQmlContext>
#include <QQmlEngine>
#include <QJSValue>
#include <QVariantMap>
#include <cassert>
#include <memory>

using namespace overte::web;

int main(int argc, char** argv) {
    QCoreApplication application(argc, argv);
    const QByteArray html = QByteArray::fromStdString(
        "<!doctype html><meta charset=utf-8><style>p{width:100%}</style>"
        "<p>Grüße 日本語 😀</p><input value='edit'><script>window.answer=42;</script>"
        "<video controls src='http://media.invalid/original.mp4'></video>");
    const QString percent = "data:text/html;charset=UTF-8," + QString::fromLatin1(QUrl::toPercentEncoding(QString::fromUtf8(html)));
    auto decoded = InlineHtmlBytes::decode(percent);
    assert(decoded.valid() && decoded.body == html && decoded.charset == "UTF-8");
    const QString base64 = "data:TEXT/HTML;CHARSET=\"UTF-8\";BASE64," + QString::fromLatin1(html.toBase64());
    assert(InlineHtmlBytes::decode(base64).body == html);
    assert(InlineHtmlBytes::decode("data:text/html;base64,PGI%2BYTwvYj4=").body == "<b>a</b>");
    assert(InlineHtmlBytes::decode("data:text/html;base64,TQ").body == "M");
    assert(InlineHtmlBytes::decode("data:text/html;base64, T W%0AE= ").body == "Ma");
    assert(InlineHtmlBytes::decode("data:text/html,Z+?query=yes%23body#fragment").body == "Z+?query=yes#body");
    assert(InlineHtmlBytes::decode("data:text/html,100% literal %zz").body == "100% literal %zz");
    const auto empty = InlineHtmlBytes::decode("data:text/html,");
    assert(empty.valid() && empty.body.isEmpty());
    const auto legacy = InlineHtmlBytes::decode("data:text/html;charset=windows-1252,%E4");
    assert(legacy.valid() && legacy.body == QByteArray(1, char(0xe4)) && legacy.charset == "windows-1252");
    for (const auto& source : {
            "https://example.invalid/page", "file:///private/document.html", "data:text/plain,<b>a</b>",
            "data:text/html", "data:text/html;base64,?", "data:text/html;base64,T", "data:text/html;base64,TQ=",
            "data:text/html;base64,TQ===", "data:text/html;base64,TQ==ignored", "data:text/html;\rcharset=UTF-8,a" }) {
        assert(!InlineHtmlBytes::decode(QString::fromLatin1(source)).valid());
    }
    assert(!InlineHtmlBytes::decode("data:text/html," + QString(InlineHtmlBytes::MAX_SOURCE_BYTES, 'x')).valid());
    const QString prefix = "data:text/html,";
    const auto maximum = prefix + QString(InlineHtmlBytes::MAX_SOURCE_BYTES - prefix.size(), 'x');
    assert(InlineHtmlBytes::decode(maximum).valid());
    assert(!InlineHtmlBytes::decode(prefix + QString(InlineHtmlBytes::MAX_SOURCE_BYTES / 2, QChar(0x20ac))).valid());

    QQmlEngine engine;
    QQmlContext context(engine.rootContext()), otherContext(engine.rootContext());
    const QString identity = "entity-inline-owner";
    InlineHtmlDocumentOwner owner;
    auto document = owner.issue(&context, identity, percent);
    assert(document.currentFor(&context, identity, percent));
    assert(!document.currentFor(&otherContext, identity, percent));
    assert(!document.currentFor(&context, "another-entity", percent));
    assert(!document.currentFor(&context, identity, base64));
    assert(document.bytes() == html && document.sha256() == QCryptographicHash::hash(html, QCryptographicHash::Sha256));
    const auto token = document.token(); const auto revision = document.revision();
    assert(token.size() == 32 && revision > 0);
    auto changedCopy = document.bytes(); changedCopy[0] = 'X'; assert(document.bytes() == html);
    context.setContextProperty("issuedDocument", QVariant::fromValue(document));
    QQmlComponent component(&engine);
    component.setData("import QtQml 2.15\nQtObject { property var forwarded: issuedDocument; "
        "property var forged: ({ token: 'copied', sourceIdentity: 'entity-inline-owner', revision: 1 }) }", QUrl());
    std::unique_ptr<QObject> root(component.create(&context)); assert(root);
    auto forwarded = root->property("forwarded");
    if (forwarded.userType() == qMetaTypeId<QJSValue>()) { forwarded = forwarded.value<QJSValue>().toVariant(); }
    assert(forwarded.userType() == qMetaTypeId<InlineHtmlDocument>());
    assert(forwarded.value<InlineHtmlDocument>().currentFor(&context, identity, percent));
    assert(root->property("forged").userType() != qMetaTypeId<InlineHtmlDocument>());
    assert(!QVariant(QVariantMap { { "token", token } }).value<InlineHtmlDocument>().current());
    assert(document.sourceURL() == percent && document.context() == &context);
    QObject observer;
    int notifications = 0;
    const auto watch = document.onRevoked(&observer, [&] { ++notifications; });
    assert(watch);
    const auto replacement = owner.issue(&context, identity, percent);
    assert(notifications == 1);
    owner.revoke();
    assert(notifications == 1);
    const auto liveReplacement = owner.issue(&context, identity, percent);
    assert(!replacement.current());
    assert(liveReplacement.current() && liveReplacement.revision() > revision && liveReplacement.token() != token);
    assert(!document.current() && !forwarded.value<InlineHtmlDocument>().current());
    assert(!owner.issue(&context, identity, "data:text/html;base64,!").current());
    assert(!liveReplacement.current()); // Invalid replacement cannot keep the previous document alive.
    auto revoked = owner.issue(&context, identity, base64); owner.revoke(); assert(!revoked.current());
    auto dyingContext = std::make_unique<QQmlContext>(engine.rootContext());
    auto contextBound = owner.issue(dyingContext.get(), identity, percent);
    int contextNotifications = 0;
    contextBound.onRevoked(&observer, [&] { ++contextNotifications; });
    assert(contextBound.current()); dyingContext.reset(); assert(!contextBound.current());
    assert(contextNotifications == 1);
    InlineHtmlDocument ownerBound;
    { InlineHtmlDocumentOwner temporary; ownerBound = temporary.issue(&context, identity, percent); assert(ownerBound.current()); }
    assert(!ownerBound.current());
    int ownerNotifications = 0;
    { InlineHtmlDocumentOwner temporary;
      auto value = temporary.issue(&context, identity, percent);
      value.onRevoked(&observer, [&] { ++ownerNotifications; }); }
    assert(ownerNotifications == 1);
    assert(!owner.issue(nullptr, identity, percent).current());
    assert(!owner.issue(&context, "  ", percent).current());
    EmbeddedWebSession ordinary;
    assert(!ordinary.open(QUrl(percent), Surface::WorldEntity, identity));
    assert(!ordinary.allowsScriptURL(QUrl(percent)));
    assert(!ordinary.allowsNavigation(ordinary.generation(), QUrl(percent), true, "GET"));
    {
        const auto source = percent + "#chapter-one";
        auto current = owner.issue(&context, identity, source);
        const auto transport = current.transportURL();
        assert(transport.scheme() == "http" && transport.fragment() == "chapter-one");
        assert(EmbeddedWebSession::isInlineNamespace(transport));
        // Knowing or copying an origin URL is never equivalent to possession
        // of the opaque native-issued document for this exact source/context.
        assert(!ordinary.open(transport, Surface::WorldEntity, identity));
        EmbeddedWebSession session;
        assert(!session.openInline(current, &otherContext, source, Surface::WorldEntity, identity));
        assert(!session.openInline(current, &context, percent, Surface::WorldEntity, identity));
        assert(!session.openInline(current, &context, source, Surface::WorldEntity, "forged-owner"));
        auto generation = session.openInline(current, &context, source, Surface::WorldEntity, identity);
        assert(generation && session.active() && session.inlineDocument());
        assert(session.url() == transport);
        assert(session.allowsInlineResponse(generation, transport, true, "GET"));
        assert(session.allowsInlineResponse(generation, transport, true, "HEAD"));
        assert(!session.allowsInlineResponse(generation, transport, false, "GET"));
        assert(!session.allowsInlineResponse(generation, transport, true, "POST"));
        assert(session.allowsBridge(generation, transport, true, 10));
        assert(!session.allowsBridge(generation, transport, false, 10));
        assert(!session.allowsBridge(generation, transport, true, 0));
        assert(!session.allowsBridge(generation, transport, true, EmbeddedWebSession::MAX_BRIDGE_BYTES + 1));
        auto fragment = transport; fragment.setFragment("chapter-two");
        assert(session.allowsBridge(generation, fragment, true, 10));
        auto otherPath = transport; otherPath.setPath("/unissued.html");
        auto otherQuery = transport; otherQuery.setQuery("unissued=1");
        auto otherScheme = transport; otherScheme.setScheme("https");
        for (const auto& unissued : { otherPath, otherQuery, otherScheme,
                QUrl("http://another.overte-inline.invalid/index.html"),
                QUrl("http://another.overte-inline.invalid./index.html"),
                QUrl("https://overte-inline.invalid/index.html") }) {
            assert(!session.allowsInlineResponse(generation, unissued, true, "GET"));
            assert(!session.allowsNavigation(generation, unissued, true, "GET"));
            assert(!session.allowsBridge(generation, unissued, true, 10));
            assert(!session.allowsScriptURL(unissued));
            assert(!ordinary.open(unissued, Surface::Tablet, identity));
        }
        const QUrl media("http://media.invalid/original.mp4");
        assert(session.allowsNavigation(generation, media, false, "GET"));
        assert(session.allowsNavigation(generation, QUrl("https://remote.invalid/page"), true, "GET"));
        assert(!session.allowsBridge(generation, media, true, 10));
        assert(!session.allowsInlineResponse(generation, media, true, "GET"));
        assert(!session.allowsNavigation(generation, QUrl("file:///private/secret"), false, "GET"));
        assert(!session.allowsNavigation(generation, QUrl("content://private/secret"), false, "GET"));
        session.setVisible(false);
        assert(!session.allowsBridge(generation, transport, true, 10));
        assert(!session.allowsInlineResponse(session.generation(), transport, true, "GET"));
        session.setVisible(true);
        assert(!session.allowsBridge(generation, transport, true, 10));
        generation = session.generation();
        assert(session.allowsBridge(generation, transport, true, 10));
        session.setForeground(false);
        assert(!session.active());
        session.setForeground(true);
        assert(!session.allowsBridge(generation, transport, true, 10));
        generation = session.generation();
        assert(session.allowsBridge(generation, transport, true, 10));
        auto replacement = owner.issue(&context, identity, base64);
        assert(!session.active()); // Native owner revocation is immediate.
        assert(!session.allowsInlineResponse(generation, transport, true, "GET"));
        assert(!session.allowsBridge(generation, transport, true, 10));
        assert(session.openInline(replacement, &context, base64, Surface::Tablet, identity));
        assert(session.open(QUrl("https://remote.invalid/page"), Surface::Tablet, identity));
        assert(!session.inlineDocument());
        assert(!session.allowsInlineResponse(session.generation(), replacement.transportURL(), true, "GET"));
        session.close();
        assert(!session.active());
        const QString script("https://scripts.invalid/source-owned.js");
        auto scripted = owner.issue(&context, identity, source, script);
        assert(!session.openInline(scripted, &context, source, Surface::WorldEntity, identity));
        assert(!session.openInline(scripted, &context, source, Surface::WorldEntity, identity,
                                   "https://scripts.invalid/changed-in-qml.js"));
        assert(session.openInline(scripted, &context, source, Surface::WorldEntity, identity, script));
        assert(scripted.scriptURL() == script);
    }
    qInfo("PASS: actual inline HTML bytes/encoding/bounds, native owner/context/replacement lifetime, opaque QML forwarding, typed session, exact local document response and frame/generation grants; OS interception and device media remain separate");
}
