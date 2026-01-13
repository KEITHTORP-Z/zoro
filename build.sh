#!/usr/bin/env bash
set -e

echo "Installing NodeJS..."
curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
apt-get install -y nodejs

node -v
npm -v
