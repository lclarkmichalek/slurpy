# Contributor: Randy Morris <randy rsontech net>
pkgname=slurpy
pkgver=2.0.0
pkgrel=1
pkgdesc="An AUR search/download/update helper in Python"
arch=('i686' 'x86_64')
url="http://rsontech.net/projects/"
license=('None')
depends=('python')
optdepends=('python-cjson: faster processing for large result sets')
conflicts=('slurpy-git')
provides=('slurpy-git')
source=(http://github.com/rson/${pkgname}/raw/v${pkgver}/${pkgname})
md5sums=('fe9cea02587e89cf05cd4b3df69c33d9')
build() {
  cd ${srcdir}
  install -D -m755 ${pkgname} ${pkgdir}/usr/bin/${pkgname}
}
