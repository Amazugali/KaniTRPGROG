HTML title → ファイル名 リネームツール
======================================

機能
----
フォルダ内の .html / .htm ファイルから

  <title>ここにある文字</title>

を読み取り、その文字列をファイル名にします。

例:

  202107oneday.html

HTML内:
  <title>One Day 通過者専用部屋</title>

実行後:
  One Day 通過者専用部屋.html


Windowsで使えない文字
----------------------
title に以下の文字が含まれていても自動補正します。

  :  -> ：
  /  -> ／
  \  -> ＼
  ?  -> ？
  *  -> ＊
  <  -> ＜
  >  -> ＞
  |  -> ｜
  "  -> ”

同名ファイルが既に存在する場合は、

  タイトル.html
  タイトル (2).html
  タイトル (3).html

のように重複を回避します。


使い方
------
■ 同じフォルダだけ処理

  rename_html_to_title.bat

を対象HTMLと同じフォルダに置いてダブルクリックします。

フォルダを .bat にドラッグ＆ドロップしても構いません。


■ spoiler/yggdrasil など下位フォルダも全部処理

  rename_html_to_title_recursive.bat

を使います。


■ 最初に結果だけ確認

  rename_html_to_title_確認のみ.bat

を使うと、実際には変更せず
「このファイルをこの名前にする」という予定だけ表示します。


Pythonから直接使う場合
----------------------
現在のフォルダ:
  python rename_html_to_title.py

フォルダ指定:
  python rename_html_to_title.py "D:\path\to\folder"

サブフォルダも含む:
  python rename_html_to_title.py "D:\path\to\folder" --recursive

確認のみ:
  python rename_html_to_title.py "D:\path\to\folder" --recursive --dry-run


補足
----
・外部ライブラリは使いません。
・UTF-8 / CP932 / Shift_JIS / EUC-JP をある程度自動判定します。
・<title> が存在しないHTMLは変更しません。
・HTML本文は一切書き換えません。ファイル名だけ変更します。
