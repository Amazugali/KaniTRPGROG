カニドラシル ログ保管庫 — 使い方
====================================

この一式は、Fresh Meeting の簡易HTML書き出しを一覧化するロビーページです。
ログ本体は書き換えません。

配置例
------
index.html
build_lobby.py
lobby-config.json
01.html
02.html
...
29.html
img/

更新方法
--------
1. Fresh Meeting から書き出したHTMLを、このフォルダへ置きます。
   ファイル名の先頭を 01、02、03 ... のような番号にしてください。
   「02(1).html」のような名前でも先頭番号から認識します。

2. 部屋名を付ける場合は lobby-config.json を編集します。
   設定していない番号は「カニドラシルな部屋 03」のような名称になります。

3. 次のコマンドを実行します。

   Windows:
     py -3 build_lobby.py

   macOS / Linux:
     python3 build_lobby.py

   同梱の rebuild_lobby.bat / rebuild_lobby.command からでも実行できます。

4. 再生成された index.html をブラウザで開きます。

補足
----
・各ログの発言数と参加者は自動集計されます。
・同じ番号のHTMLが複数ある場合、"02.html" のような短い名前を優先します。
・人物アイコンは各ログ内の相対参照どおり img/ フォルダから読み込みます。
・検索、保存済みのみ表示、並び替え、閲覧履歴は index.html 内で動作します。
