#!/usr/bin/env python
# slurpy.py - Defines the Slurpy AUR front end class
#
# Randy Morris <randy@rsontech.net>
#
# CREATED:  2009-12-15 09:41
# MODIFIED: 2010-01-26 08:37

VERSION = '3.0.0'

import imp
import os
import operator
from optparse import OptionParser
import re
import stat
import subprocess
import sys

from aur.sync import *

try:
    from aur.push import *
except ImportError:
    __doc__ = """Usage: slurpy [options] <operation> PACKAGE [PACKAGE2..]

 Operations:
  -d, --download          download PACKAGE(s)
                             if passed twice will also download dependencies
                             from the AUR
  -i, --info              show info for PACKAGE(s)
  -s, --search            search for PACKAGE(s)
  -u, --update            check explicitly installed packages for available
                          updates
                             if passed with --download flag(s), perform download
                             operation for each package with an available update

 General options:
  -c, --color             use colored output
  -f, --force             overwrite existing files when dowloading
  -q, --quiet             show only package names in search/update results
  -t DIR, --save-to=DIR   target directory where files will be downloaded
  -v, --verbose           show info messages
                             if passed twice will also show debug messages

  -h, --help              show this message
      --version           show version information"""
else:
    __doc__ = """Usage: slurpy [options] [--sync] <operation> PACKAGE [PACKAGE2..] 
       slurpy [options] --push FILE1 [FILE2..] 

 Modes:
  -S, --sync              Retrieve package(s)/info from the AUR (DEFAULT)
  -P, --push              Upload a package to the AUR

 Sync Operations:              
  -d, --download          download PACKAGE(s)
                             if passed twice will also download dependencies
                             from the AUR
  -i, --info              show info for PACKAGE(s)
  -s, --search            search for PACKAGE(s)
  -u, --update            check explicitly installed packages for available
                          updates 
                             if passed with --download flag(s), perform download
                             operation for each package with an available update

 Push Options:
  -C, --category          package category in the AUR
                             New Package DEFAULT: none
                             Update DEFAULT: current category in the AUR
  -U, --user              AUR username
      --cookie-file       file to store AUR session information in

 General options:
  -c, --color             use colored output
  -f, --force             overwrite existing files when dowloading
  -q, --quiet             show only package names in search/update results
  -t DIR, --save-to=DIR   target directory where files will be downloaded
  -v, --verbose           show info messages
                             if passed twice will also show debug messages

  -h, --help              show this message
      --version           show version information"""

# utility functions
def read_config():
    """Read in the slurpy runtime config to set default options."""

    # configuration options, sane defaults
    config_opts = {
        "aur_user" : None,
        "colors": {
            "red":     "boldred", 
            "green":   "boldgreen",
            "yellow":  "boldyellow", 
            "blue":    "boldblue",
            "magenta": "boldmagenta", 
            "cyan":    "boldcyan",
            "white":   "boldwhite",
        },
        "cookie_file": "~/.slurpy.aurcookie",
        "target_dir": ".",
        "use_color": False,
        "verbose": 0,
    }
    
    home = os.getenv('HOME')
    xdg_config_home = os.getenv('XDG_CONFIG_HOME')
    if xdg_config_home is None:
        xdg_config_home = "%s/.config/" % home

    xdg_slurpyrc_path = os.path.join(xdg_config_home, "slurpy/slurpyrc")
    home_slurpyrc_path = os.path.join(home, ".slurpyrc")
    config_path = None

    if os.path.exists(xdg_slurpyrc_path):
        config_path = xdg_slurpyrc_path
    elif os.path.exists(home_slurpyrc_path):
        config_path = home_slurpyrc_path

    # if there's a config file, load it as a module
    if config_path is not None:
        
        # ensure config file can't be tweaked by another user
        if os.stat(config_path)[stat.ST_MODE] & stat.S_IWGRP or \
            os.stat(config_path)[stat.ST_MODE] & stat.S_IWOTH:
            print "error: Permissions on %s must be 755 or less." % config_path
            sys.exit(1)

        try:
            slurpyrc = imp.load_source("slurpyrc", config_path)
            user_config = [x for x in slurpyrc.__dict__.items() \
                            if x[0].isupper() and not x[0].startswith('_')]

            for var, val in user_config:
                var = var.lower()
                if var not in config_opts:
                    print "info: Ignoring unknown option %s" % (var)
                else:
                    config_opts[var] = val

        except (SyntaxError, NameError):
            print "error: There is a syntax error in your config file."
            print "Please correct this and try again."
            sys.exit(1)

    for pathparm in ("cookie_file", "target_dir"):
        config_opts[pathparm] = os.path.expanduser(config_opts[pathparm])

    return config_opts

def fold(text, width=80, pad=0):
    """Wrap <text> at <width> characters.  Pad left side with <pad> spaces."""
    output = ''
    for line in text.split('\n'):
        while len(line) > width:
            pos = line[:width].rfind(' ')
            output = output + line[:pos] + '\n'
            line = " "*pad + line[pos+1:]
        output = output + line

    return output


class Slurpy(object):
    """
    Handles all output pertaining to packages returned by the AUR classes

    """

    COLOR_CONF = "/etc/pacman.d/color.conf"

    def __init__(self, opts, args):
        """Sets up colors and sets opts for the class"""
        self.opts = opts
        self.args = args
        if opts.push:
            self.aur = Push(opts, args)
        else:
            self.aur = Sync(opts, args)

        ansi_colors = ["black","red","green","yellow","blue","magenta","cyan",
                       "white","foreground","gray","boldred","boldgreen",
                       "boldyellow","boldblue","boldmagenta","boldcyan",
                       "boldwhite","boldforeground"
                      ]

        setattr(self, "RESET", "\033[1;m")
        for col in opts.colors:
            if opts.colors[col][:4] == "bold":
                ansi_col = opts.colors[col][4:]
                if opts.use_color:
                    if ansi_col == "":
                        setattr(self, col.upper(), "\033[1m")
                    else:
                        setattr(self, col.upper(),
                            "\033[1;3" + str(ansi_colors.index(ansi_col)) + "m")
                else:
                    setattr(self, col.upper(), "\033[1;m")
            else:
                ansi_col = opts.colors[col]
                if opts.use_color:
                    setattr(self, col.upper(), 
                            "\033[0;3" + str(ansi_colors.index(ansi_col)) + "m")
                else:
                    setattr(self, col.upper(), "\033[3;m")

    def search(self):
        try:
            stty = subprocess.Popen(['stty', 'size'], stdout=subprocess.PIPE)
        except OSError:
            win_width = 80
        else:
            dim = stty.communicate([0])[0]
            win_width = int(dim.split()[1])

        pkgs = []
        for arg in self.args:
            try:
                pkgs.extend(self.aur.search(arg))
            except AurRpcError, e:
                print "{0}error:{1} {2}".format(self.RED, self.RESET, e.value)
                continue

        if pkgs == []:
            return

        # sort
        pkgs.sort(key=operator.itemgetter(self.aur.NAME))

        # remove dups -- note: extra list traversal, but imo it's worth it
        i = 0
        for pkg in pkgs:
            if pkg == pkgs[i]: 
                continue
            i += 1
            pkgs[i] = pkg
        del pkgs[i+1:]

        for pkg in pkgs:
            if self.opts.quiet:
                print "{0}{1}{2}".format(self.WHITE, pkg[self.NAME], self.RESET)
            else:
                print "{0}aur{1}/{2}{3}".format(
                        self.MAGENTA, self.RESET, self.WHITE, pkg[self.aur.NAME]),

                if pkg[self.aur.OUT_OF_DATE] == '0':
                    print "{0}{1}{2}".format(
                            self.GREEN, pkg[self.aur.VERSION], self.RESET)
                else:
                    print "{0}{1}{2}".format(
                            self.RED, pkg[self.aur.VERSION], self.RESET)

                desc = strip_slashes(pkg[self.aur.DESCRIPTION])
                print fold("    {0}".format(desc), win_width, 4)
        

    def info(self):
        try:
            stty = subprocess.Popen(['stty', 'size'], stdout=subprocess.PIPE)
        except OSError:
            win_width = 80
        else:
            dim = stty.communicate([0])[0]
            win_width = int(dim.split()[1])

        for arg in self.args:
            try:
                pkg = self.aur.info(arg)
            except AurRpcError, e:
                print "{0}error:{1} {2}".format(self.RED, self.RESET, e.value)
                sys.exit(1)

            if pkg[self.aur.OUT_OF_DATE] == '0':
                out_of_date = "No"
            else:
                out_of_date = "Yes"

            print "Repository      : {0}aur".format(self.MAGENTA)

            print "{0}Name            : {1}{2}".format( self.RESET, self.WHITE,
                        pkg[self.aur.NAME])

            print "{0}Version         :".format(self.RESET),
            if out_of_date == "Yes":
                print "{0}{1}".format(self.RED, pkg[self.aur.VERSION])
            else:
                print "{0}{1}".format(self.GREEN, pkg[self.aur.VERSION])

            print "{0}URL             : {1}{2}".format(self.RESET, 
                        self.CYAN, strip_slashes(pkg[self.aur.URL]))

            print "{0}AUR Page        : {1}{2}/packages.php?ID={3}".format(
                        self.RESET, self.CYAN, self.aur.AUR_URL, 
                        pkg[self.aur.ID])

            print "{0}Category        : {1}".format(self.RESET, 
                        self.aur.CATEGORIES[int(pkg[self.aur.CATEGORY])])

            print "{0}Licenses        : {1}".format(
                        self.RESET, strip_slashes(pkg[self.aur.LICENSE]))

            print "{0}Number of Votes : {1}".format(
                        self.RESET, pkg[self.aur.VOTES])

            print "{0}Out of Date     :".format(self.RESET),
            if out_of_date == "Yes":
                print "{0}{1}".format(self.RED, out_of_date)
            else:
                print "{0}{1}".format(self.GREEN, out_of_date)

            desc = strip_slashes(pkg[self.aur.DESCRIPTION])
            print fold("{0}Description     : {1}".format(self.RESET, desc), 
                       win_width, 18) + '\n'

    def download(self):
        dledpkgs = [] # holds list of downloaded pkgs
        repodeps = [] # holds list of dependencies available in pacman repos
        for arg in self.args:
            if arg in repodeps: 
                continue

            try:
                pkg, deps = self.aur.download(arg)
            except AurRpcError, e:
                print "{0}error:{1} {2}".format(self.RED, self.RESET, e.value)
                continue
            except AurIOError, e:
                print "{0}error:{1} {2}".format(self.RED, self.RESET, e.value)
                continue

            if pkg is not None:
                dledpkgs.append(pkg)
            if deps is not None:
                repodeps.extend(deps)

            if self.opts.download > 1:
                deps = self.aur.get_depends(arg)

                for dep in deps:
                    dpkgs = []
                    drdeps = []

                    # download dependencies, but ignore already downloaded pkgs
                    try:
                        dpkg, ddeps = self.aur.download(dep, dledpkgs)
                    except AurRpcError, e:
                        print "{0}error:{1} {2}".format(self.RED, self.RESET, e.value)
                        continue
                    except AurIOError, e:
                        print "{0}error:{1}{2}".format(self.RED, self.RESET, e.value)
                        continue

                    if dpkg is not None:
                        dpkgs.append(dpkg)
                    if ddeps is not None:
                        drdeps.extend(ddeps)

                    for p in dpkgs:
                        d = self.aur.get_depends(p)
                        if d != []:
                            deps.extend(d)
                    
                    if dpkgs != []:
                        dledpkgs.extend(dpkgs)
                    if drdeps != []:
                        repodeps.extend(drdeps)

        # remove dups
        repodeps = list(set(repodeps))
        repodeps.sort()
        dledpkgs.sort()

        self.display_result(dledpkgs, repodeps)

    def display_result(self, pkgs, deps):
        """Print a nicely formated result of <pkgs> and <deps>"""
        if pkgs:
            if len(pkgs) == 1 and not deps:
                print "{0}{1}{2} downloaded to {3}{4}".format(self.WHITE, 
                            pkgs[0], self.RESET, self.GREEN, os.getcwd()) 
            else:
                print "{0}Packages downloaded to {1}{2}:".format(self.RESET,
                            self.GREEN, os.getcwd(), self.RESET)
                for pkg in pkgs:
                    print "   {0}{1}".format(self.WHITE, pkg)
        if deps:
            if len(deps) == 1 and not pkgs:
                print "{0}{1}{2} is available in {3}pacman repos{4}".format(
                            self.WHITE, deps[0], self.RESET, self.YELLOW,
                            self.RESET)
            else:
                print "\n{0}Dependencies found in {1}pacman repos{2}:".format(
                            self.RESET, self.YELLOW, self.RESET)
                for dep in deps:
                    print "    {0}{1}".format(self.WHITE, dep)

    def update(self):
        pkgs = self.aur.update()

        if pkgs == []:
            sys.exit(1) # mimic pacman
        
        for pkg in pkgs:
            if not self.opts.download:
                pkgname = "{0}{1}{2}".format(self.WHITE, pkg[self.aur.NAME],
                                         self.RESET)
                inst_ver = "{0}{1}{2}".format(self.GREEN, pkg['_inst_ver'], 
                                          self.RESET)
                
                if self.opts.quiet:
                    print pkgname
                elif self.opts.verbose >= 1:
                    if pkg[self.aur.OUT_OF_DATE] == '0':
                        aur_ver = "{0}{1}{2}".format(self.GREEN, 
                                    pkg[self.aur.VERSION], self.RESET)
                    else:
                        aur_ver = "{0}{1}{2}".format(self.RED, 
                                    pkg[self.aur.VERSION], self.RESET)

                    print "{0} {1} -> {2}".format(pkgname, inst_ver, aur_ver)
                else:
                    print "{0} {1}".format(pkgname, inst_ver)
        return pkgs

    def login(self):
        if self.opts.aur_user is None:
            self.opts.aur_user = raw_input('User: ')

        password = getpass('Password: ')
        if not self.aur.login(self.opts.aur_user, password):
            print "{0}error:{1}".format(self.RED, self.RESET), \
                  "Bad username or password. Please try again." 
            sys.exit(1)

    def upload(self):
        for arg in self.args:
            if not os.path.isfile(arg):
                print "{0}error:{1}{2} ".format(self.RED, self.RESET, arg), \
                      "does not exist or is not a file."
                sys.exit(1)

            success = None
            try:
                pkg = self.aur.upload(arg, self.opts.category)
            except AurUploadError, e:
                print "{0}error:{1} {2}: {3}".format(self.RED, self.RESET,
                                                    e.fname, e.msg),
                sys.exit(1)

            if pkg:
                print "{0}{1}{2} has been uploaded".format(self.WHITE, pkg,
                        self.RESET)
            else:
                print "{0}error:{1} Unknown error.".format(self.RED, self.RESET),
            

# main processing 
def main():
    conf = read_config()

    _version = ' '.join(("%prog",VERSION))
    parser = OptionParser(version=_version, conflict_handler="resolve")
    parser.add_option('-d', '--download', action='count')
    parser.add_option('-c', '--color', action='store_true', dest="use_color",
                            default=conf['use_color'])
    parser.add_option('-f', '--force', action='store_true')
    parser.add_option('-h', '--help', action='store_true')
    parser.add_option('-i', '--info', action='store_true')
    parser.add_option('-q', '--quiet', action='store_true')
    parser.add_option('-s', '--search', action='store_true')
    parser.add_option('-t', '--save-to', dest='target_dir', action='store',
                            default=conf['target_dir'])
    parser.add_option('-u', '--update', action='store_true')
    parser.add_option('-v', '--verbose', action='count',
                            default=conf['verbose'])
    parser.add_option('-S', '--sync', action='store_true', default=True)

    if 'pycurl' in sys.modules:
        parser.add_option('-C', '--category', action='store', default=None)
        parser.add_option('-P', '--push', action='store_true', default=False)
        parser.add_option('-U', '--user', action='store', dest='aur_user',
                            default=conf['aur_user'])
        parser.add_option('', '--cookie-file', action='store',
                            default=conf['cookie_file'])

    opts, args = parser.parse_args()
    setattr(opts, 'colors', conf['colors'])

    if not getattr(opts, 'push', False):
        setattr(opts, 'push', False)

    try:
        if opts.target_dir is not None and not opts.push:
            os.chdir(opts.target_dir)
    except OSError:
        print "{0}error:{1}{2}".format(slurpy.RED, slurpy.RESET, \
              opts.target_dir), "does not exist or is not a directory"
        sys.exit(1)

    opts.target_dir = os.getcwd()

    slurpy = Slurpy(opts,args)

    if 'pycurl' in sys.modules and opts.push:
        if opts.category is None or \
           opts.category not in slurpy.aur.CATEGORIES:
            print "{0}error:{1} ".format(slurpy.RED, slurpy.RESET), \
                  "Invalid category (-C, --category)\n\n", \
                  "Please enter one of the following categories:\n"

            print fold(str(slurpy.aur.CATEGORIES[2:]), 80) + '\n'
            sys.exit(1)

        slurpy.login()
        slurpy.upload()
    else:
        if opts.update and opts.download:
            updates = [] # holds all available updates

            print "Downloading updates to {0}{1}{2}".format(slurpy.GREEN,
                  os.getcwd(), slurpy.RESET)

            for pkg in slurpy.update():
                updates.append(pkg[slurpy.NAME]) 

            if updates == []:
                sys.exit(1) # mimic pacman
            else:
                slurpy.args = updates
                slurpy.download()
        elif opts.info:
            slurpy.info()
        elif opts.search:
            slurpy.search()
        elif opts.update:
            slurpy.update()
        elif opts.download:
            slurpy.download()
        else:
            print __doc__

if __name__ == '__main__':
    main()
# vim:sw=4:ts=4:sts=4:
