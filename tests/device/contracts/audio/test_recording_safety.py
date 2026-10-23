"""Production recording methods and WAV writer; native audio format is a seam."""
from pathlib import Path
import os, resource, shlex, shutil, subprocess, sys, tempfile
ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(Path(__file__).parents[1]/'lifecycle'))
from test_login_dialog_domain_receiver import block
resource.setrlimit(resource.RLIMIT_CORE,(0,0))
flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core'],text=True))
baseline=os.environ.get('OVERTE_RECORDING_BASELINE')
def read(relative):
 return (subprocess.check_output(['git','show',baseline+':'+relative],cwd=ROOT,text=True)
         if baseline else (ROOT/relative).read_text())
source=read('libraries/audio-client/src/AudioClient.cpp')
header=read('libraries/audio-client/src/AudioClient.h')
methods='\n'.join(block(source,s) for s in ('bool AudioClient::startRecording(', 'void AudioClient::stopRecording('))
record=block(source,'if (_audio->_isRecording)')
script_recording=block(read('interface/src/scripting/Audio.cpp'),'QUuid Audio::startRecording(')
snapshot_location=block(read('interface/src/ui/Snapshot.cpp'),'QString Snapshot::getSnapshotsLocation(')
field=next(line for line in header.splitlines() if '_isRecording {' in line)
fixture=r'''
#include <QDebug>
#include <QString>
#include <mutex>
#include <future>
#include <atomic>
#include <cassert>
#include <chrono>
using Lock=std::unique_lock<std::mutex>;
std::mutex _deviceMutex, _recordMutex;
struct File {
    std::atomic<bool> writing{false};
    std::promise<void> entered, release;
    std::shared_future<void> released{release.get_future()};
    bool create(int, const QString& path) { assert(!writing);return path!="failure"; }
    void close() { assert(!writing); }
    void addRawAudioChunk(char*,int) {
        writing=true;entered.set_value();released.wait();writing=false;
    }
};
struct AudioClient {
    File _audioFileWav;
    int _outputFormat=1;
    /* FIELD */
    bool startRecording(const QString&);
    void stopRecording();
};
/* METHODS */
struct Output {
    AudioClient* _audio;
    void record(char* data,int bytesWritten) { /* RECORD */ }
};
int main() {
    AudioClient audio;
    Output output{&audio};
    assert(audio.startRecording("recording"));
    auto writer=std::async(std::launch::async,[&]{output.record(nullptr,0);});
    assert(audio._audioFileWav.entered.get_future().wait_for(std::chrono::seconds(1))==std::future_status::ready);
    std::promise<void> stopping;
    auto stop=std::async(std::launch::async,[&]{stopping.set_value();audio.stopRecording();});
    stopping.get_future().wait();
    assert(stop.wait_for(std::chrono::milliseconds(100))==std::future_status::timeout);
    audio._audioFileWav.release.set_value();writer.get();stop.get();
    assert(!audio._isRecording);
    assert(audio.startRecording("recording"));
    assert(!audio.startRecording("failure") && !audio._isRecording);
}
'''
with tempfile.TemporaryDirectory(prefix='overte-recording-') as scratch:
 p=Path(scratch)
 (p/'test.cpp').write_text(fixture.replace('/* FIELD */',field).replace('/* METHODS */',methods).replace('/* RECORD */',record))
 subprocess.run(['c++','-std=c++17','-fPIC','-pthread',str(p/'test.cpp'),'-o',str(p/'test'),*flags],check=True,timeout=30)
 result=subprocess.run([str(p/'test')],capture_output=True,text=True,timeout=5)
 if baseline: assert result.returncode!=0 and '!writing' in result.stderr,result
 else: assert result.returncode==0,result.stderr
 # Compile the complete production WAV implementation with real QFile and
 # QDataStream. Only QAudioFormat/compatibility are replaced on this host.
 for name in ('AudioFileWav.h','AudioFileWav.cpp'):
  (p/name).write_text(read('libraries/audio-client/src/'+name))
 (p/'SnapshotStorage.h').write_text(read('interface/src/ui/SnapshotStorage.h'))
 (p/'QAudioFormat').write_text('struct QAudioFormat { int sampleSize()const{return 16;} int channelCount()const{return 2;} int sampleRate()const{return 48000;} };\n')
 (p/'AudioDeviceCompat.h').write_text('#pragma once\ninline int hifiAudioSampleSize(const QAudioFormat&){return 16;}\n')
 (p/'wav-test.cpp').write_text(r'''
#include "AudioFileWav.h"
#include "SnapshotStorage.h"
#include <QCoreApplication>
#include <QTemporaryDir>
#include <QUuid>
#include <QtEndian>
#include <cassert>
// Exercise the production scripting entry and native snapshot location getter.
// Only dependency ownership, locking and the device callback are host seams.
bool nativeReviewEnabled() { return true; }
struct Snapshot {
 struct LegacyLocation { QString get(const QString& = QString()) const { return {}; } } _snapshotsLocation;
 QString getSnapshotsLocation();
};
struct AudioClient {
 AudioFileWav file;
 QString path;
 bool startRecording(const QString& requested) {
  path=requested;
  // Never let the captured old implementation write outside this test's dir.
  if (!path.startsWith(qEnvironmentVariable("XDG_DATA_HOME") + "/")) { return false; }
  return file.create(QAudioFormat(),path);
 }
};
struct DependencyManager {
 template<class T> static T* get() { static T instance; return &instance; }
};
namespace scripting {
struct Audio {
 template<class T,class F> T resultWithWriteLock(F f) { return f(); }
 QUuid startRecording();
};
}
/* SNAPSHOT_LOCATION */
using namespace scripting;
/* SCRIPT_RECORDING */
int main(int argc,char**argv){
 QCoreApplication app(argc,argv);
 QTemporaryDir directory;assert(directory.isValid());
 qputenv("XDG_DATA_HOME",directory.path().toUtf8());
 auto first=directory.filePath("first.wav"),second=directory.filePath("second.wav");
 AudioFileWav file;file.close();
 QAudioFormat format;assert(file.create(format,first));
 char samples[8]={1,2,3,4,5,6,7,8};assert(file.addRawAudioChunk(samples,8));
 assert(file.create(format,second)); // must finalize first RIFF lengths
 QFile saved(first);assert(saved.open(QIODevice::ReadOnly));auto bytes=saved.readAll();
 assert(bytes.size()==52);
 assert(qFromLittleEndian<quint32>(bytes.constData()+4)==44);
 assert(qFromLittleEndian<quint32>(bytes.constData()+40)==8);
 assert(bytes.mid(44)==QByteArray(samples,8));
 file.close();file.close();
 assert(!file.create(format,directory.filePath("absent/file.wav")));

 // Mobile has a native-owned directory even when the legacy preference is absent.
 auto snapshot=DependencyManager::get<Snapshot>();
 assert(snapshot->_snapshotsLocation.get().isEmpty());
 auto root=snapshot->getSnapshotsLocation();
 assert(root.startsWith(directory.path()+"/") && !QFileInfo::exists(root));
 Audio audio;auto id=audio.startRecording();assert(!id.isNull());
 auto client=DependencyManager::get<AudioClient>();
 assert(QFileInfo(client->path).absolutePath()==root);
 assert(QFileInfo(client->path).fileName()=="overte-audio-"+id.toString()+".wav");
 assert(client->file.addRawAudioChunk(samples,8));client->file.close();
 QFile recording(client->path);assert(recording.open(QIODevice::ReadOnly));
 auto recorded=recording.readAll();recording.close();
 assert(recorded.size()==52 && recorded.mid(44)==QByteArray(samples,8));
 assert(qFromLittleEndian<quint32>(recorded.constData()+40)==8);
 // A blocked directory must return failure without changing existing data.
 assert(QDir(root).removeRecursively());
 QFile blocked(root);assert(blocked.open(QIODevice::WriteOnly));
 assert(blocked.write("keep")==4);blocked.close();
 assert(audio.startRecording().isNull());
 assert(blocked.open(QIODevice::ReadOnly) && blocked.readAll()=="keep");
}
'''.replace('/* SNAPSHOT_LOCATION */',snapshot_location).replace('/* SCRIPT_RECORDING */',script_recording))
 moc=Path(subprocess.check_output(['pkg-config','--variable=libexecdir','Qt6Core'],text=True).strip())/'moc'
 subprocess.run([str(moc),'-I'+str(p),str(p/'AudioFileWav.h'),'-o',str(p/'moc.cpp')],check=True,timeout=15)
 subprocess.run(['c++','-std=c++17','-fPIC','-I'+str(p),str(p/'AudioFileWav.cpp'),str(p/'moc.cpp'),str(p/'wav-test.cpp'),'-o',str(p/'wav-test'),*flags],check=True,timeout=30)
 result=subprocess.run([str(p/'wav-test')],capture_output=True,text=True,timeout=5)
 if baseline: assert result.returncode!=0 and '==44' in result.stderr,result
 else: assert result.returncode==0,result.stderr
print(('EXPECTED BASELINE FAILURES: concurrent file close and unfinalized RIFF header' if baseline else 'PASS actual recording serialization, WAV finalization, scripting mobile directory selection/creation and blocked directory preservation'))
