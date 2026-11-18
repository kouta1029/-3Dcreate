# Codex Cloud 環境構築キット ― Blender制作環境（エスカレーター第1回用）

## 前提
- ChatGPT の **Plus 以上のプラン**（Codex Cloud は Free / Go には含まれない）
- GitHub リポジトリ（新規でOK。例: `escalator-blender`）。参照資料 `research_escalator/` フォルダを丸ごとリポジトリに入れておく
- リソース目安: Plus は 2vCPU / 8GiB RAM / 8GiB ディスク、Pro 以上は 4vCPU / 16GiB / 32GiB。Blender 本体で約1GB使うので、Plus だとディスクはややタイト

## 手順（現行の Codex Cloud、2026年9月の刷新後）
1. chatgpt.com/codex（またはデスクトップアプリ）を開き、**Work in → Cloud** を選ぶ
2. **Select environment → Create environment** で GitHub を接続し、上記リポジトリを選ぶ
3. **Get started** で Codex とセットアップの対話が始まる。ここで下の「Install script」をそのまま渡す（Codex が試して記録してくれる）
4. 環境変数・シークレットは今回は不要（Manage は触らなくてよい）
5. インターネットアクセス: セットアップ段階はネット接続可（Blender のダウンロードに必要）。エージェント作業段階はデフォルトのオフラインでよい（資料はリポジトリ内にあるため）
6. 内容を確認して **Publish**。これで環境の公開完了
7. 新規タスクを作成し、依頼文（`codex_prompt_escalator_blender.md`）を貼って開始する
8. 成果物はタスクの diff / PR として返る。レンダーした MP4 はリポジトリにコミットさせる指示が依頼文に入っているので、そこから受け取る

※ 画面が旧方式（Settings → Environments に Setup script / Maintenance script の入力欄がある形）の場合は、同じスクリプトを Setup script 欄に貼ればよい。コンテナは最大12時間キャッシュされる。

## Install script（Blender 導入用、そのまま貼る）
```bash
#!/bin/bash
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
```
（Blender のバージョンは、その時点の最新 LTS に読み替えてよい）

## 最初のタスクで必ず確認させること（GPU が無い環境のため）
Codex Cloud のコンテナには GPU がない。Cycles（CPU）は必ず動くが、Eevee はソフトウェア描画で動くかどうかが環境依存。
→ 最初のタスクでは本制作に入る前に:
1. `blender -b` で空シーンが起動すること
2. Eevee で1フレーム描けるか、ダメなら Cycles（CPU・低サンプル）で1フレーム描けるか
3. 全体ループ5秒のテストレンダーの実測時間
の3点を報告させる（依頼文にも記載済み）。Eevee が使えない場合は、解像度を落とす／シーンを短いループ単位にする／最終レンダーだけ自分の PC で行う、のどれかに切り替える。

## リポジトリに入れる AGENTS.md（任意・推奨）
```markdown
# このリポジトリの作業ルール
- 制作仕様は MECHANISM_EP1_ESCALATOR_DESIGN.md、参照資料は research_escalator/（索引 REFERENCE_INDEX.md）に従う
- モデリングの形状・配置は参照資料が正解。推測で作った箇所は PR の説明に「推測箇所」として明記する
- 成果物（.blend、生成スクリプト、シーン別 MP4、代表フレーム画像）はリポジトリにコミットする
- レンダーはまず低解像度でテストし、フレーム画像で確認してから本番解像度に上げる
```
