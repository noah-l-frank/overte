// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#if !defined(OVERTE_E2E_FEATURE_TESTS)
#error This observer belongs only to the separately selected Snapshot companion.
#endif
#import "CompanionIdentity.h"
#import <CommonCrypto/CommonDigest.h>
#if !defined(OVT_SNAPSHOT_SHARE_ARCHIVE)
#import <Photos/Photos.h>
#endif
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <mach-o/dyld.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

#if defined(OVT_SNAPSHOT_SHARE_ARCHIVE)
static NSString* const OVTIdentityRole=@"share-archive";
static NSString* const OVTIdentityVersion=@"snapshotShareCompanionObservationVersion";
static NSString* const OVTIdentityPrefix=@"snapshot.share.companion";
static NSString* const OVTIdentityFilePrefix=@"snapshot-share-companion";
static NSArray* OVTIdentityActions(void) {return @[@"identity",@"clock"];}
#else
static NSString* const OVTIdentityRole=@"photos";
static NSString* const OVTIdentityVersion=@"snapshotCompanionObservationVersion";
static NSString* const OVTIdentityPrefix=@"snapshot.companion";
static NSString* const OVTIdentityFilePrefix=@"snapshot-companion";
static NSArray* OVTIdentityActions(void) {return @[@"identity",@"clock",@"photos"];}
#endif

static NSDictionary* OVTIdentityClock(void) {
    return @{ @"epochMs":@((long long)(NSDate.date.timeIntervalSince1970*1000)),
              @"monotonicMs":@((long long)(NSProcessInfo.processInfo.systemUptime*1000)) };
}
static NSString* OVTIdentityID(void) {return [NSUUID.UUID.UUIDString.lowercaseString stringByReplacingOccurrencesOfString:@"-" withString:@""];}
static BOOL OVTIdentityMatch(NSString* value,NSString* expression) {
    return [value isKindOfClass:NSString.class] && [value rangeOfString:expression options:NSRegularExpressionSearch].location!=NSNotFound;
}
static BOOL OVTIdentitySame(struct stat a,struct stat b) {
    return a.st_dev==b.st_dev && a.st_ino==b.st_ino && a.st_mode==b.st_mode && a.st_nlink==b.st_nlink && a.st_size==b.st_size
        && a.st_mtimespec.tv_sec==b.st_mtimespec.tv_sec && a.st_mtimespec.tv_nsec==b.st_mtimespec.tv_nsec
        && a.st_ctimespec.tv_sec==b.st_ctimespec.tv_sec && a.st_ctimespec.tv_nsec==b.st_ctimespec.tv_nsec;
}
static NSString* OVTIdentityHash(NSData* bytes) {
    NSMutableString* result=[NSMutableString new];const unsigned char* value=bytes.bytes;
    for (NSUInteger index=0;index<bytes.length;++index) {[result appendFormat:@"%02x",value[index]];}return result;
}
static BOOL OVTIdentityName(NSString* path) {
    NSData* raw=[path dataUsingEncoding:NSASCIIStringEncoding allowLossyConversion:NO];
    if (!raw || raw.length<1 || raw.length>1024 || [path hasPrefix:@"/"] || [path containsString:@"\\"]
            || [path rangeOfCharacterFromSet:NSCharacterSet.controlCharacterSet].location!=NSNotFound) {return NO;}
    NSArray* components=[path componentsSeparatedByString:@"/"];if (components.count>64) {return NO;}
    for (NSString* part in components) {if (!part.length || part.length>255 || [part isEqual:@"."] || [part isEqual:@".."]) {return NO;}}return YES;
}
#if defined(OVT_SNAPSHOT_SHARE_ARCHIVE)
static NSString* OVTIdentitySHA(NSData* bytes) {
    unsigned char value[CC_SHA256_DIGEST_LENGTH];CC_SHA256(bytes.bytes,(CC_LONG)bytes.length,value);
    return OVTIdentityHash([NSData dataWithBytes:value length:sizeof(value)]);
}
static NSString* OVTIdentityParent(struct stat value) {
    if (!S_ISDIR(value.st_mode) || value.st_uid!=geteuid()) {return nil;}
    return OVTIdentitySHA([[NSString stringWithFormat:@"%llu:%llu:%u:%u:%u",(unsigned long long)value.st_dev,
        (unsigned long long)value.st_ino,(unsigned)value.st_mode,(unsigned)value.st_uid,(unsigned)value.st_gid] dataUsingEncoding:NSUTF8StringEncoding]);
}
static NSString* OVTIdentityRevision(struct stat value) {
    return OVTIdentitySHA([[NSString stringWithFormat:@"%llu:%llu:%u:%llu:%u:%u:%lld:%lld:%lld:%lld:%lld",(unsigned long long)value.st_dev,
        (unsigned long long)value.st_ino,(unsigned)value.st_mode,(unsigned long long)value.st_nlink,(unsigned)value.st_uid,(unsigned)value.st_gid,
        (long long)value.st_size,(long long)value.st_mtimespec.tv_sec,(long long)value.st_mtimespec.tv_nsec,
        (long long)value.st_ctimespec.tv_sec,(long long)value.st_ctimespec.tv_nsec] dataUsingEncoding:NSUTF8StringEncoding]);
}
static NSDictionary* OVTIdentityOutput(int directory,NSString* name,NSString* parent) {
    if (![@[@"snapshot-share-companion-identity.json",@"snapshot-share-companion-clock.json"] containsObject:name]) {return nil;}
    int file=openat(directory,name.UTF8String,O_RDONLY|O_NOFOLLOW|O_NONBLOCK|O_CLOEXEC);struct stat before,after,named;
    BOOL valid=file>=0 && fstat(file,&before)==0 && S_ISREG(before.st_mode) && before.st_nlink==1 && before.st_uid==geteuid()
        && (before.st_mode&0777)==0600 && before.st_size>0 && before.st_size<=262144;
    NSMutableData* raw=[NSMutableData new];unsigned char buffer[32768];NSTimeInterval began=NSProcessInfo.processInfo.systemUptime;
    while (valid) {
        ssize_t size=read(file,buffer,sizeof(buffer));if (size<0 && errno==EINTR) {continue;}
        if (size<0 || NSProcessInfo.processInfo.systemUptime-began>=1.5) {valid=NO;break;}if (!size) {break;}
        if (raw.length+(NSUInteger)size>262144) {valid=NO;break;}[raw appendBytes:buffer length:(NSUInteger)size];
    }
    valid=valid && raw.length==(NSUInteger)before.st_size && fstat(file,&after)==0 && OVTIdentitySame(before,after)
        && fstatat(directory,name.UTF8String,&named,AT_SYMLINK_NOFOLLOW)==0 && OVTIdentitySame(before,named);
    if (file>=0 && close(file)!=0) {valid=NO;}if (!valid) {return nil;}
    return @{@"name":name,@"revision":OVTIdentityRevision(before),@"sha256":OVTIdentitySHA(raw),@"byteCount":@(raw.length),@"parentIdentity":parent};
}
#endif
@interface OVTIdentityNode : NSObject {
@public struct stat original;
}
@property(nonatomic,copy) NSString* path;
@property(nonatomic,strong) NSData* digest;
@property BOOL directory;
@end
@implementation OVTIdentityNode
@end

@interface OVTSnapshotCompanionIdentity () {
    int _root;
    struct stat _originalRoot;
}
@property(nonatomic,strong) NSRecursiveLock* lock;
@property(nonatomic,copy) NSString* instance;
@property(nonatomic,copy) NSString* bundle;
@property(nonatomic,copy) NSString* rootPath;
@property(nonatomic,copy) NSString* executable;
@property(nonatomic,strong) NSDictionary* born;
@property(nonatomic,strong) NSDictionary* prepared;
@property(nonatomic,strong) NSDictionary* identity;
@property(nonatomic,strong) NSMutableArray<OVTIdentityNode*>* nodes;
@property(nonatomic,strong) NSMutableSet<NSString*>* queries;
@property NSUInteger sequence;
@property BOOL ready;
@property BOOL failed;
#if defined(OVT_SNAPSHOT_SHARE_ARCHIVE)
@property(nonatomic,strong) NSURL* archiveDocuments;
@property(nonatomic,copy) NSString* archiveDocumentsIdentity;
@property(nonatomic,strong) NSMutableDictionary* archiveOutputs;
@property(nonatomic,strong) NSDictionary* lastArchiveObservation;
@property(nonatomic,strong) NSDictionary* archiveSeal;
@property(nonatomic,strong) NSData* archiveSealData;
@property(nonatomic,weak) NSObject* archiveCollector;
@property BOOL archiveSealed;
- (BOOL)persistArchive:(NSDictionary*)packet action:(NSString*)action;
#endif
@end
@implementation OVTSnapshotCompanionIdentity
+ (instancetype)shared {
    static OVTSnapshotCompanionIdentity* source;static dispatch_once_t once;
    dispatch_once(&once,^{source=[OVTSnapshotCompanionIdentity new];});return source;
}
- (instancetype)init {
    if ((self=[super init])) {
        _root=-1;self.lock=[NSRecursiveLock new];self.instance=OVTIdentityID();self.born=OVTIdentityClock();self.queries=[NSMutableSet new];self.nodes=[NSMutableArray new];
#if defined(OVT_SNAPSHOT_SHARE_ARCHIVE)
        self.archiveOutputs=[NSMutableDictionary new];self.archiveDocuments=[NSFileManager.defaultManager URLsForDirectory:NSDocumentDirectory inDomains:NSUserDomainMask].firstObject;
        struct stat documents;self.archiveDocumentsIdentity=lstat(self.archiveDocuments.fileSystemRepresentation,&documents)==0?OVTIdentityParent(documents):nil;
#endif
        NSBundle* actual=NSBundle.mainBundle;NSString* root=actual.bundleURL.URLByResolvingSymlinksInPath.path;
        NSString* executable=actual.executableURL.URLByResolvingSymlinksInPath.path;self.bundle=actual.bundleIdentifier;
        uint32_t size=0;_NSGetExecutablePath(NULL,&size);NSMutableData* name=[NSMutableData dataWithLength:size];
        BOOL process=size>0 && size<=16384 && _NSGetExecutablePath(name.mutableBytes,&size)==0;
        NSString* original=process?[[NSString stringWithUTF8String:name.bytes] stringByResolvingSymlinksInPath]:nil;
        NSString* leaf=executable.lastPathComponent;
        self.failed=![root hasSuffix:@".app"] || [root.lastPathComponent isEqual:@"Overte.app"] || ![executable isEqual:[root stringByAppendingPathComponent:leaf]]
            || ![executable isEqual:original] || !OVTIdentityName(leaf) || [leaf containsString:@"/"]
            || !OVTIdentityMatch(self.bundle,@"\\A[A-Za-z0-9_-]+(?:\\.[A-Za-z0-9_-]+)+\\z")
            || ![[actual objectForInfoDictionaryKey:@"OVTSnapshotCompanionContractVersion"] isEqual:@1]
            || ![[actual objectForInfoDictionaryKey:@"OVTSnapshotCompanionRole"] isEqual:OVTIdentityRole];
        self.rootPath=root;self.executable=leaf;
        if (!self.failed) {
#if defined(OVT_SNAPSHOT_SHARE_ARCHIVE)
            NSObject* collector=[NSObject new];self.archiveCollector=collector;
#endif
            dispatch_async(dispatch_get_global_queue(QOS_CLASS_UTILITY,0),^{
            BOOL okay=[self collect];[self.lock lock];self.prepared=okay?OVTIdentityClock():nil;
            self.failed=!okay;self.ready=okay;[self.lock unlock];
#if defined(OVT_SNAPSHOT_SHARE_ARCHIVE)
            // The actual queued block owns this lease through its final use.
            // Sealing cannot substitute ready=true for the lease's weak expiry.
            [collector class];
#endif
        });}
    }return self;
}
- (void)dealloc {if (_root>=0) {close(_root);}}
- (BOOL)census:(int)parent prefix:(NSString*)prefix expected:(NSDictionary<NSString*,OVTIdentityNode*>*)expected
        seen:(NSMutableSet<NSString*>*)seen began:(NSTimeInterval)began budget:(NSTimeInterval)budget {
    struct stat directoryBefore;
    OVTIdentityNode* directoryNode=prefix.length?expected[prefix]:nil;
    if (prefix.length && !directoryNode) {return NO;}
    struct stat original=prefix.length?directoryNode->original:_originalRoot;
    if (NSProcessInfo.processInfo.systemUptime-began>=budget || fstat(parent,&directoryBefore)!=0
            || !S_ISDIR(directoryBefore.st_mode) || !OVTIdentitySame(directoryBefore,original)) {return NO;}
    // Open a fresh directory description rather than dup(): readdir on a dup
    // shares the cached root's offset and can otherwise begin at its old EOF.
    int cursor=openat(parent,".",O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);
    if (cursor<0) {return NO;}DIR* directory=fdopendir(cursor);if (!directory) {close(cursor);return NO;}
    BOOL okay=YES;errno=0;struct dirent* entry;
    while ((entry=readdir(directory))) {
        NSString* component=[[NSString alloc] initWithBytes:entry->d_name length:strlen(entry->d_name) encoding:NSASCIIStringEncoding];
        if ([component isEqual:@"."] || [component isEqual:@".."]) {errno=0;continue;}
        NSString* path=prefix.length?[prefix stringByAppendingFormat:@"/%@",component]:component;
        OVTIdentityNode* node=component?expected[path]:nil;
        if (!node || !OVTIdentityName(path) || seen.count>=20000 || [seen containsObject:path]
                || NSProcessInfo.processInfo.systemUptime-began>=budget) {okay=NO;break;}
        struct stat named,opened;
        if (fstatat(parent,entry->d_name,&named,AT_SYMLINK_NOFOLLOW)!=0 || !OVTIdentitySame(named,node->original)) {okay=NO;break;}
        int child=openat(parent,entry->d_name,O_RDONLY|O_NOFOLLOW|O_NONBLOCK|O_CLOEXEC|(node.directory?O_DIRECTORY:0));
        if (child<0 || fstat(child,&opened)!=0 || !OVTIdentitySame(opened,node->original)) {if (child>=0) {close(child);}okay=NO;break;}
        [seen addObject:path];
        if (node.directory) {okay=[self census:child prefix:path expected:expected seen:seen began:began budget:budget];}
        // Recheck both the opened object and its parent-relative name after
        // visiting all descendants. Intermediate symlinks are never followed.
        if (fstat(child,&opened)!=0 || !OVTIdentitySame(opened,node->original)
                || fstatat(parent,entry->d_name,&named,AT_SYMLINK_NOFOLLOW)!=0 || !OVTIdentitySame(named,node->original)) {okay=NO;}
        if (close(child)!=0) {okay=NO;}if (!okay) {break;}errno=0;
    }
    if (errno) {okay=NO;}if (closedir(directory)!=0) {okay=NO;}
    struct stat directoryAfter;
    return okay && fstat(parent,&directoryAfter)==0 && OVTIdentitySame(directoryBefore,directoryAfter)
        && OVTIdentitySame(directoryAfter,original) && NSProcessInfo.processInfo.systemUptime-began<budget;
}
- (BOOL)valid:(NSTimeInterval)began budget:(NSTimeInterval)budget {
    struct stat actual;
    if (_root<0 || fstat(_root,&actual)!=0 || !OVTIdentitySame(actual,_originalRoot)
            || lstat(self.rootPath.fileSystemRepresentation,&actual)!=0 || !OVTIdentitySame(actual,_originalRoot)) {return NO;}
    NSMutableDictionary<NSString*,OVTIdentityNode*>* expected=[NSMutableDictionary new];
    for (OVTIdentityNode* node in self.nodes) {
        if (NSProcessInfo.processInfo.systemUptime-began>=budget || expected[node.path]) {return NO;}expected[node.path]=node;
    }
    NSMutableSet<NSString*>* seen=[NSMutableSet new];
    if (![self census:_root prefix:@"" expected:expected seen:seen began:began budget:budget] || seen.count!=self.nodes.count) {return NO;}
    // The current path must still refer to the same root after the complete
    // exact census. Added, missing and replaced nodes cannot reuse old hashes.
    return fstat(_root,&actual)==0 && OVTIdentitySame(actual,_originalRoot)
        && lstat(self.rootPath.fileSystemRepresentation,&actual)==0 && OVTIdentitySame(actual,_originalRoot)
        && NSProcessInfo.processInfo.systemUptime-began<budget;
}
- (BOOL)walk:(int)parent prefix:(NSString*)prefix began:(NSTimeInterval)began names:(NSMutableSet*)names total:(uint64_t*)total files:(NSUInteger*)files {
    int duplicate=dup(parent);if (duplicate<0) {return NO;}DIR* directory=fdopendir(duplicate);if (!directory) {close(duplicate);return NO;}
    BOOL okay=YES;errno=0;struct dirent* entry;
    while ((entry=readdir(directory))) {
        NSString* component=[[NSString alloc] initWithBytes:entry->d_name length:strlen(entry->d_name) encoding:NSASCIIStringEncoding];
        if ([component isEqual:@"."] || [component isEqual:@".."]) {errno=0;continue;}
        NSString* path=prefix.length?[prefix stringByAppendingFormat:@"/%@",component]:component;
        if (!component || !OVTIdentityName(path) || self.nodes.count>=20000 || [names containsObject:path.lowercaseString]
                || NSProcessInfo.processInfo.systemUptime-began>=90) {okay=NO;break;}[names addObject:path.lowercaseString];
        OVTIdentityNode* node=[OVTIdentityNode new];node.path=path;
        if (fstatat(parent,entry->d_name,&node->original,AT_SYMLINK_NOFOLLOW)!=0) {okay=NO;break;}
        node.directory=S_ISDIR(node->original.st_mode);
        if (!node.directory && (!S_ISREG(node->original.st_mode) || node->original.st_nlink!=1 || node->original.st_size<0 || node->original.st_size>1024LL*1024*1024)) {okay=NO;break;}
        int file=openat(parent,entry->d_name,O_RDONLY|O_NOFOLLOW|O_NONBLOCK|O_CLOEXEC|(node.directory?O_DIRECTORY:0));struct stat opened;
        if (file<0 || fstat(file,&opened)!=0 || !OVTIdentitySame(opened,node->original)) {if (file>=0) {close(file);}okay=NO;break;}
        CC_SHA256_CTX digest;CC_SHA256_Init(&digest);
        if (node.directory) {
            unsigned char empty[CC_SHA256_DIGEST_LENGTH];CC_SHA256_Final(empty,&digest);node.digest=[NSData dataWithBytes:empty length:sizeof(empty)];
            [self.nodes addObject:node];okay=[self walk:file prefix:path began:began names:names total:total files:files];
        } else {
            *total+=(uint64_t)node->original.st_size;if (*total>2ULL*1024*1024*1024) {okay=NO;}
            unsigned char bytes[65536];uint64_t count=0;
            while (okay) {
                ssize_t length=read(file,bytes,sizeof(bytes));if (length<0 && errno==EINTR) {continue;}
                if (length<0 || NSProcessInfo.processInfo.systemUptime-began>=90) {okay=NO;break;}if (!length) {break;}
                count+=(uint64_t)length;if (count>(uint64_t)node->original.st_size) {okay=NO;break;}CC_SHA256_Update(&digest,bytes,(CC_LONG)length);
            }
            okay=okay && count==(uint64_t)node->original.st_size;
            if (okay) {unsigned char hash[CC_SHA256_DIGEST_LENGTH];CC_SHA256_Final(hash,&digest);node.digest=[NSData dataWithBytes:hash length:sizeof(hash)];[self.nodes addObject:node];++*files;}
        }
        struct stat after;if (fstat(file,&after)!=0 || !OVTIdentitySame(after,node->original)) {okay=NO;}if (close(file)!=0) {okay=NO;}
        if (!okay) {break;}errno=0;
    }
    if (errno) {okay=NO;}if (closedir(directory)!=0) {okay=NO;}return okay;
}
- (BOOL)collect {
    NSTimeInterval began=NSProcessInfo.processInfo.systemUptime;
    _root=open(self.rootPath.fileSystemRepresentation,O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);
    if (_root<0 || fstat(_root,&_originalRoot)!=0 || !S_ISDIR(_originalRoot.st_mode)) {return NO;}
    uint64_t total=0;NSUInteger files=0;
    if (![self walk:_root prefix:@"" began:began names:[NSMutableSet new] total:&total files:&files]
            || !files || !total || ![self valid:began budget:90]) {return NO;}
    [self.nodes sortUsingComparator:^NSComparisonResult(OVTIdentityNode* a,OVTIdentityNode* b) {return [a.path compare:b.path options:NSLiteralSearch];}];
    CC_SHA256_CTX digest;CC_SHA256_Init(&digest);const char contract[]="overte-ios-installed-bundle-v1";CC_SHA256_Update(&digest,contract,sizeof(contract));
    NSString* executable=nil;
    for (OVTIdentityNode* node in self.nodes) {
        unsigned char kind=node.directory?'D':'F';CC_SHA256_Update(&digest,&kind,1);NSData* path=[node.path dataUsingEncoding:NSASCIIStringEncoding];
        unsigned char length[4],size[8];uint64_t count=node.directory?0:(uint64_t)node->original.st_size;
        for (int index=0;index<4;++index) {length[index]=(unsigned char)(path.length>>(8*(3-index)));}
        for (int index=0;index<8;++index) {size[index]=(unsigned char)(count>>(8*(7-index)));}
        CC_SHA256_Update(&digest,length,4);CC_SHA256_Update(&digest,path.bytes,(CC_LONG)path.length);CC_SHA256_Update(&digest,size,8);CC_SHA256_Update(&digest,node.digest.bytes,(CC_LONG)node.digest.length);
        if (!node.directory && [node.path isEqual:self.executable]) {executable=OVTIdentityHash(node.digest);}
    }
    if (!executable || ![self valid:began budget:90]) {return NO;}
    unsigned char hash[CC_SHA256_DIGEST_LENGTH];CC_SHA256_Final(hash,&digest);
    self.identity=@{@"bundleContractVersion":@1,@"bundleId":self.bundle,@"executableSha256":executable,
        @"bundleSha256":OVTIdentityHash([NSData dataWithBytes:hash length:sizeof(hash)]),@"nodeCount":@(self.nodes.count),@"fileCount":@(files),@"totalBytes":@(total)};return YES;
}
- (NSDictionary*)observe:(NSDictionary*)query {
    if (![NSThread isMainThread] || ![query isKindOfClass:NSDictionary.class] || query.count!=2
            || !OVTIdentityMatch(query[@"nonce"],@"\\Aios-[0-9a-f]{32}\\z") || ![OVTIdentityActions() containsObject:query[@"action"]]) {return nil;}
    [self.lock lock];NSString* nonce=query[@"nonce"],*action=query[@"action"];
#if defined(OVT_SNAPSHOT_SHARE_ARCHIVE)
    if (self.archiveSealed) {[self.lock unlock];return nil;}
#endif
    if (self.queries.count>=128 || [self.queries containsObject:nonce] || self.sequence>=9007199254740991ULL) {[self.lock unlock];return nil;}
    [self.queries addObject:nonce];NSDictionary* before=OVTIdentityClock();NSTimeInterval began=NSProcessInfo.processInfo.systemUptime;
    NSInteger permissionBefore=0,permissionAfter=0;
#if !defined(OVT_SNAPSHOT_SHARE_ARCHIVE)
    BOOL photos=[action isEqual:@"photos"];
    permissionBefore=photos?[PHPhotoLibrary authorizationStatusForAccessLevel:PHAccessLevelReadWrite]:PHAuthorizationStatusNotDetermined;
#endif
    BOOL identity=[action isEqual:@"identity"];
    if (!self.failed && self.ready && ![self valid:began budget:1.5]) {self.failed=YES;}
#if !defined(OVT_SNAPSHOT_SHARE_ARCHIVE)
    permissionAfter=photos?[PHPhotoLibrary authorizationStatusForAccessLevel:PHAccessLevelReadWrite]:PHAuthorizationStatusNotDetermined;
#endif
    NSDictionary* after=OVTIdentityClock();
    if ([after[@"epochMs"] longLongValue]<[before[@"epochMs"] longLongValue] || [after[@"monotonicMs"] longLongValue]<[before[@"monotonicMs"] longLongValue]) {self.failed=YES;}
    NSMutableDictionary* packet=[@{OVTIdentityVersion:@1,@"action":action,@"nonce":nonce,@"role":OVTIdentityRole,
        @"instance":self.instance,@"processId":@(getpid()),@"bundleId":self.bundle?:@"",@"sequence":@(++self.sequence),
        @"sourceBirthClock":self.born,@"clockBefore":before,@"clockAfter":after,@"status":self.failed?@"unavailable":identity&&!self.ready?@"pending":@"ready"} mutableCopy];
    if (identity) {packet[@"preparedClock"]=self.ready&&!self.failed?self.prepared:NSNull.null;packet[@"bundle"]=self.ready&&!self.failed?self.identity:@{};}
    if ([action isEqual:@"photos"]) {
        packet[@"readWriteAuthorizationBefore"]=@(permissionBefore);packet[@"readWriteAuthorizationAfter"]=@(permissionAfter);
        if (permissionBefore!=permissionAfter) {packet[@"status"]=@"unavailable";}
    }
#if defined(OVT_SNAPSHOT_SHARE_ARCHIVE)
    self.lastArchiveObservation=[packet copy];
#endif
    [self.lock unlock];return packet;
}
- (BOOL)persist:(NSDictionary*)packet action:(NSString*)action {
#if defined(OVT_SNAPSHOT_SHARE_ARCHIVE)
    return [self persistArchive:packet action:action];
#else
    if (!packet || ![OVTIdentityActions() containsObject:action]) {return NO;}
    NSData* bytes=[NSJSONSerialization dataWithJSONObject:packet options:0 error:nil];if (!bytes || bytes.length>262144) {return NO;}
    NSURL* root=[NSFileManager.defaultManager URLsForDirectory:NSDocumentDirectory inDomains:NSUserDomainMask].firstObject;
    NSString* temporary=[root.path stringByAppendingPathComponent:[@".companion-" stringByAppendingString:OVTIdentityID()]];
    int output=open(temporary.fileSystemRepresentation,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW,0600);if (output<0) {return NO;}
    NSUInteger offset=0;BOOL okay=YES;
    while (offset<bytes.length) {ssize_t count=write(output,(const char*)bytes.bytes+offset,bytes.length-offset);if (count<0 && errno==EINTR) {continue;}if (count<=0) {okay=NO;break;}offset+=(NSUInteger)count;}
    if (fsync(output)!=0) {okay=NO;}if (close(output)!=0) {okay=NO;}
    NSString* destination=[root.path stringByAppendingPathComponent:[NSString stringWithFormat:@"%@-%@.json",OVTIdentityFilePrefix,action]];
    if (okay && rename(temporary.fileSystemRepresentation,destination.fileSystemRepresentation)!=0) {okay=NO;}
    int directory=open(root.path.fileSystemRepresentation,O_RDONLY|O_DIRECTORY|O_NOFOLLOW);
    if (directory<0) {okay=NO;}else {if (fsync(directory)!=0) {okay=NO;}close(directory);}return okay;
#endif
}
#if defined(OVT_SNAPSHOT_SHARE_ARCHIVE)
- (BOOL)persistArchive:(NSDictionary*)packet action:(NSString*)action {
    if (![NSThread isMainThread] || !packet || ![OVTIdentityActions() containsObject:action]) {return NO;}
    [self.lock lock];BOOL valid=!self.archiveSealed && self.archiveDocumentsIdentity && [packet isEqual:self.lastArchiveObservation]
        && [packet[@"action"] isEqual:action];NSData* bytes=valid?[NSJSONSerialization dataWithJSONObject:packet options:0 error:nil]:nil;
    valid=valid && bytes.length>0 && bytes.length<=262144;struct stat opened,named,written,published;
    int directory=valid?open(self.archiveDocuments.fileSystemRepresentation,O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC):-1;
    valid=valid && directory>=0 && fstat(directory,&opened)==0 && [OVTIdentityParent(opened) isEqual:self.archiveDocumentsIdentity]
        && lstat(self.archiveDocuments.fileSystemRepresentation,&named)==0 && [OVTIdentityParent(named) isEqual:self.archiveDocumentsIdentity];
    NSString* name=[NSString stringWithFormat:@"snapshot-share-companion-%@.json",action];NSDictionary* previous=self.archiveOutputs[action];
    if (valid && previous) {valid=[previous isEqual:OVTIdentityOutput(directory,name,self.archiveDocumentsIdentity)];}
    else if (valid) {errno=0;valid=fstatat(directory,name.UTF8String,&named,AT_SYMLINK_NOFOLLOW)!=0 && errno==ENOENT;}
    NSString* temporary=[@".companion-" stringByAppendingString:OVTIdentityID()];
    int output=valid?openat(directory,temporary.UTF8String,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC,0600):-1;
    valid=valid && output>=0;NSUInteger offset=0;NSTimeInterval began=NSProcessInfo.processInfo.systemUptime;
    while (valid && offset<bytes.length) {
        ssize_t count=write(output,(const char*)bytes.bytes+offset,bytes.length-offset);if (count<0 && errno==EINTR) {continue;}
        if (count<=0 || NSProcessInfo.processInfo.systemUptime-began>=1.5) {valid=NO;break;}offset+=(NSUInteger)count;
    }
    if (output>=0) {
        if (fsync(output)!=0 || fstat(output,&written)!=0) {valid=NO;}
        if (close(output)!=0) {valid=NO;}
    }
    valid=valid && offset==bytes.length && S_ISREG(written.st_mode) && written.st_nlink==1 && written.st_uid==geteuid()
        && (written.st_mode&0777)==0600 && written.st_size==(off_t)bytes.length;
    if (valid && renameat(directory,temporary.UTF8String,directory,name.UTF8String)!=0) {valid=NO;}
    valid=valid && fstatat(directory,name.UTF8String,&published,AT_SYMLINK_NOFOLLOW)==0 && published.st_dev==written.st_dev
        && published.st_ino==written.st_ino && published.st_mode==written.st_mode && published.st_nlink==written.st_nlink
        && published.st_uid==written.st_uid && published.st_gid==written.st_gid && published.st_size==written.st_size
        && published.st_mtimespec.tv_sec==written.st_mtimespec.tv_sec && published.st_mtimespec.tv_nsec==written.st_mtimespec.tv_nsec;
    NSDictionary* pin=valid?OVTIdentityOutput(directory,name,self.archiveDocumentsIdentity):nil;
    valid=valid && pin && [pin[@"revision"] isEqual:OVTIdentityRevision(published)] && [pin[@"sha256"] isEqual:OVTIdentitySHA(bytes)]
        && fstat(directory,&named)==0 && [OVTIdentityParent(named) isEqual:self.archiveDocumentsIdentity]
        && lstat(self.archiveDocuments.fileSystemRepresentation,&named)==0 && [OVTIdentityParent(named) isEqual:self.archiveDocumentsIdentity];
    if (directory>=0) {if (fsync(directory)!=0) {valid=NO;}if (close(directory)!=0) {valid=NO;}}
    if (valid) {self.archiveOutputs[action]=pin;}else {self.failed=YES;}
    [self.lock unlock];return valid;
}
- (NSDictionary*)sealArchiveAdmission:(NSString*)nonce {
    if (![NSThread isMainThread] || !OVTIdentityMatch(nonce,@"\\Aios-[a-f0-9]{32}\\z")) {return nil;}
    [self.lock lock];
    if (self.archiveSealed || self.failed || !self.ready || self.archiveCollector || self.queries.count>=128 || [self.queries containsObject:nonce]
        || self.sequence>=9007199254740991ULL || self.archiveOutputs.count!=2) {[self.lock unlock];return nil;}
    [self.queries addObject:nonce];NSDictionary* before=OVTIdentityClock();NSTimeInterval began=NSProcessInfo.processInfo.systemUptime;
    BOOL valid=[self valid:began budget:1.5];struct stat opened,named;
    int directory=valid?open(self.archiveDocuments.fileSystemRepresentation,O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC):-1;
    valid=valid && directory>=0 && fstat(directory,&opened)==0 && [OVTIdentityParent(opened) isEqual:self.archiveDocumentsIdentity]
        && lstat(self.archiveDocuments.fileSystemRepresentation,&named)==0 && [OVTIdentityParent(named) isEqual:self.archiveDocumentsIdentity];
    NSMutableArray* outputs=[NSMutableArray new];
    for (NSString* action in @[@"identity",@"clock"]) {
        NSDictionary* pin=valid?OVTIdentityOutput(directory,[NSString stringWithFormat:@"snapshot-share-companion-%@.json",action],self.archiveDocumentsIdentity):nil;
        valid=valid && pin && [pin isEqual:self.archiveOutputs[action]];if (valid) {[outputs addObject:pin];}
    }
    valid=valid && fstat(directory,&opened)==0 && [OVTIdentityParent(opened) isEqual:self.archiveDocumentsIdentity]
        && lstat(self.archiveDocuments.fileSystemRepresentation,&named)==0 && [OVTIdentityParent(named) isEqual:self.archiveDocumentsIdentity];
    if (directory>=0 && close(directory)!=0) {valid=NO;}
    if (!valid || NSProcessInfo.processInfo.systemUptime-began>=1.5) {self.failed=YES;[self.lock unlock];return nil;}
    // Fence observation and publication before closing the original descriptor.
    // A failed close is immutable uncertainty; its numeric slot is never retried.
    self.archiveSealed=YES;NSDictionary* closing=OVTIdentityClock();int descriptor=_root;_root=-1;
    BOOL closed=descriptor>=0 && close(descriptor)==0;NSDictionary* ended=OVTIdentityClock();
    self.archiveSeal=@{@"snapshotShareAdmissionSealVersion":@1,@"requestId":nonce,@"instance":self.instance,@"processId":@(getpid()),
        @"bundleId":self.bundle,@"sequence":@(++self.sequence),@"sourceBirthClock":self.born,@"preparedClock":self.prepared,@"bundle":self.identity,
        @"bundleRootIdentity":OVTIdentityRevision(_originalRoot),@"clockBefore":before,@"clockAfter":ended,@"outputs":outputs,
        @"descriptorClose":@{@"clockBefore":closing,@"clockAfter":ended,@"succeeded":@(closed)},@"sealed":@YES,@"outputReadersClosed":@YES,
        @"collectorAlive":@(self.archiveCollector!=nil),@"readerClosed":@(closed)};
    self.archiveSealData=[NSJSONSerialization dataWithJSONObject:self.archiveSeal options:0 error:nil];
    [self.lock unlock];return self.archiveSeal;
}
- (NSDictionary*)archiveAdmissionSealOriginal {
    if (![NSThread isMainThread]) {return nil;}[self.lock lock];NSDictionary* original=self.archiveSeal;[self.lock unlock];return original;
}
- (NSData*)archiveAdmissionSealBytes {
    if (![NSThread isMainThread]) {return nil;}[self.lock lock];NSData* original=self.archiveSealData;[self.lock unlock];return original;
}
- (BOOL)archiveAdmissionSealReady {
    if (![NSThread isMainThread]) {return NO;}[self.lock lock];
    BOOL ready=self.ready && !self.failed && !self.archiveSealed && !self.archiveCollector && _root>=0 && self.archiveOutputs.count==2;
    [self.lock unlock];return ready;
}
#endif
@end

@interface OVTSnapshotCompanionIdentityPanel ()
@property(nonatomic,strong) UITextField* nonce;
@property(nonatomic,strong) UILabel* status;
@end
@implementation OVTSnapshotCompanionIdentityPanel
- (instancetype)init {
    if ((self=[super init])) {
        [OVTSnapshotCompanionIdentity shared];self.axis=UILayoutConstraintAxisVertical;self.spacing=6;
        self.nonce=[UITextField new];self.nonce.accessibilityIdentifier=[OVTIdentityPrefix stringByAppendingString:@".nonce"];self.nonce.placeholder=@"Fresh installed-code inspection nonce";
        self.nonce.borderStyle=UITextBorderStyleRoundedRect;self.nonce.autocorrectionType=UITextAutocorrectionTypeNo;self.nonce.autocapitalizationType=UITextAutocapitalizationTypeNone;[self addArrangedSubview:self.nonce];
        for (NSString* action in OVTIdentityActions()) {
            UIButton* button=[UIButton buttonWithType:UIButtonTypeSystem];button.accessibilityIdentifier=[OVTIdentityPrefix stringByAppendingFormat:@".%@",action];
            NSString* title=[action isEqual:@"identity"]?@"Inspect installed companion":[action isEqual:@"photos"]?@"Inspect Photos read permission":@"Inspect independent native clock";
            SEL selector=[action isEqual:@"identity"]?@selector(identity):[action isEqual:@"photos"]?@selector(photos):@selector(clock);
            [button setTitle:title forState:UIControlStateNormal];[button addTarget:self action:selector forControlEvents:UIControlEventTouchUpInside];[self addArrangedSubview:button];
        }
        self.status=[UILabel new];self.status.accessibilityIdentifier=[OVTIdentityPrefix stringByAppendingString:@".status"];[self addArrangedSubview:self.status];
    }return self;
}
- (void)inspect:(NSString*)action {
    NSDictionary* value=[[OVTSnapshotCompanionIdentity shared] observe:@{@"action":action,@"nonce":self.nonce.text?:@""}];
    BOOL okay=[[OVTSnapshotCompanionIdentity shared] persist:value action:action];self.status.text=okay?@"Original observation persisted":@"Observation unavailable";
}
- (void)identity {[self inspect:@"identity"];}
- (void)clock {[self inspect:@"clock"];}
- (void)photos {[self inspect:@"photos"];}
@end
