# aur - Defines the AUR base class used by Push and Sync
#
# Randy Morris <randy@rsontech.net>
#
# CREATED:  2009-12-15 09:32
# MODIFIED: 2009-12-15 09:34

class AUR():
    
    """ Main AUR class

    Just defines constants used by subclasses
    """

    AUR_URL = "http://aur.archlinux.org"
    INFO_URL = "http://aur.archlinux.org/rpc.php?type=info&arg="
    SEARCH_URL = "http://aur.archlinux.org/rpc.php?type=search&arg="
    SUBMIT_URL = "http://aur.archlinux.org/pkgsubmit.php"
