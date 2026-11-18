#!/bin/bash
# 参照資料PDFの取得スクリプト
# GitHub 連携の都合で PDF 本体はリポジトリに含まれていないため、公開元から取得する。
# Codex Cloud では「セットアップ（Install script）段階」はネット接続できるので、
# Install script の末尾にこのファイルの内容を足すか、このスクリプトを実行すること。
# 作業段階でネットが使える設定の場合も、そのまま実行できる。
set -e
cd "$(dirname "$0")"

curl -L -o JP6585230B1_toshiba_escalator_patent.pdf \
  "https://patentimages.storage.googleapis.com/4e/c6/53/889c0e781a9b5d/JP6585230B1.pdf"
curl -L -o JP3704363B2_escalator_patent.pdf \
  "https://patentimages.storage.googleapis.com/5e/e0/76/ad7b96f8594843/JP3704363B2.pdf"
curl -L -o EP3974370A1_kone_escalator_patent.pdf \
  "https://patentimages.storage.googleapis.com/db/3e/fb/02e08ee2428ffa/EP3974370A1.pdf"
curl -L -o mitsubishi_escalator_catalog_section.pdf \
  "https://www.mitsubishielectric.co.jp/elevator/catalog/pdf/c-c01-4-c6759.pdf"

ls -la *.pdf
echo "取得完了。図の抽出画像 figures/toshiba_fig_sideview.png は JP6585230B1 の7ページ目から作れる（pdftoppm 等）。"
