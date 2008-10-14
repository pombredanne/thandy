
import os
import sys
import getopt
import time

import simplejson

import glider.formats
import glider.util
import glider.keys

def tstamp():
    return time.strftime("%Y%m%d_%H%M%S", time.localtime())

def snarf(fname):
    f = open(fname, 'rb')
    try:
        return f.read()
    finally:
        f.close()

def snarfObj(fname):
    f = open(fname, 'r')
    try:
        return simplejson.load(f)
    finally:
        f.close()

def insert(args):
    repo = os.environ.get("THANDY_MASTER_REPO")
    backupDir = glider.util.userFilename("old_files")
    checkSigs = True

    options, args = getopt.getopt(args, "", ["repo=", "no-check"])
    for o,v in options:
        if o == "--repo":
            repo = v
        elif o == "--no-check":
            checkSigs = False

    if not repo:
        print "No repository specified."
        usage()
    if not os.path.exists(repo):
        print "No such repository as %r"%repo
        usage()

    if not os.path.exists(backupDir):
        os.makedirs(backupDir, 0700)

    if checkSigs:
        keys = glider.util.getKeylist(os.path.join(repo, "meta/keys.txt"))
    else:
        keys = None

    n_ok = 0
    for fn in args:
        print "Loading %s..."%fn
        try:
            content = snarf(fn)
        except OSError, e:
            print "Couldn't open %s: %s"%(fn, e)
            continue

        try:
            obj = simplejson.loads(content)
        except ValueError, e:
            print "Couldn't decode %s: %s"%(fn, e)
            continue

        try:
            ss, r, path = glider.formats.checkSignedObj(obj, keys)
        except glider.FormatException, e:
            print "Bad format on %s: %s"%(fn, e)
            continue
        if checkSigs and not ss.isValid():
            print "Not enough valid signatures on %s"%fn
            continue

        print "  Looks okay.  It goes in %s"%path
        assert path.startswith("/")
        targetPath = os.path.join(repo, path[1:])
        if os.path.exists(targetPath):
            oldContents = snarf(targetPath)
            if oldContents == content:
                print "  File unchanged!"
                n_ok += 1
                continue

            baseFname = "%s_%s" % (tstamp(), os.path.split(path)[1])
            backupFname = os.path.join(backupDir, baseFname)
            print "  Copying old file to %s"%backupFname
            glider.util.replaceFile(backupFname, oldContents)

        parentDir = os.path.split(targetPath)[0]
        if not os.path.exists(parentDir):
            print "  Making %s"%parentDir
            os.makedirs(parentDir, 0755)
        print "  Replacing file..."
        glider.util.replaceFile(targetPath, content)
        print "  Done."
        n_ok += 1
    if n_ok != len(args):
        sys.exit(1)

def timestamp(args):
    repo = os.environ.get("THANDY_MASTER_REPO")
    ts_keyfile = glider.util.userFilename("timestamp_key")

    options, args = getopt.getopt(args, "", ["repo=", "ts-key="])
    for o,v in options:
        if o == "--repo":
            repo = v
        elif o == "--ts-key":
            ts_keyfile = v

    if repo == None:
        print "No repository specified."
        usage()
    if not os.path.exists(repo):
        print "No such repository as %r"%repo
        usage()

    tsFname = os.path.join(repo, "meta/timestamp.txt")

    try:
        mObj = snarfObj(os.path.join(repo, "meta/mirrors.txt"))
    except OSError:
        print "No mirror list!"
        sys.exit(1)
    try:
        kObj = snarfObj(os.path.join(repo, "meta/keys.txt"))
    except OSError:
        print "No key list!"
        sys.exit(1)

    bundles = []
    for dirpath, dirname, fns in os.walk(os.path.join(repo, "bundleinfo")):
        for fn in fns:
            try:
                bObj = snarfObj(fn)
            except (ValueError, OSError), e:
                print "(Couldn't read bundle-like %s)"%fn
                continue
            try:
                _, r, _ = glider.formats.checkSignedObj(bObj)
            except glider.FormatException, e:
                print "Problem reading object from %s"%fn
                continue
            if r != "bundle":
                print "%s was not a good bundle"%fn
                continue
            bundles.append(bObj['signed'])

    timestamp = glider.formats.makeTimestampObj(
        mObj['signed'], kObj['signed'], bundles)
    signable = glider.formats.makeSignable(timestamp)

    keydb = glider.formats.Keylist()
    #XXXX Still a roundabout way to do this.
    keylist = glider.formats.makeKeylistObj(ts_keyfile, True)
    keydb.addFromKeylist(keylist)
    for k in keydb.iterkeys():
        glider.formats.sign(signable, k)

    content = simplejson.dumps(signable, sort_keys=True)
    glider.util.replaceFile(tsFname, content)

def usage():
    print "Known commands:"
    print "  insert [--no-check] [--repo=repository] file ..."
    print "  timestamp [--repo=repository]"
    sys.exit(1)

def main():
    if len(sys.argv) < 2:
        usage()
    cmd = sys.argv[1]
    args = sys.argv[2:]
    if cmd in [ "insert", "timestamp" ]:
        globals()[cmd](args)
    else:
        usage()

if __name__ == '__main__':
    main()
