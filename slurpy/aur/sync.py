# sync.py - Defines Sync class to retrieve source packages from the AUR
#
# Randy Morris <randy@rsontech.net>
#
# CREATED:  2009-12-15 09:29
# MODIFIED: 2010-02-04 19:08

VERSION = '3.0.0'

from cStringIO import StringIO
import glob
import os
import re
import sys
import gzip
import urllib
import urllib2
import httplib
import subprocess
from distutils import version as Version
from tarfile import TarFile

try:
    import cjson as Json
except ImportError:
    import json as Json

from aur import AUR


# utility functions

def json_decode(url):
    """Open <url> and decode the json response"""

    url = "http://" + urllib.quote(url[7:], "/?=&")

    request = urllib2.Request(url)
    request.add_header("Accept-encoding", "gzip")
    request.add_header("User-agent", "slurpy/%s" % VERSION)
    usock = None
    try:
        usock = urllib2.urlopen(request)
        data = usock.read()
        if usock.headers.get('content-encoding', None) == 'gzip':
            data = gzip.GzipFile(fileobj=StringIO(data)).read()
        usock.close()
    except:
        # just rethrow for now
        raise
    finally:
        # clean up
        del request
        del usock
    try:
        return Json.decode(data)
    except AttributeError:
        return Json.loads(data)

def json_mdecode(pkglist):
    conn = httplib.HTTPConnection("aur.archlinux.org")
    headers = {"Connection": "Keep-Alive",
            'User-agent': 'slurpy/%s' % VERSION,
            'Accept-encoding': 'gzip'}
    results = []
    for pkg in pkglist:
        conn.request("GET", "/rpc.php?type=info&arg=%s" % pkg, headers=headers)
        response = conn.getresponse()
        data = response.read()
        if response.getheader('content-encoding', None) == 'gzip':
            data = gzip.GzipFile(fileobj=StringIO(data)).read()
        try:
            results.append(Json.decode(data))
        except AttributeError:
            results.append(Json.loads(data))
    return results


def strip_slashes(text):
    """Remove extraneous backslashes (\) from <text>"""
    if text is None:
        return "None"
    text = text.encode('UTF-8')
    if 'cjson' in sys.modules:
        return text.replace('\/', '/')
    return text


# class definitions

class Sync(AUR):

    """ Handles all requests from the AUR """

    # json constants
    ID = "ID"
    NAME = "Name"
    VERSION = "Version"
    CATEGORY = "CategoryID"
    DESCRIPTION = "Description"
    LOCATION = "LocationID"
    URL = "URL"
    PATH = "URLPath"
    LICENSE = "License"
    VOTES = "NumVotes"
    OUT_OF_DATE = "OutOfDate"


    def __init__(self, opts, args):
        self.opts = opts
        self.args = []
 
        # encode white space
        for arg in args:
            self.args.append(arg.replace(" ", "%20"))

        # enable testing and community-testing repo if enabled on the machine
        conf = None
        try:
            with open(self.PACMAN_CONF, 'r') as fd:
                conf = fd.read()
        except IOError:
            # error reading pacman.conf, testing repo disabled by default
            # maybe we should raise instead?
            pass
        if conf:
            if re.search('^\s*\[testing\]', conf, re.M):
                self.PACMAN_REPOS.append('testing')
            if re.search('^\s*\[community-testing\]', conf, re.M):
                self.PACMAN_REPOS.append('community-testing')

    def download(self, pkgname, ignore=[]):
        """Downloads all packages in <self.args>
        
        Returns any (make)dependencies of that package found in the PKGBUILD.
        """

        if pkgname in ignore:
            return(None, [])

        if self.in_sync_db(pkgname) != False:
            return(None, [pkgname])

        json = json_decode(self.INFO_URL + pkgname)

        if json['type'] == 'error':
            raise AurRpcError("%s %s" % (pkgname, json['results']))

        pkg = json['results']
        url = self.AUR_URL + '/packages/' + pkgname + '/' + pkgname + '.tar.gz'

        fname = url.split('/')[-1].split('.tar.gz')[0]
        if not self.opts.force:
            if os.path.exists(fname + '.tar.gz'):
                raise AurIOError("%s/%s.tar.gz exists." %(os.getcwd(), fname))

            if os.path.exists(fname):
                raise AurIOError("%s/%s exists." %(os.getcwd(), fname))

        # download .tar.gz
        fd = open(fname + '.tar.gz', 'w')
        fd.write(urllib.urlopen(url).read())
        fd.close()

        # unzip -- per aur guidelines, all fnames must be .tar.gz'd
        try:
            fd = TarFile.open(fname + '.tar.gz', 'r:gz')
            fd.extractall()
            fd.close()
        except: 
            raise AurIOError("Error extracting archive %s.tar.gz" % fname)
        finally:
            os.unlink(fname + '.tar.gz')

        return(fname, None)
            
    def get_depends(self, pkgname):
        """Returns a list of (make)depends for pkgname"""
        if self.opts.download > 1:
            fd = open('%s/%s/PKGBUILD' % (self.opts.target_dir, pkgname), 'r')
            pkgb = fd.read()
            fd.close()

            deps = []
            deptup = re.findall('[^(opt)](make)?depends=\((.*?)\)', 
                                pkgb, re.S)
            for group in deptup:
                for dep in group[1].split():
                    dep = re.findall('(.[^<>=]*).*', dep)[0].strip("'").strip('"')
                    deps.append(dep)

            return deps

    def in_sync_db(self, name): 
        """Checks if <name> exists in the local syncdb for <repo>

        Returns true if found, otherwise false
        """
        for repo in self.PACMAN_REPOS:
            syncd = self.PACMAN_SYNC + repo
            for path in glob.glob("%s/%s-*" % (syncd, name)):
                # We assume that the dirname is $pkgname-$pkgver-$pkgrel
                if os.path.basename(path.rsplit('-', 2)[0]) == name:
                    return repo
        return False

    def info(self, pkgname):
        """Prints all known info about each package in <self.args>"""
        json = json_decode(self.INFO_URL + pkgname)
        if json['type'] == 'error':
            raise AurRpcError(json['results'])
        return json['results']

    def search(self, pkgname):
        """Search the AUR for <self.args> and print results to the screen"""
        pkgs = []
        filter = None
        # user passed a filter argument
        if pkgname[0] == '^' or pkgname[-1] == '$':
            filter = re.compile(pkgname)
            pkgname = pkgname.strip("^$")

        json = json_decode(self.SEARCH_URL + pkgname)
        if json['type'] == 'error':
            if json['results'].lower() != "no results found":
                raise AurRpcError(json['results'])
        else:
            if filter is None:
                pkgs.extend(json['results'])
            else:
                for pkg in json['results']:
                        if filter.search(pkg[self.NAME]):
                            pkgs.append(pkg)

        return pkgs

    def update(self):
        """Checks all explicitly installed packages for updates in the AUR.
        Returns a list dicts representing the package.'"""
        updates = []

        with subprocess.Popen(["pacman", "-Qm"],
                              stdout=subprocess.PIPE).stdout as fd:
            data = [l.strip() for l in fd]

        try:
            aur_data = json_mdecode(e.split(' ')[0] for e in data)
# If keep-alive for some reason fails (eg due to timeout), due to (possibly) a bug in httplib
# trying to read the response raises httplib.BadStatusLine.
        except httplib.BadStatusLine:
            aur_data = [json_decode(self.INFO_URL + pkg.split(' ')[0]) for pkg in data]

        for index, line in enumerate(data):
            pkg = aur_data[index]["results"]
            if pkg != "No result found":
                name, installed_version = line.split(" ")
# due to d.v.lv not handeling versions with '-' in them, split and compare the head and tail seperatly
                i_ver, i_rel = installed_version.split("-")
                a_ver, a_rel = pkg[self.VERSION].split("-")
                i_ver = Version.LooseVersion(i_ver)
                i_rel = Version.LooseVersion(i_rel)
                a_ver = Version.LooseVersion(a_ver)
                a_rel = Version.LooseVersion(a_rel)
                if a_ver > i_ver or (a_ver == i_ver and a_rel > i_rel):
                    pkg['_inst_ver'] = installed_version
                    updates.append(pkg)

        return updates


# exceptions

class AurRpcError(Exception):
    """To be thrown when the AUR returns errors in the JSON results"""

    def __init__(self, value):
        self.value = value.lower()

class AurIOError(Exception):
    """To be thrown when a file exists that we need to write to"""

    def __init__(self, value):
        self.value = value
