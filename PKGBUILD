# Contributor: Randy Morris <randy rsontech net>
pkgname=slurpy
pkgver=2.1.5
pkgrel=1
pkgdesc="An AUR search/download/update helper in Python"
arch=('i686' 'x86_64')
url="http://rsontech.net/projects/"
license=('None')
depends=('python')
optdepends=('python-cjson: faster processing for large result sets'
            'python-pycurl: upload packages to the AUR from the command line')
conflicts=('slurpy-git')
provides=('slurpy-git')
source=(http://github.com/rson/${pkgname}/raw/v${pkgver}/${pkgname})
md5sums=('af724471ebc828aabee08927d77391c9')
build() {
  cd ${srcdir}
  install -D -m755 ${pkgname} ${pkgdir}/usr/bin/${pkgname}
}
