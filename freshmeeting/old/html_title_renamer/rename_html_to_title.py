#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
HTML Title Renamer
------------------
フォルダ内の .html / .htm ファイルから <title> を取得し、
その title をファイル名にしてリネームします。

外部ライブラリ不要。
"""

from __future__ import annotations

import argparse
import html
import os
import re
import sys
from html.parser import HTMLParser
from pathlib import Path


INVALID_WIN_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
MULTISPACE = re.compile(r"\s+")
META_CHARSET = re.compile(
    br'<meta[^>]+charset\s*=\s*["\']?\s*([A-Za-z0-9._-]+)',
    re.IGNORECASE,
)
META_HTTP_EQUIV = re.compile(
    br'<meta[^>]+content\s*=\s*["\'][^"\']*charset\s*=\s*([A-Za-z0-9._-]+)',
    re.IGNORECASE,
)

WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


class TitleParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_title = False
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() == "title":
            self.in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.parts.append(data)

    @property
    def title(self) -> str:
        return "".join(self.parts).strip()


def detect_encoding(data: bytes) -> str:
    # BOM
    if data.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    if data.startswith(b"\xff\xfe"):
        return "utf-16-le"
    if data.startswith(b"\xfe\xff"):
        return "utf-16-be"

    # HTML内のcharset指定
    head = data[:8192]
    for pattern in (META_CHARSET, META_HTTP_EQUIV):
        m = pattern.search(head)
        if m:
            enc = m.group(1).decode("ascii", errors="ignore").strip()
            if enc:
                return enc

    # Fresh Meeting系を含む日本語HTML向けの実用的フォールバック
    for enc in ("utf-8", "cp932", "shift_jis", "euc_jp"):
        try:
            data.decode(enc)
            return enc
        except UnicodeDecodeError:
            pass

    return "utf-8"


def extract_title(path: Path) -> str:
    try:
        data = path.read_bytes()
    except OSError:
        return ""

    encoding = detect_encoding(data)
    try:
        text = data.decode(encoding, errors="replace")
    except LookupError:
        text = data.decode("utf-8", errors="replace")

    parser = TitleParser()
    try:
        parser.feed(text)
    except Exception:
        return ""

    return html.unescape(parser.title).strip()


def sanitize_filename(title: str, max_length: int = 180) -> str:
    # 改行やタブを通常スペースへまとめる
    name = MULTISPACE.sub(" ", title).strip()

    # Windowsで使えない文字を全角系に近い安全な記号へ
    replacements = {
        "<": "＜",
        ">": "＞",
        ":": "：",
        '"': "”",
        "/": "／",
        "\\": "＼",
        "|": "｜",
        "?": "？",
        "*": "＊",
    }
    for src, dst in replacements.items():
        name = name.replace(src, dst)

    # 制御文字など残りを除去
    name = INVALID_WIN_CHARS.sub("", name)

    # Windowsでは末尾の空白・ドット不可
    name = name.rstrip(" .")

    if not name:
        name = "untitled"

    # 予約語回避
    if name.upper() in WINDOWS_RESERVED:
        name = f"_{name}"

    # 長すぎるファイル名を抑制
    if len(name) > max_length:
        name = name[:max_length].rstrip(" .")

    return name


def unique_destination(src: Path, base_name: str) -> Path:
    ext = src.suffix.lower()
    candidate = src.with_name(base_name + ext)

    # 自分自身ならそのまま
    try:
        if candidate.resolve() == src.resolve():
            return candidate
    except OSError:
        if candidate == src:
            return candidate

    if not candidate.exists():
        return candidate

    n = 2
    while True:
        candidate = src.with_name(f"{base_name} ({n}){ext}")
        if not candidate.exists():
            return candidate
        n += 1


def iter_html_files(folder: Path, recursive: bool):
    patterns = ("*.html", "*.htm")
    seen: set[Path] = set()

    for pattern in patterns:
        iterator = folder.rglob(pattern) if recursive else folder.glob(pattern)
        for path in iterator:
            if path.is_file() and path not in seen:
                seen.add(path)
                yield path


def rename_files(folder: Path, recursive: bool, dry_run: bool) -> int:
    files = sorted(iter_html_files(folder, recursive), key=lambda p: str(p).lower())

    if not files:
        print("HTMLファイルが見つかりませんでした。")
        return 0

    renamed = 0
    skipped = 0

    print(f"対象フォルダ: {folder}")
    print(f"対象HTML: {len(files)} 件")
    print()

    for src in files:
        title = extract_title(src)

        if not title:
            print(f"[SKIP] <title> なし: {src.relative_to(folder)}")
            skipped += 1
            continue

        safe_name = sanitize_filename(title)
        dst = unique_destination(src, safe_name)

        if dst == src:
            print(f"[OK]   変更不要: {src.relative_to(folder)}")
            continue

        rel_src = src.relative_to(folder)
        rel_dst = dst.relative_to(folder)

        if dry_run:
            print(f"[TEST] {rel_src}")
            print(f"       -> {rel_dst}")
        else:
            try:
                src.rename(dst)
                print(f"[REN]  {rel_src}")
                print(f"       -> {rel_dst}")
                renamed += 1
            except OSError as exc:
                print(f"[ERR]  {rel_src}: {exc}")
                skipped += 1

    print()
    if dry_run:
        print("テストモードのため、実際のファイル名は変更していません。")
    else:
        print(f"完了: {renamed} 件リネーム / {skipped} 件スキップ")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="HTMLの<title>をファイル名にしてリネームします。"
    )
    parser.add_argument(
        "folder",
        nargs="?",
        default=".",
        help="対象フォルダ。省略時は現在のフォルダ。",
    )
    parser.add_argument(
        "-r", "--recursive",
        action="store_true",
        help="サブフォルダも再帰的に処理する。",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="変更内容だけ表示し、実際にはリネームしない。",
    )

    args = parser.parse_args()
    folder = Path(args.folder).expanduser().resolve()

    if not folder.exists():
        print(f"フォルダが存在しません: {folder}")
        return 1
    if not folder.is_dir():
        print(f"フォルダではありません: {folder}")
        return 1

    return rename_files(folder, args.recursive, args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
