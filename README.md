# -3Dcreate

身近な物の仕組みを解説する動画シリーズの、3Dアニメーション制作リポジトリ。
映像制作は Codex Cloud（Blender）で行い、台本・設計・QC は別途管理する。

## 第1回: エスカレーター
- `MECHANISM_EP1_ESCALATOR_DESIGN.md` ― 設計シート兼・制作仕様書（構成、シーン表、技術仕様）
- `codex_prompt_escalator_blender.md` ― Codex への依頼文
- `research_escalator/` ― 参照資料パッケージ（索引: `REFERENCE_INDEX.md`）。モデリングは想像でなく、この資料が正解
- `codex_cloud_setup_kit.md` ― Codex Cloud の環境構築手順
- `setup/install_blender.sh` ― 環境構築用 Install script

## 参照資料のバイナリ（別途アップロードが必要）
`research_escalator/` には以下の PDF・画像も入る想定（索引に記載済み）:
- `JP6585230B1_toshiba_escalator_patent.pdf`（東芝特許・全体側面図）
- `JP3704363B2_escalator_patent.pdf`（踏段・軌道・反転部）
- `EP3974370A1_kone_escalator_patent.pdf`（KONE特許）
- `mitsubishi_escalator_catalog_section.pdf`（三菱カタログ）
- `figures/toshiba_fig_sideview.png`（図1の抽出画像）

## 成果物の置き場（Codex 向け）
- `.blend` ファイルと生成 Python スクリプト: `production/`
- シーン別 MP4 と代表フレーム画像: `production/renders/`
- 納品レポート（推測箇所の明記を含む）: `production/REPORT.md`
