Fresh Meeting カニドラシル・ロビー生成一式
===============================================

前提ディレクトリ
----------------

freshmeeting/
├─ index.html                  ← build_lobby.py が生成
├─ build_lobby.py
├─ lobby-config.json
├─ spoiler-rooms.json
├─ rebuild_lobby.bat
├─ rebuild_lobby.command
├─ img/
│  └─ *_icon.jpg
├─ lobby/
│  └─ 01.html ～ 29.html
└─ spoiler/
   └─ 各通過者専用部屋.html


使い方
------
Windows:
  rebuild_lobby.bat をダブルクリック

macOS:
  rebuild_lobby.command を実行
  （初回に実行権限が必要なら chmod +x rebuild_lobby.command）

コマンドライン:
  python build_lobby.py
  または
  py -3 build_lobby.py


常設29部屋
----------
lobby/ に 01.html ～ 29.html を置いてください。
途中までしか揃っていなくても何度でもビルドできます。

index.html からのリンクは lobby/01.html などになります。


人物アイコンの自動補正
----------------------
lobby/*.html をビルド前に走査し、次の2種類を自動補正します。

1. Fresh Meeting 上の外部アイコンURL
2. lobby/ へ移動したことで参照先がずれた img/xxx_icon.jpg

例:
  src="img/sm_icon.jpg"
      ↓
  src="../img/sm_icon.jpg"

既に ../img/... になっているものは触らないため、再実行しても安全です。


Fresh Meeting デフォルトアイコン置換表
---------------------------------------
images/5f/365732_32.jpg       -> ../img/rb_icon.jpg
images/63/dfdd1d_32.jpg       -> ../img/kr_icon.jpg
images/75/ed22e5_32.jpg       -> ../img/dk_icon.jpg
images/23/555e5f_32.jpg       -> ../img/tt_icon.jpg
images/89/fd7de9_32.jpg       -> ../img/kg_icon.jpg
images/2d/cb384b_32.jpg.jpg   -> ../img/hm_icon.jpg
images/85/507424_32.jpg       -> ../img/sv_icon.jpg
images/f4/95a2b7_32.jpg       -> ../img/ch_icon.jpg
images/b6/1e30cb_32.jpg       -> ../img/wl_icon.jpg
images/1a/b9cf91_32.jpg       -> ../img/sm_icon.jpg
images/65/4cdf6e_32.jpg       -> ../img/mm_icon.jpg


通過者専用部屋
--------------
spoiler/ に各HTMLを置き、spoiler-rooms.json に登録します。

例:
[
  {
    "id": "S01",
    "title": "【シナリオ名】通過者専用部屋",
    "file": "シナリオ名.html",
    "description": "シナリオ通過者による感想・考察・GMの裏話を含む専用部屋。"
  }
]

file に単なるファイル名を書いた場合は spoiler/ 内として扱います。

ロビーでは、
  ・参加していたミーティングルーム
  ・シナリオ通過者専用部屋
をタブで切り替えます。

通過者専用部屋を開く直前にはネタバレ警告を表示します。


既存環境へ入れる場合
--------------------
既に編集済みの lobby-config.json / spoiler-rooms.json がある場合は、
それらを上書きしないでください。

最低限、今回差し替える必要があるのは build_lobby.py です。
rebuild_lobby.bat / .command は便利用なので、既存のものを使い続けても構いません。
