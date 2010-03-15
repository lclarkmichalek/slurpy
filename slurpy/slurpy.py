#!/usr/bin/env python
# slurpy.py - Defines the Slurpy AUR front end class
#
# Randy Morris <randy@rsontech.net>
#
# CREATED:  2009-12-15 09:41
# MODIFIED: 2010-03-15 19:15

VERSION = '3.0.0'


from ConfigParser import ConfigParser
import imp
import os
import operator
from optparse import OptionParser
import re
import stat
from string import Template
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
    """ Read in the slurpy runtime config to set default options. """

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


    config = ConfigParser()
    try:
        config.readfp(open('/etc/slurpyrc'))
    except IOError:
        print "error: /etc/slurpyrc could not be read"
        sys.exit(1)

    if config_path is not None:
        config.read(config_path)

    for pathparm in ("cookie_file", "target_dir"):
        config.set("settings", pathparm, os.path.expanduser(config.get('settings', pathparm)))

    return config

def fold(text, width=80, pad=0):
    """ Wrap <text> at <width> characters.  Pad left side with <pad> spaces. """
    output = ''
    for line in text.split('\n'):
        while len(line) > width:
            pos = line[:width].rfind(' ')
            output = output + line[:pos] + '\n'
            line = " "*pad + line[pos+1:]
        output = output + line

    return output

def get_win_width():
    """ Gets the width of the tty.  Default=80 """
    try:
        stty = subprocess.Popen(['stty', 'size'], stdout=subprocess.PIPE)
    except OSError:
        return 80
    else:
        dim = stty.communicate([0])[0]
        return int(dim.split()[1])


# classes
class Slurpy(object):
    """
    Handles all output pertaining to packages returned by the AUR classes

    """

    def __init__(self, opts, args):
        self.opts = opts
        self.args = args
        self.format = Formatter(opts.colors)
        if opts.push:
            self.aur = Push(opts, args)
        else:
            self.aur = Sync(opts, args)

    def search(self):
        width = get_win_width()

        pkgs = []
        for arg in self.args:
            try:
                pkgs.extend(self.aur.search(arg))
            except AurRpcError, e:
                self.format.render("${red}error${reset}: $error",
                                   { 'error': e.value })
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
                print pkg[self.NAME]
            else:
                pkgdesc = strip_slashes(pkg[self.aur.DESCRIPTION])
                pkgdesc = fold("    %s" % pkgdesc, width, 4)

                if pkg[self.aur.OUT_OF_DATE] == '0':
                    ood_color = self.opts.colors['green']
                else:
                    ood_color = self.opts.colors['red']

                t = ("$magenta$repo$reset/$white$pkgname $ood_color$pkgver\n"
                          "$reset$pkgdesc")
                c = { 'repo': 'aur',
                      'pkgname': pkg[self.aur.NAME],
                      'pkgver': pkg[self.aur.VERSION],
                      'pkgdesc': pkgdesc,
                      'ood_color': ood_color,
                }
                self.format.render(t, c)

    def info(self):
        width = get_win_width()
        for arg in self.args:
            try:
                pkg = self.aur.info(arg)
            except AurRpcError, e:
                self.format.render("${red}error${reset}: $error",
                                   { 'error': e.value })
                sys.exit(1)

            if pkg[self.aur.OUT_OF_DATE] == '0':
                out_of_date = "No"
                ood_color = self.opts.colors['green']
            else:
                out_of_date = "Yes"
                ood_color = self.opts.colors['red']

            pkgdesc = strip_slashes(pkg[self.aur.DESCRIPTION])
            pkgdesc = fold(' '*18 + pkgdesc, width, 18)

            t = ("${reset}${bold}Repository      : $magenta$repo\n"
                 "${reset}${bold}Name            : $white$pkgname\n"
                 "${reset}${bold}Version         : $ood_color$pkgver\n"
                 "${reset}${bold}URL             : $blue$srcurl\n"
                 "${reset}${bold}AUR Page        : $blue$aururl\n"
                 "${reset}${bold}Category        : $reset$category\n"
                 "${reset}${bold}Licenses        : $reset$licenses\n"
                 "${reset}${bold}Number of Votes : $reset$votes\n"
                 "${reset}${bold}Out of Date     : $ood_color$out_of_date\n"
                 "${reset}${bold}Description     : $reset$pkgdesc\n")

            c = { 'repo': 'aur',
                  'pkgname': pkg[self.aur.NAME],
                  'pkgver': pkg[self.aur.VERSION],
                  'srcurl': strip_slashes(pkg[self.aur.URL]),
                  'aururl': "%spackages.php?ID=%s" % (self.aur.AUR_URL, pkg[self.aur.ID]),
                  'category': self.aur.CATEGORIES[int(pkg[self.aur.CATEGORY])],
                  'licenses': strip_slashes(pkg[self.aur.LICENSE]),
                  'votes': pkg[self.aur.VOTES],
                  'out_of_date': out_of_date,
                  'ood_color': ood_color,
                  'pkgdesc': pkgdesc[18:],
            }

            self.format.render(t, c)

    def download(self):
        packages = self.args[:] # don't want to modify self.args
        dledpkgs = [] # holds list of downloaded pkgs
        repodeps = [] # holds list of dependencies available in pacman repos

        error_template = "${red}error${reset}: $error"

        for package in packages:
            if package in repodeps:
                continue

            try:
                pkg, deps = self.aur.download(package, dledpkgs)
            except (AurRpcError, AurIOError) as e:
                c = { 'error': e.value }
                self.format.render(error_template, c)
                continue

            if deps is not None:
                repodeps.extend(deps)

            if pkg is not None:
                dledpkgs.append(pkg)
                if self.opts.download > 1:
                    deps = self.aur.get_depends(pkg)
                    for dep in deps:
                        if self.aur.in_sync_db(dep):
                            repodeps.append(dep)
                        else:
                            packages.append(dep)

        # remove dups
        repodeps = list(set(repodeps))
        repodeps.sort()
        dledpkgs.sort()

        self.display_result(dledpkgs, repodeps)


    def display_result(self, pkgs, deps):
        """ Print a nicely formated result of <pkgs> and <deps> """
        if pkgs:
            if len(pkgs) == 1 and not deps:
                t = "${white}${pkgname}${reset} downloaded to ${yellow}${dir}${reset}"
                c = { 'pkgname': pkgs[0],
                      'dir': os.getcwd(),
                }
                self.format.render(t, c)
            else:
                t = "Packages downloaded to ${yellow}${dir}${reset}:\n${white}"
                for pkg in pkgs:
                    t += "    %s\n" % pkg

                c = { 'dir': os.getcwd(), }
                self.format.render(t, c)
        if deps:
            if len(deps) == 1 and not pkgs:
                t = "${white}${pkgname}${reset} available in ${magenta}pacman repos"
                c = { 'pkgname': deps[0], }
                self.format.render(t, c)
            else:
                t = "${reset}Dependencies found in ${yellow}pacman repos${reset}:\n${white}"
                for pkg in deps:
                    t += "    %s\n" % pkg

                c = { 'dir': os.getcwd(), }
                self.format.render(t, c)

    def update(self):
        pkgs = self.aur.update()

        if pkgs == []:
            sys.exit(1) # mimic pacman
        
        for pkg in pkgs:
            if not self.opts.download:
                pkgname = pkg[self.aur.NAME]
                inst_ver = pkg['_inst_ver']
                
                if self.opts.quiet:
                    print pkgname
                elif self.opts.verbose >= 1:
                    aur_ver = pkg[self.aur.VERSION]
                    t = "$white$pkgname $red$inst_ver $reset-> $green$aur_ver"
                    c = { 'pkgname': pkgname,
                          'inst_ver': inst_ver,
                          'aur_ver': aur_ver,
                    }
                    self.format.render(t, c)
                else:
                    t = "$white$pkgname $red$inst_ver"
                    c = { 'pkgname': pkgname,
                          'inst_ver': inst_ver,
                    }
                    self.format.render(t, c)
        return pkgs

    def login(self):
        if self.opts.aur_user is None:
            self.opts.aur_user = raw_input('User: ')

        password = getpass('Password: ')
        if not self.aur.login(self.opts.aur_user, password):
            t = "${red}error${reset}: Bad username or password. Please try again." 
            self.format.render(t, {})
            sys.exit(1)

    def upload(self):
        for arg in self.args:
            if not os.path.isfile(arg):
                t = "${red}error${reset}: $white$arg $resetdoes not exist or is not a file"
                c = { 'arg': arg, }
                self.format.render(t, c)
                sys.exit(1)

            success = None
            try:
                pkg = self.aur.upload(arg, self.opts.category)
            except AurUploadError, e:
                t = "${red}error${reset}: $white$fname $reset$msg"
                c = { 'fname': e.fname, 
                      'msg': e.msg,
                }
                self.format.render(t, c)
                sys.exit(1)

            if pkg:
                t = "$white$pkg $reset has been uploaded"
                c = { 'pkg': pkg, }
                self.format.render(t, c)
            else:
                t = "${red}error${reset}: Unknown error"
                self.format.render(t, {})
                sys.exit(1)

class Formatter(object):
    """ Format all output using ansi color escape codes """

    def __init__(self, color_context):
        self.colors = color_context
        self.template = Template(None)

    def render(self, text, context):
        """ Renders template text, using context as the template context """
        self.template.template = text
        context.update(self.colors)
        print self.template.substitute(context)
        
    
# main processing 
def main():
    config = read_config()

    _version = ' '.join(("%prog",VERSION))
    parser = OptionParser(version=_version, conflict_handler="resolve")
    parser.add_option('-d', '--download', action='count')
    parser.add_option('-f', '--force', action='store_true')
    parser.add_option('-c', '--color', action='store_true', dest='use_color',
                            default=config.getboolean('settings', 'use_color'))
    parser.add_option('-h', '--help', action='store_true')
    parser.add_option('-i', '--info', action='store_true')
    parser.add_option('-q', '--quiet', action='store_true')
    parser.add_option('-s', '--search', action='store_true')
    parser.add_option('-t', '--save-to', dest='target_dir', action='store',
                            default=config.get('settings', 'target_dir'))
    parser.add_option('-u', '--update', action='store_true')
    parser.add_option('-v', '--verbose', action='count',
                            default=config.getint('settings', 'verbose'))
    parser.add_option('-S', '--sync', action='store_true', default=True)

    if 'pycurl' in sys.modules:
        parser.add_option('-C', '--category', action='store', default=None)
        parser.add_option('-P', '--push', action='store_true', default=False)
        parser.add_option('-U', '--user', action='store', dest='aur_user',
                            default=config.get('settings', 'aur_user'))
        parser.add_option('', '--cookie-file', action='store',
                            default=config.get('settings', 'cookie_file'))

    opts, args = parser.parse_args()

    if not getattr(opts, 'push', False):
        setattr(opts, 'push', False)

    # dict to hold ansi escape color codes
    colors = { 'reset':   '',
               'bold':    '',
               'black':   '',
               'red':     '',
               'green':   '',
               'blue':    '',
               'magenta': '',
               'yellow':  '',
               'cyan':    '',
               'white':   '',
    }

    if config.getboolean('settings', 'use_color'):
        # will load defaults from /etc/slurpyrc or from the user's config
        for c in colors.keys():
            ansi = config.get('colors', c)
            colors.update({ c: '\033[%sm' % ansi})
    setattr(opts, 'colors', colors)

    try:
        if opts.target_dir is not None and not opts.push:
            os.chdir(opts.target_dir)
    except OSError:
        t = "${red}error${reset}: $dir does not exist or is not a directory"
        print Template(t).substitute(
                { 'red': colors['red'],
                  'reset': colors['reset'],
                  'dir': opts.target_dir, 
                })
        sys.exit(1)

    opts.target_dir = os.getcwd()

    slurpy = Slurpy(opts, args)

    if 'pycurl' in sys.modules and opts.push:
        if opts.category is None:
            opts.category = "None"
        elif opts.category not in slurpy.aur.CATEGORIES:
            t = ("${red}error${reset}: Invalid category (-C, --category)\n\n"
                 "Please enter one of the following categories:\n\n"
                 "$cat\n")
            print Template(t).substitute(
                    { 'red': colors['red'],
                      'reset': colors['reset'],
                      'cat': fold(str(slurpy.aur.CATEGORIES[2:]), 80),
                    })

            sys.exit(1)

        slurpy.login()
        slurpy.upload()
    else:
        if opts.update and opts.download:
            updates = [] # holds all available updates

            t = "${bold}Downloading${reset} updates to ${yellow}${dir}${reset}"
            print Template(t).substitute(
                    { 'bold': colors['bold'],
                      'yellow': colors['yellow'],
                      'reset': colors['reset'],
                      'dir': os.getcwd(),
                    })

            for pkg in slurpy.update():
                updates.append(pkg[slurpy.aur.NAME]) 

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
