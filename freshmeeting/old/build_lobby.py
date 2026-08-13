#!/usr/bin/env python3
"""Fresh Meeting の書き出しHTMLから、静的なロビーページを生成する。

使い方:
  1. freshmeeting/ 直下にこのファイルと設定ファイルを置く
  2. 01.html ... 29.html は freshmeeting/lobby/ に置く
  3. 人物アイコンは freshmeeting/img/ に置く
  4. python build_lobby.py
  5. freshmeeting/index.html を開く

ビルド時に lobby/*.html の人物アイコン参照だけを保存用パスへ正規化する。
"""

from __future__ import annotations

import html
import json
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
LOBBY_DIR = ROOT / "lobby"
SPOILER_DIR = ROOT / "spoiler"
IMG_DIR = ROOT / "img"
CONFIG_PATH = ROOT / "lobby-config.json"
SPOILER_CONFIG_PATH = ROOT / "spoiler-rooms.json"
OUTPUT_PATH = ROOT / "index.html"

# Fresh Meeting 側のデフォルトアイコンURL -> 保存用ファイル名。
# URLは http/https と www の有無を吸収して判定する。
FRESHMEETING_ICON_PATHS: dict[str, str] = {
    "images/5f/365732_32.jpg": "rb_icon.jpg",
    "images/63/dfdd1d_32.jpg": "kr_icon.jpg",
    "images/75/ed22e5_32.jpg": "dk_icon.jpg",
    "images/23/555e5f_32.jpg": "tt_icon.jpg",
    "images/89/fd7de9_32.jpg": "kg_icon.jpg",
    "images/2d/cb384b_32.jpg.jpg": "hm_icon.jpg",
    "images/85/507424_32.jpg": "sv_icon.jpg",
    "images/f4/95a2b7_32.jpg": "ch_icon.jpg",
    "images/b6/1e30cb_32.jpg": "wl_icon.jpg",
    "images/1a/b9cf91_32.jpg": "sm_icon.jpg",
    "images/65/4cdf6e_32.jpg": "mm_icon.jpg",
}
REMOTE_FM_ICON_RE = re.compile(
    r'''(?P<prefix>\bsrc\s*=\s*(?P<quote>["']))(?:https?:)?//(?:www\.)?freshmeeting\.com/(?P<path>images/[^"']+)(?P=quote)''',
    re.IGNORECASE,
)
LOCAL_IMG_RE = re.compile(
    r'''(?P<prefix>\bsrc\s*=\s*(?P<quote>["']))(?:\./)?img/(?P<name>[^"']+)(?P=quote)''',
    re.IGNORECASE,
)

ROOM_FILE_RE = re.compile(r"^(\d{1,3})(?:\D|$)")
MESSAGE_RE = re.compile(r"<p\s+class=[\"']fmparagraph[\"']", re.IGNORECASE)
SPEAKER_RE = re.compile(r"<strong>(.*?)</strong>\s*:", re.IGNORECASE | re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")

DEFAULT_CONFIG: dict[str, Any] = {
    "archive_title": "カニドラシル ログ保管庫",
    "brand_name": "Kani Meeting",
    "subtitle": "Fresh Meeting 静的ログアーカイブ",
    "notice": "Fresh Meeting のサービス終了に伴い保存した、閲覧専用の静的HTMLログです。",
    "total_rooms": 29,
    "rooms": {},
}


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return DEFAULT_CONFIG.copy()
    try:
        loaded = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"設定ファイルを読み込めません: {exc}") from exc
    merged = DEFAULT_CONFIG.copy()
    merged.update(loaded)
    if not isinstance(merged.get("rooms"), dict):
        merged["rooms"] = {}
    return merged


def load_spoiler_rooms() -> list[dict[str, Any]]:
    """通過者専用部屋の設定を読み込む。ファイルがなければ空一覧。"""
    if not SPOILER_CONFIG_PATH.exists():
        return []
    try:
        loaded = json.loads(SPOILER_CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"通過者専用部屋の設定を読み込めません: {exc}") from exc

    if isinstance(loaded, dict):
        loaded = loaded.get("rooms", [])
    if not isinstance(loaded, list):
        raise SystemExit("spoiler-rooms.json は配列、または rooms 配列を持つオブジェクトにしてください。")

    result: list[dict[str, Any]] = []
    for item in loaded:
        if isinstance(item, dict):
            result.append(item)
    return result


def clean_text(raw: str) -> str:
    raw = TAG_RE.sub("", raw)
    return html.unescape(raw).strip()


def inspect_log(path: Path, href: str | None = None) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    speakers = [clean_text(value) for value in SPEAKER_RE.findall(text)]
    speakers = [value for value in speakers if value]
    counts = Counter(speakers)
    return {
        "filename": path.name,
        "href": href if href is not None else path.name,
        "messages": len(MESSAGE_RE.findall(text)),
        "speaker_count": len(counts),
        "speakers": [name for name, _ in counts.most_common()],
        "top_speakers": [name for name, _ in counts.most_common(5)],
        "size_bytes": path.stat().st_size,
    }


def normalize_lobby_icons(path: Path) -> tuple[int, int]:
    """人物アイコン参照を ../img/ へ正規化する。

    戻り値は (Fresh Meeting 外部URLの置換数, img/ 相対パスの置換数)。
    すでに ../img/ になっている参照は変更しないため、再実行しても安全。
    """
    original = path.read_text(encoding="utf-8", errors="replace")
    remote_count = 0

    def replace_remote(match: re.Match[str]) -> str:
        nonlocal remote_count
        icon_name = FRESHMEETING_ICON_PATHS.get(match.group("path").lower())
        if not icon_name:
            return match.group(0)
        remote_count += 1
        return f'{match.group("prefix")}../img/{icon_name}{match.group("quote")}'

    updated = REMOTE_FM_ICON_RE.sub(replace_remote, original)
    updated, local_count = LOCAL_IMG_RE.subn(
        lambda m: f'{m.group("prefix")}../img/{m.group("name")}{m.group("quote")}',
        updated,
    )

    if updated != original:
        path.write_text(updated, encoding="utf-8", newline="\n")

    return remote_count, local_count


def normalize_lobby_files() -> tuple[int, int, int]:
    if not LOBBY_DIR.exists():
        return 0, 0, 0
    changed_files = 0
    remote_total = 0
    local_total = 0
    for path in sorted(LOBBY_DIR.glob("*.html")):
        remote_count, local_count = normalize_lobby_icons(path)
        if remote_count or local_count:
            changed_files += 1
            remote_total += remote_count
            local_total += local_count
    return changed_files, remote_total, local_total


def detect_logs() -> dict[int, dict[str, Any]]:
    candidates: dict[int, list[Path]] = {}
    if not LOBBY_DIR.exists():
        return {}
    for path in LOBBY_DIR.glob("*.html"):
        match = ROOM_FILE_RE.match(path.stem)
        if not match:
            continue
        number = int(match.group(1))
        candidates.setdefault(number, []).append(path)

    result: dict[int, dict[str, Any]] = {}
    for number, paths in candidates.items():
        exact_names = {f"{number:02d}.html", f"{number}.html"}
        paths.sort(key=lambda p: (0 if p.name in exact_names else 1, len(p.name), p.name.lower()))
        chosen = paths[0]
        result[number] = inspect_log(chosen, href=f"lobby/{chosen.name}")
    return result


def human_size(size: int) -> str:
    if size >= 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    if size >= 1024:
        return f"{size / 1024:.0f} KB"
    return f"{size} B"


def attr(value: Any) -> str:
    return html.escape(str(value), quote=True)


def text(value: Any) -> str:
    return html.escape(str(value))


def make_room_rows(config: dict[str, Any], logs: dict[int, dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    total_rooms = max(int(config.get("total_rooms", 29)), max(logs.keys(), default=0))
    room_config: dict[str, Any] = config.get("rooms", {})
    rows: list[str] = []
    data: list[dict[str, Any]] = []

    for number in range(1, total_rooms + 1):
        key = f"{number:02d}"
        custom = room_config.get(key, {}) if isinstance(room_config.get(key, {}), dict) else {}
        title_value = custom.get("title") or f"カニドラシルな部屋 {key}"
        description = custom.get("description", "")
        log = logs.get(number)
        saved = log is not None

        if saved:
            href = log["href"]
            messages = int(log["messages"])
            speaker_count = int(log["speaker_count"])
            speakers = list(log["speakers"])
            top_speakers = list(log["top_speakers"])
            file_size = human_size(int(log["size_bytes"]))
        else:
            href = ""
            messages = 0
            speaker_count = 0
            speakers = []
            top_speakers = []
            file_size = ""

        search_text = " ".join([key, title_value, description, *speakers]).lower()
        member_tags = "".join(
            f'<span class="member-tag">{text(name)}</span>' for name in top_speakers[:4]
        )
        if speaker_count > 4:
            member_tags += f'<span class="member-more">+{speaker_count - 4}</span>'
        if not member_tags:
            member_tags = '<span class="muted-dash">—</span>'

        if saved:
            title_markup = (
                f'<a class="room-title" href="{attr(href)}" '
                f'data-open-room="{key}" data-room-title="{attr(title_value)}">{text(title_value)}</a>'
            )
            action_markup = (
                f'<a class="open-button" href="{attr(href)}" '
                f'data-open-room="{key}" data-room-title="{attr(title_value)}">読む<span aria-hidden="true">›</span></a>'
            )
            status_markup = '<span class="status-badge saved">保存済み</span><span class="visited-label" hidden>閲覧済み</span>'
            meta_markup = f'<span>{messages:,} 発言</span><span>{speaker_count} 人</span><span>{text(file_size)}</span>'
            row_class = "room-row is-saved"
        else:
            title_markup = f'<span class="room-title disabled">{text(title_value)}</span>'
            action_markup = '<span class="open-button disabled" aria-disabled="true">準備中</span>'
            status_markup = '<span class="status-badge pending">準備中</span>'
            meta_markup = '<span>HTML未配置</span>'
            row_class = "room-row is-pending"

        desc_markup = f'<p>{text(description)}</p>' if description else ""
        rows.append(
            f'''<article class="{row_class}" data-room="{key}" data-saved="{'1' if saved else '0'}" data-search="{attr(search_text)}">
  <div class="room-number" aria-label="部屋番号 {key}"><span>{key}</span></div>
  <div class="room-summary">
    {title_markup}
    {desc_markup}
    <div class="room-meta compact">{meta_markup}</div>
  </div>
  <div class="message-count">{f'<strong>{messages:,}</strong><span>発言</span>' if saved else '<span class="muted-dash">—</span>'}</div>
  <div class="member-list" aria-label="参加者">{member_tags}</div>
  <div class="room-state">{status_markup}{action_markup}</div>
</article>'''
        )

        data.append(
            {
                "number": key,
                "title": title_value,
                "description": description,
                "saved": saved,
                "href": href,
                "messages": messages,
                "speaker_count": speaker_count,
                "speakers": speakers,
                "file_size": file_size,
            }
        )

    return "\n".join(rows), data


def make_spoiler_cards(entries: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    cards: list[str] = []
    data: list[dict[str, Any]] = []

    for index, entry in enumerate(entries, start=1):
        room_id = str(entry.get("id") or f"S{index:02d}")
        title_value = str(entry.get("title") or entry.get("scenario") or f"通過者専用部屋 {index:02d}")
        description = str(entry.get("description") or "シナリオ通過者向けの感想・考察・裏話用の専用部屋。")
        file_value = str(entry.get("file") or entry.get("href") or "").strip()
        normalized_value = file_value.replace("\\", "/")
        if normalized_value.startswith("spoiler/"):
            file_href = normalized_value
            path = ROOT / normalized_value
        else:
            file_href = f"spoiler/{normalized_value}" if normalized_value else ""
            path = SPOILER_DIR / normalized_value if normalized_value else None
        saved = bool(path and path.is_file())

        messages = 0
        speaker_count = 0
        speakers: list[str] = []
        top_speakers: list[str] = []
        file_size = ""
        if saved and path is not None:
            inspected = inspect_log(path)
            messages = int(inspected["messages"])
            speaker_count = int(inspected["speaker_count"])
            speakers = list(inspected["speakers"])
            top_speakers = list(inspected["top_speakers"])
            file_size = human_size(int(inspected["size_bytes"]))

        member_tags = "".join(
            f'<span class="member-tag">{text(name)}</span>' for name in top_speakers[:5]
        )
        if speaker_count > 5:
            member_tags += f'<span class="member-more">+{speaker_count - 5}</span>'
        if not member_tags:
            member_tags = '<span class="muted-dash">—</span>'

        if saved:
            action = (
                f'<a class="spoiler-open-button" href="{attr(file_href)}" '
                f'data-spoiler-room="{attr(room_id)}" data-spoiler-title="{attr(title_value)}">'
                '警告を確認して入室<span aria-hidden="true">›</span></a>'
            )
            status = '<span class="spoiler-status saved">保存済み</span>'
            meta = f'<span>{messages:,} 発言</span><span>{speaker_count} 人</span><span>{text(file_size)}</span>'
            card_class = "spoiler-card is-saved"
        else:
            action = '<span class="spoiler-open-button disabled" aria-disabled="true">HTML未配置</span>'
            status = '<span class="spoiler-status pending">準備中</span>'
            meta = '<span>HTML未配置</span>'
            card_class = "spoiler-card is-pending"

        search_text = " ".join([room_id, title_value, description, *speakers]).lower()
        cards.append(
            f'''<article class="{card_class}" data-spoiler-id="{attr(room_id)}" data-search="{attr(search_text)}">
  <div class="spoiler-card-head">
    <span class="spoiler-symbol" aria-hidden="true">!</span>
    <div class="spoiler-title-block">
      <span class="spoiler-kicker">SCENARIO CLEARED MEMBERS ONLY</span>
      <h3>{text(title_value)}</h3>
    </div>
    {status}
  </div>
  <p class="spoiler-description">{text(description)}</p>
  <div class="spoiler-meta">{meta}</div>
  <div class="spoiler-members" aria-label="主な参加者">{member_tags}</div>
  <div class="spoiler-action">{action}</div>
</article>'''
        )
        data.append({
            "id": room_id,
            "title": title_value,
            "description": description,
            "file": file_href,
            "saved": saved,
            "messages": messages,
            "speaker_count": speaker_count,
            "speakers": speakers,
            "file_size": file_size,
        })

    return "\n".join(cards), data


TEMPLATE = r'''<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<meta name="theme-color" content="#55ad30">
<title>@@PAGE_TITLE@@</title>
<style>
:root {
  --green: #55ad30;
  --green-dark: #32861b;
  --green-deep: #246b13;
  --green-soft: #d8ffb5;
  --green-pale: #f3ffe9;
  --green-line: #9dd66f;
  --yellow: #fff8d7;
  --yellow-line: #e9d68a;
  --blue: #0759bf;
  --blue-hover: #003e8e;
  --ink: #202520;
  --muted: #687168;
  --line: #d8ddd6;
  --line-strong: #c5cbc2;
  --paper: #ffffff;
  --wash: #f4f6f3;
  --shadow: 0 1px 3px rgba(29, 45, 25, .12);
  --radius: 7px;
}

[hidden] { display: none !important; }
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0;
  color: var(--ink);
  background: linear-gradient(#fff 0, #fff 300px, var(--wash) 100%);
  font-family: -apple-system, BlinkMacSystemFont, "Yu Gothic UI", "Yu Gothic", Meiryo, sans-serif;
  font-size: 14px;
  line-height: 1.6;
}
a { color: var(--blue); text-decoration: underline; text-underline-offset: 2px; }
a:hover { color: var(--blue-hover); }
button, input { font: inherit; }

.site-header {
  min-height: 64px;
  background:
    radial-gradient(circle at 14% -110%, rgba(255,255,255,.98) 0 155px, transparent 156px),
    linear-gradient(#fff, #f1f1f1);
  border-bottom: 1px solid #c9c9c9;
  box-shadow: 0 1px 4px rgba(0,0,0,.10);
}
.header-inner {
  width: min(1360px, calc(100% - 28px));
  min-height: 64px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
}
.brand {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  color: var(--green);
  text-decoration: none;
  white-space: nowrap;
}
.brand:hover { color: var(--green-dark); }
.brand-mark {
  position: relative;
  width: 34px;
  height: 29px;
  flex: 0 0 auto;
}
.brand-mark::before,
.brand-mark::after {
  content: "";
  position: absolute;
  border: 2px solid currentColor;
  background: #fff;
  border-radius: 7px;
}
.brand-mark::before { width: 23px; height: 15px; left: 0; top: 6px; }
.brand-mark::after { width: 17px; height: 11px; right: 0; top: 0; background: var(--yellow); }
.brand-dots {
  position: absolute;
  left: 6px;
  top: 12px;
  width: 3px;
  height: 3px;
  border-radius: 50%;
  background: currentColor;
  box-shadow: 6px 0 currentColor, 12px 0 currentColor;
  z-index: 2;
}
.brand-copy { display: flex; align-items: baseline; gap: 8px; }
.brand-name { font-size: clamp(23px, 3vw, 31px); font-weight: 800; letter-spacing: -.05em; line-height: 1; }
.brand-badge {
  padding: 2px 7px;
  border: 1px solid var(--green-line);
  border-radius: 999px;
  background: var(--green-pale);
  color: var(--green-deep);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: .12em;
}
.header-nav { display: flex; align-items: center; gap: 16px; font-size: 13px; }
.header-nav a { display: inline-flex; align-items: center; gap: 5px; }
.header-nav .nav-dot { width: 7px; height: 7px; border: 1px solid var(--green); background: var(--green-soft); }

.notice-bar {
  border-bottom: 1px solid var(--yellow-line);
  background: var(--yellow);
  color: #6a5312;
}
.notice-inner {
  width: min(1360px, calc(100% - 28px));
  margin: 0 auto;
  padding: 7px 6px;
  font-weight: 650;
}
.notice-inner strong { margin-right: 7px; }
.breadcrumb {
  width: min(1360px, calc(100% - 28px));
  margin: 0 auto;
  padding: 8px 2px;
  color: #6c746b;
  font-size: 12px;
}
.breadcrumb a { margin-right: 6px; }

.page-shell {
  width: min(1360px, calc(100% - 28px));
  margin: 8px auto 48px;
}
.hero {
  position: relative;
  overflow: hidden;
  display: grid;
  grid-template-columns: 1fr auto;
  align-items: center;
  gap: 22px;
  min-height: 142px;
  padding: 22px 26px;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background:
    linear-gradient(90deg, rgba(243,255,233,.96), rgba(255,255,255,.96) 62%),
    repeating-linear-gradient(135deg, rgba(85,173,48,.05) 0 7px, transparent 7px 15px);
  box-shadow: var(--shadow);
}
.hero::after {
  content: "";
  position: absolute;
  width: 260px;
  height: 260px;
  right: -92px;
  top: -125px;
  border: 32px solid rgba(85,173,48,.09);
  border-radius: 50%;
}
.hero-copy { position: relative; z-index: 1; }
.eyebrow { margin: 0 0 2px; color: var(--green-deep); font-size: 12px; font-weight: 800; letter-spacing: .08em; }
.hero h1 { margin: 0; font-size: clamp(25px, 4vw, 38px); letter-spacing: -.04em; line-height: 1.25; }
.hero-subtitle { margin: 5px 0 0; color: var(--muted); font-size: 15px; }
.hero-actions { position: relative; z-index: 1; display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 9px; }
.primary-button,
.secondary-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 40px;
  padding: 7px 15px;
  border-radius: 5px;
  font-weight: 750;
  text-decoration: none;
  white-space: nowrap;
}
.primary-button { border: 1px solid var(--green-dark); background: linear-gradient(#6dca43, #4fa92a); color: #fff; text-shadow: 0 1px rgba(0,0,0,.25); }
.primary-button:hover { color: #fff; background: linear-gradient(#5fbd37, #438f24); }
.secondary-button { border: 1px solid var(--line-strong); background: linear-gradient(#fff, #f2f3f1); color: #364036; }
.secondary-button:hover { color: #172317; background: #fff; }

.content-grid {
  display: grid;
  grid-template-columns: 238px minmax(0, 1fr);
  gap: 10px;
  margin-top: 10px;
}
.sidebar { display: flex; flex-direction: column; gap: 10px; }
.panel {
  overflow: hidden;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--paper);
  box-shadow: var(--shadow);
}
.panel-heading {
  min-height: 35px;
  padding: 6px 10px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  border-bottom: 1px solid var(--green-line);
  background: linear-gradient(#e2ffc7, #c9fb9f);
}
.panel-heading h2,
.panel-heading h3 { margin: 0; font-size: 14px; line-height: 1.35; }
.panel-heading .small-count { color: #4c6e3e; font-size: 11px; font-weight: 650; }
.panel-body { padding: 12px; }

.stats-list { display: grid; grid-template-columns: 1fr 1fr; gap: 7px; }
.stat {
  padding: 8px;
  border: 1px solid #dfe7da;
  background: #fbfef9;
  text-align: center;
}
.stat strong { display: block; color: var(--green-deep); font-size: 20px; line-height: 1.15; }
.stat span { color: var(--muted); font-size: 11px; }
.side-note { margin: 10px 0 0; color: var(--muted); font-size: 11px; }
.last-read-empty { margin: 0; color: var(--muted); }
.last-read-link { display: block; font-weight: 700; }
.last-read-meta { display: block; margin-top: 4px; color: var(--muted); font-size: 11px; }
.clear-history {
  margin-top: 8px;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--blue);
  text-decoration: underline;
  cursor: pointer;
  font-size: 11px;
}
.archive-notes { margin: 0; padding-left: 1.4em; }
.archive-notes li + li { margin-top: 4px; }

.main-panel { min-width: 0; }
.archive-tabs {
  display: flex;
  align-items: stretch;
  gap: 0;
  border-bottom: 1px solid var(--green-line);
  background: linear-gradient(#eefee1, #d9fbc0);
}
.archive-tab {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  min-height: 42px;
  padding: 8px 15px;
  border: 0;
  border-right: 1px solid #b8dc98;
  background: transparent;
  color: #4b6840;
  font: inherit;
  font-size: 13px;
  font-weight: 750;
  text-align: left;
  cursor: pointer;
}
.archive-tab:hover { background: rgba(255,255,255,.48); color: var(--green-deep); }
.archive-tab[aria-selected="true"] {
  z-index: 1;
  margin-bottom: -1px;
  border-bottom: 1px solid #fff;
  background: #fff;
  color: var(--green-deep);
}
.archive-tab[aria-selected="true"]::before {
  content: "";
  position: absolute;
  left: 0;
  right: 0;
  top: 0;
  height: 3px;
  background: var(--green);
}
.archive-tab.warning-tab { color: #81531a; }
.archive-tab.warning-tab[aria-selected="true"] { color: #7d450b; }
.archive-tab.warning-tab[aria-selected="true"]::before { background: #d98927; }
.archive-tab-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 24px;
  min-height: 18px;
  padding: 1px 6px;
  border: 1px solid #b9d79f;
  border-radius: 10px;
  background: rgba(255,255,255,.7);
  color: #58744b;
  font-size: 10px;
  line-height: 1;
}
.warning-tab .archive-tab-count { border-color: #dfc17c; color: #81531a; }
.archive-tab-panel { min-width: 0; }
.archive-tab-panel[hidden] { display: none !important; }
.archive-tab-meta {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  min-height: 29px;
  padding: 5px 10px;
  border-bottom: 1px solid var(--line);
  background: #fafbf9;
  color: var(--muted);
  font-size: 11px;
}
.toolbar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px 12px;
  padding: 9px 10px;
  border-bottom: 1px solid var(--line);
  background: #fafbf9;
}
.search-box {
  position: relative;
  flex: 1 1 320px;
  max-width: 520px;
}
.search-box::before {
  content: "";
  position: absolute;
  left: 11px;
  top: 50%;
  width: 9px;
  height: 9px;
  border: 2px solid var(--green);
  border-radius: 50%;
  transform: translateY(-60%);
}
.search-box::after {
  content: "";
  position: absolute;
  left: 21px;
  top: 55%;
  width: 7px;
  height: 2px;
  background: var(--green);
  transform: rotate(45deg);
  transform-origin: left center;
}
.search-box input {
  width: 100%;
  min-height: 34px;
  padding: 5px 12px 5px 34px;
  border: 1px solid #bfc8bc;
  border-radius: 4px;
  background: #fff;
  outline: none;
}
.search-box input:focus { border-color: var(--green); box-shadow: 0 0 0 3px rgba(85,173,48,.14); }
.check-control { display: inline-flex; align-items: center; gap: 6px; white-space: nowrap; cursor: pointer; }
.check-control input { accent-color: var(--green); }
.sort-button {
  min-height: 32px;
  padding: 4px 10px;
  border: 1px solid #bfc8bc;
  border-radius: 4px;
  background: linear-gradient(#fff, #f0f2ef);
  color: #3d473b;
  cursor: pointer;
}
.sort-button:hover { background: #fff; }
.result-count { margin-left: auto; color: var(--muted); font-size: 12px; }

.room-table-head,
.room-row {
  display: grid;
  grid-template-columns: 68px minmax(250px, 1fr) 90px minmax(210px, .72fr) 150px;
  align-items: center;
}
.room-table-head {
  min-height: 36px;
  padding: 0 10px;
  border-bottom: 1px solid var(--line);
  background: linear-gradient(#f7f7f7, #e9ebe8);
  color: #727972;
  font-size: 11px;
  font-weight: 700;
}
.room-table-head span:first-child { text-align: center; }
.room-table-head span:nth-child(3) { text-align: center; }
.room-table-head span:last-child { text-align: right; padding-right: 8px; }
.room-list { min-height: 180px; }
.room-row {
  min-height: 82px;
  padding: 9px 10px;
  border-bottom: 1px solid var(--line);
  background: #fff;
  transition: background-color .12s ease, box-shadow .12s ease;
}
.room-row:last-child { border-bottom: 0; }
.room-row:nth-child(even) { background: #fcfdfb; }
.room-row.is-saved:hover { position: relative; z-index: 1; background: #f7fff1; box-shadow: inset 4px 0 var(--green); }
.room-row.is-pending { color: #8a9189; background: #fafafa; }
.room-row.is-hidden { display: none; }
.room-row.is-visited .room-number span::after {
  content: "✓";
  position: absolute;
  right: -5px;
  top: -5px;
  width: 16px;
  height: 16px;
  display: grid;
  place-items: center;
  border: 2px solid #fff;
  border-radius: 50%;
  background: var(--green);
  color: #fff;
  font-size: 10px;
  font-weight: 800;
}
.room-number { text-align: center; }
.room-number span {
  position: relative;
  display: inline-grid;
  place-items: center;
  width: 42px;
  height: 42px;
  border: 1px solid var(--green-line);
  border-radius: 4px;
  background: linear-gradient(#efffe4, #d9ffbd);
  color: var(--green-deep);
  font-size: 16px;
  font-weight: 850;
}
.is-pending .room-number span { border-color: #d6dad4; background: #f2f3f1; color: #929891; }
.room-summary { min-width: 0; padding-right: 12px; }
.room-title { display: inline-block; font-size: 14px; font-weight: 750; }
.room-title.disabled { color: #8a9189; text-decoration: none; }
.room-summary p { margin: 3px 0 0; color: #6e766d; font-size: 12px; }
.room-meta.compact { display: none; margin-top: 4px; gap: 8px; color: var(--muted); font-size: 11px; }
.message-count { text-align: center; }
.message-count strong { display: block; color: #3e473d; font-size: 15px; line-height: 1.15; }
.message-count span { color: var(--muted); font-size: 10px; }
.member-list { display: flex; align-items: center; flex-wrap: wrap; gap: 4px; padding-right: 10px; }
.member-tag,
.member-more {
  display: inline-block;
  max-width: 105px;
  overflow: hidden;
  padding: 1px 6px;
  border: 1px solid #d9e6d2;
  border-radius: 2px;
  background: #f5fbf1;
  color: #47613b;
  font-size: 10px;
  line-height: 1.65;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.member-more { border-color: #ddd; background: #f7f7f7; color: #666; }
.muted-dash { color: #a4aaa3; }
.room-state { display: grid; grid-template-columns: 1fr auto; align-items: center; gap: 6px; justify-items: end; }
.status-badge,
.visited-label {
  display: inline-block;
  justify-self: start;
  padding: 1px 6px;
  border-radius: 2px;
  font-size: 10px;
  font-weight: 750;
  white-space: nowrap;
}
.status-badge.saved { border: 1px solid #9bd178; background: #eaffda; color: #2e7519; }
.status-badge.pending { border: 1px solid #d5d8d3; background: #f1f2f0; color: #777d76; }
.visited-label { border: 1px solid #b9d5e8; background: #eaf6ff; color: #37627c; }
.open-button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-width: 64px;
  justify-content: center;
  padding: 4px 8px;
  border: 1px solid var(--green-dark);
  border-radius: 4px;
  background: linear-gradient(#70c94a, #50a92e);
  color: #fff;
  font-weight: 750;
  text-decoration: none;
  text-shadow: 0 1px rgba(0,0,0,.2);
}
.open-button:hover { color: #fff; background: linear-gradient(#61ba3d, #438e27); }
.open-button span { font-size: 17px; line-height: 1; }
.open-button.disabled { border-color: #d0d4ce; background: #eceeeb; color: #8e948d; text-shadow: none; }
.empty-state { display: none; padding: 40px 20px; color: var(--muted); text-align: center; }
.empty-state.visible { display: block; }

.footer {
  margin-top: 14px;
  padding: 17px 12px 6px;
  border-top: 1px solid var(--line);
  color: #747b73;
  text-align: center;
  font-size: 11px;
}
.footer strong { color: #536351; }

:focus-visible { outline: 3px solid rgba(7,89,191,.35); outline-offset: 2px; }

@media (max-width: 1020px) {
  .content-grid { grid-template-columns: 210px minmax(0, 1fr); }
  .room-table-head,
  .room-row { grid-template-columns: 58px minmax(220px, 1fr) 76px minmax(140px, .65fr) 135px; }
  .member-tag:nth-of-type(n+3) { display: none; }
}

@media (max-width: 800px) {
  .header-nav { display: none; }
  .hero { grid-template-columns: 1fr; }
  .hero-actions { justify-content: flex-start; }
  .content-grid { grid-template-columns: 1fr; }
  .sidebar { display: grid; grid-template-columns: 1fr 1fr; }
  .sidebar .panel:last-child { grid-column: 1 / -1; }
  .room-table-head { display: none; }
  .room-row {
    grid-template-columns: 54px minmax(0, 1fr) auto;
    grid-template-areas:
      "number summary state"
      "number members state";
    min-height: 92px;
  }
  .room-number { grid-area: number; }
  .room-summary { grid-area: summary; }
  .message-count { display: none; }
  .member-list { grid-area: members; margin-top: 5px; }
  .room-state { grid-area: state; grid-template-columns: 1fr; align-content: center; }
  .status-badge, .visited-label { justify-self: end; }
  .room-meta.compact { display: flex; }
}

@media (max-width: 560px) {
  body { font-size: 13px; }
  .header-inner,
  .notice-inner,
  .breadcrumb,
  .page-shell { width: min(100% - 16px, 1360px); }
  .site-header, .header-inner { min-height: 56px; }
  .brand-name { font-size: 23px; }
  .brand-badge { display: none; }
  .notice-inner { padding: 6px 2px; font-size: 11px; }
  .hero { padding: 18px 16px; }
  .hero-actions { display: grid; grid-template-columns: 1fr; }
  .primary-button, .secondary-button { width: 100%; }
  .sidebar { grid-template-columns: 1fr; }
  .sidebar .panel:last-child { grid-column: auto; }
  .toolbar { align-items: stretch; }
  .search-box { max-width: none; flex-basis: 100%; }
  .result-count { width: 100%; margin-left: 0; }
  .room-row {
    grid-template-columns: 46px minmax(0, 1fr);
    grid-template-areas:
      "number summary"
      "number members"
      "state state";
    gap: 5px 6px;
    padding: 10px 8px;
  }
  .room-number span { width: 38px; height: 38px; }
  .room-state { grid-template-columns: auto 1fr auto; justify-items: start; margin-top: 4px; padding-left: 52px; }
  .visited-label { justify-self: start; }
  .open-button { justify-self: end; }
  .archive-tabs { display: grid; grid-template-columns: 1fr 1fr; }
  .archive-tab { min-height: 48px; padding: 7px 9px; border-right: 1px solid #b8dc98; font-size: 11px; line-height: 1.35; }
  .archive-tab-count { flex: 0 0 auto; }
}

@media (prefers-reduced-motion: reduce) {
  html { scroll-behavior: auto; }
  *, *::before, *::after { transition: none !important; }
}

.spoiler-panel { overflow: hidden; }
.spoiler-intro {
  padding: 14px 16px;
  border-bottom: 1px solid #e0c986;
  background: linear-gradient(#fffdf2, #fff9df);
  color: #584b20;
  font-size: 13px;
  line-height: 1.7;
}
.spoiler-intro strong { color: #8a3b14; }
.spoiler-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  padding: 12px;
  background: #f8f8f6;
}
.spoiler-card {
  display: flex;
  flex-direction: column;
  min-width: 0;
  border: 1px solid #d8d2be;
  background: #fff;
  box-shadow: 0 1px 2px rgba(0,0,0,.04);
}
.spoiler-card.is-saved:hover { border-color: #caa95b; box-shadow: inset 4px 0 #d88e2f, 0 1px 3px rgba(0,0,0,.06); }
.spoiler-card.is-pending { background: #fafafa; color: #8b8b84; }
.spoiler-card-head {
  display: grid;
  grid-template-columns: 38px minmax(0,1fr) auto;
  align-items: center;
  gap: 9px;
  padding: 11px 11px 8px;
}
.spoiler-symbol {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: #fff3ce;
  border: 1px solid #e4bf61;
  color: #a15312;
  font-weight: 900;
  font-size: 18px;
}
.spoiler-title-block { min-width: 0; }
.spoiler-kicker { display: block; color: #9b6c19; font-size: 9px; font-weight: 800; letter-spacing: .08em; }
.spoiler-title-block h3 { margin: 1px 0 0; color: #333025; font-size: 15px; line-height: 1.4; overflow-wrap: anywhere; }
.spoiler-status {
  display: inline-flex;
  align-items: center;
  min-height: 22px;
  padding: 2px 7px;
  border-radius: 2px;
  font-size: 10px;
  font-weight: 750;
  white-space: nowrap;
}
.spoiler-status.saved { color: #70430b; background: #fff1c8; border: 1px solid #e5c16d; }
.spoiler-status.pending { color: #777; background: #eee; border: 1px solid #ddd; }
.spoiler-description { margin: 0; padding: 0 11px 9px 58px; color: #625e52; font-size: 12px; line-height: 1.55; }
.spoiler-meta { display: flex; gap: 10px; flex-wrap: wrap; padding: 8px 11px 0; border-top: 1px dotted #ddd4bb; color: #7c7565; font-size: 10px; }
.spoiler-members { display: flex; flex-wrap: wrap; gap: 4px; min-height: 28px; padding: 7px 11px; }
.spoiler-action { margin-top: auto; padding: 0 11px 11px; }
.spoiler-open-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 32px;
  padding: 5px 11px;
  border: 1px solid #bf8b27;
  background: linear-gradient(#fff6d8, #ffe8a8);
  color: #704008;
  font-size: 12px;
  font-weight: 750;
  text-decoration: none;
}
.spoiler-open-button:hover { background: #ffe7a0; color: #542e04; }
.spoiler-open-button.disabled { border-color: #ddd; background: #eee; color: #999; cursor: default; }
.spoiler-empty { padding: 18px; color: #777; text-align: center; font-size: 12px; background: #fafafa; }
.spoiler-dialog-backdrop[hidden] { display: none; }
.spoiler-dialog-backdrop {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: grid;
  place-items: center;
  padding: 18px;
  background: rgba(23, 20, 13, .64);
}
.spoiler-dialog {
  width: min(560px, 100%);
  border: 1px solid #c8a650;
  background: #fffdf6;
  box-shadow: 0 16px 55px rgba(0,0,0,.32);
}
.spoiler-dialog-head {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 13px 15px;
  border-bottom: 1px solid #e2c779;
  background: linear-gradient(#fff7d9, #ffeab1);
}
.spoiler-dialog-head strong { color: #713b0c; font-size: 15px; }
.spoiler-dialog-body { padding: 16px; color: #40392d; font-size: 13px; line-height: 1.75; }
.spoiler-dialog-room { margin: 0 0 10px; padding: 8px 10px; border-left: 4px solid #d99a33; background: #fff6dc; font-weight: 750; }
.spoiler-dialog-actions { display: flex; justify-content: flex-end; gap: 8px; padding: 0 16px 16px; }
.spoiler-cancel, .spoiler-proceed { min-height: 34px; padding: 6px 12px; font: inherit; font-size: 12px; font-weight: 700; cursor: pointer; }
.spoiler-cancel { border: 1px solid #bbb; background: #fff; color: #444; }
.spoiler-proceed { border: 1px solid #a86a18; background: #d98927; color: #fff; text-decoration: none; display: inline-flex; align-items: center; }
.spoiler-proceed:hover { background: #b96f18; }

@media (max-width: 720px) {
  .spoiler-grid { grid-template-columns: 1fr; }
  .spoiler-card-head { grid-template-columns: 36px minmax(0,1fr); }
  .spoiler-status { grid-column: 2; justify-self: start; }
  .spoiler-description { padding-left: 56px; }
  .spoiler-dialog-actions { flex-direction: column-reverse; }
  .spoiler-cancel, .spoiler-proceed { width: 100%; justify-content: center; }
}

@media print {
  .site-header, .notice-bar, .hero-actions, .sidebar, .toolbar, .open-button { display: none !important; }
  body { background: #fff; }
  .page-shell { width: 100%; margin: 0; }
  .content-grid { display: block; }
  .panel { box-shadow: none; }
  .room-row { break-inside: avoid; }
}
</style>
</head>
<body>
<header class="site-header">
  <div class="header-inner">
    <a class="brand" href="./index.html" aria-label="@@BRAND_NAME@@ ホーム">
      <span class="brand-mark" aria-hidden="true"><span class="brand-dots"></span></span>
      <span class="brand-copy">
        <span class="brand-name">@@BRAND_NAME@@</span>
        <span class="brand-badge">ARCHIVE</span>
      </span>
    </a>
    <nav class="header-nav" aria-label="ページ内ナビゲーション">
      <a href="#rooms" data-archive-tab-link="rooms"><span class="nav-dot" aria-hidden="true"></span>常設ログ</a>
      <a href="#spoiler-rooms" data-archive-tab-link="spoiler"><span class="nav-dot" aria-hidden="true"></span>通過者専用部屋</a>
      <a href="#archive-info"><span class="nav-dot" aria-hidden="true"></span>保存情報</a>
    </nav>
  </div>
</header>

<div class="notice-bar">
  <div class="notice-inner"><strong>【保存版】</strong>@@NOTICE@@</div>
</div>

<div class="breadcrumb"><a href="./index.html">ホーム</a> » ログ保管庫</div>

<main class="page-shell">
  <section class="hero" aria-labelledby="archive-title">
    <div class="hero-copy">
      <p class="eyebrow">READ-ONLY MEETING LOGS</p>
      <h1 id="archive-title">@@ARCHIVE_TITLE@@</h1>
      <p class="hero-subtitle">@@SUBTITLE@@</p>
    </div>
    <div class="hero-actions">
      <a id="start-reading" class="primary-button" href="@@FIRST_HREF@@" @@FIRST_LINK_DATA@@>最初の部屋から読む</a>
      <a class="secondary-button" href="#rooms" data-archive-tab-link="rooms">全@@TOTAL_ROOMS@@部屋を見る</a>
    </div>
  </section>

  <div class="content-grid">
    <aside class="sidebar" id="archive-info" aria-label="保存情報">
      <section class="panel">
        <div class="panel-heading"><h2>アーカイブ概要</h2></div>
        <div class="panel-body">
          <div class="stats-list">
            <div class="stat"><strong>@@TOTAL_ROOMS@@</strong><span>全室</span></div>
            <div class="stat"><strong>@@SAVED_ROOMS@@</strong><span>保存済み</span></div>
            <div class="stat"><strong>@@TOTAL_MESSAGES@@</strong><span>保存発言</span></div>
            <div class="stat"><strong>@@TOTAL_SPEAKERS@@</strong><span>確認参加者</span></div>
          </div>
          <p class="side-note">生成日：@@GENERATED_DATE@@<br>ログ本文は保存時の内容を維持し、人物アイコンの参照先のみ保存用パスへ補正しています。</p>
        </div>
      </section>

      <section class="panel">
        <div class="panel-heading"><h2>最後に開いた部屋</h2></div>
        <div class="panel-body" id="last-read-box">
          <p class="last-read-empty">まだ閲覧履歴はありません。</p>
        </div>
      </section>

      <section class="panel">
        <div class="panel-heading"><h2>閲覧上の注意</h2></div>
        <div class="panel-body">
          <ul class="archive-notes">
            <li>ログは当時の内容をそのまま保存しています。</li>
            <li>外部リンクはリンク先の終了・移転により開けない場合があります。</li>
            <li>人物アイコンは各ログから <code>../img/</code> を参照します。</li>
          </ul>
        </div>
      </section>
    </aside>

    <section class="panel main-panel" id="archive-rooms" aria-label="ミーティングルーム一覧">
      <div class="archive-tabs" role="tablist" aria-label="ミーティングルームの種類">
        <button class="archive-tab" id="tab-rooms" type="button" role="tab" aria-selected="true" aria-controls="rooms" data-archive-tab="rooms">
          <span>参加していたミーティングルーム</span><span class="archive-tab-count">@@TOTAL_ROOMS@@</span>
        </button>
        <button class="archive-tab warning-tab" id="tab-spoiler" type="button" role="tab" aria-selected="false" aria-controls="spoiler-rooms" tabindex="-1" data-archive-tab="spoiler">
          <span>シナリオ通過者専用部屋</span><span class="archive-tab-count">@@SPOILER_COUNT@@</span>
        </button>
      </div>

      <div class="archive-tab-panel" id="rooms" role="tabpanel" aria-labelledby="tab-rooms" data-archive-panel="rooms">
        <div class="archive-tab-meta">進行順 01 → @@TOTAL_ROOMS_PADDED@@</div>
        <div class="toolbar">
          <label class="search-box">
            <span class="sr-only"></span>
            <input id="room-search" type="search" autocomplete="off" placeholder="部屋名・説明・参加者で検索" aria-label="ログを検索">
          </label>
          <label class="check-control"><input id="saved-only" type="checkbox">保存済みのみ</label>
          <button class="sort-button" id="sort-order" type="button" data-order="asc">新しい順にする</button>
          <span class="result-count" id="result-count" aria-live="polite">@@TOTAL_ROOMS@@部屋を表示中</span>
        </div>

        <div class="room-table-head" aria-hidden="true">
          <span>No.</span><span>ミーティングルーム</span><span>発言数</span><span>主な参加者</span><span>状態</span>
        </div>

        <div class="room-list" id="room-list">
@@ROOM_ROWS@@
        </div>
        <div class="empty-state" id="empty-state">条件に一致する部屋はありません。</div>
      </div>

      <div class="archive-tab-panel spoiler-panel" id="spoiler-rooms" role="tabpanel" aria-labelledby="tab-spoiler" data-archive-panel="spoiler" hidden>
        <div class="archive-tab-meta">@@SPOILER_COUNT@@室 / 保存済み @@SPOILER_SAVED@@室</div>
        <div class="spoiler-intro">
          <strong>ネタバレ注意：</strong>ここにある部屋は、Fresh Meeting 上では各シナリオの通過者だけが招待されていた専用部屋です。
          移管後はアクセス制限を設けず、閲覧前の警告のみとしています。未通過のシナリオを今後遊ぶ予定がある場合は閲覧にご注意ください。
        </div>
        @@SPOILER_BODY@@
      </div>
    </section>
  </div>

  <footer class="footer">
    <strong>@@ARCHIVE_TITLE@@</strong><br>
    Fresh Meeting の簡易HTML書き出しをもとに構成した、非公式の閲覧用アーカイブです。
  </footer>
</main>

<div class="spoiler-dialog-backdrop" id="spoiler-dialog" hidden>
  <div class="spoiler-dialog" role="dialog" aria-modal="true" aria-labelledby="spoiler-dialog-title" aria-describedby="spoiler-dialog-description">
    <div class="spoiler-dialog-head">
      <span class="spoiler-symbol" aria-hidden="true">!</span>
      <strong id="spoiler-dialog-title">シナリオのネタバレを含みます</strong>
    </div>
    <div class="spoiler-dialog-body" id="spoiler-dialog-description">
      <p class="spoiler-dialog-room" id="spoiler-dialog-room"></p>
      この部屋は本来、シナリオ通過者のみが招待されていた専用部屋です。シナリオの核心・結末・GM情報などを含む可能性があります。内容を承知のうえで閲覧してください。
    </div>
    <div class="spoiler-dialog-actions">
      <button class="spoiler-cancel" id="spoiler-cancel" type="button">戻る</button>
      <a class="spoiler-proceed" id="spoiler-proceed" href="#">内容を承知して入室する</a>
    </div>
  </div>
</div>

<script id="archive-data" type="application/json">@@ROOM_JSON@@</script>
<script>
(() => {
  'use strict';
  const STORAGE_KEY = 'kani-meeting-archive-state-v1';
  const searchInput = document.getElementById('room-search');
  const savedOnly = document.getElementById('saved-only');
  const sortButton = document.getElementById('sort-order');
  const roomList = document.getElementById('room-list');
  const resultCount = document.getElementById('result-count');
  const emptyState = document.getElementById('empty-state');
  const lastReadBox = document.getElementById('last-read-box');
  const startReading = document.getElementById('start-reading');
  const spoilerDialog = document.getElementById('spoiler-dialog');
  const spoilerDialogRoom = document.getElementById('spoiler-dialog-room');
  const spoilerProceed = document.getElementById('spoiler-proceed');
  const spoilerCancel = document.getElementById('spoiler-cancel');
  const archiveTabs = [...document.querySelectorAll('[data-archive-tab]')];
  const archivePanels = [...document.querySelectorAll('[data-archive-panel]')];

  const loadState = () => {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
    } catch (_) {
      return {};
    }
  };

  const saveState = (state) => {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(state)); } catch (_) {}
  };

  const escapeHtml = (value) => String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');

  const renderHistory = () => {
    const state = loadState();
    const visited = Array.isArray(state.visited) ? state.visited : [];
    document.querySelectorAll('.room-row').forEach((row) => {
      const isVisited = visited.includes(row.dataset.room);
      row.classList.toggle('is-visited', isVisited);
      const label = row.querySelector('.visited-label');
      if (label) label.hidden = !isVisited;
    });

    if (state.last && state.last.href) {
      lastReadBox.innerHTML =
        `<a class="last-read-link" href="${escapeHtml(state.last.href)}" data-open-room="${escapeHtml(state.last.number)}" data-room-title="${escapeHtml(state.last.title)}">${escapeHtml(state.last.number)}　${escapeHtml(state.last.title)}</a>` +
        `<span class="last-read-meta">前回このブラウザで開いた部屋</span>` +
        `<button class="clear-history" type="button" id="clear-history">閲覧履歴を消す</button>`;
      startReading.textContent = '続きから読む';
      startReading.href = state.last.href;
      startReading.dataset.openRoom = state.last.number;
      startReading.dataset.roomTitle = state.last.title;
    } else {
      lastReadBox.innerHTML = '<p class="last-read-empty">まだ閲覧履歴はありません。</p>';
    }
  };

  const rememberRoom = (link) => {
    const number = link.dataset.openRoom;
    const title = link.dataset.roomTitle || link.textContent.trim();
    if (!number) return;
    const state = loadState();
    const visited = new Set(Array.isArray(state.visited) ? state.visited : []);
    visited.add(number);
    state.visited = [...visited];
    state.last = { number, title, href: link.getAttribute('href') };
    saveState(state);
  };

  document.addEventListener('click', (event) => {
    const link = event.target.closest('[data-open-room]');
    if (link) rememberRoom(link);
    if (event.target.id === 'clear-history') {
      try { localStorage.removeItem(STORAGE_KEY); } catch (_) {}
      startReading.textContent = '最初の部屋から読む';
      startReading.href = '@@FIRST_HREF_JS@@';
      startReading.dataset.openRoom = '@@FIRST_NUMBER@@';
      startReading.dataset.roomTitle = '@@FIRST_TITLE_JS@@';
      renderHistory();
    }
  });

  const activateArchiveTab = (name, options = {}) => {
    const { focus = false, updateHash = false } = options;
    const tab = archiveTabs.find((item) => item.dataset.archiveTab === name);
    const panel = archivePanels.find((item) => item.dataset.archivePanel === name);
    if (!tab || !panel) return;

    archiveTabs.forEach((item) => {
      const active = item === tab;
      item.setAttribute('aria-selected', active ? 'true' : 'false');
      item.tabIndex = active ? 0 : -1;
    });
    archivePanels.forEach((item) => { item.hidden = item !== panel; });

    if (focus) tab.focus();
    if (updateHash) {
      const hash = name === 'spoiler' ? '#spoiler-rooms' : '#rooms';
      try { history.replaceState(null, '', hash); } catch (_) {}
    }
  };

  archiveTabs.forEach((tab, index) => {
    tab.addEventListener('click', () => activateArchiveTab(tab.dataset.archiveTab, { updateHash: true }));
    tab.addEventListener('keydown', (event) => {
      if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
      event.preventDefault();
      let nextIndex = index;
      if (event.key === 'ArrowLeft') nextIndex = (index - 1 + archiveTabs.length) % archiveTabs.length;
      if (event.key === 'ArrowRight') nextIndex = (index + 1) % archiveTabs.length;
      if (event.key === 'Home') nextIndex = 0;
      if (event.key === 'End') nextIndex = archiveTabs.length - 1;
      const nextTab = archiveTabs[nextIndex];
      activateArchiveTab(nextTab.dataset.archiveTab, { focus: true, updateHash: true });
    });
  });

  document.querySelectorAll('[data-archive-tab-link]').forEach((link) => {
    link.addEventListener('click', (event) => {
      const name = link.dataset.archiveTabLink;
      if (!name) return;
      event.preventDefault();
      activateArchiveTab(name, { updateHash: true });
      document.getElementById('archive-rooms')?.scrollIntoView({ block: 'start' });
    });
  });

  const syncTabFromHash = () => {
    activateArchiveTab(location.hash === '#spoiler-rooms' ? 'spoiler' : 'rooms');
  };
  window.addEventListener('hashchange', syncTabFromHash);

  const applyFilters = () => {
    const query = searchInput.value.trim().toLowerCase();
    const onlySaved = savedOnly.checked;
    let visible = 0;
    document.querySelectorAll('.room-row').forEach((row) => {
      const matchesQuery = !query || row.dataset.search.includes(query);
      const matchesSaved = !onlySaved || row.dataset.saved === '1';
      const show = matchesQuery && matchesSaved;
      row.classList.toggle('is-hidden', !show);
      if (show) visible += 1;
    });
    resultCount.textContent = `${visible}部屋を表示中`;
    emptyState.classList.toggle('visible', visible === 0);
  };

  searchInput.addEventListener('input', applyFilters);
  savedOnly.addEventListener('change', applyFilters);
  sortButton.addEventListener('click', () => {
    const rows = [...roomList.querySelectorAll('.room-row')];
    const nextOrder = sortButton.dataset.order === 'asc' ? 'desc' : 'asc';
    rows.sort((a, b) => {
      const delta = Number(a.dataset.room) - Number(b.dataset.room);
      return nextOrder === 'asc' ? delta : -delta;
    });
    rows.forEach((row) => roomList.appendChild(row));
    sortButton.dataset.order = nextOrder;
    sortButton.textContent = nextOrder === 'asc' ? '新しい順にする' : '古い順にする';
  });

  const closeSpoilerDialog = () => {
    if (!spoilerDialog) return;
    spoilerDialog.hidden = true;
    spoilerProceed.href = '#';
  };

  document.addEventListener('click', (event) => {
    const spoilerLink = event.target.closest('[data-spoiler-room]');
    if (spoilerLink) {
      event.preventDefault();
      spoilerDialogRoom.textContent = spoilerLink.dataset.spoilerTitle || spoilerLink.textContent.trim();
      spoilerProceed.href = spoilerLink.getAttribute('href');
      spoilerDialog.hidden = false;
      spoilerCancel.focus();
      return;
    }
    if (event.target === spoilerDialog) closeSpoilerDialog();
  });

  spoilerCancel?.addEventListener('click', closeSpoilerDialog);
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && spoilerDialog && !spoilerDialog.hidden) closeSpoilerDialog();
  });

  syncTabFromHash();
  renderHistory();
  applyFilters();
})();
</script>
</body>
</html>
'''


def build() -> None:
    config = load_config()
    changed_files, remote_icons, local_icons = normalize_lobby_files()
    logs = detect_logs()
    room_rows, room_data = make_room_rows(config, logs)
    spoiler_entries = load_spoiler_rooms()
    spoiler_cards, spoiler_data = make_spoiler_cards(spoiler_entries)

    total_rooms = len(room_data)
    saved_rooms = sum(1 for item in room_data if item["saved"])
    total_messages = sum(int(item["messages"]) for item in room_data)
    unique_speakers = sorted({speaker for item in room_data for speaker in item["speakers"]})
    first_saved = next((item for item in room_data if item["saved"]), None)

    if first_saved:
        first_href = first_saved["href"]
        first_number = first_saved["number"]
        first_title = first_saved["title"]
        first_link_data = f'data-open-room="{attr(first_number)}" data-room-title="{attr(first_title)}"'
    else:
        first_href = "#rooms"
        first_number = ""
        first_title = ""
        first_link_data = ""

    spoiler_saved = sum(1 for item in spoiler_data if item["saved"])
    if spoiler_cards:
        spoiler_body = f'<div class="spoiler-grid">{spoiler_cards}</div>'
    else:
        spoiler_body = '<div class="spoiler-empty">まだ通過者専用部屋は登録されていません。<code>spoiler-rooms.json</code> に追加するとここに表示されます。</div>'

    replacements = {
        "@@PAGE_TITLE@@": text(config["archive_title"]),
        "@@ARCHIVE_TITLE@@": text(config["archive_title"]),
        "@@BRAND_NAME@@": text(config["brand_name"]),
        "@@SUBTITLE@@": text(config["subtitle"]),
        "@@NOTICE@@": text(config["notice"]),
        "@@TOTAL_ROOMS@@": f"{total_rooms:,}",
        "@@TOTAL_ROOMS_PADDED@@": f"{total_rooms:02d}",
        "@@SAVED_ROOMS@@": f"{saved_rooms:,}",
        "@@TOTAL_MESSAGES@@": f"{total_messages:,}",
        "@@TOTAL_SPEAKERS@@": f"{len(unique_speakers):,}",
        "@@GENERATED_DATE@@": datetime.now(timezone(timedelta(hours=9))).date().isoformat(),
        "@@FIRST_HREF@@": attr(first_href),
        "@@FIRST_LINK_DATA@@": first_link_data,
        "@@FIRST_HREF_JS@@": first_href.replace("\\", "\\\\").replace("'", "\\'"),
        "@@FIRST_NUMBER@@": first_number.replace("'", "\\'"),
        "@@FIRST_TITLE_JS@@": first_title.replace("\\", "\\\\").replace("'", "\\'"),
        "@@SPOILER_COUNT@@": f"{len(spoiler_data):,}",
        "@@SPOILER_SAVED@@": f"{spoiler_saved:,}",
        "@@SPOILER_BODY@@": spoiler_body,
        "@@ROOM_ROWS@@": room_rows,
        "@@ROOM_JSON@@": json.dumps(room_data, ensure_ascii=False).replace("</", r"<\/"),
    }

    output = TEMPLATE
    for needle, replacement in replacements.items():
        output = output.replace(needle, replacement)

    OUTPUT_PATH.write_text(output, encoding="utf-8", newline="\n")
    print(f"生成しました: {OUTPUT_PATH.name}")
    if changed_files:
        print(
            f"アイコン参照を補正: {changed_files} ファイル "
            f"(Fresh Meeting URL {remote_icons} 件 / img/ 相対参照 {local_icons} 件)"
        )
    else:
        print("アイコン参照: 補正不要")
    print(f"保存済み: {saved_rooms}/{total_rooms} 部屋、発言数: {total_messages:,}")
    print(f"通過者専用部屋: {spoiler_saved}/{len(spoiler_data)} 室")
    if logs:
        for number, item in sorted(logs.items()):
            print(f"  {number:02d}: {item['filename']} ({item['messages']:,} 発言 / {item['speaker_count']} 人)")


if __name__ == "__main__":
    build()
