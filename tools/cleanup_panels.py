#!/usr/bin/env python3
"""Bersihkan pesan panel musik & now-playing CrspyMusic yang tertinggal di chat.

Utilitas sekali-jalan untuk menghapus sisa pesan panel lama yang dikirim bot
sebelum perbaikan e7ef0a3 (dulu panel tidak dihapus saat bot keluar voice).

Aman dijalankan selagi bot hidup: skrip ini murni REST (tanpa koneksi
gateway), dan hanya menyentuh pesan milik bot sendiri.

Pemakaian (dari /opt/discord-music-bot):
    ./venv/bin/python tools/cleanup_panels.py                  # dry-run (default)
    ./venv/bin/python tools/cleanup_panels.py --apply          # hapus sungguhan
    ./venv/bin/python tools/cleanup_panels.py --apply --days 14 --queue-notes
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import discord

PANEL_AUTHOR_NAME = "MUSIC PANEL"
NOW_PLAYING_PREFIX = "Now playing:"
QUEUE_NOTE_PREFIXES = ("Ditambahkan ke antrian:", "Ditambahkan ")


def load_token(env_path: Path) -> str:
    token = os.environ.get("DISCORD_TOKEN", "").strip()
    if token:
        return token
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("DISCORD_TOKEN="):
                value = line.split("=", 1)[1].strip().strip('"').strip("'")
                if value:
                    return value
    raise SystemExit(f"DISCORD_TOKEN tidak ditemukan (environment atau {env_path})")


def is_panel_message(msg, bot_id: int) -> bool:
    """Pesan panel MUSIC PANEL milik bot (embed author atau tombol music:*)."""
    if getattr(getattr(msg, "author", None), "id", None) != bot_id:
        return False
    for embed in getattr(msg, "embeds", None) or []:
        author = getattr(embed, "author", None)
        if author is not None and getattr(author, "name", None) == PANEL_AUTHOR_NAME:
            return True
    for row in getattr(msg, "components", None) or []:
        for child in getattr(row, "children", None) or []:
            cid = getattr(child, "custom_id", None)
            if isinstance(cid, str) and cid.startswith("music:"):
                return True
    return False


def is_now_playing_message(msg, bot_id: int) -> bool:
    if getattr(getattr(msg, "author", None), "id", None) != bot_id:
        return False
    return (getattr(msg, "content", None) or "").startswith(NOW_PLAYING_PREFIX)


def is_queue_note_message(msg, bot_id: int) -> bool:
    if getattr(getattr(msg, "author", None), "id", None) != bot_id:
        return False
    content = getattr(msg, "content", None) or ""
    return content.startswith(QUEUE_NOTE_PREFIXES)


def classify_message(msg, bot_id: int, enabled: set[str]) -> str | None:
    if "panel" in enabled and is_panel_message(msg, bot_id):
        return "panel"
    if "now-playing" in enabled and is_now_playing_message(msg, bot_id):
        return "now-playing"
    if "queue-note" in enabled and is_queue_note_message(msg, bot_id):
        return "queue-note"
    return None


def _preview(msg) -> str:
    text = getattr(msg, "content", None) or ""
    if not text:
        embeds = getattr(msg, "embeds", None) or []
        if embeds:
            text = getattr(embeds[0], "description", None) or "(embed panel)"
    return text[:70]


async def run(args: argparse.Namespace) -> int:
    token = load_token(Path(args.env))
    client = discord.Client(intents=discord.Intents.none())
    await client.login(token)
    exit_code = 0
    try:
        bot_id = client.user.id
        enabled = {"panel", "now-playing"}
        if args.queue_notes:
            enabled.add("queue-note")
        after = datetime.now(timezone.utc) - timedelta(days=args.days)

        guilds = [g async for g in client.fetch_guilds(limit=200)]
        if args.guild:
            guilds = [g for g in guilds if g.id in set(args.guild)]
        if args.channel:
            wanted = set(args.channel)
        else:
            wanted = None

        totals = {cat: 0 for cat in enabled}
        deleted = 0
        print(f"Scan pesan bot sejak {after:%Y-%m-%d %H:%M UTC} "
              f"(kategori: {', '.join(sorted(enabled))})")

        for guild in guilds:
            print(f"\n== {guild.name} ({guild.id}) ==")
            try:
                channels = await guild.fetch_channels()
            except discord.HTTPException as exc:
                print(f"  ! gagal ambil daftar channel: {exc}")
                exit_code = 1
                continue
            for channel in channels:
                if not isinstance(channel, discord.TextChannel):
                    continue
                if wanted is not None and channel.id not in wanted:
                    continue
                hits = []
                try:
                    async for msg in channel.history(after=after, limit=args.limit):
                        cat = classify_message(msg, bot_id, enabled)
                        if cat:
                            hits.append((cat, msg))
                except discord.Forbidden:
                    continue
                except discord.HTTPException as exc:
                    print(f"  ! #{channel.name}: gagal baca history: {exc}")
                    exit_code = 1
                    continue
                if not hits:
                    continue
                print(f"  #{channel.name}: {len(hits)} pesan cocok")
                for cat, msg in hits:
                    totals[cat] += 1
                    ts = msg.created_at.astimezone().strftime("%Y-%m-%d %H:%M")
                    print(f"    [{cat}] {ts} id={msg.id} {_preview(msg)!r}")
                    if not args.apply:
                        continue
                    try:
                        await msg.delete()
                        deleted += 1
                    except discord.NotFound:
                        pass
                    except discord.HTTPException as exc:
                        print(f"    ! gagal hapus id={msg.id}: {exc}")
                        exit_code = 1
                    await asyncio.sleep(args.delay)

        print("\n=== Ringkasan ===")
        for cat in sorted(totals):
            print(f"  {cat}: {totals[cat]}")
        if args.apply:
            print(f"  dihapus: {deleted}")
        else:
            print("  (dry-run — tambahkan --apply untuk benar-benar menghapus)")
    finally:
        await client.close()
    return exit_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true",
                        help="hapus pesan (default: dry-run, hanya menampilkan)")
    parser.add_argument("--days", type=int, default=30,
                        help="batas umur pesan yang dipindai (default: 30)")
    parser.add_argument("--limit", type=int, default=500,
                        help="maksimum pesan dipindai per channel (default: 500)")
    parser.add_argument("--delay", type=float, default=0.35,
                        help="jeda antar penghapusan detik (default: 0.35)")
    parser.add_argument("--queue-notes", action="store_true",
                        help="ikut hapus pesan 'Ditambahkan ke antrian: ...'")
    parser.add_argument("--guild", type=int, action="append",
                        help="batasi ke guild id tertentu (boleh berulang)")
    parser.add_argument("--channel", type=int, action="append",
                        help="batasi ke channel id tertentu (boleh berulang)")
    parser.add_argument("--env", default=str(Path(__file__).resolve().parent.parent / ".env"),
                        help="path file .env berisi DISCORD_TOKEN")
    args = parser.parse_args(argv)
    try:
        return asyncio.run(run(args))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
