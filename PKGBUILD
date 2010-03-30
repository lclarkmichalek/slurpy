# Contributor: Randy Morris <randy rsontech net>
pkgname=slurpy
pkgver=2.2.0
pkgrel=1
pkgdesc="An AUR search/download/update helper in Python"
arch=('i686' 'x86_64')
url="http://github.com/rson/slurpy/"
license=('None')
depends=('python')
optdepends=('python-cjson: faster processing for large result sets'
            'python-pycurl: upload packages to the AUR from the command line')
conflicts=('slurpy-git')
provides=('slurpy-git')
source=(http://github.com/rson/${pkgname}/raw/v${pkgver}/${pkgname})
md5sums=('7333086d559a0a681f1bc9a13209fff1')
build() {
  cd ${srcdir}
  install -D -m755 ${pkgname} ${pkgdir}/usr/bin/${pkgname}
}
