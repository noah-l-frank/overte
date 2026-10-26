// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#import "ShareSourceOutputs.h"
#import "ShareJournal.h"
#import <CommonCrypto/CommonDigest.h>
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <unistd.h>

static NSArray* OVTSourceNames(void) {return @[@"snapshot-share-chunk.json",@"snapshot-share-retire-intent.json",@"snapshot-share-retire.json",@"snapshot-share-retirement-observation.json"];}
static NSString* const OVTSourceFinalIntent=@"snapshot-share-source-retire-intent.json";
static NSArray* OVTSourceAllNames(void) {
    return [@[@"snapshot-share-companion-identity.json",@"snapshot-share-companion-clock.json"] arrayByAddingObjectsFromArray:OVTSourceNames()];
}
static NSString* OVTSourceSHA(NSData* bytes) {
    unsigned char raw[CC_SHA256_DIGEST_LENGTH];CC_SHA256(bytes.bytes,(CC_LONG)bytes.length,raw);NSMutableString* hash=[NSMutableString new];
    for (NSUInteger at=0;at<sizeof(raw);++at) {[hash appendFormat:@"%02x",raw[at]];}return hash;
}
static NSString* OVTSourceParent(struct stat value) {
    if (!S_ISDIR(value.st_mode) || value.st_uid!=geteuid()) {return nil;}
    return OVTSourceSHA([[NSString stringWithFormat:@"%llu:%llu:%u:%u:%u",(unsigned long long)value.st_dev,
        (unsigned long long)value.st_ino,(unsigned)value.st_mode,(unsigned)value.st_uid,(unsigned)value.st_gid] dataUsingEncoding:NSUTF8StringEncoding]);
}
static NSDictionary* OVTSourcePin(int parent,NSString* name,NSString* identity) {
    int file=openat(parent,name.UTF8String,O_RDONLY|O_NOFOLLOW|O_NONBLOCK|O_CLOEXEC);struct stat before,after,named;
    BOOL valid=file>=0 && fstat(file,&before)==0 && S_ISREG(before.st_mode) && before.st_nlink==1 && before.st_uid==geteuid()
        && (before.st_mode&0777)==0600 && before.st_size>0 && before.st_size<=720896;
    NSMutableData* bytes=[NSMutableData new];unsigned char buffer[32768];NSTimeInterval began=NSProcessInfo.processInfo.systemUptime;
    while (valid) {
        ssize_t count=read(file,buffer,sizeof(buffer));if (count<0 && errno==EINTR) {continue;}
        if (count<0 || NSProcessInfo.processInfo.systemUptime-began>=1.5) {valid=NO;break;}if (!count) {break;}
        if (bytes.length+(NSUInteger)count>720896) {valid=NO;break;}[bytes appendBytes:buffer length:(NSUInteger)count];
    }
    valid=valid && bytes.length==(NSUInteger)before.st_size && fstat(file,&after)==0 && [OVTShareFileRevision(after) isEqual:OVTShareFileRevision(before)]
        && fstatat(parent,name.UTF8String,&named,AT_SYMLINK_NOFOLLOW)==0 && [OVTShareFileRevision(named) isEqual:OVTShareFileRevision(before)];
    if (file>=0 && close(file)!=0) {valid=NO;}if (!valid) {return nil;}
    return @{@"name":name,@"revision":OVTShareFileRevision(before),@"sha256":OVTSourceSHA(bytes),@"byteCount":@(bytes.length),@"parentIdentity":identity};
}
static BOOL OVTSourceCensusMask(int parent,NSUInteger mask) {
    if (mask>127) {return NO;}NSArray* names=[OVTSourceAllNames() arrayByAddingObject:OVTSourceFinalIntent];NSMutableSet* expected=[NSMutableSet new];
    for (NSUInteger index=0;index<names.count;++index) {if (mask&(1U<<index)) {[expected addObject:names[index]];}}
    int cursor=openat(parent,".",O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);if (cursor<0) {return NO;}
    DIR* reader=fdopendir(cursor);if (!reader) {close(cursor);return NO;}NSMutableSet* seen=[NSMutableSet new];BOOL valid=YES;
    errno=0;struct dirent* entry;NSUInteger count=0;NSTimeInterval began=NSProcessInfo.processInfo.systemUptime;
    while ((entry=readdir(reader))) {
        NSString* name=[[NSString alloc] initWithUTF8String:entry->d_name];
        if (!name || ++count>8192 || NSProcessInfo.processInfo.systemUptime-began>=1.5) {valid=NO;break;}
        if ([name hasPrefix:@"snapshot-share-"] || [name hasPrefix:@".record-"] || [name hasPrefix:@".companion-"]) {
            if (![expected containsObject:name] || [seen containsObject:name]) {valid=NO;break;}[seen addObject:name];
        }
        errno=0;
    }
    if (errno) {valid=NO;}if (closedir(reader)!=0) {valid=NO;}return valid && [seen isEqual:expected];
}
static BOOL OVTSourceCensus(int parent) {return OVTSourceCensusMask(parent,63);}
static NSDictionary* OVTSourceExclusiveIntent(int directory,NSData* bytes,NSString* parent) {
    int file=openat(directory,OVTSourceFinalIntent.UTF8String,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC,0600);
    BOOL valid=file>=0 && bytes.length>0 && bytes.length<=262144;NSUInteger offset=0;struct stat written;
    while (valid && offset<bytes.length) {
        ssize_t count=write(file,(const char*)bytes.bytes+offset,bytes.length-offset);if (count<0 && errno==EINTR) {continue;}
        if (count<=0) {valid=NO;break;}offset+=(NSUInteger)count;
    }
    if (file>=0) {if (fsync(file)!=0 || fstat(file,&written)!=0) {valid=NO;}if (close(file)!=0) {valid=NO;}}
    NSDictionary* pin=valid?OVTSourcePin(directory,OVTSourceFinalIntent,parent):nil;
    valid=valid && pin && [pin[@"revision"] isEqual:OVTShareFileRevision(written)] && [pin[@"sha256"] isEqual:OVTSourceSHA(bytes)] && fsync(directory)==0;
    if (!valid) {return nil;}NSMutableDictionary* original=[pin mutableCopy];original[@"data"]=[bytes base64EncodedStringWithOptions:0];return original;
}
@interface OVTShareSourceOutputs ()
@property(nonatomic,strong) NSURL* documents;
@property(nonatomic,copy) NSString* parent;
@property(nonatomic,copy) NSString* instance;
@property(nonatomic,strong) NSDictionary* born;
@property(nonatomic,strong) NSMutableDictionary* pins;
@property(nonatomic,strong) NSMutableDictionary* originals;
@property(nonatomic,strong) NSData* sealBytes;
@property(nonatomic,strong) NSData* inventoryBytes;
@property BOOL frozen;
@property BOOL failed;
@property BOOL retirementIssued;
@property(nonatomic,strong) NSData* retirementBytes;
@property(nonatomic,strong) NSData* retirementObservationBytes;
@property(nonatomic,strong) NSMutableSet* retirementQueries;
@end
@implementation OVTShareSourceOutputs
+ (instancetype)shared {
    static OVTShareSourceOutputs* source;static dispatch_once_t once;dispatch_once(&once,^{source=[self new];});return source;
}
- (instancetype)init {
    if ((self=[super init])) {
        self.documents=[NSFileManager.defaultManager URLsForDirectory:NSDocumentDirectory inDomains:NSUserDomainMask].firstObject;
        self.instance=OVTShareID();self.born=OVTShareClock();self.pins=[NSMutableDictionary new];self.originals=[NSMutableDictionary new];self.retirementQueries=[NSMutableSet new];struct stat parent;
        self.parent=lstat(self.documents.fileSystemRepresentation,&parent)==0?OVTSourceParent(parent):nil;self.failed=!self.parent;
    }return self;
}
- (int)openParent {
    int directory=open(self.documents.fileSystemRepresentation,O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);struct stat opened,named;
    BOOL valid=directory>=0 && fstat(directory,&opened)==0 && [OVTSourceParent(opened) isEqual:self.parent]
        && lstat(self.documents.fileSystemRepresentation,&named)==0 && [OVTSourceParent(named) isEqual:self.parent];
    if (!valid) {if (directory>=0) {close(directory);}return -1;}return directory;
}
- (BOOL)publish:(OVTShareSourceOutput)kind bytes:(NSData*)bytes {
    if (![NSThread isMainThread] || self.failed || self.frozen || kind>OVTShareSourceRetireObservation || !bytes.length
        || bytes.length>(kind==OVTShareSourceChunk?720896:262144)) {return NO;}
    NSString* name=OVTSourceNames()[kind];NSDictionary* old=self.pins[name];int directory=[self openParent];struct stat named,written,published;
    BOOL valid=directory>=0;
    if (valid && old) {valid=kind!=OVTShareSourceRetireIntent && [old isEqual:OVTSourcePin(directory,name,self.parent)];}
    else if (valid) {errno=0;valid=fstatat(directory,name.UTF8String,&named,AT_SYMLINK_NOFOLLOW)!=0 && errno==ENOENT;}
    BOOL exclusive=kind==OVTShareSourceRetireIntent;NSString* temporary=exclusive?name:[@".record-" stringByAppendingString:OVTShareID()];
    int file=valid?openat(directory,temporary.UTF8String,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC,0600):-1;
    valid=valid && file>=0;NSUInteger offset=0;NSTimeInterval began=NSProcessInfo.processInfo.systemUptime;
    while (valid && offset<bytes.length) {
        ssize_t count=write(file,(const char*)bytes.bytes+offset,bytes.length-offset);if (count<0 && errno==EINTR) {continue;}
        if (count<=0 || NSProcessInfo.processInfo.systemUptime-began>=1.5) {valid=NO;break;}offset+=(NSUInteger)count;
    }
    if (file>=0) {if (fsync(file)!=0 || fstat(file,&written)!=0) {valid=NO;}if (close(file)!=0) {valid=NO;}}
    valid=valid && offset==bytes.length && S_ISREG(written.st_mode) && written.st_nlink==1 && written.st_uid==geteuid()
        && (written.st_mode&0777)==0600 && written.st_size==(off_t)bytes.length;
    if (valid && !exclusive && renameat(directory,temporary.UTF8String,directory,name.UTF8String)!=0) {valid=NO;}
    valid=valid && fstatat(directory,name.UTF8String,&published,AT_SYMLINK_NOFOLLOW)==0 && published.st_dev==written.st_dev
        && published.st_ino==written.st_ino && published.st_mode==written.st_mode && published.st_nlink==written.st_nlink
        && published.st_uid==written.st_uid && published.st_gid==written.st_gid && published.st_size==written.st_size
        && published.st_mtimespec.tv_sec==written.st_mtimespec.tv_sec && published.st_mtimespec.tv_nsec==written.st_mtimespec.tv_nsec;
    NSDictionary* pin=valid?OVTSourcePin(directory,name,self.parent):nil;
    valid=valid && pin && [pin[@"revision"] isEqual:OVTShareFileRevision(published)] && [pin[@"sha256"] isEqual:OVTSourceSHA(bytes)]
        && fstat(directory,&named)==0 && [OVTSourceParent(named) isEqual:self.parent]
        && lstat(self.documents.fileSystemRepresentation,&named)==0 && [OVTSourceParent(named) isEqual:self.parent];
    if (directory>=0) {if (fsync(directory)!=0) {valid=NO;}if (close(directory)!=0) {valid=NO;}}
    if (valid) {self.pins[name]=pin;self.originals[name]=[bytes copy];}else {self.failed=YES;}return valid;
}
- (void)freezeWithAdmissionSeal:(NSData*)original {
    if (![NSThread isMainThread] || self.frozen) {return;}
    // Even an uncertain admission close fences all later original producers.
    self.frozen=YES;self.sealBytes=[original copy];
}
- (BOOL)producersFrozen {return self.frozen;}
- (BOOL)inventoryReady {
    if (![NSThread isMainThread] || !self.frozen || self.failed || self.pins.count!=4 || self.inventoryBytes) {return NO;}
    id seal=self.sealBytes?[NSJSONSerialization JSONObjectWithData:self.sealBytes options:0 error:nil]:nil;
    return [seal isKindOfClass:NSDictionary.class] && [seal[@"sealed"] isEqual:@YES] && [seal[@"readerClosed"] isEqual:@YES]
        && [seal[@"outputReadersClosed"] isEqual:@YES] && [seal[@"collectorAlive"] isEqual:@NO];
}
- (NSData*)inventory:(NSString*)nonce {
    if (![self inventoryReady] || !OVTShareMatch(nonce,@"\\Aios-[a-f0-9]{32}\\z")) {return nil;}
    NSDictionary* seal=[NSJSONSerialization JSONObjectWithData:self.sealBytes options:0 error:nil];NSDictionary* before=OVTShareClock();
    int directory=[self openParent];BOOL valid=directory>=0 && OVTSourceCensus(directory);NSMutableArray* outputs=[NSMutableArray new];
    NSArray* names=@[@"snapshot-share-companion-identity.json",@"snapshot-share-companion-clock.json"];
    if (![seal[@"outputs"] isKindOfClass:NSArray.class] || [seal[@"outputs"] count]!=2) {
        if (directory>=0) {close(directory);}self.failed=YES;return nil;
    }
    for (NSUInteger index=0;index<2;++index) {
        NSDictionary* pin=seal[@"outputs"][index];valid=[pin[@"name"] isEqual:names[index]] && [pin[@"parentIdentity"] isEqual:self.parent];
        valid=valid && [pin isEqual:OVTSourcePin(directory,names[index],self.parent)];[outputs addObject:pin];
    }
    for (NSString* name in OVTSourceNames()) {
        NSDictionary* pin=self.pins[name];if (!pin) {valid=NO;break;}
        valid=valid && [pin isEqual:OVTSourcePin(directory,name,self.parent)];NSMutableDictionary* original=[pin mutableCopy];
        if ([name isEqual:@"snapshot-share-retire-intent.json"] || [name isEqual:@"snapshot-share-retire.json"]) {
            original[@"data"]=[self.originals[name] base64EncodedStringWithOptions:0];
        }
        [outputs addObject:original];
    }
    struct stat named;valid=valid && OVTSourceCensus(directory) && fstat(directory,&named)==0 && [OVTSourceParent(named) isEqual:self.parent]
        && lstat(self.documents.fileSystemRepresentation,&named)==0 && [OVTSourceParent(named) isEqual:self.parent];
    if (directory>=0 && close(directory)!=0) {valid=NO;}
    NSDictionary* packet=@{@"snapshotShareSourceInventoryVersion":@1,@"requestId":nonce,@"processId":@(getpid()),@"bundleId":NSBundle.mainBundle.bundleIdentifier,
        @"instance":self.instance,@"sourceBirthClock":self.born,@"sourceInstance":seal[@"instance"],@"admissionSealSha256":OVTSourceSHA(self.sealBytes),
        @"clockBefore":before,@"clockAfter":OVTShareClock(),@"parentIdentity":self.parent,@"outputs":outputs,
        @"frozen":@(self.frozen),@"current":@(valid),@"readersClosed":@(valid)};
    NSData* raw=[NSJSONSerialization dataWithJSONObject:packet options:0 error:nil];
    if (!raw || raw.length>262144) {self.failed=YES;return nil;}self.inventoryBytes=raw;return raw;
}
- (NSData*)inventoryOriginal {return [NSThread isMainThread]?self.inventoryBytes:nil;}
- (BOOL)retirementReady {
    if (![NSThread isMainThread] || !self.frozen || self.failed || self.retirementIssued || !self.inventoryBytes) {return NO;}
    NSDictionary* inventory=[NSJSONSerialization JSONObjectWithData:self.inventoryBytes options:0 error:nil];
    return [inventory[@"current"] isEqual:@YES] && [inventory[@"readersClosed"] isEqual:@YES] && [inventory[@"frozen"] isEqual:@YES];
}
- (BOOL)parentCurrent:(int)directory {
    struct stat opened,named;return directory>=0 && fstat(directory,&opened)==0 && [OVTSourceParent(opened) isEqual:self.parent]
        && lstat(self.documents.fileSystemRepresentation,&named)==0 && [OVTSourceParent(named) isEqual:self.parent];
}
- (NSData*)retire:(NSString*)nonce {
    if (![self retirementReady] || !OVTShareMatch(nonce,@"\\Aios-[a-f0-9]{32}\\z")) {return nil;}
    NSDictionary* inventory=[NSJSONSerialization JSONObjectWithData:self.inventoryBytes options:0 error:nil];
    NSDictionary* seal=[NSJSONSerialization JSONObjectWithData:self.sealBytes options:0 error:nil];
    if ([nonce isEqual:inventory[@"requestId"]] || [nonce isEqual:seal[@"requestId"]]) {return nil;}
    self.retirementIssued=YES;[self.retirementQueries addObject:nonce];[self.retirementQueries addObject:inventory[@"requestId"]];
    [self.retirementQueries addObject:seal[@"requestId"]];NSMutableArray* files=[NSMutableArray new];
    for (NSDictionary* original in inventory[@"outputs"]) {NSMutableDictionary* pin=[original mutableCopy];[pin removeObjectForKey:@"data"];[files addObject:pin];}
    NSDictionary* imported=[NSJSONSerialization JSONObjectWithData:self.originals[@"snapshot-share-retire.json"] options:0 error:nil];
    NSMutableDictionary* record=[@{@"snapshotShareSourceRetirementVersion":@1,@"requestId":nonce,@"runId":imported[@"runId"],
        @"processId":@(getpid()),@"bundleId":NSBundle.mainBundle.bundleIdentifier,@"instance":self.instance,@"sourceInstance":seal[@"instance"],
        @"sourceBirthClock":self.born,@"inventorySha256":OVTSourceSHA(self.inventoryBytes),@"parentIdentity":self.parent,@"outputs":files,
        @"clockBefore":OVTShareClock(),@"clockAfter":NSNull.null,@"intent":NSNull.null,@"steps":[NSMutableArray new],
        @"readersClosed":@NO,@"parentDescriptorClosed":@NO,@"complete":@NO} mutableCopy];
    int directory=[self openParent];BOOL valid=directory>=0 && OVTSourceCensus(directory) && files.count==6;
    for (NSDictionary* pin in files) {valid=valid && [pin isEqual:OVTSourcePin(directory,pin[@"name"],self.parent)];}
    NSData* initial=valid?[NSJSONSerialization dataWithJSONObject:record options:0 error:nil]:nil;
    NSDictionary* intent=initial?OVTSourceExclusiveIntent(directory,initial,self.parent):nil;
    valid=valid && intent && [self parentCurrent:directory] && OVTSourceCensusMask(directory,127);
    if (intent) {record[@"intent"]=intent;}record[@"readersClosed"]=@(valid);
    NSArray* removal=intent?[files arrayByAddingObject:intent]:files;NSUInteger mask=intent?127:63;
    for (NSDictionary* pin in removal) {
        if (!valid) {break;}struct stat named;NSString* name=pin[@"name"];
        valid=[self parentCurrent:directory] && fstatat(directory,name.UTF8String,&named,AT_SYMLINK_NOFOLLOW)==0
            && [OVTShareFileRevision(named) isEqual:pin[@"revision"]];
        BOOL unlinked=valid && unlinkat(directory,name.UTF8String,0)==0;BOOL synchronized=unlinked && fsync(directory)==0;
        errno=0;int found=unlinked?fstatat(directory,name.UTF8String,&named,AT_SYMLINK_NOFOLLOW):0;
        BOOL absent=unlinked && found<0 && errno==ENOENT && [self parentCurrent:directory];
        NSUInteger index=[record[@"steps"] count];if (unlinked) {mask&=~(1U<<index);}
        [record[@"steps"] addObject:@{@"sequence":@(index+1),@"name":name,@"unlinked":@(unlinked),@"synchronized":@(synchronized),@"absent":@(absent),@"clock":OVTShareClock()}];
        valid=unlinked && synchronized && absent && OVTSourceCensusMask(directory,mask);
    }
    valid=valid && mask==0 && [record[@"steps"] count]==7 && [self parentCurrent:directory] && OVTSourceCensusMask(directory,0);
    BOOL closed=directory>=0 && close(directory)==0;record[@"parentDescriptorClosed"]=@(closed);record[@"complete"]=@(valid && closed);
    record[@"clockAfter"]=OVTShareClock();NSData* raw=[NSJSONSerialization dataWithJSONObject:record options:0 error:nil];
    if (!raw || raw.length>262144) {self.failed=YES;return nil;}self.retirementBytes=raw;return raw;
}
- (NSData*)retirementOriginal {return [NSThread isMainThread]?self.retirementBytes:nil;}
- (NSData*)inspectRetirement:(NSString*)nonce {
    if (![NSThread isMainThread] || !self.retirementBytes || !OVTShareMatch(nonce,@"\\Aios-[a-f0-9]{32}\\z")
        || [self.retirementQueries containsObject:nonce] || self.retirementQueries.count>=128) {return nil;}
    [self.retirementQueries addObject:nonce];NSDictionary* original=[NSJSONSerialization JSONObjectWithData:self.retirementBytes options:0 error:nil];
    NSDictionary* before=OVTShareClock();int directory=[self openParent];BOOL errors=directory<0;NSMutableArray* files=[NSMutableArray new];
    for (NSString* name in [OVTSourceAllNames() arrayByAddingObject:OVTSourceFinalIntent]) {
        struct stat named;errno=0;int found=directory>=0?fstatat(directory,name.UTF8String,&named,AT_SYMLINK_NOFOLLOW):0;
        BOOL absent=directory>=0 && found<0 && errno==ENOENT;if (found<0 && errno!=ENOENT) {errors=YES;}
        [files addObject:@{@"name":name,@"absent":@(absent)}];
    }
    BOOL empty=directory>=0 && OVTSourceCensusMask(directory,0);errors=errors || ![self parentCurrent:directory];
    BOOL closed=directory>=0 && close(directory)==0;errors=errors || !closed;
    NSDictionary* packet=@{@"snapshotShareSourceRetirementObservationVersion":@1,@"requestId":nonce,@"runId":original[@"runId"],
        @"processId":@(getpid()),@"bundleId":NSBundle.mainBundle.bundleIdentifier,@"instance":self.instance,@"sourceInstance":original[@"sourceInstance"],
        @"retirementSha256":OVTSourceSHA(self.retirementBytes),@"parentIdentity":self.parent,@"clockBefore":before,@"clockAfter":OVTShareClock(),
        @"files":files,@"sourceNamespaceEmpty":@(empty),@"observationErrors":@(errors),@"parentDescriptorClosed":@(closed)};
    NSData* raw=[NSJSONSerialization dataWithJSONObject:packet options:0 error:nil];if (!raw || raw.length>262144) {return nil;}
    self.retirementObservationBytes=raw;return raw;
}
- (NSData*)retirementObservationOriginal {return [NSThread isMainThread]?self.retirementObservationBytes:nil;}
@end
