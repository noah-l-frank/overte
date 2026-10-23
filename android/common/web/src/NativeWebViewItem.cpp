// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#include "NativeWebViewItem.h"
#include <QCoreApplication>
#include <QFile>
#include <QFocusEvent>
#include <QHash>
#include <QInputMethod>
#include <QInputMethodEvent>
#include <QGuiApplication>
#include <QJsonDocument>
#include <QKeyEvent>
#include <QJSEngine>
#include <QMimeDatabase>
#include <QMouseEvent>
#include <QTouchEvent>
#include <QNetworkAccessManager>
#include <QNetworkReply>
#include <QQmlContext>
#include <QQuickWindow>
#include <QSGSimpleTextureNode>
#include <QTimer>
#include <QWheelEvent>
#include <QtQml>
#include <jni.h>
#include <atomic>
#include <cmath>
#include <limits>

namespace {
QMutex registryMutex;
QHash<jlong, NativeWebViewItem*> registry;
QMutex resourceRegistryMutex;
QHash<jlong, std::shared_ptr<overte::android::web::NativeResourceState>> resourceRegistry;
std::shared_ptr<overte::android::web::NativeResourceState> resourceState(jlong handle) {
    QMutexLocker guard(&resourceRegistryMutex); return resourceRegistry.value(handle);
}
jlong nextHandle { 1 };
QStringList packagedRoots;
std::atomic<bool> foreground { false };
std::atomic<JavaVM*> vm { nullptr };
std::atomic<jclass> backend { nullptr };
struct Jni {
    JNIEnv* env { nullptr }; bool attached { false };
    Jni() { auto* machine = vm.load(); if (!machine) return;
        if (machine->GetEnv(reinterpret_cast<void**>(&env), JNI_VERSION_1_6) != JNI_OK) {
            #if defined(Q_OS_ANDROID)
            attached = machine->AttachCurrentThread(&env, nullptr) == JNI_OK;
#else
            attached = machine->AttachCurrentThread(reinterpret_cast<void**>(&env), nullptr) == JNI_OK;
#endif
        }
    }
    ~Jni() { if (attached && vm.load()) vm.load()->DetachCurrentThread(); }
    jstring string(const QString& value) const {
        return env ? env->NewString(reinterpret_cast<const jchar*>(value.utf16()), value.size()) : nullptr;
    }
};
QString string(JNIEnv* env, jstring value) {
    if (!value) return {};
    const auto* text = env->GetStringChars(value, nullptr);
    if (!text) return {};
    QString result = QString::fromUtf16(reinterpret_cast<const ushort*>(text), env->GetStringLength(value));
    env->ReleaseStringChars(value, text); return result;
}
bool call(const char* method, const char* signature, jvalue* args) {
    Jni jni; if (!jni.env || !backend.load()) return false;
    auto id = jni.env->GetStaticMethodID(backend.load(), method, signature);
    if (id) jni.env->CallStaticVoidMethodA(backend.load(), id, args);
    bool valid = id && !jni.env->ExceptionCheck();
    if (jni.env->ExceptionCheck()) jni.env->ExceptionClear();
    return valid;
}
QString resourceText(const QString& path) { QFile file(path); return file.open(QFile::ReadOnly) ? QString::fromUtf8(file.readAll()) : QString(); }
void registerType() { qmlRegisterType<NativeWebViewItem>("Overte.Android", 1, 0, "NativeWebView"); }
}
Q_COREAPP_STARTUP_FUNCTION(registerType)

NativeWebViewItem::NativeWebViewItem(QQuickItem* parent) : QQuickItem(parent),
    _transport(new NativeWebTransport(this)), _bridge(new NativeSurfaceBridge(this)), _channel(new QWebChannel(this)) {
    { QMutexLocker guard(&registryMutex);
      if (nextHandle > 0) { _handle = nextHandle; nextHandle = nextHandle == std::numeric_limits<jlong>::max() ? 0 : nextHandle + 1; registry.insert(_handle, this); } }
    _session.setForeground(foreground.load());
    setFlag(ItemHasContents, true); setFlag(ItemAcceptsInputMethod, true); setAcceptedMouseButtons(Qt::LeftButton); setAcceptHoverEvents(true); setAcceptTouchEvents(true);
    _channel->registerObject("eventBridge", _bridge);
    _channel->registerObject("eventBridgeWrapper", new NativeBridgeWrapper(_bridge, this));
    _channel->connectTo(_transport);
    connect(_bridge, &NativeSurfaceBridge::webEvent, this, &NativeWebViewItem::webEventReceived);
    connect(_transport, &NativeWebTransport::outbound, this, [this](const QJsonObject& message) {
        quint64 grant, page; { QMutexLocker guard(&_mutex); grant = _session.generation(); page = _page; }
        const auto payload = QJsonDocument(message).toJson(QJsonDocument::Compact);
        { QMutexLocker guard(&_mutex); if (!_session.allowsBridge(grant, sourceURL(_document), true, payload.size())) return; }
        const auto data = QString::fromUtf8(QJsonDocument(QJsonArray { QString::number(grant), QString::number(page), message }).toJson(QJsonDocument::Compact));
        evaluate("window.__overteTransport&&window.__overteTransport.receive.apply(null," + data + ");", grant, page);
    });
    connect(this, &QQuickItem::visibleChanged, this, &NativeWebViewItem::synchronizeVisibility);
    connect(this, &QQuickItem::enabledChanged, this, &NativeWebViewItem::synchronizeVisibility);
    connect(this, &QQuickItem::xChanged, this, &NativeWebViewItem::updateGeometry);
    connect(this, &QQuickItem::yChanged, this, &NativeWebViewItem::updateGeometry);
    connect(this, &QQuickItem::scaleChanged, this, &NativeWebViewItem::updateGeometry);
    connect(this, &QQuickItem::rotationChanged, this, &NativeWebViewItem::updateGeometry);
    connect(this, &QQuickItem::transformOriginChanged, this, &NativeWebViewItem::updateGeometry);
    connect(this, &QQuickItem::parentChanged, this, &NativeWebViewItem::trackGeometry);
    trackGeometry();
}
NativeWebViewItem::~NativeWebViewItem() {
    { QMutexLocker guard(&registryMutex); registry.remove(_handle); }
    if (_resourceState) _resourceState->revoke();
    { QMutexLocker guard(&resourceRegistryMutex); resourceRegistry.remove(_handle); }
    { QMutexLocker guard(&_mutex); _session.close(); }
    jvalue args[1]; args[0].j = _handle; call("destroy", "(J)V", args);
}
void NativeWebViewItem::setPackagedResourceRoots(const QStringList& roots) { QMutexLocker guard(&registryMutex); packagedRoots = roots; }
void NativeWebViewItem::setUrl(const QString& value) { if (_url == value) return; _url = value; emit urlChanged(); navigate(); }
void NativeWebViewItem::setInlineDocument(const QVariant& value) {
    _inlineCarrier = value;
    QVariant native = value;
    if (native.userType() == qMetaTypeId<QJSValue>()) native = native.value<QJSValue>().toVariant();
    const auto type = native.userType();
    const bool absent = !native.isValid() || type == QMetaType::Nullptr
        || (type == QMetaType::QObjectStar && native.isNull());
    { QMutexLocker guard(&_mutex);
      _inlineProvided = !absent;
      _inlineDocument = type == qMetaTypeId<overte::web::InlineHtmlDocument>()
          ? native.value<overte::web::InlineHtmlDocument>() : overte::web::InlineHtmlDocument();
      // Publication on Android's UI thread must never observe a new carrier
      // paired with the previous source session or its still-live lease.
      _session.close(); _sourceAuthorized = false;
      if (_inlineLifetime) _inlineLifetime->store(false,std::memory_order_release);
      if (_resourceState) _resourceState->revoke();
    }
    emit inlineDocumentChanged(); navigate();
}
void NativeWebViewItem::setScriptUrl(const QString& value) {
    if (_scriptUrl == value) return; _scriptUrl = value; ++_scriptVersion; cancelSourceScripts(); _injectedPage = 0; emit scriptUrlChanged();
    quint64 grant, page; { QMutexLocker guard(&_mutex); grant = _session.generation(); page = _page; }
    if (_inlineProvided || _url.startsWith("data:", Qt::CaseInsensitive)) { navigate(); return; }
    if (!_loading) injectUserScript(grant, page, QUrl(value));
}
void NativeWebViewItem::setSourceIdentity(const QString& value) { if (_sourceIdentity == value) return; _sourceIdentity = value; emit sourceIdentityChanged(); navigate(); }
void NativeWebViewItem::setSurface(Surface value) { if (_surface == value) return; _surface = value; emit surfaceChanged(); navigate(); }
void NativeWebViewItem::setPresentation(Presentation value) { if (_presentation == value) return; _presentation = value; emit presentationChanged();
    if (_created) { jvalue args[1]; args[0].j = _handle; call("destroy", "(J)V", args); _created = false; } navigate(); }
void NativeWebViewItem::setUseBackground(bool value) { if (_background == value) return; _background = value; emit useBackgroundChanged();
    if (_created) { jvalue args[2]; args[0].j = _handle; args[1].z = value; call("background", "(JZ)V", args); } }
void NativeWebViewItem::setUserAgent(const QString& value) { if (_userAgent == value) return; _userAgent = value; emit userAgentChanged();
    if (_created) { Jni jni; if (!jni.env) return; jstring text = jni.string(value); jvalue args[2]; args[0].j = _handle; args[1].l = text;
        call("userAgent", "(JLjava/lang/String;)V", args); jni.env->DeleteLocalRef(text); } }
void NativeWebViewItem::componentComplete() {
    QQuickItem::componentComplete();
    if (auto* context = qmlContext(this)) {
        if (_bootstrap.isEmpty()) _bootstrap = context->contextProperty("eventBridgeJavaScriptToInject").toString();

    }
    navigate();
}
QString NativeWebViewItem::scriptRoot(const QUrl& source) const {
    QMutexLocker guard(&registryMutex);
    for (const auto& root : packagedRoots) if (overte::web::EmbeddedWebSession::isPackagedURL(source, root)) return root;
    return {};
}
bool NativeWebViewItem::openSourceSession(const QUrl& source, const QString& root) {
    const auto surface = _surface == Tablet ? overte::web::Surface::Tablet : overte::web::Surface::WorldEntity;
    disconnect(_inlineRevocation); disconnect(_resourceRevocation);
    if (_inlineLifetime) _inlineLifetime->store(false,std::memory_order_release);
    _inlineLifetime.reset(); _inlineBytes.clear(); _inlineCharset.clear(); _inlineTransport=QUrl(); _inlineRevision=0;
    if (_inlineProvided) {
        auto* owner = _inlineDocument.context();
        bool descendant = false;
        for (auto* context = qmlContext(this); context; context = context->parentContext()) {
            if (context == owner) { descendant = true; break; }
        }
        if (!descendant || !_inlineDocument.currentFor(owner, _sourceIdentity, _url)
                || _inlineDocument.scriptURL() != _scriptUrl) { _session.close(); return false; }
        _inlineBytes=_inlineDocument.bytes(); _inlineCharset=_inlineDocument.charset();
        _inlineTransport=_inlineDocument.transportURL(); _inlineRevision=_inlineDocument.revision();
        _inlineLifetime=std::make_shared<std::atomic<bool>>(true);
        const auto live=_inlineLifetime;
        _resourceRevocation=_inlineDocument.onRevoked(this,[live] { live->store(false,std::memory_order_release); },Qt::DirectConnection);
        _session.openInline(_inlineDocument, owner, _url, surface, _sourceIdentity, _scriptUrl);
        _inlineRevocation = _inlineDocument.onRevoked(this, [this] { revokeInlineDocument(); }, Qt::AutoConnection);
        return true;
    }
    _session.open(source, surface, _sourceIdentity, root);
    return !_sourceIdentity.trimmed().isEmpty() && (overte::web::EmbeddedWebSession::isNetworkURL(source)
        || overte::web::EmbeddedWebSession::isPackagedURL(source, root));
}
void NativeWebViewItem::cancelSourceScripts() {
    const auto replies = _scriptReplies; _scriptReplies.clear();
    _scriptAttemptGrant = 0; _scriptAttemptPage = 0; _injectedPage = 0;
    for (const auto& reply : replies) if (reply) reply->abort();
}
void NativeWebViewItem::revokeInlineDocument() {
    if (_inlineDocument.current()) return; // A queued previous-owner revoke cannot cancel its replacement.
    { QMutexLocker guard(&_mutex); _session.close(); _image = QImage(); _sourceAuthorized = false; }
    publishResourceSource(); _callbacks.clear(); resetEditor(); ++_scriptVersion; cancelSourceScripts();
    _loading = false; _bridgeAvailable = false; _status = 6;
    jvalue args[1]; args[0].j = _handle; call("revoke", "(J)V", args); call("destroy", "(J)V", args);
    _created = false; _pending = false; update(); emit stateChanged();
}
void NativeWebViewItem::navigate() {
    if (!isComponentComplete()) return;
    _callbacks.clear(); resetEditor(); ++_scriptVersion; cancelSourceScripts();
    { QMutexLocker guard(&_mutex); _image = QImage(); } update();
    if (_created || _pending) { jvalue a[1]; a[0].j = _handle; call("revoke", "(J)V", a); }
    _resumeDocument = QUrl();
    if (_suspendedDocument) { { QMutexLocker guard(&_mutex); _suspendedDocument = false; } _created = false; jvalue a[1]; a[0].j = _handle; call("destroy", "(J)V", a); }
    QUrl source(_url); const auto root = scriptRoot(source); QUrl browser; bool authorized;
    { QMutexLocker guard(&_mutex);
      _mapping = overte::android::web::NativeResourceMapping(root, _handle);
      source = _mapping.canonicalSource(source);
      authorized = openSourceSession(source, root); _sourceAuthorized = authorized;
      _session.setVisible(isVisible() && isEnabled()); _page = 0; _document = QUrl(); browser = _mapping.toBrowser(_session.url()); }
    publishResourceSource();
    if (!authorized) {
        _status = 6; { QMutexLocker guard(&_mutex); _image = QImage(); } update(); emit stateChanged();
        if (_created) {
            Jni jni; if (jni.env) { jstring blank = jni.string("about:blank"); jvalue args[3]; args[0].j = _handle; args[1].j = 0; args[2].l = blank;
                call("load", "(JJLjava/lang/String;)V", args); jni.env->DeleteLocalRef(blank); }
        }
        return;
    }
    if (!generation()) { retryCreation(); return; }
    if (!_created) { _attempts = 0; create(); return; }
    Jni jni; if (!jni.env) return; jstring url = jni.string(browser.toString(QUrl::FullyEncoded));
    jvalue args[3]; args[0].j = _handle; args[1].j = generation(); args[2].l = url;
    call("load", "(JJLjava/lang/String;)V", args); jni.env->DeleteLocalRef(url);
}
void NativeWebViewItem::create() {
    if (_suspendedDocument || !_handle || !isComponentComplete() || _created || _pending || width() <= 1 || height() <= 1 || !isVisible() || !isEnabled()) return;
    Jni jni; if (!jni.env || !backend.load() || !generation()) { retryCreation(); return; }
    QUrl source; { QMutexLocker guard(&_mutex); source = _session.url(); }
    const QString root = scriptRoot(source);
    QUrl browser; { QMutexLocker guard(&_mutex);
        // Each new WebView has a fresh source revision even if its URL is unchanged.
        if (!openSourceSession(_mapping.canonicalSource(QUrl(_url)), root)) return;
        _page = 0; _document = QUrl();
        browser = _resumeDocument.isEmpty() ? _mapping.toBrowser(_session.url()) : _resumeDocument;
    }
    const QString script = resourceText(":/overte/android/web/resources/transport.js") + '\n' + _bootstrap;
    const QString editorScript = resourceText(":/overte/android/web/resources/editor-transport.js") + '\n' + resourceText(":/overte/android/web/resources/editor.js");
    jstring url = jni.string(browser.toString(QUrl::FullyEncoded)), agent = jni.string(_userAgent), bootstrap = jni.string(script);
    if (!url || !agent || !bootstrap) { if (jni.env->ExceptionCheck()) jni.env->ExceptionClear(); retryCreation(); return; }
    jstring editorBootstrap = jni.string(editorScript);
    if (!editorBootstrap) { if (jni.env->ExceptionCheck()) jni.env->ExceptionClear(); jni.env->DeleteLocalRef(url); jni.env->DeleteLocalRef(agent); jni.env->DeleteLocalRef(bootstrap); retryCreation(); return; }
    const auto bounds = sceneBounds().toAlignedRect(), clip = sceneClipBounds().toAlignedRect(); jvalue args[16]; args[0].j = _handle; args[1].j = generation();
    { QMutexLocker guard(&_mutex);
      _creationRevision = args[1].j; _creationIdentity = _sourceIdentity;
      _creationSurface = _surface; _creationPresentation = _presentation; _creationSource = _session.url(); }
    publishResourceSource();
    args[2].l = url; args[3].l = agent;
    args[4].z = _background; args[5].z = _presentation == NativeOverlay; args[6].i = bounds.x(); args[7].i = bounds.y();
    args[8].i = bounds.width(); args[9].i = bounds.height();
    args[10].i = clip.x(); args[11].i = clip.y(); args[12].i = clip.width(); args[13].i = clip.height(); args[14].l = bootstrap;
    args[15].l = editorBootstrap;
    _pending = call("create", "(JJLjava/lang/String;Ljava/lang/String;ZZIIIIIIIILjava/lang/String;Ljava/lang/String;)V", args);
    jni.env->DeleteLocalRef(editorBootstrap);
    jni.env->DeleteLocalRef(url); jni.env->DeleteLocalRef(agent); jni.env->DeleteLocalRef(bootstrap);
    if (!_pending) retryCreation();
}
void NativeWebViewItem::retryCreation() { if (_retryPending) return; if (++_attempts > 30) { _status = 3; emit stateChanged(); return; } _retryPending = true;
    QTimer::singleShot(250, this, [this] { _retryPending = false; create(); }); }
quint64 NativeWebViewItem::generation() const { QMutexLocker guard(&_mutex); const auto value = _session.generation();
    return _session.active() && value <= static_cast<quint64>(std::numeric_limits<jlong>::max()) ? value : 0; }
quint64 NativeWebViewItem::lifecycleRevision() const { QMutexLocker guard(&_mutex);
    const auto value = _session.generation(); return value <= quint64(std::numeric_limits<jlong>::max()) ? value : 0; }
bool NativeWebViewItem::current(quint64 grant, quint64 page) const { return !_suspendedDocument && _session.active() && grant && grant == _session.generation() && page && page == _page; }
QUrl NativeWebViewItem::sourceURL(const QUrl& browser) const { return _mapping.toSource(browser); }
bool NativeWebViewItem::matchesOrigin(const QUrl& document, const QUrl& origin) const {
    if (overte::web::EmbeddedWebSession::sameOrigin(document, origin)) return true;
    const auto transport = _session.url();
    return _inlineProvided && _session.allowsInlineResponse(_session.generation(), document, true, "GET")
        && origin.isValid() && origin.userInfo().isEmpty() && !origin.hasQuery() && !origin.hasFragment()
        && (origin.path().isEmpty() || origin.path() == "/")
        && origin.scheme() == transport.scheme() && origin.host() == transport.host()
        && origin.port(80) == transport.port(80);
}
bool NativeWebViewItem::allowsNavigation(quint64 grant, const QUrl& target, bool mainFrame, const QString& method) const {
    QMutexLocker guard(&_mutex); return _session.allowsNavigation(grant, sourceURL(target), mainFrame, method);
}
bool NativeWebViewItem::allowsBridgeDocument(quint64 grant, quint64 page, const QUrl& document) const {
    QMutexLocker guard(&_mutex);
    return current(grant, page) && sourceURL(document) == sourceURL(_document)
        && _session.allowsBridge(grant, sourceURL(document), true, 1);
}
bool NativeWebViewItem::allowsEditorDocument(quint64 grant, quint64 page, const QUrl& document) const {
    QMutexLocker guard(&_mutex);
    return current(grant, page) && document.adjusted(QUrl::RemoveFragment) == _document.adjusted(QUrl::RemoveFragment)
        && _session.allowsNavigation(grant, sourceURL(document), true, "GET");
}
bool NativeWebViewItem::allowsFileChooser(quint64 grant, quint64 page, const QUrl& document) const {
    QMutexLocker guard(&_mutex);
    return current(grant, page) && sourceURL(document) == sourceURL(_document)
        && _session.allowsNavigation(grant, sourceURL(document), true, "GET");
}
void NativeWebViewItem::acceptPage(quint64 grant, quint64 page, const QUrl& document) {
    QMutexLocker guard(&_mutex);
    if (!_session.allowsNavigation(grant, sourceURL(document), true, "GET") || !page || page <= _page) return;
    _page = page; _document = document;
    QMetaObject::invokeMethod(this, [this] { _callbacks.clear(); resetEditor();
        if (auto* input = QGuiApplication::inputMethod()) input->update(Qt::ImQueryInput); }, Qt::QueuedConnection);
}
bool NativeWebViewItem::acceptMessage(quint64 grant, quint64 page, const QUrl& document, const QUrl& origin,
                                     bool mainFrame, const QString& type, const QByteArray& payload) {
    { QMutexLocker guard(&_mutex);
      if (!current(grant, page) || !mainFrame || payload.isEmpty() || payload.size() > int(overte::web::EmbeddedWebSession::MAX_BRIDGE_BYTES)
          || !matchesOrigin(document, origin)
          || (type == "channel" ? !_session.allowsBridge(grant, sourceURL(document), mainFrame, payload.size())
                                : !_session.allowsNavigation(grant, sourceURL(document), true, "GET"))
          || document.adjusted(QUrl::RemoveFragment) != _document.adjusted(QUrl::RemoveFragment)
          || (type != "channel" && type != "editor")) return false; }
    quint64 inputEpoch; { QMutexLocker guard(&_mutex); inputEpoch = _inputEpoch; if (type == "editor" && !_inputFocused) return false; }
    const auto parsed = QJsonDocument::fromJson(payload); if (!parsed.isObject()) return false;
    if (type == "channel") {
        const auto object = parsed.object(); const int messageType = object.value("type").toInt(-1);
        if (messageType == 6) {
            const auto method = object.value("method");
            const int allowed = _bridge->metaObject()->indexOfMethod("emitWebEvent(QVariant)");
            if (object.value("object").toString() != "eventBridge" || object.value("args").toArray().size() != 1
                || !((method.isDouble() && method.toInt(-1) == allowed) || (method.isString() && method.toString() == "emitWebEvent"))) return false;
        } else if (messageType == 7 || messageType == 8) {
            if (object.value("object").toString() != "eventBridge"
                || object.value("signal").toInt(-1) != _bridge->metaObject()->indexOfSignal("scriptEventReceived(QVariant)")) return false;
        } else if (messageType != 3 && messageType != 4) return false;
    }
    QPointer<NativeWebViewItem> self(this); QMetaObject::invokeMethod(this, [self, grant, page, document, type, inputEpoch, object = parsed.object()] {
        if (!self) return;
        if (type == "editor" ? !self->allowsEditorDocument(grant, page, document) : !self->allowsBridgeDocument(grant, page, document)) return;
        if (type == "editor") { QMutexLocker guard(&self->_mutex); if (!self->_inputFocused || self->_inputEpoch != inputEpoch) return; }
        if (type == "channel") self->_transport->receive(object); else self->updateEditor(object);
    }, Qt::QueuedConnection); return true;
}
void NativeWebViewItem::acceptState(quint64 grant, quint64 page, const QUrl& document, bool loading, bool back, bool forward, bool bridge, int status) {
    QPointer<NativeWebViewItem> self(this); QMetaObject::invokeMethod(this, [self, grant, page, document, loading, back, forward, bridge, status] {
        if (!self) return;
        { QMutexLocker guard(&self->_mutex); if (!self->current(grant, page)) return;
          self->_document = document; self->_currentUrl = self->_inlineProvided
              && document.adjusted(QUrl::RemoveFragment) == self->_inlineDocument.transportURL().adjusted(QUrl::RemoveFragment)
              ? self->_url : self->sourceURL(document).toString();
          self->_bridgeAvailable = bridge && self->_session.allowsBridge(grant, self->sourceURL(document), true, 1); }
        self->_loading = loading; self->_canGoBack = back; self->_canGoForward = forward; self->_status = status;
        if (bridge && !self->_bridgeAvailable) self->_status = 9;
        emit self->stateChanged();
        // A fetch attempted under a suspended grant is not a completed injection.
        // A retained page may publish again with a new grant after resume.
        if (!loading && self->_injectedPage != page
            && (self->_scriptAttemptGrant != grant || self->_scriptAttemptPage != page))
            self->injectUserScript(grant, page, QUrl(self->_scriptUrl));
    }, Qt::QueuedConnection);
}
void NativeWebViewItem::acceptFrame(quint64 grant, quint64 page, const void* pixels, qsizetype bytes, int width, int height) {
    if (!pixels || width <= 0 || height <= 0 || width > 2048 || height > 2048 || bytes < qsizetype(width) * height * 4) return;
    { QMutexLocker guard(&_mutex); if (!current(grant, page)) return; _image = QImage(static_cast<const uchar*>(pixels), width, height, QImage::Format_ARGB32_Premultiplied).copy(); }
    QMetaObject::invokeMethod(this, [this] { update(); }, Qt::QueuedConnection);
}
void NativeWebViewItem::acceptCreated(bool created, quint64 revision) {
    QPointer<NativeWebViewItem> self(this); QMetaObject::invokeMethod(this, [self, created, revision] {
        if (!self || revision != self->_creationRevision) return;
        self->_pending = false;
        bool sameSource; { QMutexLocker guard(&self->_mutex);
            sameSource = self->_creationSource == self->_session.url() && self->_creationIdentity == self->_sourceIdentity
                && self->_creationSurface == self->_surface && self->_creationPresentation == self->_presentation; }
        if (!sameSource) {
            self->_created = false;
            { QMutexLocker guard(&self->_mutex); self->_suspendedDocument = false; }
            jvalue args[2]; args[0].j = self->_handle; args[1].j = revision; call("destroyExpected", "(JJ)V", args);
            if (self->generation()) self->create();
            return;
        }
        self->_created = created;
        if (created) { self->_injectedPage = 0; self->_attempts = 0; self->updateGeometry(); self->synchronizeVisibility(); self->_resumeDocument = QUrl(); }
        else if (!self->_suspendedDocument && self->generation()) self->retryCreation();
        if (!created) { self->_canGoBack = false; self->_canGoForward = false; }
    }, Qt::QueuedConnection);
}
void NativeWebViewItem::acceptSuspended(quint64 revision, const QUrl& document, bool back, bool forward, quint64 birth) {
    QPointer<NativeWebViewItem> self(this); QMetaObject::invokeMethod(this, [self, revision, document, back, forward, birth] {
        if (!self || birth != self->_creationRevision || !self->_sourceAuthorized || self->lifecycleRevision() != revision) return;
        { QMutexLocker guard(&self->_mutex); self->_suspendedDocument = true; } self->_loading = false; self->_bridgeAvailable = false;
        self->_resumeDocument = document;
        self->_currentUrl = self->_inlineProvided && document.adjusted(QUrl::RemoveFragment) == self->_inlineDocument.transportURL().adjusted(QUrl::RemoveFragment)
            ? self->_url : document.toString(); self->_canGoBack = back; self->_canGoForward = forward;
        self->_status = 10; self->_callbacks.clear(); self->resetEditor();
        { QMutexLocker guard(&self->_mutex); self->_image = QImage(); }
        self->update(); emit self->stateChanged();
    }, Qt::QueuedConnection);
}
void NativeWebViewItem::requestResume(quint64 revision, const QUrl& document, quint64 birth) {
    QPointer<NativeWebViewItem> self(this); QMetaObject::invokeMethod(this, [self, revision, document, birth] {
        if (!self || birth != self->_creationRevision || !self->_suspendedDocument || self->lifecycleRevision() != revision || !self->generation()
            || !self->allowsNavigation(revision, document, true, "GET")) return;
        QUrl source; { QMutexLocker guard(&self->_mutex); source = self->_session.url(); }
        const QString root = self->scriptRoot(source);
        { QMutexLocker guard(&self->_mutex);
            if (!self->openSourceSession(self->_mapping.canonicalSource(QUrl(self->_url)), root)) return;
            self->_page = 0; self->_document = QUrl(); self->_suspendedDocument = false;
        }
        self->_callbacks.clear(); self->_resumeDocument = document; self->_created = false;
        self->_status = 0; self->_loading = true; emit self->stateChanged();
        self->create();
    }, Qt::QueuedConnection);
}
void NativeWebViewItem::acceptInputFocus(quint64 revision, quint64 birth, bool focused) {
    quint64 epoch;
    { QMutexLocker guard(&_mutex);
      if (!revision || birth != _creationRevision || revision != _session.generation()) return;
      if (_inputEpoch == std::numeric_limits<quint64>::max()) focused = false;
      else ++_inputEpoch;
      _inputFocused = focused; epoch = _inputEpoch;
    }
    if (!focused) {
        QPointer<NativeWebViewItem> self(this); QMetaObject::invokeMethod(this, [self, epoch] {
            if (!self) return;
            { QMutexLocker guard(&self->_mutex); if (self->_inputEpoch != epoch || self->_inputFocused) return; }
            self->_pressed = false; self->_touchId = -1; self->resetEditor();
            if (auto* input = QGuiApplication::inputMethod()) { input->update(Qt::ImQueryInput); input->hide(); }
        }, Qt::QueuedConnection);
    }
}
void NativeWebViewItem::acceptForeground(bool active) {
    { QMutexLocker guard(&_mutex); _session.setForeground(active); }
    publishResourceSource();
    if (!active) QMetaObject::invokeMethod(this, [this] { _callbacks.clear(); _bridgeAvailable = false; _loading = false; emit stateChanged(); resetEditor();
        if (auto* input = QGuiApplication::inputMethod()) { input->update(Qt::ImQueryInput); input->hide(); } }, Qt::QueuedConnection);
    if (active) QMetaObject::invokeMethod(this, [this] { if (!_created) create(); }, Qt::QueuedConnection);
}
void NativeWebViewItem::publishResourceSource() {
    QMutexLocker guard(&_mutex);
    const auto grant = _session.active() && _sourceAuthorized ? _session.generation() : 0;
    if (_resourceState && _resourceGrant == grant && _resourceCreation == _creationRevision && _resourceState->active()) return;
    if (_resourceState) _resourceState->revoke();
    _resourceState.reset(); _resourceGrant = grant; _resourceCreation = _creationRevision;
    if (grant && _creationRevision) {
        overte::android::web::NativeResourceSource source;
        source.grant = grant; source.creation = _creationRevision; source.mapping = _mapping;
        if (_inlineProvided && _inlineLifetime && _inlineLifetime->load(std::memory_order_acquire)) {
            source.inlineURL=_inlineTransport; source.bytes=_inlineBytes; source.charset=_inlineCharset;
            source.revision=_inlineRevision; source.ownerValid=_inlineLifetime;
        }
        _resourceState = std::make_shared<overte::android::web::NativeResourceState>(std::move(source));
    }
    QMutexLocker resources(&resourceRegistryMutex);
    if (_resourceState) resourceRegistry.insert(_handle, _resourceState);
    else resourceRegistry.remove(_handle);
}
void NativeWebViewItem::synchronizeVisibility() {
    quint64 grant; { QMutexLocker guard(&_mutex); _session.setVisible(isVisible() && isEnabled()); grant = _session.generation(); }
    publishResourceSource();
    if (!isVisible() || !isEnabled()) { _callbacks.clear(); _bridgeAvailable = false; resetEditor(); emit stateChanged(); }
    if (!_created) { create(); return; } jvalue args[3]; args[0].j = _handle; args[1].j = grant; args[2].z = isVisible() && isEnabled();
    call("visibility", "(JJZ)V", args);
}
void NativeWebViewItem::trackGeometry() {
    for (const auto& connection : _geometryConnections) disconnect(connection); _geometryConnections.clear();
    for (auto* ancestor = parentItem(); ancestor; ancestor = ancestor->parentItem()) {
        _geometryConnections.push_back(connect(ancestor, &QQuickItem::xChanged, this, &NativeWebViewItem::updateGeometry));
        _geometryConnections.push_back(connect(ancestor, &QQuickItem::yChanged, this, &NativeWebViewItem::updateGeometry));
        _geometryConnections.push_back(connect(ancestor, &QQuickItem::scaleChanged, this, &NativeWebViewItem::updateGeometry));
        _geometryConnections.push_back(connect(ancestor, &QQuickItem::rotationChanged, this, &NativeWebViewItem::updateGeometry));
        _geometryConnections.push_back(connect(ancestor, &QQuickItem::widthChanged, this, &NativeWebViewItem::updateGeometry));
        _geometryConnections.push_back(connect(ancestor, &QQuickItem::heightChanged, this, &NativeWebViewItem::updateGeometry));
        _geometryConnections.push_back(connect(ancestor, &QQuickItem::clipChanged, this, &NativeWebViewItem::updateGeometry));
        _geometryConnections.push_back(connect(ancestor, &QQuickItem::transformOriginChanged, this, &NativeWebViewItem::updateGeometry));
        _geometryConnections.push_back(connect(ancestor, &QQuickItem::parentChanged, this, &NativeWebViewItem::trackGeometry));
    }
    updateGeometry();
}
QRectF NativeWebViewItem::sceneClipBounds() const {
    auto bounds = sceneBounds();
    for (auto* ancestor = parentItem(); ancestor; ancestor = ancestor->parentItem()) {
        if (ancestor->clip()) bounds = bounds.intersected(ancestor->mapRectToScene(ancestor->boundingRect()));
    }
    return bounds;
}
void NativeWebViewItem::updateGeometry() { if (!_created) { create(); return; }
    const auto bounds = sceneBounds().toAlignedRect(), clip = sceneClipBounds().toAlignedRect();
    jvalue args[9]; args[0].j = _handle; args[1].i = bounds.x(); args[2].i = bounds.y(); args[3].i = bounds.width(); args[4].i = bounds.height();
    args[5].i = clip.x(); args[6].i = clip.y(); args[7].i = clip.width(); args[8].i = clip.height();
    call("resize", "(JIIIIIIII)V", args); }
void NativeWebViewItem::geometryChanged(const QRectF& geometry, const QRectF& old) { QQuickItem::geometryChanged(geometry, old); updateGeometry(); }
QSGNode* NativeWebViewItem::updatePaintNode(QSGNode* old, UpdatePaintNodeData*) {
    auto* node = static_cast<QSGSimpleTextureNode*>(old); if (_presentation == NativeOverlay) { delete node; return nullptr; }
    QImage frame; { QMutexLocker guard(&_mutex); frame = _image; } if (frame.isNull() || !window()) { delete node; return nullptr; }
    if (!node) node = new QSGSimpleTextureNode;
    auto* previous = node->texture(); node->setOwnsTexture(false); node->setTexture(window()->createTextureFromImage(frame)); node->setOwnsTexture(true); delete previous; node->setRect(boundingRect()); return node;
}
bool NativeWebViewItem::evaluate(const QString& script, quint64 grant, quint64 page) {
    { QMutexLocker guard(&_mutex); if (!current(grant, page) || !_session.allowsBridge(grant, sourceURL(_document), true, 1)) return false; }
    Jni jni; if (!jni.env || !backend.load()) return false; auto text = jni.string(script);
    if (!text) { if (jni.env->ExceptionCheck()) jni.env->ExceptionClear(); return false; } jvalue args[4]; args[0].j = _handle; args[1].j = grant; args[2].j = page; args[3].l = text;
    const auto posted = call("evaluate", "(JJJLjava/lang/String;)V", args); jni.env->DeleteLocalRef(text); return posted;
}
bool NativeWebViewItem::emitScriptEvent(const QVariant& message) {
    const auto bytes = QJsonDocument(QJsonArray { QJsonValue::fromVariant(message) }).toJson(QJsonDocument::Compact).size();
    { QMutexLocker guard(&_mutex); if (!_session.allowsBridge(_session.generation(), sourceURL(_document), true, bytes)) return false; }
    _bridge->forwardScriptEvent(message); return true;
}
bool NativeWebViewItem::runJavaScript(const QString& source, const QJSValue& callback) {
    quint64 grant, page; { QMutexLocker guard(&_mutex); grant = _session.generation(); page = _page;
        if (!current(grant, page) || !_session.allowsBridge(grant, sourceURL(_document), true, 1)) return false; }
    if (source.toUtf8().size() > 1024 * 1024 || _callbacks.size() >= 32 || !_nextRequest) return false;
    if (!callback.isCallable()) return evaluate(source, grant, page);
    Jni jni; if (!jni.env || !backend.load()) return false;
    const auto request = _nextRequest; _nextRequest = request == quint64(std::numeric_limits<jlong>::max()) ? 0 : request + 1;
    auto text = jni.string(source); if (!text) { if (jni.env->ExceptionCheck()) jni.env->ExceptionClear(); return false; }
    jvalue args[5]; args[0].j = _handle; args[1].j = grant; args[2].j = page; args[3].j = request; args[4].l = text;
    _callbacks.insert(request, callback); const bool posted = call("evaluateResult", "(JJJJLjava/lang/String;)V", args); jni.env->DeleteLocalRef(text);
    if (!posted) { _callbacks.remove(request); return false; }
    QTimer::singleShot(10000, this, [this, grant, page, request] {
        auto expired = _callbacks.take(request);
        { QMutexLocker guard(&_mutex); if (!current(grant, page)) return; }
        if (expired.isCallable()) expired.call({ QJSValue(QJSValue::UndefinedValue) });
    }); return true;
}
void NativeWebViewItem::acceptResult(quint64 grant, quint64 page, quint64 request, const QByteArray& json) {
    if (json.size() > int(overte::web::EmbeddedWebSession::MAX_BRIDGE_BYTES)) return;
    QPointer<NativeWebViewItem> self(this); QMetaObject::invokeMethod(this, [self, grant, page, request, json] {
        if (!self) return; { QMutexLocker guard(&self->_mutex); if (!self->current(grant, page)) return; }
        auto callback = self->_callbacks.take(request); if (!callback.isCallable()) return;
        const auto parsed = QJsonDocument::fromJson('[' + json + ']'); auto* engine = qjsEngine(self);
        QJSValue result(QJSValue::UndefinedValue);
        if (engine && parsed.isArray() && parsed.array().size() == 1) result = parsed.array()[0].isNull() ? QJSValue(QJSValue::NullValue) : engine->toScriptValue(parsed.array()[0].toVariant());
        callback.call({ result });
    }, Qt::QueuedConnection);
}
void NativeWebViewItem::stop() { jvalue args[1]; args[0].j = _handle; call("stop", "(J)V", args); }
void NativeWebViewItem::reload() { if (_suspendedDocument) { requestResume(lifecycleRevision(), _resumeDocument.isEmpty() ? QUrl(_currentUrl) : _resumeDocument, _creationRevision); return; } jvalue args[1]; args[0].j = _handle; call("reload", "(J)V", args); }
void NativeWebViewItem::goForward() { jvalue args[1]; args[0].j = _handle; call("goForward", "(J)V", args); }
void NativeWebViewItem::reloadAndBypassCache() { if (_suspendedDocument) { reload(); return; } jvalue args[1]; args[0].j = _handle; call("reloadAndBypassCache", "(J)V", args); }
void NativeWebViewItem::unfocus() { setFocus(false); resetEditor(); jvalue args[2]; args[0].j = _handle; args[1].z = false; call("focus", "(JZ)V", args); }
void NativeWebViewItem::openNative() { jvalue args[1]; args[0].j = _handle; call("openNative", "(J)V", args); }
void NativeWebViewItem::goBack() { jvalue args[1]; args[0].j = _handle; call("goBack", "(J)V", args); }
void NativeWebViewItem::pointer(int action, const QPointF& position) {
    // Java maps the requested scene size to its density and capped texture.
    // Using the captured image size here would apply the texture cap twice.
    const auto sceneSize = sceneBounds().size();
    QPointF pixel = position;
    if (width() > 0 && height() > 0) {
        pixel = QPointF(position.x() * sceneSize.width() / width(), position.y() * sceneSize.height() / height());
    }
    jvalue args[4]; args[0].j = _handle; args[1].i = action; args[2].f = pixel.x(); args[3].f = pixel.y(); call("pointer", "(JIFF)V", args);
}
void NativeWebViewItem::touchEvent(QTouchEvent* event) {
    if (event->type() == QEvent::TouchCancel) {
        touchUngrabEvent(); event->accept(); return;
    }
    // World surfaces retain a stationary point while hovering. A subsequent
    // press can therefore arrive as TouchUpdate, and hover alone is no press.
    for (const auto& point : event->touchPoints()) {
        if (point.state() != Qt::TouchPointPressed) continue;
        if (event->type() != QEvent::TouchBegin && _touchId >= 0 && point.id() != _touchId) continue;
        if (_pressed) pointer(3, {});
        _touchId = point.id();
        forceActiveFocus(Qt::MouseFocusReason);
        _pressed = true;
        pointer(0, point.pos());
        event->accept(); return;
    }
    if (_touchId < 0 || !_pressed) { event->ignore(); return; }
    for (const auto& point : event->touchPoints()) {
        if (point.id() != _touchId) continue;
        if (point.state() == Qt::TouchPointReleased || event->type() == QEvent::TouchEnd) {
            pointer(1, point.pos()); _pressed = false; _touchId = -1;
        } else if (point.state() == Qt::TouchPointMoved) {
            pointer(2, point.pos());
        }
        event->accept(); return;
    }
    touchUngrabEvent(); event->accept();
}
void NativeWebViewItem::touchUngrabEvent() {
    if (_touchId >= 0 && _pressed) pointer(3, {});
    _touchId = -1; _pressed = false;
}
void NativeWebViewItem::mousePressEvent(QMouseEvent* event) { forceActiveFocus(Qt::MouseFocusReason); if (_pressed) pointer(3, {}); _pressed = true; pointer(0, event->localPos()); event->accept(); }
void NativeWebViewItem::mouseMoveEvent(QMouseEvent* event) { if (!_pressed) { event->ignore(); return; } pointer(2, event->localPos()); event->accept(); }
void NativeWebViewItem::mouseReleaseEvent(QMouseEvent* event) { if (!_pressed) { event->ignore(); return; } pointer(1, event->localPos()); _pressed = false; event->accept(); }
void NativeWebViewItem::mouseUngrabEvent() { if (_pressed) { pointer(3, {}); _pressed = false; } }
void NativeWebViewItem::hoverEnterEvent(QHoverEvent* event) { pointer(9, event->posF()); event->accept(); }
void NativeWebViewItem::hoverMoveEvent(QHoverEvent* event) { pointer(7, event->posF()); event->accept(); }
void NativeWebViewItem::hoverLeaveEvent(QHoverEvent* event) { pointer(10, event->posF()); event->accept(); }
void NativeWebViewItem::wheelEvent(QWheelEvent* event) {
    event->ignore();
    const auto position = event->position();
    if (!isVisible() || !isEnabled() || !boundingRect().contains(position) || width() <= 0 || height() <= 0) return;
    quint64 grant, page; QUrl document;
    { QMutexLocker guard(&_mutex);
      if (!_inputFocused) return;
      grant = _session.generation(); page = _page; document = _document;
    }
    // Scrolling is private document input, independent of source EventBridge
    // authority and of whether a text editor currently has focus.
    if (!allowsEditorDocument(grant, page, document)) return;
    Jni jni; if (!jni.env || !backend.load()) return;
    const auto size = sceneBounds().size();
    const qreal sx = size.width() / width(), sy = size.height() / height();
    const auto pixel = event->pixelDelta(), angle = event->angleDelta();
    jstring url = jni.string(document.toString(QUrl::FullyEncoded)); if (!url) return;
    jvalue args[11]; args[0].j = _handle; args[1].j = grant; args[2].j = page; args[3].l = url;
    args[4].f = position.x() * sx; args[5].f = position.y() * sy;
    args[6].f = pixel.x() * sx; args[7].f = pixel.y() * sy;
    args[8].f = angle.x(); args[9].f = angle.y(); args[10].z = !pixel.isNull();
    if (call("wheel", "(JJJLjava/lang/String;FFFFFFZ)V", args)) event->accept();
    jni.env->DeleteLocalRef(url);
}
bool NativeWebViewItem::editorCommand(const QJsonObject& command) {
    if (!_editorActive || !hasActiveFocus() || _editorSequence >= 9007199254740991ULL
            || _pendingEditorCommands.size() >= 4096) return false;
    quint64 grant, page; QUrl document;
    { QMutexLocker guard(&_mutex); grant = _session.generation(); page = _page; document = _document; }
    if (!allowsEditorDocument(grant, page, document)) return false;
    Jni jni; if (!jni.env || !backend.load()) return false;
    const auto sequence = ++_editorSequence;
    auto packet = command;
    packet["editor"] = QString::number(_editorOwner); packet["sequence"] = double(sequence);
    jstring url = jni.string(document.toString(QUrl::FullyEncoded));
    jstring data = jni.string(QString::fromUtf8(QJsonDocument(packet).toJson(QJsonDocument::Compact)));
    bool sent = false;
    if (url && data) { jvalue args[5]; args[0].j = _handle; args[1].j = grant; args[2].j = page; args[3].l = url; args[4].l = data;
        sent = call("edit", "(JJJLjava/lang/String;Ljava/lang/String;)V", args); }
    if (jni.env->ExceptionCheck()) { jni.env->ExceptionClear(); sent = false; }
    if (url) jni.env->DeleteLocalRef(url); if (data) jni.env->DeleteLocalRef(data);
    if (!sent) return false;
    auto pending = command;
    if (_sensitive) {
        // Retain only lengths for reconciliation, never typed password contents.
        for (const auto* name : {"text", "commit", "preedit"}) {
            if (pending.contains(name)) pending[name] = QString(pending.value(name).toString().size(), QChar(0x2022));
        }
    }
    _pendingEditorCommands.append(qMakePair(sequence, pending));
    applyPendingEditorCommand(pending);
    return true;
}
void NativeWebViewItem::applyPendingEditorCommand(const QJsonObject& command) {
    const auto action = command.value("action").toString();
    if (action == "point") return; // Only browser layout can resolve a pointer position.
    auto boundary = [](const QString& text, int index) {
        return index >= 0 && index <= text.size() && !(index > 0 && index < text.size()
            && text.at(index - 1).isHighSurrogate() && text.at(index).isLowSurrogate());
    };
    int start = qMin(_cursor, _anchor), end = qMax(_cursor, _anchor);
    QString insertion;
    if (action == "ime") {
        insertion = command.value("commit").toString();
        const bool hasPreedit = !command.value("preedit").toString().isEmpty();
        // Qt can update just its selection. An empty update is not a request
        // to replace the selected text with an empty string.
        if (!insertion.isEmpty() || hasPreedit || _editorComposing || command.value("replaceLength").toInt() > 0) {
            auto base = _editorText; base.remove(start, end - start);
            start += command.value("replaceStart").toInt(); end = start + command.value("replaceLength").toInt();
            if (!boundary(base, start) || !boundary(base, end) || start > end) return;
            base.replace(start, end - start, insertion); _editorText = base;
            _cursor = _anchor = start + insertion.size();
            _editorComposing = hasPreedit;
        }
        const auto selected = command.value("selection").toObject();
        if (!selected.isEmpty()) {
            const int position = selected.value("start").toInt() - _surroundingStart;
            const int focus = position + selected.value("length").toInt();
            if (boundary(_editorText, position) && (_editorComposing || boundary(_editorText, focus))) {
                _anchor = position; _cursor = _editorComposing ? position : focus;
            }
        }
    } else if (action == "left" || action == "right" || action == "home" || action == "end") {
        int next = _cursor;
        if (action == "home") next = next > 0 ? _editorText.lastIndexOf('\n', next - 1) + 1 : 0;
        else if (action == "end") { next = _editorText.indexOf('\n', next); if (next < 0) next = _editorText.size(); }
        else {
            const int direction = action == "left" ? -1 : 1;
            next = qBound(0, next + direction, _editorText.size());
            if (!boundary(_editorText, next)) next += direction;
        }
        if (!command.value("extend").toBool()) _anchor = next;
        _cursor = next; _editorComposing = false;
    } else {
        if (action == "enter") {
            if (_editorComposing || (_editorKind != "textarea" && _editorKind != "contenteditable")) return;
            insertion = "\n";
        } else if (action == "backspace") {
            if (start == end && start > 0) { --start; if (!boundary(_editorText, start)) --start; }
        } else if (action == "delete") {
            if (start == end && end < _editorText.size()) { ++end; if (!boundary(_editorText, end)) ++end; }
        } else insertion = command.value("text").toString();
        if (!boundary(_editorText, start) || !boundary(_editorText, end)) return;
        _editorText.replace(start, end - start, insertion); _cursor = _anchor = start + insertion.size();
        _editorComposing = false;
    }
    // Match the browser's bounded surrounding-text window without dropping new input.
    if (_editorText.size() > 16384) {
        int first = qMax(0, _cursor - 8192);
        if (!boundary(_editorText, first)) --first;
        int last = qMin(_editorText.size(), first + 16384);
        if (!boundary(_editorText, last)) --last;
        _editorText = _editorText.mid(first, last - first); _surroundingStart += first;
        _cursor -= first; _anchor = qBound(0, _anchor - first, _editorText.size());
    }
}
bool NativeWebViewItem::moveInputCursorToPoint(const QPointF& position, int handle) {
    if (_presentation != Texture || !_editorActive || !hasActiveFocus() || !isVisible() || !isEnabled()
            || width() <= 0 || height() <= 0 || !std::isfinite(position.x()) || !std::isfinite(position.y())
            || handle < 1 || handle > 3 || (handle != 1 && _cursor == _anchor)) return false;
    QSize imageSize;
    quint64 grant, page; QUrl document;
    { QMutexLocker guard(&_mutex); imageSize = _image.size(); grant = _session.generation(); page = _page; document = _document; }
    if (imageSize.isEmpty()) return false;
    if (!allowsEditorDocument(grant, page, document)) return false;
    const QPointF css(position.x() * imageSize.width() / width(), position.y() * imageSize.height() / height());
    if (!std::isfinite(css.x()) || !std::isfinite(css.y()) || !_editorRect.contains(css)) return false;
    // Finish the IME's old composition before requesting an asynchronous DOM
    // selection. The caller leaves the positional QVariant invalid so Qt does
    // not send a stale synchronous selection over the browser's later result.
    if (auto* input = QGuiApplication::inputMethod()) input->commit();
    editorCommand({{"action", "point"}, {"x", css.x()}, {"y", css.y()}, {"handle", handle}});
    return true;
}
void NativeWebViewItem::keyPressEvent(QKeyEvent* event) {
    if (!_editorActive || (event->modifiers() & (Qt::ControlModifier | Qt::AltModifier | Qt::MetaModifier))) { event->ignore(); return; }
    QJsonObject command;
    if (event->key() == Qt::Key_Return || event->key() == Qt::Key_Enter)
        command = {{"action", "enter"}, {"shift", bool(event->modifiers() & Qt::ShiftModifier)}};
    else if (event->key() == Qt::Key_Backspace) command = {{"action", "backspace"}};
    else if (event->key() == Qt::Key_Delete) command = {{"action", "delete"}};
    else if (event->key() == Qt::Key_Left || event->key() == Qt::Key_Right || event->key() == Qt::Key_Home || event->key() == Qt::Key_End) {
        const auto action = event->key() == Qt::Key_Left ? "left" : event->key() == Qt::Key_Right ? "right" : event->key() == Qt::Key_Home ? "home" : "end";
        command = {{"action", action}, {"extend", bool(event->modifiers() & Qt::ShiftModifier)}};
    }
    else if (!event->text().isEmpty()) command = {{"text", event->text()}}; else { event->ignore(); return; }
    if (editorCommand(command)) event->accept(); else event->ignore();
}
void NativeWebViewItem::inputMethodEvent(QInputMethodEvent* event) {
    if (!_editorActive || !hasActiveFocus() || event->commitString().size() > 16384 || event->preeditString().size() > 16384) { event->ignore(); return; }
    QJsonObject command {{"action", "ime"}, {"commit", event->commitString()}, {"preedit", event->preeditString()},
        {"replaceStart", event->replacementStart()}, {"replaceLength", event->replacementLength()}, {"cursor", event->preeditString().size()}};
    for (const auto& attribute : event->attributes()) {
        if (attribute.type == QInputMethodEvent::Cursor) command["cursor"] = qBound(0, attribute.start, event->preeditString().size());
        if (attribute.type == QInputMethodEvent::Selection) command["selection"] = QJsonObject {{"start", _surroundingStart + attribute.start}, {"length", attribute.length}};
    }
    if (_pendingEditorCommands.isEmpty() && !_editorComposing && event->commitString().isEmpty() && event->preeditString().isEmpty()
            && event->replacementLength() == 0 && !command.contains("selection")) {
        // Nothing changes in the real Qt editor contract. Do not manufacture
        // DOM input events or consume a pending-command slot for this update.
        // A page can reject an earlier pending commit; retain its following
        // finish event until the actual composition state is acknowledged.
        event->accept(); return;
    }
    if (editorCommand(command)) event->accept(); else event->ignore();
}
void NativeWebViewItem::resetEditor() {
    const bool changed = _editorActive; _editorActive = false; _editorText.clear();
    _editorComposing = false; _editorOwner = _editorAcknowledged = 0; _pendingEditorCommands.clear();
    _cursorRect = _anchorRect = _editorRect = {};
    if (changed) { emit editorStateChanged(); emit editorFocusChanged(false, false, false); }
}
void NativeWebViewItem::updateEditor(const QJsonObject& state) {
    const auto previousOwner = _editorOwner;
    const auto previousKind = _editorKind;
    const bool active = state.value("active").toBool();
    const auto owner = state.value("editor").toString().toULongLong();
    if (state.contains("editor") && (!owner || owner > 9007199254740991ULL
            || state.value("editor").toString() != QString::number(owner))) return;
    if (state.contains("sequence") && !state.value("sequence").isDouble()) return;
    const double rawSequence = state.value("sequence").toDouble();
    if (!std::isfinite(rawSequence) || rawSequence < 0 || rawSequence > double(_editorSequence)
            || std::floor(rawSequence) != rawSequence) return;
    const auto acknowledged = quint64(rawSequence);
    if (active && ((_editorOwner && owner && owner < _editorOwner)
            || (owner == _editorOwner && acknowledged < _editorAcknowledged))) return;
    if (!active || owner != _editorOwner) _pendingEditorCommands.clear();
    _editorOwner = active ? owner : 0; _editorAcknowledged = acknowledged;
    while (!_pendingEditorCommands.isEmpty() && _pendingEditorCommands.first().first <= acknowledged)
        _pendingEditorCommands.removeFirst();
    const bool previousActive = editorFocused(), previousNumeric = editorNumeric(), previousPassword = editorPassword();
    _editorActive = state.value("active").toBool(); _sensitive = state.value("sensitive").toBool();
    // Qt's input connection needs matching surrounding length and selection,
    // even for passwords. Retain only mask characters, never the DOM contents.
    _editorText = _sensitive ? QString(qBound(0, state.value("length").toInt(), 16384), QChar(0x2022)) :
        state.value("text").toString().left(16384);
    _cursor = qBound(0, state.value("cursor").toInt(), _editorText.size()); _anchor = qBound(0, state.value("anchor").toInt(), _editorText.size());
    _surroundingStart = qMax(0, state.value("absoluteCursor").toInt() - state.value("cursor").toInt());
    _editorKind = state.value("kind").toString();
    _editorComposing = state.value("composing").toBool();
    for (auto& pending : _pendingEditorCommands) {
        if (_sensitive) {
            for (const auto* name : {"text", "commit", "preedit"}) {
                if (pending.second.contains(name)) pending.second[name] = QString(pending.second.value(name).toString().size(), QChar(0x2022));
            }
        }
        applyPendingEditorCommand(pending.second);
    }
    const auto rectangle = [](const QJsonObject& object) {
        const qreal x = object.value("x").toDouble(std::numeric_limits<double>::quiet_NaN());
        const qreal y = object.value("y").toDouble(std::numeric_limits<double>::quiet_NaN());
        const qreal w = object.value("width").toDouble(), h = object.value("height").toDouble();
        if (!std::isfinite(x) || !std::isfinite(y) || !std::isfinite(w) || !std::isfinite(h)
                || !std::isfinite(x + w) || !std::isfinite(y + h) || w <= 0 || h <= 0) return QRectF();
        return QRectF(x, y, w, h);
    };
    _editorRect = rectangle(state);
    _cursorRect = rectangle(state.value("caret").toObject());
    _anchorRect = rectangle(state.value("anchorCaret").toObject());
    if (_cursorRect.isEmpty()) _cursorRect = _editorRect;
    if (_anchorRect.isEmpty()) _anchorRect = _cursorRect;
    if (previousActive != editorFocused() || previousNumeric != editorNumeric() || previousPassword != editorPassword()) {
        emit editorStateChanged(); emit editorFocusChanged(editorFocused(), editorNumeric(), editorPassword());
    }
    if (_presentation == NativeOverlay) return; // The native WebView owns its OS input connection.
    if (auto* input = QGuiApplication::inputMethod()) {
        // DOM focus arrives after Qt focus; refresh Qt's cached acceptance too.
        input->update(Qt::ImEnabled | Qt::ImQueryInput | Qt::ImHints);
        if (_editorActive && hasActiveFocus()) {
            // A text/selection acknowledgement must not request the already
            // visible OS keyboard again. Preserve field/hint changes and the
            // normal retap after Back hides the input panel.
            // That retap is explicit: Qt's visibility cache may still say
            // visible after Android has already hidden the actual keyboard.
            if (state.value("requestKeyboard").toBool() || !input->isVisible() || !previousActive || previousOwner != _editorOwner
                    || previousKind != _editorKind || previousPassword != editorPassword()) input->show();
        } else input->hide();
    }
}
QVariant NativeWebViewItem::inputMethodQuery(Qt::InputMethodQuery query) const {
    if (query == Qt::ImEnabled) return _presentation == Texture && generation() && _editorActive && isVisible() && isEnabled() && hasActiveFocus();
    if (query == Qt::ImSurroundingText) return _editorText;
    if (query == Qt::ImAbsolutePosition) return _surroundingStart + _cursor;
    if (query == Qt::ImTextBeforeCursor) return _editorText.left(_cursor);
    if (query == Qt::ImTextAfterCursor) return _editorText.mid(_cursor);
    if (query == Qt::ImCursorPosition) return _cursor;
    if (query == Qt::ImAnchorPosition) return _anchor;
    if (query == Qt::ImCurrentSelection) return _editorText.mid(qMin(_cursor, _anchor), qAbs(_cursor - _anchor));
    if (query == Qt::ImCursorRectangle || query == Qt::ImAnchorRectangle) {
        const auto rectangle = query == Qt::ImAnchorRectangle ? _anchorRect : _cursorRect;
        if (_presentation == Texture && !_image.isNull()) {
            const auto x = width() / _image.width(), y = height() / _image.height();
            return QRectF(rectangle.x() * x, rectangle.y() * y, rectangle.width() * x, rectangle.height() * y);
        }
        return rectangle;
    }
    if (query == Qt::ImHints) return int(_sensitive ? Qt::ImhHiddenText | Qt::ImhSensitiveData | Qt::ImhNoPredictiveText :
        _editorKind == "textarea" || _editorKind == "contenteditable" ? Qt::ImhMultiLine :
        _editorKind == "number" ? Qt::ImhFormattedNumbersOnly : _editorKind == "tel" ? Qt::ImhDialableCharactersOnly :
        _editorKind == "email" ? Qt::ImhEmailCharactersOnly : _editorKind == "url" ? Qt::ImhUrlCharactersOnly : Qt::ImhNone);
    return QQuickItem::inputMethodQuery(query);
}
void NativeWebViewItem::focusInEvent(QFocusEvent* event) { QQuickItem::focusInEvent(event); jvalue args[2]; args[0].j = _handle; args[1].z = true; call("focus", "(JZ)V", args); }
void NativeWebViewItem::focusOutEvent(QFocusEvent* event) { resetEditor(); QQuickItem::focusOutEvent(event); jvalue args[2]; args[0].j = _handle; args[1].z = false; call("focus", "(JZ)V", args); }
QString NativeWebViewItem::errorText() const {
    return (_status == 2 || _status == 3 || _status == 4 || _status == 6) ? statusText() : QString();
}
QString NativeWebViewItem::warningText() const { return errorText().isEmpty() ? statusText() : QString(); }
QString NativeWebViewItem::statusText() const { switch (_status) {
    case 10: return tr("This page was closed to stop audio. Reload to continue. Unsaved form entries and page progress were lost.");
    case 1: return tr("This WebView provider cannot provide this page's Overte bridge. Update Android System WebView.");
    case 2: return tr("The page could not be loaded."); case 3: return tr("The WebView stopped. Reopen the page.");
    case 4: return tr("Native tablet presentation is unavailable on this client."); case 5: return tr("File selection is unavailable on this client.");
    case 9: return tr("This navigated page cannot access this surface’s Overte bridge.");
    case 8: return tr("An external browser is unavailable on this client.");
    case 6: return tr("This document has no authorized source or packaged resource root."); case 7: return tr("The page's script could not be loaded."); default: return {}; } }
void NativeWebViewItem::injectUserScript(quint64 grant, quint64 page, const QUrl& url, int redirects) {
    if (url.isEmpty()) return; QString root = scriptRoot(url);
    { QMutexLocker guard(&_mutex); if (!current(grant, page) || !_session.allowsBridge(grant, sourceURL(_document), true, 1) || !_session.allowsScriptURL(url, root)) return; }
    if (!redirects) {
        cancelSourceScripts();
        _scriptAttemptGrant = grant; _scriptAttemptPage = page;
    }
    if (!root.isEmpty()) {
        QFile file(url.scheme() == "qrc" ? ':' + url.path() : url.toLocalFile());
        if (file.open(QFile::ReadOnly) && file.size() <= 1024 * 1024) {
            if (evaluate(QString::fromUtf8(file.readAll()), grant, page)) _injectedPage = page;
        }
        else { _status = 7; emit stateChanged(); } return;
    }
    if (redirects > 5) { _status = 7; emit stateChanged(); return; }
    auto* network = new QNetworkAccessManager(this); QNetworkRequest request(url);
    request.setAttribute(QNetworkRequest::RedirectPolicyAttribute, QNetworkRequest::ManualRedirectPolicy);
    auto* reply = network->get(request); _scriptReplies.push_back(reply); auto* timeout = new QTimer(reply); timeout->setSingleShot(true); timeout->start(10000);
    connect(timeout, &QTimer::timeout, reply, &QNetworkReply::abort);
    connect(reply, &QIODevice::readyRead, reply, [reply] { if (reply->bytesAvailable() > 1024 * 1024) reply->abort(); });
    const auto revision = _scriptVersion;
    connect(reply, &QNetworkReply::finished, this, [this, grant, page, url, redirects, reply, network, revision] {
        _scriptReplies.removeAll(reply);
        { QMutexLocker guard(&_mutex); if (!current(grant, page) || revision != _scriptVersion) { reply->deleteLater(); network->deleteLater(); return; } }
        const auto redirect = reply->attribute(QNetworkRequest::RedirectionTargetAttribute).toUrl();
        if (!redirect.isEmpty()) injectUserScript(grant, page, url.resolved(redirect), redirects + 1);
        else if (reply->error() == QNetworkReply::NoError && reply->bytesAvailable() <= 1024 * 1024) {
            if (evaluate(QString::fromUtf8(reply->readAll()), grant, page)) _injectedPage = page;
        }
        else { _status = 7; emit stateChanged(); }
        reply->deleteLater(); network->deleteLater();
    });
}

extern "C" JNIEXPORT void JNICALL Java_org_overte_web_EmbeddedWebView_nativeInitialize(JNIEnv* env, jclass type) {
    JavaVM* machine = nullptr; if (env->GetJavaVM(&machine) != JNI_OK) return;
    jclass value = static_cast<jclass>(env->NewGlobalRef(type)); if (!value) return;
    vm.store(machine); jclass expected = nullptr; if (!backend.compare_exchange_strong(expected, value)) env->DeleteGlobalRef(value);
}
extern "C" JNIEXPORT void JNICALL Java_org_overte_web_EmbeddedWebView_nativeForeground(JNIEnv*, jclass, jboolean active) {
    foreground.store(active); QMutexLocker guard(&registryMutex); for (auto* item : registry) item->acceptForeground(active);
}
extern "C" JNIEXPORT jlong JNICALL Java_org_overte_web_EmbeddedWebView_nativeGeneration(JNIEnv*, jclass, jlong handle) {
    QMutexLocker guard(&registryMutex); auto* item = registry.value(handle); return item ? item->generation() : 0;
}
extern "C" JNIEXPORT jlong JNICALL Java_org_overte_web_EmbeddedWebView_nativeLifecycleRevision(JNIEnv*, jclass, jlong handle) {
    QMutexLocker guard(&registryMutex); auto* item = registry.value(handle); return item ? item->lifecycleRevision() : 0;
}
extern "C" JNIEXPORT void JNICALL Java_org_overte_web_EmbeddedWebView_nativeSuspended(JNIEnv* env, jclass, jlong handle, jlong birth, jlong revision, jstring url, jboolean back, jboolean forward) {
    const QUrl document(string(env, url)); QMutexLocker guard(&registryMutex);
    if (auto* item = registry.value(handle)) item->acceptSuspended(revision, document, back, forward, birth);
}
extern "C" JNIEXPORT void JNICALL Java_org_overte_web_EmbeddedWebView_nativeResumeRequest(JNIEnv* env, jclass, jlong handle, jlong birth, jlong revision, jstring url) {
    const QUrl document(string(env, url)); QMutexLocker guard(&registryMutex);
    if (auto* item = registry.value(handle)) item->requestResume(revision, document, birth);
}
extern "C" JNIEXPORT jboolean JNICALL Java_org_overte_web_EmbeddedWebView_nativeNavigation(JNIEnv* env, jclass, jlong handle, jlong grant, jstring url, jboolean mainFrame, jstring method) {
    auto target = QUrl(string(env, url)); auto verb = string(env, method); QMutexLocker guard(&registryMutex); auto* item = registry.value(handle);
    return item && item->allowsNavigation(grant, target, mainFrame, verb);
}
extern "C" JNIEXPORT jboolean JNICALL Java_org_overte_web_EmbeddedWebView_nativeBridgeAllowed(JNIEnv* env, jclass, jlong handle, jlong grant, jlong page, jstring document) {
    auto target = QUrl(string(env, document)); QMutexLocker guard(&registryMutex); auto* item = registry.value(handle);
    return item && item->allowsBridgeDocument(grant, page, target);
}
extern "C" JNIEXPORT jboolean JNICALL Java_org_overte_web_EmbeddedWebView_nativeEditorAllowed(JNIEnv* env, jclass, jlong handle, jlong grant, jlong page, jstring document) {
    auto target = QUrl(string(env, document)); QMutexLocker guard(&registryMutex); auto* item = registry.value(handle);
    return item && item->allowsEditorDocument(grant, page, target);
}
extern "C" JNIEXPORT jboolean JNICALL Java_org_overte_web_EmbeddedWebView_nativeFileChooserAllowed(JNIEnv* env, jclass, jlong handle, jlong grant, jlong page, jstring document) {
    auto target = QUrl(string(env, document)); QMutexLocker guard(&registryMutex); auto* item = registry.value(handle);
    return item && item->allowsFileChooser(grant, page, target);
}
extern "C" JNIEXPORT jboolean JNICALL Java_org_overte_web_EmbeddedWebView_nativeMessage(JNIEnv* env, jclass, jlong handle, jlong grant, jlong page, jstring document, jstring origin, jboolean mainFrame, jstring type, jstring payload) {
    auto target = QUrl(string(env, document)); auto source = QUrl(string(env, origin)); auto kind = string(env, type); auto data = string(env, payload).toUtf8();
    QMutexLocker guard(&registryMutex); auto* item = registry.value(handle); return item && item->acceptMessage(grant, page, target, source, mainFrame, kind, data);
}
extern "C" JNIEXPORT void JNICALL Java_org_overte_web_EmbeddedWebView_nativePage(JNIEnv* env, jclass, jlong handle, jlong grant, jlong page, jstring document) {
    auto url = QUrl(string(env, document)); QMutexLocker guard(&registryMutex); if (auto* item = registry.value(handle)) item->acceptPage(grant, page, url);
}
extern "C" JNIEXPORT void JNICALL Java_org_overte_web_EmbeddedWebView_nativeState(JNIEnv* env, jclass, jlong handle, jlong grant, jlong page, jstring document, jboolean loading, jboolean back, jboolean forward, jboolean bridge, jint status) {
    auto url = QUrl(string(env, document)); QMutexLocker guard(&registryMutex); if (auto* item = registry.value(handle)) item->acceptState(grant, page, url, loading, back, forward, bridge, status);
}
extern "C" JNIEXPORT void JNICALL Java_org_overte_web_EmbeddedWebView_nativeInputFocus(JNIEnv*, jclass, jlong handle, jlong birth, jlong revision, jboolean focused) {
    QMutexLocker guard(&registryMutex); if (auto* item = registry.value(handle)) item->acceptInputFocus(revision, birth, focused);
}
extern "C" JNIEXPORT void JNICALL Java_org_overte_web_EmbeddedWebView_nativeCreated(JNIEnv*, jclass, jlong handle, jlong revision, jboolean created) {
    QMutexLocker guard(&registryMutex); if (auto* item = registry.value(handle)) item->acceptCreated(created, revision);
}
extern "C" JNIEXPORT void JNICALL Java_org_overte_web_EmbeddedWebView_nativeFrame(JNIEnv* env, jclass, jlong handle, jlong grant, jlong page, jobject pixels, jint width, jint height) {
    auto* bytes = env->GetDirectBufferAddress(pixels); const auto capacity = env->GetDirectBufferCapacity(pixels);
    QMutexLocker guard(&registryMutex); if (auto* item = registry.value(handle)) item->acceptFrame(grant, page, bytes, capacity, width, height);
}
extern "C" JNIEXPORT jlong JNICALL Java_org_overte_web_EmbeddedWebView_nativeBeginResourceLoad(JNIEnv* env, jclass, jlong handle, jlong creation, jlong grant, jlong page, jstring url) {
    const auto state = resourceState(handle);
    return state ? state->begin(creation, grant, page, QUrl(string(env, url))) : 0;
}
extern "C" JNIEXPORT jboolean JNICALL Java_org_overte_web_EmbeddedWebView_nativeBindResourcePage(JNIEnv* env, jclass, jlong handle, jlong creation, jlong grant, jlong load, jlong pendingPage, jlong actualPage, jstring url) {
    const auto state = resourceState(handle);
    return state && state->bind(creation, grant, load, pendingPage, actualPage, QUrl(string(env, url)));
}
extern "C" JNIEXPORT jboolean JNICALL Java_org_overte_web_EmbeddedWebView_nativeResourceCurrent(JNIEnv*, jclass, jlong handle, jlong creation, jlong grant, jlong load, jlong page) {
    const auto state = resourceState(handle);
    return state && state->current(creation, grant, load, page);
}
extern "C" JNIEXPORT jobject JNICALL Java_org_overte_web_EmbeddedWebView_nativeRequest(JNIEnv* env, jclass, jlong handle, jlong creation, jlong grant, jlong load, jlong page, jstring url, jboolean mainFrame, jstring method) {
    const auto state = resourceState(handle);
    if (!state) return nullptr;
    const auto response = state->response(creation, grant, load, page, QUrl(string(env, url)), mainFrame, string(env, method));
    auto type = env->FindClass("org/overte/web/WebResourceLease$Response");
    if (!type) return nullptr;
    auto constructor = env->GetMethodID(type, "<init>", "(I[BLjava/lang/String;Ljava/lang/String;)V");
    if (!constructor) { env->DeleteLocalRef(type); return nullptr; }
    auto bytes = env->NewByteArray(response.bytes.size());
    if (!bytes) { env->DeleteLocalRef(type); return nullptr; }
    env->SetByteArrayRegion(bytes, 0, response.bytes.size(), reinterpret_cast<const jbyte*>(response.bytes.constData()));
    auto mime = env->NewString(reinterpret_cast<const jchar*>(response.mime.utf16()), response.mime.size());
    auto charset = env->NewString(reinterpret_cast<const jchar*>(response.charset.utf16()), response.charset.size());
    auto result = mime && charset && !env->ExceptionCheck()
        ? env->NewObject(type, constructor, jint(response.action), bytes, mime, charset) : nullptr;
    env->DeleteLocalRef(bytes); env->DeleteLocalRef(mime); env->DeleteLocalRef(charset); env->DeleteLocalRef(type);
    return result;
}

extern "C" JNIEXPORT void JNICALL Java_org_overte_web_EmbeddedWebView_nativeResult(JNIEnv* env, jclass, jlong handle, jlong grant, jlong page, jlong request, jstring result) {
    auto json = string(env, result).toUtf8(); QMutexLocker guard(&registryMutex); if (auto* item = registry.value(handle)) item->acceptResult(grant, page, request, json);
}
