#!/usr/bin/env bash
# Builds AVL from the MIT sources and installs the executable in PREFIX/bin
#
# usage: ci/build-avl.sh [VERSION] [PREFIX]
#
# Needs gfortran, make and the X11 development files (Ubuntu: gfortran
# libx11-dev). Set PLTLIB to override the X11 link flags, e.g. on macOS with
# Homebrew: PLTLIB="-L$(brew --prefix)/lib -lX11"
set -euo pipefail

version="${1:-3.52}"
prefix="${2:-$HOME/.local}"
url="https://web.mit.edu/drela/Public/web/avl/avl${version}.tgz"

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

curl -sSfL "$url" | tar xz -C "$work"
src="$(find "$work" -mindepth 1 -maxdepth 1 -type d | head -n 1)"

# double precision build, as recommended for AVL 3.4x and later
make -C "$src/plotlib" gfortranDP
make -C "$src/eispack" -f Makefile.gfortran
if [ -n "${PLTLIB:-}" ]; then
    make -C "$src/bin" -f Makefile.gfortranDP avl PLTLIB="$PLTLIB"
else
    make -C "$src/bin" -f Makefile.gfortranDP avl
fi

mkdir -p "$prefix/bin"
cp "$src/bin/avl" "$prefix/bin/avl"
echo "AVL $version installed in $prefix/bin/avl"
