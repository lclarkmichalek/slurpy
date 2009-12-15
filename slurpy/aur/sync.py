# sync.py - Defines Sync class to retrieve source packages from the AUR
#
# Randy Morris <randy@rsontech.net>
#
# CREATED:  2009-12-15 09:29
# MODIFIED: 2009-12-15 13:45

VERSION = '3.0.0'

from cStringIO import StringIO
import glob
import os
import re
import sys
import gzip
import urllib
import urllib2
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
    request = urllib2.Request(url)
    request.add_header("Accept-encoding", "gzip")
    request.add_header("User-agent", "slurpy/%s" % VERSION)
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

def strip_slashes(str):
    """Remove extraneous backslashes (\) from <str>"""
    if str is None:
        return "None"
    str = str.encode('UTF-8')
    if 'cjson' in sys.modules:
        return str.replace('\/', '/')
    return str

class Sync(AUR):

    """ Handles all pull requests from the AUR """

    PACMAN_CACHE = "/var/lib/pacman/local"
    PACMAN_CONF = "/etc/pacman.conf"
    PACMAN_REPOS = ['core', 'extra', 'community']
    PACMAN_SYNC = "/var/lib/pacman/sync/"

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
    CATEGORIES = [None, None, "daemons", "devel", "editors", "emulators",
                  "games", "gnome", "i18n", "kde", "lib", "modules",
                  "multimedia", "network", "office", "science", "system",
                  "x11", "xfce", "kernels"]


    def __init__(self, opts, args):
        self.opts = opts
        self.args = []
        
        # encode white space
        for arg in args:
            self.args.append(arg.replace(" ", "%20"))

        # enable testing repo if enabled on the machine
        try:
            fd = open(self.PACMAN_CONF, 'r')
            conf = fd.read()
            fd.close()
        except IOError:
            # error reading pacman.conf, testing repo disabled by default
            pass
        else:
            if re.search('^\s*\[testing\]', conf, re.M):
                self.PACMAN_REPOS = ['testing'] + self.PACMAN_REPOS

    def download(self, pkgname, ignore=[]):
        """Downloads all packages in <self.args>
        
        Returns any (make)dependencies of that package found in the PKGBUILD.
        """

        if pkgname in ignore:
            return(none, [])

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
        """stub"""
        # download deps
        if self.opts.download > 1:
            fd = open('%s/%s/PKGBUILD' % (self.opts.target_dir, pkgname), 'r')
            pkgb = fd.read()
            fd.close()

            deps = []
            deptup = re.findall('[^(opt)](make)?depends=\((.*?)\)', 
                                pkgb, re.S)
            for group in deptup:
                for dep in group[1].split():
                    dep = re.findall('(.[^<>=]*).*', dep)[0].strip("'")
                    deps.append(dep)

            return deps

    def in_sync_db(self, name): 
        """Checks if <name> exists in the local syncdb for <repo>

        Returns true if found, otherwise false
        """
        for repo in self.PACMAN_REPOS:
            syncd = self.PACMAN_SYNC + repo
            if glob.glob(syncd + "/" + name + "-*"):
                return repo
        return False

    def info(self, pkgname):
        """Prints all known info about each package in <self.args>"""
        json = json_decode(self.INFO_URL + pkgname)
        if json['type'] == 'error':
            raise AurRpcError(json['results'])
        return json['results']

    def run(self):
        """Main processing for AURSync.

        Handles all function dispatching and pre/post result output.
        """
        pass

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
            data = fd.readlines()
        
        for ln in data:
            name, inst_ver  = ln[:-1].split(' ')
            pkg = json_decode(self.INFO_URL + name)['results']
            if pkg != "No result found":
               aur_ver = Version.LooseVersion(pkg[self.VERSION])
               inst_ver = Version.LooseVersion(inst_ver)
               if aur_ver > inst_ver:
                   pkg['_inst_ver'] = str(inst_ver)
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
