#!/usr/bin/env python3
"""Original complete Qt meta-call body, actual moc dispatch and Qt/V8 runtime."""
import os
import pathlib
import shlex
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[4]


class V8Signal(unittest.TestCase):
    def test_original_signal_dispatch(self):
        prefix = pathlib.Path(os.environ["V8_TEST_ROOT"]).resolve(strict=True)
        source = (ROOT / "libraries/script-engine/src/v8/ScriptObjectV8Proxy.cpp").read_text()
        admission_baseline = os.environ.get('OVERTE_ABORT_ADMISSION_BASELINE')
        if admission_baseline:
            source = subprocess.check_output(['git', '-C', str(ROOT), 'show',
                admission_baseline + ':libraries/script-engine/src/v8/ScriptObjectV8Proxy.cpp'], text=True)
        body = "int ScriptSignalV8Proxy::qt_metacall(" + source.split(
            "int ScriptSignalV8Proxy::qt_metacall(", 1)[1].split(
            "int ScriptSignalV8Proxy::discoverMetaCallIdx()", 1)[0]
        if os.environ.get('OVERTE_SIGNAL_SKIP_CONSENT_ENVIRONMENT'):
            body = body.replace('if (conn.invokeInEnvironment) { conn.invokeInEnvironment(invoke); } else { invoke(); }', 'invoke();')
        header = (ROOT / "libraries/script-engine/src/v8/ScriptObjectV8Proxy.h").read_text()
        base = "class ScriptSignalV8ProxyBase :" + header.split(
            "class ScriptSignalV8ProxyBase :", 1)[1].split("class ScriptSignalV8Proxy final", 1)[0]
        flags = shlex.split(subprocess.check_output(["pkg-config", "--cflags", "--libs", "Qt6Core"], text=True))
        moc = pathlib.Path(subprocess.check_output(["pkg-config", "--variable=libexecdir", "Qt6Core"], text=True).strip()) / "moc"
        with tempfile.TemporaryDirectory(prefix="sh005-v8-signal-") as temporary:
            temporary = pathlib.Path(temporary)
            (temporary / "signal-body.inc").write_text(body)
            (temporary / "signal-meta.h").write_text(
                "#pragma once\n#include <QObject>\nstruct ScriptValue {};\nstruct Scriptable {};\n" + base +
                "class Emitter : public QObject { Q_OBJECT\n public: signals:\n"
                "void zero(); void ping(int); void ten(int,int,int,int,int,int,int,int,int,int);\n"
                "void huge(int,int,int,int,int,int,int,int,int,int,int);\n};\n")
            subprocess.run([str(moc), str(temporary / "signal-meta.h"), "-o", str(temporary / "signal-moc.inc")], check=True, timeout=10)
            engine_header = (ROOT / 'libraries/script-engine/src/v8/ScriptEngineV8.h').read_text()
            scope_type = 'class ScriptEngineScopeGuardV8 final :' + engine_header.split(
                'class ScriptEngineScopeGuardV8 final :', 1)[1].split(
                'std::unique_ptr<ScriptEngineScopeGuard> getScopeGuard()', 1)[0]
            (temporary / 'method-scopeguard-type.inc').write_text(scope_type)
            state = '\n'.join(line for line in engine_header.splitlines() if 'std::atomic<' in line and
                any(name in line for name in ('_abortRequested', '_cleanupStarted', '_cleanupRunning', '_abortGeneration')))
            state += '\n' + next(line for line in engine_header.splitlines() if 'bool isEvaluationAborted() const' in line)
            engine_source = (ROOT / 'libraries/script-engine/src/v8/ScriptEngineV8.cpp').read_text()
            guard = 'std::unique_ptr<ScriptEngine::ScriptEngineScopeGuard> ScriptEngineV8::getScopeGuard()' + engine_source.split(
                'std::unique_ptr<ScriptEngine::ScriptEngineScopeGuard> ScriptEngineV8::getScopeGuard()', 1)[1].split('\n}', 1)[0] + '\n}\n'
            (temporary / 'method-scopeguard.inc').write_text(guard)
            lifetime = 'ScriptMethodV8Proxy::~ScriptMethodV8Proxy()' + source.split(
                'ScriptMethodV8Proxy::~ScriptMethodV8Proxy()', 1)[1].split('\n}', 1)[0] + '\n}\n'
            lifetime += 'void ScriptMethodV8Proxy::weakHandleCallback(' + source.split(
                'void ScriptMethodV8Proxy::weakHandleCallback(', 1)[1].split('\n}', 1)[0] + '\n}\n'
            (temporary / 'method-lifetime.inc').write_text(lifetime)
            abort = 'void ScriptEngineV8::abortEvaluation(' + engine_source.split('void ScriptEngineV8::abortEvaluation(', 1)[1].split('\n}', 1)[0] + '\n}\n'
            (temporary / 'abort-state.inc').write_text(state)
            (temporary / 'abort-method.inc').write_text(abort)
            binary = temporary / "test"
            library = prefix / "usr/lib64"
            subprocess.run(["c++", "-std=c++17", "-fPIC", "-pthread", "-DQT_NO_DEBUG", "-I", str(temporary),
                            "-I", str(ROOT / "libraries/shared/src/shared"),
                            "-isystem", str(prefix / "usr/include/node"),
                            str(pathlib.Path(__file__).with_name("v8-signal-test.cpp")),
                            "-L", str(library), "-Wl,-rpath," + str(library), "-lnode", "-o", str(binary), *flags],
                           check=True, timeout=40)
            for mode in ("zero", "one", "ten", "over", "empty-callback", "null-callback", "object-callback",
                         "undefined-callback", "empty-conversion", "null-arguments", "null-argument", "throw", "terminate", "stopped", "conversion-stop", "consent-denied", "consent-allowed", "method-live-delete", "method-weak-deferred-delete"):
                with self.subTest(mode=mode):
                    result = subprocess.run(["unshare", "--user", "--map-root-user", "--net", str(binary), mode],
                                            text=True, capture_output=True, timeout=5)
                    self.assertEqual(result.returncode, 0, result.stderr)


    def test_avatar_bookmark_owns_v8_scope(self):
        """Run the complete bookmark producer outside its new engine's isolate."""
        prefix = pathlib.Path(os.environ['V8_TEST_ROOT']).resolve(strict=True)
        bookmark_source = (ROOT / 'interface/src/AvatarBookmarks.cpp').read_text()
        if os.environ.get('OVERTE_BOOKMARK_SCOPE_BASELINE'):
            bookmark_source = subprocess.check_output([
                'git', '-C', str(ROOT), 'show',
                os.environ['OVERTE_BOOKMARK_SCOPE_BASELINE'] + ':interface/src/AvatarBookmarks.cpp'], text=True)
        body = 'QVariantMap AvatarBookmarks::getAvatarDataToBookmark()' + bookmark_source.split(
            'QVariantMap AvatarBookmarks::getAvatarDataToBookmark()', 1)[1].split('\n}', 1)[0] + '\n}\n'
        header = (ROOT / 'libraries/script-engine/src/v8/ScriptEngineV8.h').read_text()
        scope_type = 'class ScriptEngineScopeGuardV8 final :' + header.split(
            'class ScriptEngineScopeGuardV8 final :', 1)[1].split(
            'std::unique_ptr<ScriptEngineScopeGuard> getScopeGuard()', 1)[0]
        engine_source = (ROOT / 'libraries/script-engine/src/v8/ScriptEngineV8.cpp').read_text()
        guard = 'std::unique_ptr<ScriptEngine::ScriptEngineScopeGuard> ScriptEngineV8::getScopeGuard()' + engine_source.split(
            'std::unique_ptr<ScriptEngine::ScriptEngineScopeGuard> ScriptEngineV8::getScopeGuard()', 1)[1].split('\n}', 1)[0] + '\n}\n'
        # Entity-tree lookup and serialization are boundaries. Isolate entry,
        # locking, context switching and object/number creation use real V8.
        driver = r'''
#include <QCoreApplication>
#include <QMap>
#include <QVariant>
#include <QUrl>
#include <QUuid>
#include <v8.h>
#include <libplatform/libplatform.h>
#include <cassert>
#include <memory>
static v8::ArrayBuffer::Allocator* allocator;
struct ScriptEngine {
    struct ScriptEngineScopeGuard { virtual ~ScriptEngineScopeGuard() = default; };
    virtual std::unique_ptr<ScriptEngineScopeGuard> getScopeGuard() = 0;
    virtual ~ScriptEngine() = default;
};
struct ScriptEngineV8 final : ScriptEngine {
    v8::Isolate* _v8Isolate;
    v8::Global<v8::Context> context;
    ScriptEngineV8() {
        v8::Isolate::CreateParams parameters; parameters.array_buffer_allocator = allocator;
        _v8Isolate = v8::Isolate::New(parameters);
        auto scope = getScopeGuard(); v8::HandleScope handles(_v8Isolate);
        context.Reset(_v8Isolate, v8::Context::New(_v8Isolate));
    }
    ~ScriptEngineV8() override {
        { auto scope = getScopeGuard(); context.Reset(); }
        _v8Isolate->Dispose();
    }
#include "bookmark-scope-type.inc"
    std::unique_ptr<ScriptEngineScopeGuard> getScopeGuard() override;
};
#include "bookmark-scope.inc"
using ScriptEnginePointer = std::shared_ptr<ScriptEngine>;
ScriptEnginePointer newScriptEngine() { return std::make_shared<ScriptEngineV8>(); }
struct ScriptValue { QVariantMap values; QVariant toVariant() const { return values; } };
struct EncodeBitstreamParams {};
enum { PROP_LOCAL_POSITION=1, PROP_LOCAL_ROTATION=2, PROP_JOINT_ROTATIONS_SET=4,
       PROP_JOINT_ROTATIONS=8, PROP_JOINT_TRANSLATIONS_SET=16, PROP_JOINT_TRANSLATIONS=32,
       PROP_LOCAL_DIMENSIONS=64 };
struct EntityItemProperties { double scale = 2.0; };
struct Entity {
    bool wearable = true;
    int getEntityProperties(EncodeBitstreamParams&) { return 0; }
    EntityItemProperties getProperties(int) { return {}; }
};
struct Tree {
    QMap<QUuid, std::shared_ptr<Entity>> entities;
    std::shared_ptr<Entity> findEntityByID(const QUuid& id) { return entities.value(id); }
};
using EntityTreePointer = std::shared_ptr<Tree>;
struct Avatar {
    QMap<QUuid, QVariant> entities;
    QUrl getSkeletonModelURL() const { return QUrl("qrc:///meshes/defaultAvatar_full.fst"); }
    double getAvatarScale() const { return 1.0; }
    QMap<QUuid, QVariant> getAvatarEntityDataNonDefault() const { return entities; }
};
struct AvatarManager { std::shared_ptr<Avatar> avatar = std::make_shared<Avatar>(); auto getMyAvatar() { return avatar; } };
struct EntityTreeRenderer { EntityTreePointer tree = std::make_shared<Tree>(); auto getTree() { return tree; } };
template<class T> struct Service { inline static std::shared_ptr<T> value = std::make_shared<T>(); };
struct DependencyManager { template<class T> static auto get() { return Service<T>::value; } };
bool isWearableEntity(const std::shared_ptr<Entity>& entity) { return entity->wearable; }
static int conversions = 0;
ScriptValue EntityItemPropertiesToScriptValue(ScriptEngine* base, const EntityItemProperties& properties) {
    auto engine = static_cast<ScriptEngineV8*>(base);
    // This is the same entry invariant asserted by the real newObject path
    // in the device tombstone, with real Locker state checked as well.
    assert(engine->_v8Isolate->IsCurrent() && v8::Locker::IsLocked(engine->_v8Isolate));
    v8::HandleScope handles(engine->_v8Isolate);
    auto context = engine->context.Get(engine->_v8Isolate); v8::Context::Scope active(context);
    auto object = v8::Object::New(engine->_v8Isolate);
    auto key = v8::String::NewFromUtf8Literal(engine->_v8Isolate, "scale");
    assert(object->Set(context, key, v8::Number::New(engine->_v8Isolate, properties.scale)).FromJust());
    const double actual = object->Get(context, key).ToLocalChecked()->NumberValue(context).FromJust();
    ++conversions; return { { { "scale", actual } } };
}
const QString ENTRY_VERSION="version", ENTRY_AVATAR_URL="avatarUrl", ENTRY_AVATAR_ICON="avatarIcon",
              ENTRY_AVATAR_SCALE="avatarScale", ENTRY_AVATAR_ENTITIES="avatarEntites";
constexpr int AVATAR_BOOKMARK_VERSION=1;
struct AvatarBookmarks { QVariantMap getAvatarDataToBookmark(); };
#include "bookmark-body.inc"
int main(int argc, char** argv) {
    QCoreApplication app(argc, argv); assert(argc==2);
    v8::V8::InitializeICUDefaultLocation(argv[0]); auto platform=v8::platform::NewDefaultPlatform();
    v8::V8::InitializePlatform(platform.get()); assert(v8::V8::Initialize());
    auto allocation=std::unique_ptr<v8::ArrayBuffer::Allocator>(v8::ArrayBuffer::Allocator::NewDefaultAllocator()); allocator=allocation.get();
    const QString mode=QString::fromLocal8Bit(argv[1]);
    auto avatar=DependencyManager::get<AvatarManager>()->avatar; auto tree=DependencyManager::get<EntityTreeRenderer>()->tree;
    if(mode!="empty") {
        const auto valid=QUuid::createUuid(), missing=QUuid::createUuid(), filtered=QUuid::createUuid();
        avatar->entities.insert(valid, {}); avatar->entities.insert(missing, {}); avatar->entities.insert(filtered, {});
        tree->entities.insert(valid, std::make_shared<Entity>()); tree->entities.insert(filtered, std::make_shared<Entity>());
        tree->entities[filtered]->wearable=false;
    }
    auto verify=[&] {
        const auto result=AvatarBookmarks().getAvatarDataToBookmark();
        assert(result.value(ENTRY_AVATAR_SCALE).toDouble()==1.0);
        const auto entities=result.value(ENTRY_AVATAR_ENTITIES).toList();
        assert(entities.size()==(mode=="empty" ? 0 : 1));
        assert(conversions==(mode=="empty" ? 0 : 1));
        if(!entities.isEmpty()) assert(entities[0].toMap().value("properties").toMap().value("scale").toDouble()==2.0);
    };
    if(mode=="other-isolate-current") {
        ScriptEngineV8 caller;
        { auto scope=caller.getScopeGuard(); verify(); assert(caller._v8Isolate->IsCurrent()); }
    } else { verify(); }
    v8::V8::Dispose(); v8::V8::DisposePlatform();
}
'''
        flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs', 'Qt6Core'], text=True))
        with tempfile.TemporaryDirectory(prefix='overte-bookmark-v8-scope-') as temporary:
            temporary = pathlib.Path(temporary)
            (temporary / 'bookmark-body.inc').write_text(body)
            (temporary / 'bookmark-scope-type.inc').write_text(scope_type)
            (temporary / 'bookmark-scope.inc').write_text(guard)
            source = temporary / 'test.cpp'; source.write_text(driver)
            binary = temporary / 'test'; library = prefix / 'usr/lib64'
            subprocess.run(['c++', '-std=c++17', '-fPIC', '-pthread', '-I', str(temporary),
                            '-isystem', str(prefix / 'usr/include/node'), str(source),
                            '-L', str(library), '-Wl,-rpath,' + str(library), '-lnode', '-o', str(binary), *flags],
                           check=True, timeout=40)
            for mode in ('empty', 'one', 'other-isolate-current'):
                with self.subTest(mode=mode):
                    result = subprocess.run(['unshare', '--user', '--map-root-user', '--net', str(binary), mode],
                                            capture_output=True, text=True, timeout=5)
                    self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
