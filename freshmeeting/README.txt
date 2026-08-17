spoiler-rooms.json 自動追記対応版
==================================

対象フォルダ
------------
freshmeeting/spoiler/yggdrasil/
freshmeeting/spoiler/coc/

rebuild_lobby.bat を実行すると build_lobby.py が上記2フォルダを確認し、
*.html のうち spoiler-rooms.json に未登録のものだけを自動追記します。

新規登録例
----------
{
  "id": "202107oneday",
  "title": "202107oneday",
  "file": "yggdrasil/202107oneday.html",
  "description": ""
}

title はHTML内に <title> があればその文字列を使います。
<title> が無ければHTMLのファイル名を使います。

既存設定について
----------------
・既存の title / description / id は上書きしません。
・同じ file がすでに登録済みなら何もしません。
・同じ file の重複登録がある場合は最初の1件を残して整理します。
・JSONに登録されているがHTMLが見つからない項目は削除しません。
・yggdrasil と coc 以外の spoiler サブフォルダはJSON自動追記の対象外です。
  （アイコン補正自体は従来どおり spoiler/ 以下を再帰処理します。）

今回いただいた spoiler-rooms.json について
-----------------------------------------
元ファイルはオブジェクト間のカンマが抜けておりJSONとして無効でした。
また yggdrasil/202008typhoon.html が重複登録されていました。

同梱の spoiler-rooms.json は
・正しいJSONへ修正
・202008typhoon の重複を1件に整理
したものです。

初回はこの修正版で既存 spoiler-rooms.json を置き換えてください。
