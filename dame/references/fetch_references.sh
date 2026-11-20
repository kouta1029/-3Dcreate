#!/usr/bin/env bash
# D01 参照画像の取得スクリプト（エスカレーター制作の fetch_references.sh と同じ方式）
# 画像そのものはリポジトリにコミットせず、このスクリプトで出典URLから取得する。
set -euo pipefail
cd "$(dirname "$0")"

UA='Mozilla/5.0'
ACC='Accept: image/png,image/jpeg,image/gif,image/webp,image/*;q=0.5'

fetch() {
  local out="$1" url="$2"
  if [ -s "$out" ]; then
    echo "skip (already exists): $out"
    return 0
  fi
  echo "fetch: $out"
  curl -fsSL --connect-timeout 10 --max-time 120 -A "$UA" -H "$ACC" -o "$out" "$url"
}

fetch ref_microwave_interior.jpg 'https://www.njuskalo.hr/image-xlsize/mikrovalne-pecnice/mikrovalna-samsung-slika-227050484.jpg'
fetch ref_microwave_exterior.jpg 'https://p1.akcdn.net/productdescription/838637976_48888_rd.jpg'
fetch ref_foil_crumpled.jpg 'https://alu-recycling.ch/wp-content/themes/alurecycling/assets/img/igora-alu-toppografy.jpg'
fetch ref_foil_flat.jpg 'https://m.media-amazon.com/images/I/41psqYzjDaL._AC_SL3840_.jpg'
fetch ref_sweet_potato.jpg 'https://sudachirecipes.com/wp-content/uploads/2022/10/satsumaimo.jpg'

echo "done:"
ls -la ref_*.jpg
