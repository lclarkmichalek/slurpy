# push.py - defines the Push class, to upload source packages to the AUR
#
# Randy Morris <randy@rsontech.net>
#
#
# CREATED:  
# MODIFIED: 2010-01-06 13:52

import os
import sys
from getpass import getpass
from cStringIO import StringIO

import pycurl
from aur import AUR

class Push(AUR):
    
    """ Handles all uploads to the AUR """

    def __init__(self, opts, args):

        self.opts = opts
        self.args = args
        self.buffer = StringIO()

        self.curl = pycurl.Curl()
        self.curl.setopt(pycurl.HTTPHEADER, ["Expect:"])
        self.curl.setopt(pycurl.COOKIEJAR, self.opts.cookie_file)
        self.curl.setopt(pycurl.WRITEFUNCTION, self.buffer.write)
        self.curl.setopt(pycurl.FOLLOWLOCATION, 1)

    def __del__(self):
        """ Clean up curl and cookie file """
        self.curl.close()
        if os.path.exists(self.opts.cookie_file):
            os.unlink(self.opts.cookie_file)

    def login(self, user, passwd):
        """ Log in to the AUR web interface with self.opts.user,
        prompt for password.
        """
        data = [
            ('user', user),
            ('passwd', passwd)]

        self.curl.setopt(pycurl.HTTPPOST, data)
        self.curl.setopt(pycurl.URL, self.AUR_URL)
        self.curl.perform()
        
        # Bad username or password
        if self.buffer.getvalue().find("Bad username or password") != -1:
            return False
        return True

    def upload(self, fname, category):
        """ Upload files in self.args to the aur """

        data = [
            ('pkgsubmit', '1'),
            ('category', '%s' % self.CATEGORIES.index(category)),
            ('pfile', (pycurl.FORM_FILE, fname))]

        self.curl.setopt(pycurl.HTTPPOST, data)
        self.curl.setopt(pycurl.URL, self.SUBMIT_URL)

        self.buffer.truncate(0)
        try:
            self.curl.perform()
        except:
            raise AurUploadError(fname, "Something is wrong with the "
                                  "selected file.\nIf it is a .tar.gz, "
                                  "try rebuilding it.")

        if self.buffer.getvalue().find("not allowed to overwrite") != -1:
            raise AurUploadError(fname, "You do not own this package and "
                                  "can not overwrite these files.")
        elif self.buffer.getvalue().find("Unknown file format") != -1:
            raise AurUploadError(fname, "Incorrect file format. Upload "
                                  "must conform to AUR packaging "
                                  "guidelines.")

        idx = self.buffer.getvalue().find("<span class='f2'>")
        if idx != -1:
            pkg = self.buffer.getvalue()[17+idx:]

            idx = pkg.find("</span>")
            if idx != -1:
                pkg = pkg[:idx]
                
                if pkg is not None:
                    return pkg
        return False


# exceptions

class AurUploadError(Exception):
    """To be thrown when pycurl can not upload the file"""

    def __init__(self, fname, msg):
        self.fname = fname
        self.msg = msg
