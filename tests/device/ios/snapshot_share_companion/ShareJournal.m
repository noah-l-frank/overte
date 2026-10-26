// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#import "ShareJournal.h"
#import <CommonCrypto/CommonDigest.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/stat.h>
#include <errno.h>
#include <stdio.h>

NSDictionary* OVTShareClock(void) {
    return @{@"epochMs":@((long long)(NSDate.date.timeIntervalSince1970*1000)),
             @"monotonicMs":@((long long)(NSProcessInfo.processInfo.systemUptime*1000))};
}
NSString* OVTShareID(void) {return [NSUUID.UUID.UUIDString.lowercaseString stringByReplacingOccurrencesOfString:@"-" withString:@""];}
BOOL OVTShareMatch(NSString* value,NSString* expression) {
    return [value isKindOfClass:NSString.class] && [value rangeOfString:expression options:NSRegularExpressionSearch].location!=NSNotFound;
}
NSURL* OVTShareGroup(void) {
    NSString* group=[NSBundle.mainBundle objectForInfoDictionaryKey:@"OVTSnapshotShareGroup"];
    if (!OVTShareMatch(group,@"\\Agroup\\.[A-Za-z0-9.-]+\\z")) {return nil;}
    return [NSFileManager.defaultManager containerURLForSecurityApplicationGroupIdentifier:group];
}
static BOOL OVTWriteAll(int file,const void* bytes,NSUInteger length) {
    NSUInteger offset=0;
    while (offset<length) {
        ssize_t written=write(file,(const char*)bytes+offset,length-offset);
        if (written<0 && errno==EINTR) {continue;}if (written<=0) {return NO;}offset+=(NSUInteger)written;
    }return YES;
}
static BOOL OVTSyncDirectory(NSURL* root) {
    int directory=open(root.fileSystemRepresentation,O_RDONLY|O_DIRECTORY|O_NOFOLLOW);
    if (directory<0) {return NO;}BOOL saved=fsync(directory)==0;if (close(directory)!=0) {saved=NO;}return saved;
}
static BOOL OVTShareWriteBounded(NSURL* root,NSString* basename,NSData* bytes,NSUInteger limit) {
    if (!root || !bytes || bytes.length>limit || !OVTShareMatch(basename,@"\\A[a-z-]+\\.json\\z")) {return NO;}
    NSURL* temporary=[root URLByAppendingPathComponent:[@".record-" stringByAppendingString:OVTShareID()]];
    int file=open(temporary.fileSystemRepresentation,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW,0600);
    if (file<0) {return NO;}BOOL saved=OVTWriteAll(file,bytes.bytes,bytes.length);
    if (fsync(file)!=0) {saved=NO;}if (close(file)!=0) {saved=NO;}
    NSURL* destination=[root URLByAppendingPathComponent:basename];
    if (saved && rename(temporary.fileSystemRepresentation,destination.fileSystemRepresentation)!=0) {saved=NO;}
    return OVTSyncDirectory(root) && saved;
}
BOOL OVTShareWrite(NSURL* root,NSString* basename,NSData* bytes) {return OVTShareWriteBounded(root,basename,bytes,262144);}
BOOL OVTShareWriteChunk(NSURL* root,NSData* bytes) {return OVTShareWriteBounded(root,@"snapshot-share-chunk.json",bytes,720896);}
static NSString* OVTShareHashText(NSString* text) {
    NSData* value=[text dataUsingEncoding:NSUTF8StringEncoding];unsigned char digest[CC_SHA256_DIGEST_LENGTH];CC_SHA256(value.bytes,(CC_LONG)value.length,digest);
    NSMutableString* output=[NSMutableString new];for (NSUInteger at=0;at<sizeof(digest);++at) {[output appendFormat:@"%02x",digest[at]];}return output;
}
NSString* OVTShareFileRevision(struct stat value) {
    return OVTShareHashText([NSString stringWithFormat:@"%llu:%llu:%u:%llu:%u:%u:%lld:%lld:%lld:%lld:%lld",(unsigned long long)value.st_dev,
        (unsigned long long)value.st_ino,(unsigned)value.st_mode,(unsigned long long)value.st_nlink,(unsigned)value.st_uid,(unsigned)value.st_gid,(long long)value.st_size,
        (long long)value.st_mtimespec.tv_sec,(long long)value.st_mtimespec.tv_nsec,(long long)value.st_ctimespec.tv_sec,(long long)value.st_ctimespec.tv_nsec]);
}
NSString* OVTShareRootIdentity(struct stat value) {
    if (!S_ISDIR(value.st_mode) || value.st_uid!=geteuid() || (value.st_mode&0777)!=0700) {return nil;}
    return OVTShareHashText([NSString stringWithFormat:@"%llu:%llu:%u:%u:%u",(unsigned long long)value.st_dev,(unsigned long long)value.st_ino,
        (unsigned)value.st_mode,(unsigned)value.st_uid,(unsigned)value.st_gid]);
}
BOOL OVTShareCopyFile(NSURL* source,NSURL* destination,NSString** hash,NSUInteger* count) {
    return OVTShareCopyFileAnchored(source,destination,hash,count,NULL);
}
BOOL OVTShareCopyFileAnchored(NSURL* source,NSURL* destination,NSString** hash,NSUInteger* count,NSString** revision) {
    if (!source.isFileURL || !destination.isFileURL) {return NO;}
    int input=open(source.fileSystemRepresentation,O_RDONLY|O_NOFOLLOW|O_NONBLOCK|O_CLOEXEC);if (input<0) {return NO;}
    struct stat before,after;
    if (fstat(input,&before)!=0 || !S_ISREG(before.st_mode) || before.st_nlink!=1 || before.st_size<=0 || before.st_size>256*1024*1024) {close(input);return NO;}
    int output=open(destination.fileSystemRepresentation,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW,0600);
    if (output<0) {close(input);return NO;}
    BOOL saved=YES;NSUInteger total=0;unsigned char buffer[65536];CC_SHA256_CTX digest;CC_SHA256_Init(&digest);
    for (;;) {
        ssize_t size=read(input,buffer,sizeof(buffer));if (size<0 && errno==EINTR) {continue;}
        if (size<0) {saved=NO;break;}if (!size) {break;}total+=(NSUInteger)size;
        if (total>256*1024*1024 || !OVTWriteAll(output,buffer,(NSUInteger)size)) {saved=NO;break;}
        CC_SHA256_Update(&digest,buffer,(CC_LONG)size);
    }
    if (fstat(input,&after)!=0 || before.st_dev!=after.st_dev || before.st_ino!=after.st_ino || before.st_size!=after.st_size
            || before.st_mtimespec.tv_sec!=after.st_mtimespec.tv_sec || before.st_mtimespec.tv_nsec!=after.st_mtimespec.tv_nsec
            || before.st_ctimespec.tv_sec!=after.st_ctimespec.tv_sec || before.st_ctimespec.tv_nsec!=after.st_ctimespec.tv_nsec
            || total!=(NSUInteger)before.st_size) {saved=NO;}
    struct stat completed,named;
    if (fsync(output)!=0 || fstat(output,&completed)!=0 || !S_ISREG(completed.st_mode) || completed.st_nlink!=1
        || completed.st_uid!=geteuid() || (completed.st_mode&0777)!=0600 || completed.st_size!=(off_t)total
        || lstat(destination.fileSystemRepresentation,&named)!=0 || ![OVTShareFileRevision(named) isEqual:OVTShareFileRevision(completed)]
        || lstat(source.fileSystemRepresentation,&named)!=0 || ![OVTShareFileRevision(named) isEqual:OVTShareFileRevision(before)]) {saved=NO;}
    if (close(output)!=0) {saved=NO;}if (close(input)!=0) {saved=NO;}
    if (!OVTSyncDirectory([destination URLByDeletingLastPathComponent])) {saved=NO;}
    if (!saved) {return NO;}
    unsigned char result[CC_SHA256_DIGEST_LENGTH];CC_SHA256_Final(result,&digest);NSMutableString* text=[NSMutableString new];
    for (NSUInteger index=0;index<sizeof(result);++index) {[text appendFormat:@"%02x",result[index]];}
    *hash=text;*count=total;if (revision) {*revision=OVTShareFileRevision(completed);}return YES;
}
NSData* OVTShareReadMetadata(NSURL* source) {
    if (!source.isFileURL) {return nil;}
    int file=open(source.fileSystemRepresentation,O_RDONLY|O_NOFOLLOW|O_NONBLOCK|O_CLOEXEC);if (file<0) {return nil;}
    struct stat before,after;
    if (fstat(file,&before)!=0 || !S_ISREG(before.st_mode) || before.st_nlink!=1 || before.st_size<1 || before.st_size>262144) {close(file);return nil;}
    NSMutableData* bytes=[NSMutableData dataWithLength:(NSUInteger)before.st_size];NSUInteger offset=0;BOOL valid=YES;
    while (offset<bytes.length) {
        ssize_t size=read(file,(char*)bytes.mutableBytes+offset,bytes.length-offset);
        if (size<0 && errno==EINTR) {continue;}if (size<=0) {valid=NO;break;}offset+=(NSUInteger)size;
    }
    unsigned char trailing;
    if (read(file,&trailing,1)!=0 || fstat(file,&after)!=0 || before.st_dev!=after.st_dev || before.st_ino!=after.st_ino
            || before.st_size!=after.st_size || before.st_mtimespec.tv_sec!=after.st_mtimespec.tv_sec
            || before.st_mtimespec.tv_nsec!=after.st_mtimespec.tv_nsec || before.st_ctimespec.tv_sec!=after.st_ctimespec.tv_sec
            || before.st_ctimespec.tv_nsec!=after.st_ctimespec.tv_nsec) {valid=NO;}
    if (close(file)!=0) {valid=NO;}return valid?bytes:nil;
}
@implementation OVTShareJournal
- (instancetype)init {if ((self=[super init])) {_lock=[NSRecursiveLock new];_valid=YES;}return self;}
- (BOOL)persist {
    if (!_valid) {return NO;}NSData* bytes=[NSJSONSerialization dataWithJSONObject:_record options:0 error:nil];
    if (!OVTShareWrite(_root,@"share-original.json",bytes)) {_valid=NO;return NO;}return YES;
}
- (BOOL)event:(NSString*)kind {
    [_lock lock];NSMutableArray* events=_record[@"events"];
    if (!_valid || events.count>=512) {_valid=NO;[_lock unlock];return NO;}
    [events addObject:@{@"sequence":@(events.count+1),@"kind":kind,@"clock":OVTShareClock()}];
    BOOL saved=[self persist];[_lock unlock];return saved;
}
@end
