// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#import "ShareArchiveFiles.h"
#import "ShareJournal.h"
#import <CommonCrypto/CommonDigest.h>
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <unistd.h>

NSDictionary* OVTShareArchiveChunk(NSURL* root,NSDictionary* imported,NSString* nonce,NSString* offset) {
    if (![NSThread isMainThread] || !root.isFileURL || ![imported[@"iosSnapshotShareImportVersion"] isEqual:@2]
            || ![imported[@"phase"] isEqual:@"complete"] || !OVTShareMatch(nonce,@"\\Aios-[a-f0-9]{32}\\z")
            || !OVTShareMatch(offset,@"\\A(0|[1-9][0-9]{0,8})\\z")
            || ![root.lastPathComponent isEqual:[@"snapshot-share-" stringByAppendingString:imported[@"runId"]]]) {return nil;}
    unsigned long long position=offset.longLongValue,count=[imported[@"byteCount"] unsignedLongLongValue];NSUInteger limit=512*1024;
    if (!count || count>256*1024*1024 || position>=count || position%limit) {return nil;}
    NSDictionary* before=OVTShareClock();NSTimeInterval began=NSProcessInfo.processInfo.systemUptime;
    int directory=open(root.fileSystemRepresentation,O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);
    if (directory<0) {return nil;}struct stat directoryBefore,directoryAfter,named,opened,after;
    BOOL valid=fstat(directory,&directoryBefore)==0 && [OVTShareRootIdentity(directoryBefore) isEqual:imported[@"archiveRootIdentity"]]
        && lstat(root.fileSystemRepresentation,&named)==0 && [OVTShareFileRevision(named) isEqual:OVTShareFileRevision(directoryBefore)]
        && fstatat(directory,"original.bytes",&named,AT_SYMLINK_NOFOLLOW)==0;
    int file=valid?openat(directory,"original.bytes",O_RDONLY|O_NOFOLLOW|O_NONBLOCK|O_CLOEXEC):-1;
    valid=valid && file>=0 && fstat(file,&opened)==0 && S_ISREG(opened.st_mode) && opened.st_nlink==1 && opened.st_uid==geteuid()
        && (opened.st_mode&0777)==0600 && opened.st_size==(off_t)count && [OVTShareFileRevision(opened) isEqual:OVTShareFileRevision(named)]
        && [OVTShareFileRevision(opened) isEqual:imported[@"artifactRevision"]];
    NSUInteger length=(NSUInteger)MIN((unsigned long long)limit,count-position),received=0;NSMutableData* raw=[NSMutableData dataWithLength:length];
    while (valid && received<length) {
        ssize_t bytes=pread(file,(char*)raw.mutableBytes+received,length-received,(off_t)(position+received));
        if (bytes<0 && errno==EINTR) {continue;}
        if (bytes<=0 || NSProcessInfo.processInfo.systemUptime-began>=1.5) {valid=NO;break;}received+=(NSUInteger)bytes;
    }
    valid=valid && fstat(file,&after)==0 && [OVTShareFileRevision(after) isEqual:OVTShareFileRevision(opened)]
        && fstatat(directory,"original.bytes",&named,AT_SYMLINK_NOFOLLOW)==0 && [OVTShareFileRevision(named) isEqual:OVTShareFileRevision(opened)]
        && fstat(directory,&directoryAfter)==0 && [OVTShareFileRevision(directoryAfter) isEqual:OVTShareFileRevision(directoryBefore)]
        && lstat(root.fileSystemRepresentation,&named)==0 && [OVTShareFileRevision(named) isEqual:OVTShareFileRevision(directoryBefore)];
    if (file>=0 && close(file)!=0) {valid=NO;}if (close(directory)!=0) {valid=NO;}
    NSDictionary* ended=OVTShareClock();if (!valid || NSProcessInfo.processInfo.systemUptime-began>=1.5) {return nil;}
    return @{@"snapshotShareChunkVersion":@1,@"nonce":nonce,@"runId":imported[@"runId"],@"instance":imported[@"instance"],
        @"processId":@(getpid()),@"basename":imported[@"basename"],@"clockDomain":@"native-share-archive",@"clockBefore":before,@"clockAfter":ended,
        @"revision":OVTShareFileRevision(opened),@"byteCount":@(count),@"sha256":imported[@"sha256"],@"offset":@(position),
        @"eof":@(position+length==count),@"readerClosed":@YES,@"data":[raw base64EncodedStringWithOptions:0]};
}

// Only the two roots created by this receiver/import are admitted. No caller
// supplies an expected result, filename, PID, digest or absence instruction.
static NSString* OVTRetireSHA(NSData* bytes) {
    unsigned char hash[CC_SHA256_DIGEST_LENGTH];CC_SHA256(bytes.bytes,(CC_LONG)bytes.length,hash);
    NSMutableString* value=[NSMutableString new];for (NSUInteger at=0;at<sizeof(hash);++at) {[value appendFormat:@"%02x",hash[at]];}return value;
}
static NSString* OVTRetireParent(struct stat value) {
    if (!S_ISDIR(value.st_mode) || value.st_uid!=geteuid()) {return nil;}
    return OVTRetireSHA([[NSString stringWithFormat:@"%llu:%llu:%u:%u:%u",(unsigned long long)value.st_dev,
        (unsigned long long)value.st_ino,(unsigned)value.st_mode,(unsigned)value.st_uid,(unsigned)value.st_gid] dataUsingEncoding:NSUTF8StringEncoding]);
}
static BOOL OVTRetireCensus(int directory,NSArray* expected) {
    int copied=dup(directory);if (copied<0) {return NO;}DIR* reader=fdopendir(copied);if (!reader) {close(copied);return NO;}
    rewinddir(reader);NSMutableSet* names=[NSMutableSet new];BOOL valid=YES;errno=0;struct dirent* entry;
    while ((entry=readdir(reader))) {
        NSString* name=[[NSString alloc] initWithUTF8String:entry->d_name];
        if (!name) {valid=NO;break;}if (![name isEqual:@"."] && ![name isEqual:@".."]) {[names addObject:name];}
    }
    if (errno!=0) {valid=NO;}if (closedir(reader)!=0) {valid=NO;}return valid && [names isEqual:[NSSet setWithArray:expected]];
}
static NSDictionary* OVTRetireFile(int directory,NSString* name) {
    struct stat before,after,named;int file=openat(directory,name.UTF8String,O_RDONLY|O_NOFOLLOW|O_NONBLOCK|O_CLOEXEC);
    BOOL valid=file>=0 && fstat(file,&before)==0 && S_ISREG(before.st_mode) && before.st_nlink==1 && before.st_uid==geteuid()
        && (before.st_mode&0777)==0600 && before.st_size>0 && before.st_size<=256*1024*1024;
    CC_SHA256_CTX sha;CC_SHA256_Init(&sha);NSUInteger total=0;unsigned char buffer[65536];NSTimeInterval began=NSProcessInfo.processInfo.systemUptime;
    while (valid) {
        ssize_t size=read(file,buffer,sizeof(buffer));if (size<0 && errno==EINTR) {continue;}
        if (size<0 || NSProcessInfo.processInfo.systemUptime-began>=5) {valid=NO;break;}if (!size) {break;}
        total+=(NSUInteger)size;if (total>256*1024*1024) {valid=NO;break;}CC_SHA256_Update(&sha,buffer,(CC_LONG)size);
    }
    valid=valid && total==(NSUInteger)before.st_size && fstat(file,&after)==0 && [OVTShareFileRevision(before) isEqual:OVTShareFileRevision(after)]
        && fstatat(directory,name.UTF8String,&named,AT_SYMLINK_NOFOLLOW)==0 && [OVTShareFileRevision(before) isEqual:OVTShareFileRevision(named)];
    if (file>=0 && close(file)!=0) {valid=NO;}if (!valid) {return nil;}
    unsigned char raw[CC_SHA256_DIGEST_LENGTH];CC_SHA256_Final(raw,&sha);NSMutableString* digest=[NSMutableString new];
    for (NSUInteger index=0;index<sizeof(raw);++index) {[digest appendFormat:@"%02x",raw[index]];}
    return @{@"name":name,@"revision":OVTShareFileRevision(before),@"sha256":digest,@"byteCount":@(total)};
}
static BOOL OVTRetireExclusive(NSURL* documents,NSString* identity,NSData* bytes) {
    int parent=open(documents.fileSystemRepresentation,O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);if (parent<0) {return NO;}
    struct stat opened,named;
    if (fstat(parent,&opened)!=0 || ![OVTRetireParent(opened) isEqual:identity]
        || lstat(documents.fileSystemRepresentation,&named)!=0 || ![OVTRetireParent(named) isEqual:identity]) {close(parent);return NO;}
    int file=openat(parent,"snapshot-share-retire-intent.json",O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC,0600);
    BOOL valid=file>=0;NSUInteger offset=0;
    while (valid && offset<bytes.length) {
        ssize_t count=write(file,(const char*)bytes.bytes+offset,bytes.length-offset);
        if (count<0 && errno==EINTR) {continue;}if (count<=0) {valid=NO;break;}offset+=(NSUInteger)count;
    }
    if (file>=0) {if (fsync(file)!=0) {valid=NO;}if (close(file)!=0) {valid=NO;}}
    if (fsync(parent)!=0) {valid=NO;}if (close(parent)!=0) {valid=NO;}return valid;
}
@interface OVTShareArchiveRetirement ()
@property(nonatomic,strong) NSURL* group;
@property(nonatomic,strong) NSURL* archive;
@property(nonatomic,strong) NSDictionary* imported;
@property(nonatomic,strong) NSDictionary* parents;
@property(nonatomic,strong) NSArray* files;
@property(nonatomic,strong) NSMutableDictionary* record;
@property(nonatomic,strong) NSMutableSet* nonces;
@property BOOL issued;
@property BOOL valid;
@end
@implementation OVTShareArchiveRetirement
+ (instancetype)ownerWithGroup:(NSURL*)group archive:(NSURL*)archive imported:(NSDictionary*)imported
    revisions:(NSDictionary*)revisions metadata:(NSData*)metadata intent:(NSData*)intent importedBytes:(NSData*)importedBytes {
    if (![NSThread isMainThread] || ![imported[@"iosSnapshotShareImportVersion"] isEqual:@2] || ![imported[@"phase"] isEqual:@"complete"]
        || ![group.lastPathComponent isEqual:[@"snapshot-share-" stringByAppendingString:imported[@"runId"]]]
        || ![archive.lastPathComponent isEqual:group.lastPathComponent]) {return nil;}
    OVTShareArchiveRetirement* owner=[self new];owner.group=group;owner.archive=archive;owner.imported=[imported copy];
    owner.nonces=[NSMutableSet new];NSMutableArray* files=[NSMutableArray new];NSMutableDictionary* parents=[NSMutableDictionary new];
    NSDictionary* names=@{@"group":@[@"original.bytes",@"share-original.json"],@"archive":@[@"original.bytes",@"original-extension.json",@"import-intent.json",@"import-original.json"]};
    NSDictionary* hashes=@{@"group/original.bytes":imported[@"sha256"],@"archive/original.bytes":imported[@"sha256"],
        @"group/share-original.json":OVTRetireSHA(metadata),@"archive/original-extension.json":OVTRetireSHA(metadata),
        @"archive/import-intent.json":OVTRetireSHA(intent),@"archive/import-original.json":OVTRetireSHA(importedBytes)};
    BOOL valid=metadata && intent && importedBytes;
    for (NSString* role in @[@"group",@"archive"]) {
        NSURL* root=[role isEqual:@"group"]?group:archive;struct stat before,after,named,parentStat;
        int directory=open(root.fileSystemRepresentation,O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);
        NSURL* parent=[root URLByDeletingLastPathComponent];NSString* identity=[role isEqual:@"group"]?imported[@"groupRootIdentity"]:imported[@"archiveRootIdentity"];
        valid=valid && directory>=0 && fstat(directory,&before)==0 && [OVTShareRootIdentity(before) isEqual:identity]
            && lstat(root.fileSystemRepresentation,&named)==0 && [OVTShareFileRevision(named) isEqual:OVTShareFileRevision(before)]
            && lstat(parent.fileSystemRepresentation,&parentStat)==0 && OVTRetireParent(parentStat) && OVTRetireCensus(directory,names[role]);
        if (valid) {parents[role]=OVTRetireParent(parentStat);}
        for (NSString* name in names[role]) {
            NSDictionary* file=valid?OVTRetireFile(directory,name):nil;NSString* key=[NSString stringWithFormat:@"%@/%@",role,name];
            valid=valid && file && [file[@"revision"] isEqual:revisions[key]] && [file[@"sha256"] isEqual:hashes[key]];
            if (valid) {NSMutableDictionary* pin=[file mutableCopy];pin[@"root"]=role;[files addObject:pin];}
        }
        valid=valid && fstat(directory,&after)==0 && [OVTShareFileRevision(before) isEqual:OVTShareFileRevision(after)]
            && lstat(root.fileSystemRepresentation,&named)==0 && [OVTShareFileRevision(named) isEqual:OVTShareFileRevision(before)];
        if (directory>=0 && close(directory)!=0) {valid=NO;}
    }
    if (!valid || files.count!=6) {return nil;}owner.files=files;owner.parents=parents;owner.valid=YES;
    owner.record=[@{@"snapshotShareRetirementVersion":@1,@"runId":imported[@"runId"],@"instance":imported[@"instance"],
        @"processId":imported[@"processId"],@"bundleId":imported[@"bundleId"],@"clockDomain":@"native-share-archive",
        @"originalMetadataSha256":OVTRetireSHA(metadata),@"importOriginalSha256":OVTRetireSHA(importedBytes),
        @"groupRootIdentity":imported[@"groupRootIdentity"],@"archiveRootIdentity":imported[@"archiveRootIdentity"],@"files":files,
        @"requestId":NSNull.null,@"clockBefore":NSNull.null,@"clockAfter":NSNull.null,@"steps":[NSMutableArray new],@"complete":@NO,@"readersClosed":@NO} mutableCopy];return owner;
}
- (BOOL)root:(NSString*)role directory:(int*)directory parent:(int*)parent {
    NSURL* root=[role isEqual:@"group"]?self.group:self.archive;NSURL* parentURL=[root URLByDeletingLastPathComponent];struct stat opened,named,container;
    *parent=open(parentURL.fileSystemRepresentation,O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);*directory=-1;
    BOOL valid=*parent>=0 && fstat(*parent,&container)==0 && [OVTRetireParent(container) isEqual:self.parents[role]]
        && lstat(parentURL.fileSystemRepresentation,&named)==0 && [OVTRetireParent(named) isEqual:self.parents[role]];
    if (valid) {*directory=openat(*parent,root.lastPathComponent.UTF8String,O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);}
    NSString* identity=self.imported[[role isEqual:@"group"]?@"groupRootIdentity":@"archiveRootIdentity"];
    return valid && *directory>=0 && fstat(*directory,&opened)==0 && [OVTShareRootIdentity(opened) isEqual:identity]
        && fstatat(*parent,root.lastPathComponent.UTF8String,&named,AT_SYMLINK_NOFOLLOW)==0 && [OVTShareRootIdentity(named) isEqual:identity];
}
- (BOOL)persist {return OVTShareWrite([self.archive URLByDeletingLastPathComponent],@"snapshot-share-retire.json",[NSJSONSerialization dataWithJSONObject:self.record options:0 error:nil]);}
- (BOOL)retire:(NSString*)nonce {
    if (![NSThread isMainThread] || !self.valid || self.issued || !OVTShareMatch(nonce,@"\\Aios-[a-f0-9]{32}\\z")) {return NO;}
    self.issued=YES;self.record[@"requestId"]=nonce;self.record[@"clockBefore"]=OVTShareClock();
    NSData* intent=[NSJSONSerialization dataWithJSONObject:self.record options:0 error:nil];
    if (!intent || !OVTRetireExclusive([self.archive URLByDeletingLastPathComponent],self.parents[@"archive"],intent)) {self.valid=NO;return NO;}
    int group=-1,groupParent=-1,archive=-1,archiveParent=-1;BOOL valid=[self root:@"group" directory:&group parent:&groupParent];
    valid=[self root:@"archive" directory:&archive parent:&archiveParent] && valid;
    valid=valid && OVTRetireCensus(group,@[@"original.bytes",@"share-original.json"])
        && OVTRetireCensus(archive,@[@"original.bytes",@"original-extension.json",@"import-intent.json",@"import-original.json"]);
    for (NSDictionary* pin in self.files) {NSDictionary* actual=valid?OVTRetireFile([pin[@"root"] isEqual:@"group"]?group:archive,pin[@"name"]):nil;
        valid=valid && actual && [actual[@"revision"] isEqual:pin[@"revision"]] && [actual[@"sha256"] isEqual:pin[@"sha256"]];}
    // Every owned reader is closed before the first unlink. The remaining
    // descriptors anchor only the private directories and their parents.
    self.record[@"readersClosed"]=@(valid);valid=valid && [self persist];
    for (NSDictionary* pin in self.files) {
        if (!valid) {break;}BOOL isGroup=[pin[@"root"] isEqual:@"group"];int directory=isGroup?group:archive,parent=isGroup?groupParent:archiveParent;
        NSURL* root=isGroup?self.group:self.archive;struct stat current,named;
        valid=fstatat(parent,root.lastPathComponent.UTF8String,&current,AT_SYMLINK_NOFOLLOW)==0
            && [OVTShareRootIdentity(current) isEqual:self.imported[isGroup?@"groupRootIdentity":@"archiveRootIdentity"]]
            && fstatat(directory,[pin[@"name"] UTF8String],&named,AT_SYMLINK_NOFOLLOW)==0 && [OVTShareFileRevision(named) isEqual:pin[@"revision"]];
        BOOL removed=valid && unlinkat(directory,[pin[@"name"] UTF8String],0)==0;
        [self.record[@"steps"] addObject:@{@"sequence":@([self.record[@"steps"] count]+1),@"kind":@"unlink",@"root":pin[@"root"],@"name":pin[@"name"],@"succeeded":@(removed),@"clock":OVTShareClock()}];
        valid=removed && fsync(directory)==0 && [self persist];
    }
    for (NSString* role in @[@"group",@"archive"]) {
        if (!valid) {break;}BOOL isGroup=[role isEqual:@"group"];int directory=isGroup?group:archive,parent=isGroup?groupParent:archiveParent;
        NSURL* root=isGroup?self.group:self.archive;struct stat named;
        valid=OVTRetireCensus(directory,@[]) && fstatat(parent,root.lastPathComponent.UTF8String,&named,AT_SYMLINK_NOFOLLOW)==0
            && [OVTShareRootIdentity(named) isEqual:self.imported[isGroup?@"groupRootIdentity":@"archiveRootIdentity"]];
        BOOL removed=valid && unlinkat(parent,root.lastPathComponent.UTF8String,AT_REMOVEDIR)==0;
        [self.record[@"steps"] addObject:@{@"sequence":@([self.record[@"steps"] count]+1),@"kind":@"rmdir",@"root":role,@"name":root.lastPathComponent,@"succeeded":@(removed),@"clock":OVTShareClock()}];
        valid=removed && fsync(parent)==0 && [self persist];
    }
    for (NSNumber* fd in @[@(group),@(groupParent),@(archive),@(archiveParent)]) {if (fd.intValue>=0 && close(fd.intValue)!=0) {valid=NO;}}
    self.record[@"clockAfter"]=OVTShareClock();self.record[@"complete"]=@(valid);BOOL saved=[self persist];self.valid=saved;
    return saved && valid;
}
- (NSDictionary*)inspect:(NSString*)nonce {
    if (![NSThread isMainThread] || !self.valid || !self.issued || !OVTShareMatch(nonce,@"\\Aios-[a-f0-9]{32}\\z")
        || [self.nonces containsObject:nonce] || self.nonces.count>=128) {return nil;}
    [self.nonces addObject:nonce];NSDictionary* before=OVTShareClock();NSMutableDictionary* absent=[NSMutableDictionary new];BOOL errors=NO;
    for (NSString* role in @[@"group",@"archive"]) {
        NSURL* root=[role isEqual:@"group"]?self.group:self.archive;NSURL* container=[root URLByDeletingLastPathComponent];struct stat stat,named;
        int parent=open(container.fileSystemRepresentation,O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);
        BOOL valid=parent>=0 && fstat(parent,&stat)==0 && [OVTRetireParent(stat) isEqual:self.parents[role]]
            && lstat(container.fileSystemRepresentation,&named)==0 && [OVTRetireParent(named) isEqual:self.parents[role]];
        errno=0;int found=valid?fstatat(parent,root.lastPathComponent.UTF8String,&named,AT_SYMLINK_NOFOLLOW):-1;
        BOOL missing=valid && found<0 && errno==ENOENT;if (!valid || (found<0 && errno!=ENOENT)) {errors=YES;}
        if (parent>=0 && close(parent)!=0) {errors=YES;}absent[role]=@(missing);
    }
    return @{@"snapshotShareRetirementObservationVersion":@1,@"requestId":nonce,@"runId":self.imported[@"runId"],
        @"processId":self.imported[@"processId"],@"clockDomain":@"native-share-archive",@"clockBefore":before,@"clockAfter":OVTShareClock(),
        @"retirement":[self.record copy],@"groupRunAbsent":absent[@"group"],@"archiveRunAbsent":absent[@"archive"],@"observationErrors":@(errors)};
}
@end
