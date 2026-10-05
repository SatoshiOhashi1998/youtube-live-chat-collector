from __future__ import annotations

import os
import re
from datetime import UTC, date, datetime, time, timedelta, timezone

from myutils.youtube_api import YouTubeAPI, create_youtube_api, to_utc_z


def get_target_videos(
    channel_id: str,
    start_date: str | date | datetime,
    end_date: str | date | datetime,
    api: YouTubeAPI | None = None,
) -> list[dict]:
    """
    指定チャンネル・指定期間の動画をyoutube.dbへ反映し、
    youtube.dbから対象動画を返す。

    live_streaming_detailsの有無で通常動画を判定し、
    is_live=True/Falseを付加する。
    """
    api = api or create_youtube_api()

    start = to_utc_z(start_date)
    end = to_utc_z(end_date, end_date=True)

    api.sync_channel_videos(
        channel_id,
        start_date=start,
        end_date=end,
    )

    rows = api.db.get_videos_by_channel_and_date(
        channel_id,
        start,
        end,
    )

    video_ids = [row[0] for row in rows]
    live_video_ids = api.get_live_streaming_video_ids(video_ids)

    videos = []
    for row in rows:
        video_id = row[0]
        channel_row = api.db.get_channel_by_id(row[2])
        channel_title = channel_row[1] if channel_row else ""

        videos.append(
            {
                "video_id": video_id,
                "title": row[1],
                "channel_id": row[2],
                "channel": channel_title,
                "published_at": row[3],
                "duration": row[4],
                "is_live": video_id in live_video_ids,
                "url": f"https://www.youtube.com/watch?v={video_id}",
            }
        )

    return videos


def refresh_historical_channel(
    channel_id: str,
    start_date: str | date | datetime,
    end_date: str | date | datetime,
    api: YouTubeAPI | None = None,
) -> bool:
    """
    指定チャンネルの過去動画をAPIから再取得し、
    youtube.dbへ保存する。

    既存の同期状態は取得判定に使用しない。
    """

    api = api or create_youtube_api()

    start = to_utc_z(start_date)
    end = to_utc_z(
        end_date,
        end_date=True,
    )

    return api.refresh_channel_videos(
        channel_id,
        start_date=start,
        end_date=end,
    )

def sync_current_channel(
    channel_id: str,
    api: YouTubeAPI | None = None,
) -> bool:
    api = api or create_youtube_api()

    state = api.db.get_channel_sync_state(channel_id)

    if not state:
        return False

    newest_synced_at = state[3]

    if not newest_synced_at:
        return False

    start = to_utc_z(newest_synced_at)

    end = to_utc_z(
        datetime.now(UTC) - timedelta(days=1)
    )

    if start >= end:
        return True

    return api.sync_channel_videos(
        channel_id,
        start_date=start,
        end_date=end,
    )
