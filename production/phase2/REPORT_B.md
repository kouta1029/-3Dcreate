# フェーズ2 タスクB 制作・QC レポート

Phase 1 の `escalator_phase1.blend` を使用。踏段、車輪、踏段チェーン、案内レールの寸法と組み付け位置は Phase 1 と同じ。Blender 4.3.2、Eevee 16 サンプル、24 fps、黒背景。PNG 連番から FFmpeg で H.264 MP4 に変換した。映像は無音・無文字。

| シーン | 納品 | フレーム | 尺 | 解像度 |
| --- | --- | ---: | ---: | --- |
| A2 踏段単体 | [MP4](../renders/a2_step_solo.mp4) · [PNG](../renders/a2_step_solo.png) · [Blender](a2_step_solo.blend) | 96 | 4.000 秒 | 1920 × 1080 |
| A3 軌道クローズ | [MP4](../renders/a3_tracks.mp4) · [PNG](../renders/a3_tracks.png) · [Blender](a3_tracks.blend) | 120 | 5.000 秒 | 1280 × 720 |

## 実測

計測区間は Eevee の描画呼び出しから各フレームの PNG 保存まで。初回のシェーダー準備を含む。本番の動画エンコードは別に計測した。CPU のソフトウェア描画を使用し、A2 と A3 は一部の時間帯で並行して描画した。

| シーン | 平均 秒/フレーム | 中央値 | 最短–最長 | 描画と PNG 保存の合計 | MP4 エンコード |
| --- | ---: | ---: | ---: | ---: | ---: |
| A2 | 37.02 | 36.38 | 26.74–84.62 | 59分13.88秒 （3553.88秒） | 15.59 秒 |
| A3 | 48.10 | 36.80 | 30.31–99.63 | 96分12.31秒 （5772.31秒） | 6.31 秒 |

低解像度の静止画で構図を確認した後に本番を開始した。この環境の Blender 4.3.2 では Eevee のヘッドレス描画を確認した。Cycles は CPU、デノイズ無効の最小シーンで起動を確認し、本番には Eevee を使用した。全体ループ5秒の既存ベンチマークは [Phase 1 レポート](../REPORT.md) の 960 × 540、120 フレーム、30分21.01秒（平均15.16秒/フレーム）を参照した。A3 の 1920 × 1080 の試写は2フレーム目が126.87秒で、120フレーム換算では約4時間14分となった。試写後に遮蔽物の透過を調整し、共通仕様の2時間基準に従って 1280 × 720 で本番を描画した。

## 推測箇所・参照からの逸脱

- A2 は [JP3704363B2 第2～4図](../../research_escalator/JP3704363B2_escalator_patent.pdf) を踏段と前後輪・踏段チェーンの関係の参照とした。Phase 1 の一踏段とその三角リンク、前後の短い踏段チェーンを抜き出した。切り出し範囲、回転軸、照明は説明用の演出。溝、ライザー、黄線および軸・車輪の模式寸法は [Phase 1 の推測](../REPORT.md#推測箇所) を継承した。
- A3 は [JP3704363B2 第3・4・9図](../../research_escalator/JP3704363B2_escalator_patent.pdf) と [JP6585230B1 図1](../../research_escalator/JP6585230B1_toshiba_escalator_patent.pdf) を参照。手前の欄干と同一メッシュの奥の欄干・スカートガード・インレット部をカットアウェイとして非表示にした。手摺りベルトの上側を表示し、機構と重なる下側の走行部を透過させた。案内レールに重なる踏段チェーンのプレートと手摺り駆動部も半透明にした。案内レールのシアン（前輪用）と緑（後輪用）の発光色は説明用の演出。トラスの透過と緩和曲線、最大約2 mmの踏面とライザーの重なりは Phase 1 から継承した。
- A3 は Phase 1 と同じ6ピッチ／5秒の周期を使用した。モデル上の速度は 0.4896 m/s（定格値 0.5 m/s）。緩和区間では踏面を水平に保ったまま、同時刻の隣接踏段の高低差が傾斜区間の約204 mmから水平部のほぼ0 mmへ詰まることを軌道計算と映像で確認した。

## ループと出力確認

- A2 は1フレームあたり3.75°。未収録の97フレーム目が1フレーム目と同じ姿勢に戻ることを Blender の変換行列で確認した。代表静止画は1フレーム目。
- A3 は未収録の121フレーム目で、踏段・前後輪・三角リンクが6踏段分、踏段チェーンが36リンク分ずれた同一配置に戻ることを Blender の変換行列で確認した。後輪はホイールの60°回転対称性を考慮した。代表静止画は1フレーム目。
- FFprobe で両 MP4 の H.264、解像度、24 fps、フレーム数、尺を確認。FFmpeg で全フレームをデコードした。各シーンで最終フレームと先頭フレームの画素差が、収録内の隣接フレームの画素差の範囲内に収まることを確認した。

## 再生成

リポジトリのルートで実行する。

```sh
blender -b production/escalator_phase1.blend --python-exit-code 1 \
  --python production/phase2/build_task_b.py -- a2_step_solo
blender -b production/escalator_phase1.blend --python-exit-code 1 \
  --python production/phase2/build_task_b.py -- a3_tracks
blender -b -t 2 production/phase2/a2_step_solo.blend --python-exit-code 1 \
  --python production/phase2/render_task_b.py -- work/task-b/a2 --still 1
blender -b -t 2 production/phase2/a3_tracks.blend --python-exit-code 1 \
  --python production/phase2/render_task_b.py -- work/task-b/a3 --still 1 --height 720
```
