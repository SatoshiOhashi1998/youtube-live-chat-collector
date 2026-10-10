from __future__ import annotations

import csv
import os
from pathlib import Path

from .comments_db import CommentsDB


def parse_timestamp(timestamp: str) -> int | None:
    if not timestamp:
        return None

    text = timestamp.strip()
    sign = -1 if text.startswith("-") else 1
    text = text.lstrip("-")

    try:
        parts = [int(part) for part in text.split(":")]
    except ValueError:
        return None

    if len(parts) == 3:
        hours, minutes, seconds = parts
    elif len(parts) == 2:
        hours = 0
        minutes, seconds = parts
    elif len(parts) == 1:
        hours = minutes = 0
        seconds = parts[0]
    else:
        return None

    return sign * (hours * 3600 + minutes * 60 + seconds)


def build_timestamp_url(video_id: str, timestamp: str) -> str:
    base_url = f"https://www.youtube.com/watch?v={video_id}"
    seconds = parse_timestamp(timestamp)
    if seconds is None or seconds < 0:
        return base_url
    return f"{base_url}&t={seconds}s"

def export_comments_to_csv(
    output_csv: str,
    db: CommentsDB | None = None,
    channel: str | list[str] | None = None,
    keyword: str | list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> str:
    """条件を指定してコメントを検索し、CSVに出力する。

    Args:
        output_csv: CSVの出力先パス。
        db: 使用するCommentsDBインスタンス。
        channel: チャンネル名、またはチャンネル名のリスト。
        keyword: コメント本文のキーワード、またはキーワードのリスト。
        start_date: 検索開始日（YYYY-MM-DD）。指定日を含む。
        end_date: 検索終了日（YYYY-MM-DD）。指定日を含む。

    Returns:
        出力したCSVファイルのパス。
    """
    db = db or CommentsDB()

    rows = db.search_comments(
        channel=channel,
        keyword=keyword,
        start_date=start_date,
        end_date=end_date,
    )

    output_path = Path(output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "Title",
        "URL",
        "timestamp",
        "Comment",
        "Author",
        "Channel",
        "Date",
    ]

    with output_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()

        for row in rows:
            writer.writerow(
                {
                    "Title": row["title"],
                    "URL": build_timestamp_url(
                        row["video_id"],
                        row["timestamp"],
                    ),
                    "timestamp": row["timestamp"],
                    "Comment": row["comment"],
                    "Author": row["author_name"],
                    "Channel": row["channel"],
                    "Date": row["date"] or "",
                }
            )

    print(f"CSVを出力しました: {output_path}")
    print(f"コメント数: {len(rows)}")
    return str(output_path)
