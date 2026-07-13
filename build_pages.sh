#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

DIST_DIR="dist"

rm -rf "$DIST_DIR"
mkdir -p "$DIST_DIR"
mkdir -p "$DIST_DIR/static"

cp index.html "$DIST_DIR/"
cp category.html "$DIST_DIR/"
cp products.json "$DIST_DIR/"
cp ads.txt "$DIST_DIR/"
cp sitemap.xml "$DIST_DIR/"
cp _redirects "$DIST_DIR/"

cp templates/contact.html "$DIST_DIR/contact.html"
cp templates/privacy.html "$DIST_DIR/privacy.html"
cp templates/terms.html "$DIST_DIR/terms.html"
cp templates/refund.html "$DIST_DIR/refund.html"
cp templates/pricing.html "$DIST_DIR/pricing.html"

if [[ -d static/previews ]]; then
    cp -R static/previews "$DIST_DIR/static/"
fi

if [[ -d static/js ]]; then
    cp -R static/js "$DIST_DIR/static/"
fi

echo "Built Cloudflare Pages output in $DIST_DIR"