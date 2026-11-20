#!/usr/bin/env bash
# D01 参照画像の取得スクリプト（エスカレーター制作の fetch_references.sh と同じ方式）
# 画像そのものはリポジトリにコミットせず、このスクリプトで出典URLから取得する。
# 注意: クラウド環境のIPがホスト側に弾かれて 403 になることがある（実績あり）。
# 1ファイルの失敗で全体を止めず、方法を変えて再試行し、最後に失敗一覧を表示する。
set -uo pipefail
cd "$(dirname "$0")"

UA='Mozilla/5.0'
ACC='Accept: image/png,image/jpeg,image/gif,image/webp,image/*;q=0.5'
FAILED=""

try_fetch() {
  local out="$1" url="$2"
  # 1回目: ブラウザ相当のヘッダ
  curl -fsSL --connect-timeout 10 --max-time 120 -A "$UA" -H "$ACC" -o "$out" "$url" 2>/dev/null && return 0
  # 2回目: Referer を付けて再試行
  curl -fsSL --connect-timeout 10 --max-time 120 -A "$UA" -H "$ACC" -H 'Referer: https://www.google.com/' -o "$out" "$url" 2>/dev/null && return 0
  # 3回目: 既定UAで再試行
  curl -fsSL --connect-timeout 10 --max-time 120 -o "$out" "$url" 2>/dev/null && return 0
  return 1
}

fetch() {
  local out="$1" url="$2"
  if [ -s "$out" ]; then
    echo "skip (already exists): $out"
    return 0
  fi
  echo "fetch: $out"
  if try_fetch "$out" "$url"; then
    echo "ok: $out"
  else
    rm -f "$out"
    echo "FAILED: $out  ($url)"
    FAILED="$FAILED $out"
  fi
}

fetch ref_microwave_interior.jpg 'https://www.njuskalo.hr/image-xlsize/mikrovalne-pecnice/mikrovalna-samsung-slika-227050484.jpg'
fetch ref_microwave_exterior.jpg 'https://p1.akcdn.net/productdescription/838637976_48888_rd.jpg'
fetch ref_foil_crumpled.jpg 'https://alu-recycling.ch/wp-content/themes/alurecycling/assets/img/igora-alu-toppografy.jpg'
fetch ref_foil_flat.jpg 'https://m.media-amazon.com/images/I/41psqYzjDaL._AC_SL3840_.jpg'
fetch ref_sweet_potato.jpg 'https://sudachirecipes.com/wp-content/uploads/2022/10/satsumaimo.jpg'

echo "---- result ----"
ls -la ref_*.jpg 2>/dev/null || true
if [ -n "$FAILED" ]; then
  echo "取得できなかったファイル:$FAILED"
  echo "取得できた資料の範囲で作業を進め、レポートに不足分を明記すること。"
fi
exit 0
