#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== A.Y.U.S. Linux Paketleme Aracı (.deb ve AppImage) ==="

# Python ve sanal ortam kontrolü
PYTHON_BIN=""
if [ -f ".venv/bin/python" ]; then
    PYTHON_BIN=".venv/bin/python"
elif command -v uv >/dev/null 2>&1; then
    echo "uv bulundu, sanal ortam hazırlanıyor..."
    uv venv --python 3.13 .venv 2>/dev/null || uv venv .venv
    PYTHON_BIN=".venv/bin/python"
    uv pip install -r requirements-build.txt
elif command -v python3 >/dev/null 2>&1; then
    echo "python3 ile sanal ortam oluşturuluyor..."
    python3 -m venv .venv
    PYTHON_BIN=".venv/bin/python"
    "$PYTHON_BIN" -m pip install --upgrade pip
    "$PYTHON_BIN" -m pip install -r requirements-build.txt
else
    echo "Hata: Python 3 bulunamadı." >&2
    exit 1
fi

# PyInstaller kurulu mu kontrol et
if ! "$PYTHON_BIN" -m PyInstaller --version >/dev/null 2>&1; then
    echo "Paketleme bağımlılıkları yükleniyor..."
    if command -v uv >/dev/null 2>&1; then
        uv pip install -r requirements-build.txt
    else
        "$PYTHON_BIN" -m pip install -r requirements-build.txt
    fi
fi

# Versiyonu pyproject.toml üzerinden oku
VERSION=$(grep -m1 '^version' pyproject.toml | cut -d'"' -f2 || echo "0.3.0")
ARCH="x86_64"
DEB_ARCH="amd64"
APP_NAME="ayus"
DISPLAY_NAME="A.Y.U.S"

echo "Sürüm: ${VERSION}"
echo "Mimari: ${ARCH} (deb: ${DEB_ARCH})"

# 1. PyInstaller ile ikili (binary) derleme
echo ""
echo "[1/3] PyInstaller ikili dosyası oluşturuluyor..."
"$PYTHON_BIN" -m PyInstaller --clean --noconfirm ayus.spec

if [ ! -f "dist/A.Y.U.S" ]; then
    echo "Hata: dist/A.Y.U.S oluşturulamadı!" >&2
    exit 1
fi

# 2. Debian (.deb) Paketi Oluşturma
echo ""
echo "[2/3] .deb paketi oluşturuluyor..."
DEB_ROOT="build/deb/${APP_NAME}_${VERSION}_${DEB_ARCH}"
rm -rf "$DEB_ROOT"
mkdir -p "${DEB_ROOT}/DEBIAN" \
         "${DEB_ROOT}/usr/bin" \
         "${DEB_ROOT}/usr/lib/${APP_NAME}" \
         "${DEB_ROOT}/usr/share/applications" \
         "${DEB_ROOT}/usr/share/icons/hicolor/256x256/apps" \
         "${DEB_ROOT}/usr/share/pixmaps" \
         "${DEB_ROOT}/usr/share/metainfo" \
         "${DEB_ROOT}/usr/share/doc/${APP_NAME}"

cp dist/A.Y.U.S "${DEB_ROOT}/usr/lib/${APP_NAME}/A.Y.U.S"
chmod 755 "${DEB_ROOT}/usr/lib/${APP_NAME}/A.Y.U.S"

cat << 'INNER_EOF' > "${DEB_ROOT}/usr/bin/ayus"
#!/bin/sh
exec /usr/lib/ayus/A.Y.U.S "$@"
INNER_EOF
chmod 755 "${DEB_ROOT}/usr/bin/ayus"

DESKTOP_ID="io.github.beratbesli.AYUS.desktop"
cp "assets/${DESKTOP_ID}" "${DEB_ROOT}/usr/share/applications/${DESKTOP_ID}"
chmod 644 "${DEB_ROOT}/usr/share/applications/${DESKTOP_ID}"

if [ -f "assets/ayus.appdata.xml" ]; then
    cp assets/ayus.appdata.xml "${DEB_ROOT}/usr/share/metainfo/io.github.beratbesli.AYUS.appdata.xml"
    chmod 644 "${DEB_ROOT}/usr/share/metainfo/io.github.beratbesli.AYUS.appdata.xml"
fi

cp assets/ayus.png "${DEB_ROOT}/usr/share/icons/hicolor/256x256/apps/ayus.png"
cp assets/ayus.png "${DEB_ROOT}/usr/share/pixmaps/ayus.png"
chmod 644 "${DEB_ROOT}/usr/share/icons/hicolor/256x256/apps/ayus.png"
chmod 644 "${DEB_ROOT}/usr/share/pixmaps/ayus.png"

cp README.md "${DEB_ROOT}/usr/share/doc/${APP_NAME}/README.md"
cp LICENSE "${DEB_ROOT}/usr/share/doc/${APP_NAME}/copyright"
chmod 644 "${DEB_ROOT}/usr/share/doc/${APP_NAME}/"*

INSTALLED_SIZE=$(du -s "${DEB_ROOT}/usr" | awk '{print $1}')

cat << INNER_EOF > "${DEB_ROOT}/DEBIAN/control"
Package: ${APP_NAME}
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: ${DEB_ARCH}
Maintainer: Berat Besli <beratbesli26@gmail.com>
Installed-Size: ${INSTALLED_SIZE}
Description: A.Y.U.S. - Afet Rota Planlayici
 A.Y.U.S., goruntu tabanli afet acil durum rota planlama prototipidir.
 Goruntu kenar yogunlugundan goreli bir risk haritasi cikarir
 ve gecilebilir grid hucreleri uzerinden rota onerir.
INNER_EOF

dpkg-deb --build --root-owner-group "$DEB_ROOT" "dist/${APP_NAME}_${VERSION}_${DEB_ARCH}.deb"
echo "Hazır: dist/${APP_NAME}_${VERSION}_${DEB_ARCH}.deb"

# 3. AppImage Paketi Oluşturma
echo ""
echo "[3/3] AppImage paketi oluşturuluyor..."
APPDIR="build/AppDir"
rm -rf "$APPDIR"
mkdir -p "${APPDIR}/usr/bin" \
         "${APPDIR}/usr/share/applications" \
         "${APPDIR}/usr/share/metainfo" \
         "${APPDIR}/usr/share/icons/hicolor/256x256/apps"

cp dist/A.Y.U.S "${APPDIR}/usr/bin/A.Y.U.S"
chmod 755 "${APPDIR}/usr/bin/A.Y.U.S"
ln -sf A.Y.U.S "${APPDIR}/usr/bin/ayus"

cp "assets/${DESKTOP_ID}" "${APPDIR}/${DESKTOP_ID}"
cp "assets/${DESKTOP_ID}" "${APPDIR}/usr/share/applications/${DESKTOP_ID}"

if [ -f "assets/ayus.appdata.xml" ]; then
    cp assets/ayus.appdata.xml "${APPDIR}/usr/share/metainfo/io.github.beratbesli.AYUS.appdata.xml"
fi

cp assets/ayus.png "${APPDIR}/ayus.png"
cp assets/ayus.png "${APPDIR}/.DirIcon"
cp assets/ayus.png "${APPDIR}/usr/share/icons/hicolor/256x256/apps/ayus.png"

cat << 'INNER_EOF' > "${APPDIR}/AppRun"
#!/bin/sh
HERE="$(dirname "$(readlink -f "${0}")")"
export PATH="${HERE}/usr/bin:${PATH}"
exec "${HERE}/usr/bin/A.Y.U.S" "$@"
INNER_EOF
chmod 755 "${APPDIR}/AppRun"

APPIMAGETOOL_VERSION="1.9.1"
APPIMAGETOOL_SHA256="ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0"
APPIMAGETOOL="${APPIMAGETOOL:-${SCRIPT_DIR}/.cache/appimagetool-${APPIMAGETOOL_VERSION}-x86_64.AppImage}"
if [ ! -f "$APPIMAGETOOL" ]; then
    echo "appimagetool ${APPIMAGETOOL_VERSION} indiriliyor..."
    mkdir -p "$(dirname "$APPIMAGETOOL")"
    curl --proto '=https' --tlsv1.2 -fsSL \
        -o "$APPIMAGETOOL" \
        "https://github.com/AppImage/appimagetool/releases/download/${APPIMAGETOOL_VERSION}/appimagetool-x86_64.AppImage"
fi
echo "${APPIMAGETOOL_SHA256}  ${APPIMAGETOOL}" | sha256sum --check --status || {
    echo "Hata: appimagetool SHA-256 doğrulaması başarısız." >&2
    exit 1
}
chmod +x "$APPIMAGETOOL"

APPIMAGE_OUT="dist/${DISPLAY_NAME}-${VERSION}-${ARCH}.AppImage"
ARCH="${ARCH}" "$APPIMAGETOOL" "$APPDIR" "$APPIMAGE_OUT"
chmod +x "$APPIMAGE_OUT"
echo "Hazır: ${APPIMAGE_OUT}"

echo ""
echo "=== Paketleme Başarıyla Tamamlandı! ==="
echo "Oluşturulan paketler:"
ls -lh "dist/${APP_NAME}_${VERSION}_${DEB_ARCH}.deb" "${APPIMAGE_OUT}"
