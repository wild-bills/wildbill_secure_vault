#!/usr/bin/env bash

set -euo pipefail

# Wrapper for Cloudflare builds that run with deploy/ as the working directory.
cd ..
bash ./build_pages.sh