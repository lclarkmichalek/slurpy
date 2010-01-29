# aur - Defines the AUR base class used by Push and Sync
#
# Randy Morris <randy@rsontech.net>
#
# CREATED:  2009-12-15 09:32
# MODIFIED: 2010-01-29 13:11

class AUR(object):
    
    """ Main AUR class

    Just defines constants used by subclasses
    """

    AUR_URL = "http://aur.archlinux.org/"
    INFO_URL = AUR_URL + "rpc.php?type=info&arg="
    SEARCH_URL = AUR_URL + "rpc.php?type=search&arg="
    SUBMIT_URL = AUR_URL + "pkgsubmit.php"
    
    CATEGORIES = [None, "None", "daemons", "devel", "editors", "emulators",
                  "games", "gnome", "i18n", "kde", "lib", "modules",
                  "multimedia", "network", "office", "science", "system",
                  "x11", "xfce", "kernels"]

    PACMAN_CACHE = "/var/lib/pacman/local"
    PACMAN_CONF = "/etc/pacman.conf"
    PACMAN_REPOS = ['core', 'extra', 'community']
    PACMAN_SYNC = "/var/lib/pacman/sync/"

