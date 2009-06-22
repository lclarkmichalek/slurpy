#!/usr/bin/python
#
# slurpy - AUR search/download/update helper
#
# Randy Morris <randy@rsontech.net>
#
# depends:
#           python
#
# optdepends: 
#           python-cjson - speeds up processing significantly on operations
#                          with many results
#
#
# Credits: This code started off as a port of the original arson ruby code
#          written by Colin Shea.  It has since changed very much, but the
#          roots are still obvious.
#
#          Colin's project can be found at <http://evaryont.github.com/arson>
#
# CREATED:  2008-08-22 18:41
# MODIFIED: 2009-06-22 09:42

"""usage: slurpy [options] <operation> PACKAGE [PACKAGE2..] 
 operations:              
  -d, --download          download PACKAGE(s)
                             if passed twice will also download dependencies
                             from the AUR
  -i, --info              show info for PACKAGE(s)
  -s, --search            search for PACKAGE(s)
  -u, --update            check explicitly installed packages for available
                          updates
                             if passed with --download flag(s), the download
                             operation specified will be performed for each
                             available update

   Note:  Other than --download --update, no other operations can be combined.
          If multiple operations are passed, only one will be performed.
          Operations take precidence according to the order above.

 options:
  -q, --quiet             show only package names in search/update results
  -t DIR, --save-to=DIR   target directory where files will be downloaded

  -h, --help              show this message
  --version               show version information"""

import glob
import os
import re
import string
import sys
import urllib

from distutils import version as Version
from optparse import OptionParser
from tarfile import TarFile

try:
    import cjson as Json
except ImportError:
    import json as Json

# utility functions
def strip_slashes(str):
    """Remove extraneous backslashes (\) from <str>"""
    return re.sub(r"\\(.)", r"\1", str.encode('UTF-8'))

def json_decode(url):
    """Open <url> and decode the json response"""
    try: 
        return Json.decode(urllib.urlopen(url).read())
    except AttributeError:
        return Json.loads(urllib.urlopen(url).read())

def display_result(pkgs, deps):
    """Print a nicely formated result of <pkgs> and <deps>"""
    if pkgs:
        if len(pkgs) == 1 and not deps:
            print pkgs[0], "downloaded to", os.getcwd()
        else:
            print "packages downloaded to %s:" % os.getcwd()
            for pkg in pkgs:
                print "   ", pkg
    if deps:
        if len(deps) == 1 and not pkgs:
            print deps[0], "is available in pacman repos"
        else:
            print "\ndependencies found in pacman repos:"
            for dep in deps:
                print "   ", dep

# class definitions
class slurpy():
    
    """slurpy base class
    
    Members:
     - opts
     - args
     - a shit ton of consants
    
    Methods to be overridden:
     - download()
     - info()
     - search()
     - update()
    """

    # This class really is the AUR subclass.  Until I figure out how to implement
    # the ABS side, this will stay the only class.

    _DOWNLOAD_URL = "http://aur.archlinux.org"
    _INFO_URL = "http://aur.archlinux.org/rpc.php?type=info&arg="
    _SEARCH_URL = "http://aur.archlinux.org/rpc.php?type=search&arg="
    _PACMAN_CACHE = "/var/lib/pacman/local"
    _PACMAN_SYNC = "/var/lib/pacman/sync/"

    # json constants
    _ID = "ID"
    _NAME = "Name"
    _VERSION = "Version"
    _CATEGORY = "CategoryID"
    _DESCRIPTION = "Description"
    _LOCATION = "LocationID"
    _URL = "URL"
    _PATH = "URLPath"
    _LICENSE = "License"
    _VOTES = "NumVotes"
    _OUT_OF_DATE = "OutOfDate"
    _CATEGORIES = [None, None, "daemons", "devel", "editors", "emulators", 
                               "games", "gnome", "i18n", "kde", "lib", 
                               "modules", "multimedia", "network", "office", 
                               "science", "system", "x11", "xfce", "kernels"]

    def __init__(self, opts, args):
        self.opts = opts
        self.args = args

    def download(self, ignore=[]):
        """Downloads all packages in <self.args>
        
        Returns any (make)dependencies of that package found in the PKGBUILD.
        """
        dledpkgs = [] # holds list of downloaded pkgs
        repodeps = [] # holds list of dependencies available in pacman repos
        for arg in self.args:
            if arg in ignore: 
                return (dledpkgs, repodeps)

            if (self.in_sync_db("core", arg) or self.in_sync_db("extra", arg) 
                    or self.in_sync_db("community", arg)):
                repodeps.append(arg)
                return(dledpkgs, repodeps)

            json = json_decode(self._INFO_URL + arg)

            if json['type'] == 'error':
                print "slurpy:", arg, json['results'].lower()
                return(dledpkgs, repodeps)

            pkg = json['results']
            url = self._DOWNLOAD_URL + strip_slashes(pkg[self._PATH])
            file = url.split('/')[-1].split('.tar.gz')[0]
            if not self.opts.force:
                if os.path.exists(file + '.tar.gz') or os.path.exists(file):
                    print "slurpy: file exists. pass -f to force this operation"
                    sys.exit()

            # download .tar.gz
            fp = open(file + '.tar.gz', 'w')
            fp.write(urllib.urlopen(url).read())
            fp.close()

            # unzip -- per aur guidelines, all files must be .tar.gz'd
            try:
                fp = TarFile.open(file + '.tar.gz', 'r:gz')
                fp.extractall()
                fp.close()
            except:
                print 'slurpy: error extracting archive %s.tar.gz' % file
                os.unlink(file + '.tar.gz')
                sys.exit()

            os.unlink(file + '.tar.gz')
            dledpkgs.append(file)
            
            # download deps
            if self.opts.download > 1:
                fp = open(file + '/PKGBUILD', 'r')
                pkgb = fp.read()
                fp.close()

                deps = []
                deptup = re.findall('[^(opt)](make)?depends=\((.*?)\)', pkgb, re.S)
                for group in deptup:
                    for dep in group[1].split():
                        dep = re.findall('(.[^<>=]*).*', dep)[0].strip("'")
                        deps.append(dep)

                # download dependencies, but ignore already downloaded pkgs
                pkgs, deps = slurpy(self.opts,deps).download(dledpkgs)

                if pkgs != []:
                    dledpkgs.extend(pkgs)
                if deps != []:
                    repodeps.extend(deps)

        # remove dups
        repodeps = set(repodeps).union(set(repodeps))

        return dledpkgs, repodeps

    def info(self):
        """Prints all known info about each package in <self.args>"""
        for arg in self.args:
            json = json_decode(self._INFO_URL + arg)
            if json['type'] == 'error':
                print "slurpy:", json['results'].lower()
                sys.exit()
            pkg = json['results']
            if pkg[self._LOCATION] == 3:
                repo = "community"
            else:
                repo = "aur"

            if pkg[self._OUT_OF_DATE] == 1:
                out_of_date = "No"
            else:
                out_of_date = "Yes"

            print "Repository      : %s\n" % repo, \
                  "Name            : %s\n" % pkg[self._NAME],\
                  "Versio          : %s\n" % pkg[self._VERSION],\
                  "URL             : %s\n" % strip_slashes(pkg[self._URL]),\
                  "Category        : %s\n" % self._CATEGORIES[int(pkg[self._CATEGORY])],\
                  "Licenses        : %s\n" % pkg[self._LICENSE],\
                  "Number of Votes : %s\n" % pkg[self._VOTES],\
                  "Out of Date     : %s\n" % out_of_date,\
                  "Description     : %s\n" % strip_slashes(pkg[self._DESCRIPTION])

    def search(self):
        """Search the AUR for <self.args> and print results to the screen"""
        pkgs = []
        for arg in self.args:
            json = json_decode(self._SEARCH_URL + arg)
            if json['type'] == 'error':
                print "slurpy:", json['results'].lower()
                sys.exit()
            pkgs.extend(json['results'])

        # sort
        spkgs = sorted(pkgs, key=lambda k: k[self._NAME])

        # remove dups -- note: extra list traversal, but imo it's worth it
        i=0
        for pkg in spkgs:
            if pkg == spkgs[i]: continue
            i += 1
            spkgs[i] = pkg
        del spkgs[i+1:]

        for pkg in spkgs:
            if self.opts.quiet:
                print pkg[self._NAME]
            else:
                if self.in_sync_db("community", pkg[self._NAME]):
                    repo = "community"
                    category = ""
                else:
                    repo = "aur"

                print "%s/%s %s" % (repo, pkg[self._NAME], pkg[self._VERSION])
                print "        %s" % strip_slashes(pkg[self._DESCRIPTION])

    def update(self):
        """Checks all explicitly installed packages for updates in the AUR"""
        updates = []

        if not self.opts.quiet:
            print "checking for package updates..."

        fp = os.popen("pacman -Qm")
        for ln in fp.readlines():
            name, version = ln[:-1].split(' ')
            pkg = json_decode(self._INFO_URL + name)['results']
            if pkg != "No result found":
                if self.update_available(pkg['Name'], pkg['Version']):
                    updates.append((name, pkg['Version']))

        return updates

    def update_available(self, name, version):
        """Helper for update(): does version comparison logic 
        
        Returns true if a new version is available, otherwise false
        """
        #TODO: What the fuck is going on here? I don't remember.
        # We have to do some funky shit in here because of scm version numbering.
        # Most of this may be unnecessary now because idgaf about return codes
        # anymore.
        if os.path.exists(self._PACMAN_CACHE + "/" + name + "-" + version):
            return False
        else:
            glb = glob.glob(self._PACMAN_CACHE + "/" + name + "-*")
            if len(glb) == 1:
                pkg_name = os.path.basename(glb[0])
                r_scm = re.compile('-[0-9]{8}-[0-9]+$')
                r_pkg = re.compile(name + '-.+-[0-9]+$')

                if r_scm.search(pkg_name):
                    scm_installed = True
                elif r_pkg.search(pkg_name):
                    scm_installed = False
                else:
                    print "slurpy: failed to detect pkg version type. please contact \
                            my developer with the below info"
                    print "pkg_name:", name, pkg_name
                    print "pkg_version:", version
                    sys.exit()
                
                if r_scm.search(name + "-" + version):
                    scm_passed = True
                elif r_pkg.search(name+ "-" + version):
                    scm_passed = False

                if scm_passed and scm_installed:
                    passed_version = r_scm.search(name + "-" + version).group().split("-")
                    installed_version = r_scm.search(pkg_name).group().split("-")
                    if passed_version[1] > installed_version[1]\
                         or (passed_version[1] == installed_version[1]\
                         and passed_version[2] > installed_version[2]):
                        return True
                    else:
                        return False
                elif not scm_installed and not scm_passed:
                    iv = Version.LooseVersion(r_pkg.search(pkg_name).group()[len(name)+1:])
                    pccv = Version.LooseVersion(version)
                    if pccv > iv:
                        return True
                    else:
                        return False

                elif scm_installed and not scm_passed:
                    iv = Version.LooseVersion(r_pkg.search(pkg_name).group()[len(name)+1:])
                    pccv = Version.LooseVersion(version)
                    if pccv > iv:
                        return True 
                    else:
                        return False

    def in_sync_db(self, repo, name): 
        """Checks if <name> exists in the local syncdb for <repo>

        Returns true if found, otherwise false
        """
        syncd = self._PACMAN_SYNC + repo
        if glob.glob(syncd + "/" + name + "-*"):
            return True
        return False


# main processing 
if __name__ == '__main__':

    parser = OptionParser(version="%prog 0.1.1", conflict_handler="resolve")
    parser.add_option('-d', '--download', action='count')
    parser.add_option('-f', '--force', action='store_true')
    parser.add_option('-h', '--help', action='store_true')
    parser.add_option('-i', '--info', action='store_true')
    parser.add_option('-q', '--quiet', action='store_true')
    parser.add_option('-s', '--search', action='store_true')
    parser.add_option('-t', '--save-to', dest='target_dir', action='store') 
    parser.add_option('-u', '--update', action='store_true')
    
    slurp = slurpy(*parser.parse_args())

    if slurp.opts.update and slurp.opts.download:
        updates = []
        for pkg, version in slurp.update():
            updates.append(pkg) 
        slurp.args = updates

        print "downloading updates...\n"
        display_result(*slurp.download())

    elif slurp.opts.download:
        try:
            if slurp.opts.target_dir is not None:
                os.chdir(slurp.opts.target_dir)
        except OSError:
            print "slurpy: target dir does not exist or is not a directory"
            sys.exit()
        display_result(*slurp.download())

    elif slurp.opts.info:
        slurp.info()
    elif slurp.opts.search:
        slurp.search()
    elif slurp.opts.update:
        for pkg, version in slurp.update():
            if slurp.opts.quiet:
                print pkg 
            elif not slurp.opts.download:
                print "-", pkg, version
    else:
        print __doc__ 

# vim:sw=4:ts=4:sts=4:
