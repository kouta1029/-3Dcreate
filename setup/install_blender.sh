#!/bin/bash
# Codex Cloud 環境構築用 Install script（Blender 4.2 LTS 導入）
set -e
apt-get update
apt-get install -y --no-install-recommends \
  xz-utils curl ffmpeg \
  libgl1 libegl1 libglx-mesa0 libxrender1 libxfixes3 libxi6 libxkbcommon0 libsm6 libice6
cd /opt
curl -L -o blender.tar.xz https://download.blender.org/release/Blender4.2/blender-4.2.0-linux-x64.tar.xz
tar -xf blender.tar.xz
ln -sf /opt/blender-4.2.0-linux-x64/blender /usr/local/bin/blender
blender --version
