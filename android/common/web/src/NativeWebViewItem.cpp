// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#include "NativeWebViewItem.h"
#include <QCoreApplication>
#include <QDateTime>
#include <QCryptographicHash>
#include <QJsonArray>
#include <QThread>
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include "../../../../tests/device/native/WebDOMObservationBridge.h"
#include "../../../../tests/device/native/WebRuntimeBridge.h"
#include "../../../../tests/device/native/PicoBrowserFeatureBridge.h"
#include "../../../../tests/device/native/PicoWorldWebRay.h"
#include "../../../../tests/device/native/PicoWorldWebText.h"
#endif
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
#include <limits>
#include <algorithm>

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
bool featureEnabled() {
#if defined(OVERTE_E2E_FEATURE_TESTS)
    const auto arguments=QCoreApplication::arguments();
    const int script=arguments.indexOf("--testScript"),results=arguments.indexOf("--testResultsLocation");
    return script>=0 && script+1<arguments.size() && !arguments[script+1].isEmpty()
        && results>=0 && results+1<arguments.size() && !arguments[results+1].isEmpty();
#else
    return false;
#endif
}
void registerType() {
    qmlRegisterType<NativeWebViewItem>("Overte.Android", 1, 0, "NativeWebView");
#if defined(OVERTE_E2E_FEATURE_TESTS)
    if (featureEnabled() && QCoreApplication::instance()) {
        overte::e2e::WebDOMProvider provider=[](const QVariantMap& command) { return NativeWebViewItem::featureWebDOMObservation(command); };
        QCoreApplication::instance()->setProperty(overte::e2e::webDOMProviderProperty(),QVariant::fromValue(provider));
#if defined(ANDROID_APP_PICO_INTERFACE)
        overte::e2e::WebDOMProvider browser=[](const QVariantMap& command) { return NativeWebViewItem::featurePicoBrowser(command); };
        QCoreApplication::instance()->setProperty(overte::e2e::picoBrowserProperty(),QVariant::fromValue(browser));
        overte::e2e::WebRuntimeProvider runtime{[](const QVariantMap& command) { return NativeWebViewItem::featureWebRuntimeObservation(command); }};
        QCoreApplication::instance()->setProperty(overte::e2e::webRuntimeProperty(),QVariant::fromValue(runtime));
#endif
    }
#endif
}
}
Q_COREAPP_STARTUP_FUNCTION(registerType)

NativeWebViewItem::NativeWebViewItem(QQuickItem* parent) : QQuickItem(parent),
    _transport(new NativeWebTransport(this)), _bridge(new NativeSurfaceBridge(this)), _channel(new QWebChannel(this)) {
    { QMutexLocker guard(&registryMutex);
      if (nextHandle > 0) { _handle = nextHandle; nextHandle = nextHandle == std::numeric_limits<jlong>::max() ? 0 : nextHandle + 1; registry.insert(_handle, this); } }
    _session.setForeground(foreground.load());
    setFlag(ItemHasContents, true); setFlag(ItemAcceptsInputMethod, true); setAcceptedMouseButtons(Qt::LeftButton); setAcceptHoverEvents(true);
    _channel->registerObject("eventBridge", _bridge);
    _channel->registerObject("eventBridgeWrapper", new NativeBridgeWrapper(_bridge, this));
    _channel->connectTo(_transport);
    connect(_bridge, &NativeSurfaceBridge::webEvent, this, &NativeWebViewItem::webEventReceived);
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
    connect(_bridge,&NativeSurfaceBridge::webEvent,this,[this](const QVariant& message) { featurePicoBrowserRecord("requests",message); });
#endif
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
    QString editorScript = resourceText(":/overte/android/web/resources/editor-transport.js") + '\n' + resourceText(":/overte/android/web/resources/editor.js");
#if defined(OVERTE_E2E_FEATURE_TESTS)
    if (featureEnabled()) {
        const auto source=resourceText(":/overte/e2e/browser/web-dom-observation.js");
        // A missing observer blocks evidence, without changing product navigation.
        if (!source.isEmpty()) { editorScript += "\n(function(){"+source+"\nObject.defineProperty(window,'__overteFeatureWebDOM',{value:overteWebDOMSource(window),writable:false,configurable:false});})();"; }
    }
#endif
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
    QPointer<NativeWebViewItem> self(this); QMetaObject::invokeMethod(this, [self, grant, page, document, type, inputEpoch,
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
        origin,mainFrame,payload,
#endif
        object = parsed.object()] {
        if (!self) return;
        if (type == "editor" ? !self->allowsEditorDocument(grant, page, document) : !self->allowsBridgeDocument(grant, page, document)) return;
        if (type == "editor") { QMutexLocker guard(&self->_mutex); if (!self->_inputFocused || self->_inputEpoch != inputEpoch) return; }
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
        if (type=="channel" && self->featurePicoTabletIntercept(grant,page,document,origin,mainFrame,payload,object)) { return; }
#endif
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
            self->_pressed = false; self->resetEditor();
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
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
    featurePicoBrowserRecord("replies",message);
#endif
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
#if defined(OVERTE_E2E_FEATURE_TESTS)
    if (featureEnabled()) {
        QString original;{ QMutexLocker guard(&_mutex);original=_session.url().toString(QUrl::FullyEncoded); }
        const QUrl observed(original);
        if (observed.userInfo().isEmpty() && !observed.hasQuery() && !observed.hasFragment()
                && QRegularExpression("\\A/feature-fixture/v1/runs/[0-9a-f]{32}/tickets/[0-9a-f]{32}/[^/]+\\z").match(observed.path()).hasMatch()) {
            if (_featureCallbackSources.size()<1024) { _featureCallbackSources.insert(request,original); }
            else { _featureCallbackSourcesComplete=false; }
        }
    }
#endif
    if (!posted) { _callbacks.remove(request); return false; }
#if defined(OVERTE_E2E_FEATURE_TESTS)
    std::shared_ptr<quint8> featureExpiry;
    if (_featureCallbackSources.contains(request)) {
        featureExpiry=std::make_shared<quint8>(0);
        _featureCallbackExpiries.insert(request,featureExpiry);
    }
#endif
    QTimer::singleShot(10000, this, [this, grant, page, request
#if defined(OVERTE_E2E_FEATURE_TESTS)
            , featureExpiry
#endif
            ] {
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
    QPointF pixel = position; { QMutexLocker guard(&_mutex); if (!_image.isNull() && width() > 0 && height() > 0) pixel = QPointF(position.x() * _image.width()/width(), position.y() * _image.height()/height()); }
    jvalue args[4]; args[0].j = _handle; args[1].i = action; args[2].f = pixel.x(); args[3].f = pixel.y(); call("pointer", "(JIFF)V", args);
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
void NativeWebViewItem::editorCommand(const QJsonObject& command) { if (!_editorActive || !hasActiveFocus()) return;
    quint64 grant, page; QUrl document;
    { QMutexLocker guard(&_mutex); grant = _session.generation(); page = _page; document = _document; }
    if (!allowsEditorDocument(grant, page, document)) return;
    Jni jni; if (!jni.env || !backend.load()) return;
    jstring url = jni.string(document.toString(QUrl::FullyEncoded));
    jstring data = jni.string(QString::fromUtf8(QJsonDocument(command).toJson(QJsonDocument::Compact)));
    if (url && data) { jvalue args[5]; args[0].j = _handle; args[1].j = grant; args[2].j = page; args[3].l = url; args[4].l = data;
        call("edit", "(JJJLjava/lang/String;Ljava/lang/String;)V", args); }
    if (jni.env->ExceptionCheck()) jni.env->ExceptionClear();
    if (url) jni.env->DeleteLocalRef(url); if (data) jni.env->DeleteLocalRef(data);
}
void NativeWebViewItem::keyPressEvent(QKeyEvent* event) {
    if (!_editorActive || (event->modifiers() & (Qt::ControlModifier | Qt::AltModifier | Qt::MetaModifier))) { event->ignore(); return; }
    if (event->key() == Qt::Key_Return || event->key() == Qt::Key_Enter)
        editorCommand({{"action", "enter"}, {"shift", bool(event->modifiers() & Qt::ShiftModifier)}});
    else if (event->key() == Qt::Key_Backspace) editorCommand({{"action", "backspace"}});
    else if (event->key() == Qt::Key_Delete) editorCommand({{"action", "delete"}});
    else if (event->key() == Qt::Key_Left || event->key() == Qt::Key_Right || event->key() == Qt::Key_Home || event->key() == Qt::Key_End) {
        const auto action = event->key() == Qt::Key_Left ? "left" : event->key() == Qt::Key_Right ? "right" : event->key() == Qt::Key_Home ? "home" : "end";
        editorCommand({{"action", action}, {"extend", bool(event->modifiers() & Qt::ShiftModifier)}});
    }
    else if (!event->text().isEmpty()) editorCommand({{"text", event->text()}}); else { event->ignore(); return; }
    event->accept();
}
void NativeWebViewItem::inputMethodEvent(QInputMethodEvent* event) {
    if (!_editorActive || !hasActiveFocus() || event->commitString().size() > 16384 || event->preeditString().size() > 16384) { event->ignore(); return; }
    QJsonObject command {{"action", "ime"}, {"commit", event->commitString()}, {"preedit", event->preeditString()},
        {"replaceStart", event->replacementStart()}, {"replaceLength", event->replacementLength()}, {"cursor", event->preeditString().size()}};
    for (const auto& attribute : event->attributes()) {
        if (attribute.type == QInputMethodEvent::Cursor) command["cursor"] = qBound(0, attribute.start, event->preeditString().size());
        if (attribute.type == QInputMethodEvent::Selection) command["selection"] = QJsonObject {{"start", _surroundingStart + attribute.start}, {"length", attribute.length}};
    }
    editorCommand(command); event->accept();
}
void NativeWebViewItem::resetEditor() {
    const bool changed = _editorActive; _editorActive = false; _editorText.clear();
    if (changed) { emit editorStateChanged(); emit editorFocusChanged(false, false, false); }
}
void NativeWebViewItem::updateEditor(const QJsonObject& state) {
    const bool previousActive = editorFocused(), previousNumeric = editorNumeric(), previousPassword = editorPassword();
    _editorActive = state.value("active").toBool(); _sensitive = state.value("sensitive").toBool();
    _editorText = _sensitive ? QString() : state.value("text").toString().left(16384);
    _cursor = qBound(0, state.value("cursor").toInt(), _editorText.size()); _anchor = qBound(0, state.value("anchor").toInt(), _editorText.size());
    _surroundingStart = qMax(0, state.value("absoluteCursor").toInt() - state.value("cursor").toInt());
    _editorKind = state.value("kind").toString(); _cursorRect = QRectF(state.value("x").toDouble(), state.value("y").toDouble(), state.value("width").toDouble(), state.value("height").toDouble());
    if (previousActive != editorFocused() || previousNumeric != editorNumeric() || previousPassword != editorPassword()) {
        emit editorStateChanged(); emit editorFocusChanged(editorFocused(), editorNumeric(), editorPassword());
    }
    if (_presentation == NativeOverlay) return; // The native WebView owns its OS input connection.
    if (auto* input = QGuiApplication::inputMethod()) { input->update(Qt::ImQueryInput); if (_editorActive && hasActiveFocus()) input->show(); else input->hide(); }
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
    if (query == Qt::ImCursorRectangle) {
        if (_presentation == Texture && !_image.isNull()) {
            const auto x = width() / _image.width(), y = height() / _image.height();
            return QRectF(_cursorRect.x() * x, _cursorRect.y() * y, _cursorRect.width() * x, _cursorRect.height() * y);
        }
        return _cursorRect;
    }
    if (query == Qt::ImHints) return int(_sensitive ? Qt::ImhHiddenText | Qt::ImhSensitiveData | Qt::ImhNoPredictiveText :
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


#if defined(OVERTE_E2E_FEATURE_TESTS)
namespace {
struct WebRuntime {
    const QString instance { QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-') };
    quint64 sequence { 0 };
    qint64 epoch { 0 };
    QVariantMap command,packet,before;
    QElapsedTimer timer;
    QHash<QString,QVariantList> histories;
    QSet<QString> requests;
    bool complete { true };
};
WebRuntime webRuntime;
bool runtimeOwned(const QString& raw,const QString& root) {
    const QUrl url(raw,QUrl::StrictMode);
    const auto original=url.adjusted(QUrl::RemoveQuery|QUrl::RemoveFragment).toString(QUrl::FullyEncoded);
    const auto prefix=root+"tickets/";
    return url.isValid() && url.userInfo().isEmpty() && original.startsWith(prefix)
        && QRegularExpression("\\A[0-9a-f]{32}/[A-Za-z0-9_.-]{1,80}\\z").match(original.mid(prefix.size())).hasMatch();
}
QString runtimeHash(const QString& value) { return QString::fromLatin1(QCryptographicHash::hash(value.toUtf8(),QCryptographicHash::Sha256).toHex()); }
QVariantMap runtimePacket(const QVariantMap& command,const QString& status,const QVariantMap& source={}) {
    const auto now=QDateTime::currentMSecsSinceEpoch();
    if (now<=0 || now<webRuntime.epoch || webRuntime.sequence>=1000000000) { return {}; }
    webRuntime.epoch=now;
    return {{"webRuntimeVersion",2},{"commandId",command.value("commandId")},{"runId",command.value("runId")},
        {"instance",webRuntime.instance},{"sequence",static_cast<qulonglong>(++webRuntime.sequence)},
        {"processId",QCoreApplication::applicationPid()},{"capturedEpochMs",now},{"status",status},{"source",source}};
}
}

QVariantMap NativeWebViewItem::featureWebSnapshot(const QVariantMap& command) {
    if (!featureEnabled() || !overte::e2e::webRuntimeCommand(command)
            || !QCoreApplication::instance() || QThread::currentThread()!=QCoreApplication::instance()->thread()) { return {}; }
    QList<QPointer<NativeWebViewItem>> original;
    { QMutexLocker guard(&registryMutex);
      if (registry.size()>128) { return {}; }
      for (auto* item:registry) { original.append(item); } }
    for (const auto& item:original) { if (!item || item->thread()!=QThread::currentThread()) { return {}; } }
    std::sort(original.begin(),original.end(),[](const auto& a,const auto& b) { return a->_handle<b->_handle; });
    const auto run=command.value("runId").toString(),root=command.value("fixtureUrl").toString();
    if (!webRuntime.histories.contains(run) && webRuntime.histories.size()>=32) { webRuntime.complete=false;return {}; }
    auto& history=webRuntime.histories[run];QSet<QString> known;
    for (const auto& value:history) { known.insert(value.toMap().value("handle").toString()); }
    QVariantList views;
    const auto now=QDateTime::currentMSecsSinceEpoch();
    for (const auto& item:original) {
        QString source,document;quint64 grant,page;bool active,authorized,suspended;
        { QMutexLocker guard(&item->_mutex);source=item->_session.url().toString(QUrl::FullyEncoded);
          document=item->_document.toString(QUrl::FullyEncoded);grant=item->_session.generation();page=item->_page;
          active=item->_session.active();authorized=item->_sourceAuthorized;suspended=item->_suspendedDocument; }
        const auto creation=item->_creationSource.toString(QUrl::FullyEncoded),handle=QString::number(item->_handle);
        const bool inlineOwned=item->featurePicoTabletOwned(run,root);
        const bool sourceOwned=runtimeOwned(source,root) || inlineOwned,documentOwned=runtimeOwned(document,root) || inlineOwned,
            creationOwned=runtimeOwned(creation,root) || inlineOwned;
        int callbacks=0;
        if (!item->_featureCallbackSourcesComplete) { webRuntime.complete=false; }
        for (auto found=item->_featureCallbackSources.cbegin();found!=item->_featureCallbackSources.cend();++found) {
            if (runtimeOwned(found.value(),root) && (item->_callbacks.contains(found.key())
                    || !item->_featureCallbackExpiries.value(found.key()).expired())) { ++callbacks; }
        }
        if (!sourceOwned && !documentOwned && !creationOwned && !callbacks && !known.contains(handle)) { continue; }
        if (!known.contains(handle)) {
            if (history.size()>=256) { webRuntime.complete=false;return {}; }
            const auto observedSource=sourceOwned ? source : documentOwned ? document : creation;
            history.append(QVariantMap{{"handle",handle},{"firstObservedEpochMs",now},{"sourceSha256",runtimeHash(observedSource)}});known.insert(handle);
        }
        int replies=0;
        if (sourceOwned || documentOwned) { for (const auto& reply:item->_scriptReplies) { replies += reply ? 1 : 0; } }
        const bool domPending=item->_featureWebCommand.value("runId").toString()==run
            && item->_featureWebPacket.value("status")=="pending" && item->_featureWebTimer.isValid() && item->_featureWebTimer.elapsed()<4000;
        views.append(QVariantMap{{"handle",handle},{"surface",item->_surface==WorldEntity ? "world" : "tablet"},
            {"creation",static_cast<qulonglong>(item->_creationRevision)},{"grant",static_cast<qulonglong>(grant)},{"page",static_cast<qulonglong>(page)},
            {"sourceOwned",sourceOwned},{"documentOwned",documentOwned},{"creationOwned",creationOwned},
            {"sourceSha256",runtimeHash(source)},{"documentSha256",runtimeHash(document)},{"creationSha256",runtimeHash(creation)},
            {"sessionActive",active},{"authorized",authorized},{"created",item->_created},{"pendingCreate",item->_pending},
            {"retryPending",item->_retryPending},{"suspended",suspended},{"loading",item->_loading},
            {"callbacks",callbacks},{"scriptReplies",replies},{"domPending",domPending}});
    }
    return {{"capturedEpochMs",now},{"complete",webRuntime.complete},{"knownHandles",history},{"views",views}};
}

QVariantMap NativeWebViewItem::featureWebRuntimeObservation(const QVariantMap& command) {
#if defined(ANDROID_APP_PICO_INTERFACE)
    if (!featureEnabled() || !overte::e2e::webRuntimeCommand(command) || !QCoreApplication::instance()
            || QThread::currentThread()!=QCoreApplication::instance()->thread()) { return {}; }
    if (webRuntime.command.value("commandId")==command.value("commandId")) {
        if (webRuntime.command!=command) { return {}; }
        if (webRuntime.packet.value("status")=="pending" && webRuntime.timer.elapsed()>=4000) {
            webRuntime.packet=runtimePacket(command,"unavailable");
        }
        return webRuntime.packet; // Original completed epoch, never retimed.
    }
    if (webRuntime.packet.value("status")=="pending") { return {}; }
    const auto nonce=command.value("commandId").toString();
    if (webRuntime.requests.contains(nonce) || webRuntime.requests.size()>=4096) { return {}; }
    webRuntime.requests.insert(nonce);
    webRuntime.command=command;webRuntime.before=featureWebSnapshot(command);webRuntime.timer.start();
    if (webRuntime.before.isEmpty()) { webRuntime.packet=runtimePacket(command,"unavailable");return webRuntime.packet; }
    webRuntime.packet=runtimePacket(command,"pending");
    Jni jni;if (!jni.env) { webRuntime.packet=runtimePacket(command,"unavailable");return webRuntime.packet; }
    const auto id=jni.string(command.value("commandId").toString()),root=jni.string(command.value("fixtureUrl").toString());
    const auto known=jni.string(QString::fromUtf8(QJsonDocument(QJsonArray::fromVariantList(webRuntime.before.value("knownHandles").toList())).toJson(QJsonDocument::Compact)));
    if (!id || !root || !known) { webRuntime.packet=runtimePacket(command,"unavailable"); }
    else {
        jvalue args[3];args[0].l=id;args[1].l=root;args[2].l=known;
        if (!call("featureRuntimeSnapshot","(Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;)V",args)) {
            webRuntime.packet=runtimePacket(command,"unavailable");
        }
    }
    if (id) { jni.env->DeleteLocalRef(id); }if (root) { jni.env->DeleteLocalRef(root); }if (known) { jni.env->DeleteLocalRef(known); }
    return webRuntime.packet;
#else
    Q_UNUSED(command);return {};
#endif
}

void NativeWebViewItem::acceptFeatureWebRuntime(const QString& request,const QByteArray& json) {
    if (!featureEnabled() || json.size()>262144 || !QCoreApplication::instance()) { return; }
    QMetaObject::invokeMethod(QCoreApplication::instance(),[request,json] {
        if (webRuntime.command.value("commandId")!=request || webRuntime.packet.value("status")!="pending") { return; }
        const auto document=QJsonDocument::fromJson(json);const auto source=document.isObject() ? document.object().toVariantMap() : QVariantMap();
        const auto after=NativeWebViewItem::featureWebSnapshot(webRuntime.command);
        if (webRuntime.timer.elapsed()>=4000 || source.value("commandId")!=request || source.value("complete")!=true || after.isEmpty()) {
            webRuntime.packet=runtimePacket(webRuntime.command,"unavailable");return;
        }
        webRuntime.packet=runtimePacket(webRuntime.command,"ready",{{"nativeBefore",webRuntime.before},{"java",source},{"nativeAfter",after}});
    },Qt::QueuedConnection);
}

QVariantMap NativeWebViewItem::featureWebPacket(const QVariantMap& command, const QString& status, const QVariantMap& source) {
    const auto epoch=QDateTime::currentMSecsSinceEpoch();
    if (epoch<=0 || epoch<_featureWebEpoch || _featureWebSequence>=9007199254740991ULL) { return {}; }
    _featureWebEpoch=epoch;
    return {{"webNativeVersion",1},{"commandId",command.value("commandId")},{"runId",command.value("runId")},
        {"surface",_surface==Tablet ? "tablet" : "world"},{"instance",_featureWebInstance},
        {"sequence",static_cast<qulonglong>(++_featureWebSequence)},{"processId",QCoreApplication::applicationPid()},
        {"capturedEpochMs",epoch},{"status",status},{"source",source}};
}
QVariantMap NativeWebViewItem::featureWebDOMObservation(const QVariantMap& command) {
    if (!featureEnabled() || !overte::e2e::webDOMCommand(command)) { return {}; }
    QList<QPointer<NativeWebViewItem>> original;
    { QMutexLocker guard(&registryMutex);
      if (registry.size()>128) { return {}; }
      for (auto* item:registry) { original.append(item); } }
    QPointer<NativeWebViewItem> selected;
    const auto prefix=command.value("fixtureUrl").toString()+"tickets/";
    const auto surface=command.value("surface").toString()=="tablet" ? Tablet : WorldEntity;
    for (const auto& item:original) {
        if (!item) { continue; }
        // No unbounded blocking invocation into another QML/GUI thread.
        if (item->thread()!=QThread::currentThread()) { return {}; }
        if (!item->isVisible() || !item->isEnabled()) { continue; }
        QString source;bool inlineSource;
        { QMutexLocker guard(&item->_mutex);source=item->_session.url().toString(QUrl::FullyEncoded);inlineSource=item->_inlineProvided; }
        if (item->_surface!=surface || inlineSource || !source.startsWith(prefix)
                || !QRegularExpression("\\A[0-9a-f]{32}/(?:index|reference)\\.html\\z").match(source.mid(prefix.size())).hasMatch()) { continue; }
        if (selected) { return {}; }selected=item;
    }
    return selected ? selected->featureWebDOMRequest(command) : QVariantMap();
}
QVariantMap NativeWebViewItem::featureWebDOMRequest(const QVariantMap& command) {
    if (!featureEnabled() || (!overte::e2e::webDOMCommand(command) && !overte::e2e::picoTabletDOMCommand(command))
            || thread()!=QThread::currentThread()) { return {}; }
    quint64 grant,page;QUrl document;
    { QMutexLocker guard(&_mutex);grant=_session.generation();page=_page;document=_document; }
    if (!grant || !page || !allowsEditorDocument(grant,page,document)) { return {}; }
    const auto id=command.value("commandId").toString();
    if (!_featureWebCommand.isEmpty() && _featureWebCommand.value("commandId")==id) {
        if (_featureWebCommand!=command || _featureWebGrant!=grant || _featureWebPage!=page || _featureWebDocument!=document) { return {}; }
    } else {
        if (_featureWebPacket.value("status")=="pending") { return {}; }
        _featureWebCommand=command;_featureWebGrant=grant;_featureWebPage=page;_featureWebDocument=document;
        _featureWebIssued=false;_featureWebTimer.start();_featureWebPacket=featureWebPacket(command,"pending");
    }
    if (_featureWebPacket.value("status")!="pending") { return _featureWebPacket; }
    if (!_featureWebTimer.isValid() || _featureWebTimer.elapsed()>=4000) {
        _featureWebPacket=featureWebPacket(command,"unavailable");return _featureWebPacket;
    }
    if (_featureWebFinishedGrant!=grant || _featureWebFinishedPage!=page
            || _featureWebFinishedDocument!=document) { return _featureWebPacket; }
    if (!_featureWebIssued) {
        _featureWebIssued=true;
        Jni jni;if (!jni.env) { _featureWebPacket=featureWebPacket(command,"unavailable");return _featureWebPacket; }
        const auto nonce=jni.string(id);if (!nonce) { _featureWebPacket=featureWebPacket(command,"unavailable");return _featureWebPacket; }
        jvalue args[4];args[0].j=_handle;args[1].j=grant;args[2].j=page;args[3].l=nonce;
        const bool posted=call(command.value("action")=="feature-pico-tablet-dom-observe" ? "featurePicoReadOwned" : "featureRead",
            "(JJJLjava/lang/String;)V",args);jni.env->DeleteLocalRef(nonce);
        if (!posted) { _featureWebPacket=featureWebPacket(command,"unavailable"); }
    }
    return _featureWebPacket;
}
void NativeWebViewItem::acceptFeatureWebFinished(quint64 grant, quint64 page, const QUrl& document) {
    QPointer<NativeWebViewItem> self(this);
    QMetaObject::invokeMethod(this,[self,grant,page,document] {
        if (!self || !featureEnabled() || !self->allowsEditorDocument(grant,page,document)) { return; }
        { QMutexLocker guard(&self->_mutex);if (!self->current(grant,page) || self->_document!=document) { return; } }
        self->_featureWebFinishedGrant=grant;self->_featureWebFinishedPage=page;self->_featureWebFinishedDocument=document;
#if defined(ANDROID_APP_PICO_INTERFACE)
        self->featurePicoBrowserRecord("documents");
#endif
    },Qt::QueuedConnection);
}
void NativeWebViewItem::acceptFeatureWebHTTPError(quint64 grant, quint64 page, const QUrl& document, int status) {
    QPointer<NativeWebViewItem> self(this);
    QMetaObject::invokeMethod(this,[self,grant,page,document,status] {
        if (!self || !featureEnabled() || status<400 || status>599 || !self->allowsEditorDocument(grant,page,document)) { return; }
        { QMutexLocker guard(&self->_mutex);if (!self->current(grant,page) || self->_document!=document) { return; } }
        self->_featureWebHTTPGrant=grant;self->_featureWebHTTPPage=page;self->_featureWebHTTPStatus=status;
    },Qt::QueuedConnection);
}
void NativeWebViewItem::acceptFeatureWebDOM(quint64 grant, quint64 page, const QUrl& document,
                                         const QString& request, const QByteArray& result) {
    QPointer<NativeWebViewItem> self(this);
    QMetaObject::invokeMethod(this,[self,grant,page,document,request,result] {
        if (!self || !featureEnabled() || self->_featureWebPacket.value("status")!="pending"
                || self->_featureWebCommand.value("commandId")!=request || self->_featureWebGrant!=grant
                || self->_featureWebPage!=page || self->_featureWebDocument!=document
                || !self->_featureWebTimer.isValid() || self->_featureWebTimer.elapsed()>=4000
                || !self->allowsEditorDocument(grant,page,document)) { return; }
        QString source;bool inlineLease;
        { QMutexLocker guard(&self->_mutex);
          if (!self->current(grant,page) || self->_document!=document) { return; }
          source=self->_session.url().toString(QUrl::FullyEncoded);inlineLease=self->_inlineProvided && self->_inlineDocument.current(); }
        const auto quoted=QJsonDocument::fromJson('['+result+']');QVariantMap dom;
        if (result.size()<=262144 && quoted.isArray() && quoted.array().size()==1 && quoted.array()[0].isString()) {
            const auto raw=quoted.array()[0].toString().toUtf8();
            if (raw.size()<=262144) { const auto parsed=QJsonDocument::fromJson(raw);if (parsed.isObject()) { dom=parsed.object().toVariantMap(); } }
        }
        const auto actualDocument=dom.value("document").toMap();
        if (QJsonObject::fromVariantMap(dom).value("webDOMVersion")!=QJsonValue(1)
                || dom.value("requestId")!=request || actualDocument.value("runId")!=self->_featureWebCommand.value("runId")
                || actualDocument.value("href")!=document.toString(QUrl::FullyEncoded)
                || (inlineLease && (self->_featureWebCommand.value("action")!="feature-pico-tablet-dom-observe"
                    || !self->featurePicoTabletOwned(self->_featureWebCommand.value("runId").toString(),self->_featureWebCommand.value("fixtureUrl").toString())))
                || self->_featureWebFinishedGrant!=grant || self->_featureWebFinishedPage!=page || self->_featureWebFinishedDocument!=document) {
            self->_featureWebPacket=self->featureWebPacket(self->_featureWebCommand,"unavailable");return;
        }
        QVariantMap view{{"handle",QString::number(self->_handle)},{"creation",static_cast<qulonglong>(self->_creationRevision)},
            {"grant",static_cast<qulonglong>(grant)},{"page",static_cast<qulonglong>(page)},{"url",document.toString(QUrl::FullyEncoded)},
            {"nativeFinished",true},{"httpErrorStatus",self->_featureWebHTTPGrant==grant && self->_featureWebHTTPPage==page ? self->_featureWebHTTPStatus : 0},
            {"inlineLease",inlineLease},{"sourceUrl",source},{"sourceIdentity",self->_sourceIdentity}};
        QVariantMap sources{{"nativeView",view},{"dom",dom}};
#if defined(ANDROID_APP_PICO_INTERFACE)
        if (inlineLease) { sources.insert("inline",self->featurePicoTabletInline()); }
#endif
        self->_featureWebPacket=self->featureWebPacket(self->_featureWebCommand,"ready",sources);
#if defined(ANDROID_APP_PICO_INTERFACE)
        self->featurePicoBrowserRecord("dom",self->_featureWebPacket);
#endif
    },Qt::QueuedConnection);
}
#endif

extern "C" JNIEXPORT void JNICALL Java_org_overte_web_EmbeddedWebView_nativeFeatureRuntimeResult(JNIEnv* env,jclass,jstring request,jstring result) {
#if defined(OVERTE_E2E_FEATURE_TESTS)
    if (!request || !result || env->GetStringLength(request)!=32 || env->GetStringLength(result)>262144) { return; }
    NativeWebViewItem::acceptFeatureWebRuntime(string(env,request),string(env,result).toUtf8());
#else
    Q_UNUSED(env);Q_UNUSED(request);Q_UNUSED(result);
#endif
}
extern "C" JNIEXPORT jboolean JNICALL Java_org_overte_web_EmbeddedWebView_nativeFeatureEnabled(JNIEnv*, jclass) { return featureEnabled(); }
extern "C" JNIEXPORT void JNICALL Java_org_overte_web_EmbeddedWebView_nativeFeatureDOMResult(JNIEnv* env, jclass, jlong handle,
    jlong grant,jlong page,jstring document,jstring request,jstring result) {
#if defined(OVERTE_E2E_FEATURE_TESTS)
    // Bound Java UTF-16 before allocating a native copy of arbitrary script data.
    if (!result || env->GetStringLength(result)>524288) { return; }
    const auto url=QUrl(string(env,document));const auto nonce=string(env,request);const auto raw=string(env,result).toUtf8();
    QMutexLocker guard(&registryMutex);if (auto* item=registry.value(handle)) { item->acceptFeatureWebDOM(grant,page,url,nonce,raw); }
#endif
}
extern "C" JNIEXPORT void JNICALL Java_org_overte_web_EmbeddedWebView_nativeFeatureFinished(JNIEnv* env, jclass,jlong handle,
    jlong grant,jlong page,jstring document) {
#if defined(OVERTE_E2E_FEATURE_TESTS)
    const auto url=QUrl(string(env,document));QMutexLocker guard(&registryMutex);
    if (auto* item=registry.value(handle)) { item->acceptFeatureWebFinished(grant,page,url); }
#endif
}
extern "C" JNIEXPORT void JNICALL Java_org_overte_web_EmbeddedWebView_nativeFeatureHTTPError(JNIEnv* env,jclass,jlong handle,
    jlong grant,jlong page,jstring document,jint status) {
#if defined(OVERTE_E2E_FEATURE_TESTS)
    const auto url=QUrl(string(env,document));QMutexLocker guard(&registryMutex);
    if (auto* item=registry.value(handle)) { item->acceptFeatureWebHTTPError(grant,page,url,status); }
#endif
}

extern "C" JNIEXPORT void JNICALL Java_org_overte_web_EmbeddedWebView_nativeResult(JNIEnv* env, jclass, jlong handle, jlong grant, jlong page, jlong request, jstring result) {
    auto json = string(env, result).toUtf8(); QMutexLocker guard(&registryMutex); if (auto* item = registry.value(handle)) item->acceptResult(grant, page, request, json);
}

#include "PicoBrowserFeatureE2E.inc"
