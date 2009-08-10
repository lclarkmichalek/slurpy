# Contributor: Randy Morris <randy rsontech net>
pkgname=slurpy
pkgver=1.0.3
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
md5sums=('d2444214a2c1f309c4b6018bbc5f8121')
build() {
  cd ${srcdir}
  install -D -m755 ${pkgname} ${pkgdir}/usr/bin/${pkgname}
}
