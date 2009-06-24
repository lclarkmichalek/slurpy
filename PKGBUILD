# Contributor: Randy Morris <randy rsontech net>
pkgname=slurpy-svn
pkgver=10
pkgrel=1
pkgdesc="An AUR search/download/update helper in Python"
arch=('i686' 'x86_64')
url="http://rsontech.net/projects/"
license=('GPLv3')
depends=('python')
conflicts=('slurpy')
provides=('slurpy')
optdepends=('python-cjson: faster processing for large result sets')
makedepends=('subversion')
source=()
md5sums=()
_svntrunk=http://svn.rsontech.net/slurpy/trunk
_svnmod=slurpy
build() {
  cd ${srcdir}
  if [ -d ${_svnmod}/.svn ]; then
    (cd ${_svnmod} && svn up -r ${pkgver})
  else
    svn co ${_svntrunk} --config-dir ./ -r ${pkgver} ${_svnmod}
  fi
  msg "SVN checkout done or server timeout"
  msg "Starting make..."
  install -D -m755 ${_svnmod}/${_svnmod} ${pkgdir}/usr/bin/${_svnmod}
}
