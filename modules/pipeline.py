"""YouTubeライブチャットの取得・処理パイプラインを管理するモジュール。

対象チャンネルの動画を取得し、処理状態に応じて動画を選別したうえで、
ライブチャットのダウンロード、コメントの抽出・保存、処理状態の更新を行う。

主な関数:

* process_channel():
    指定したチャンネルの動画を処理し、コメントの取得・保存を行う。

* process_channels():
    複数のチャンネルを対象に、process_channel() による処理を実行する。

* process_historical_channels():
    指定したチャンネルの過去動画に関する情報を更新する。

* process_current_channels():
    指定したチャンネルの最新の動画情報を同期する。

* _get_target_channels():
    CSV一括処理またはチャンネルID指定に応じて対象チャンネルを選択する。
"""

from __future__ import annotations

from .channel import Channel
from .comment_processor import extract_comments
from .comments_db import CommentsDB
from .config import (
    CHANNEL_DATAS,
    COMMENT_KEYWORDS,
    COOKIES_FILE,
    JSON_DIRECTORY,
    get_channels,
)
from .live_chat import (
    NO_CHAT,
    RETRY,
    SUCCESS,
    delete_video_json,
    download_live_chat,
)
from .youtube import (
    get_target_videos,
    refresh_historical_channel,
    sync_current_channel,
)


def process_channel(
    channel_id: str,
    start_date,
    end_date,
    keywords: list[str] | None = None,
    db: CommentsDB | None = None,
) -> dict[str, int]:
    """指定したチャンネルの動画を処理する。"""
    keywords = keywords if keywords is not None else COMMENT_KEYWORDS
    db = db or CommentsDB()

    videos = get_target_videos(channel_id, start_date, end_date)
    db.ensure_jobs(video["video_id"] for video in videos)

    stats = {
        "total": len(videos),
        "completed": 0,
        "excluded": 0,
        "retry": 0,
    }

    for video in videos:
        video_id = video["video_id"]

        if db.is_completed(video_id):
            stats["completed"] += 1
            print(f"SKIP completed: {video_id} {video['title']}")
            continue

        if db.is_excluded(video_id):
            stats["excluded"] += 1
            print(f"SKIP excluded: {video_id} {video['title']}")
            continue

        # ライブ配信ではない通常動画はここで対象外にする。
        if not video["is_live_broadcast"]:
            db.mark_excluded(video_id)
            stats["excluded"] += 1
            print(f"EXCLUDE non-live: {video_id} {video['title']}")
            continue

        print(f"PROCESS: {video_id} {video['title']}")

        result = download_live_chat(
            video_id,
            JSON_DIRECTORY,
            cookies_file=COOKIES_FILE,
        )

        if result.status == NO_CHAT:
            db.mark_excluded(video_id)
            stats["excluded"] += 1
            print(f"EXCLUDE no-chat: {video_id}")
            continue

        if result.status == RETRY:
            stats["retry"] += 1
            print(f"RETRY next run: {video_id}: {result.error}")
            continue

        if result.status != SUCCESS or result.json_path is None:
            stats["retry"] += 1
            print(f"RETRY next run: {video_id}: unknown download result")
            continue

        try:
            comments = extract_comments(
                result.json_path,
                keywords,
                video,
            )
            db.save_comments(comments)

            # DB保存成功後にJSONを削除する。
            delete_video_json(video_id, JSON_DIRECTORY)
            db.mark_completed(video_id)
            stats["completed"] += 1

            print(
                f"COMPLETED: {video_id} "
                f"comments={len(comments)}"
            )

        except Exception as exc:
            # completed=0 のまま。JSONも残す。
            stats["retry"] += 1
            print(f"ERROR: {video_id}: {exc}")

    return stats


def process_channels(
    channels: list[Channel],
    start_date,
    end_date,
    keywords: list[str] | None = None,
    db: CommentsDB | None = None,
) -> dict[str, int]:
    """複数のチャンネルを処理する。"""
    db = db or CommentsDB()

    total_stats = {
        "total": 0,
        "completed": 0,
        "excluded": 0,
        "retry": 0,
    }

    for channel in channels:
        print()
        print("=" * 60)
        print(f"CHANNEL: {channel.channel_name} ({channel.channel_id})")
        print("=" * 60)

        stats = process_channel(
            channel_id=channel.channel_id,
            start_date=start_date,
            end_date=end_date,
            keywords=keywords,
            db=db,
        )

        for key in total_stats:
            total_stats[key] += stats[key]

    return total_stats


def _get_target_channels(
    channel_id: str | None = None,
) -> list[tuple[str, str]]:
    """処理対象チャンネルを選択する。

    channel_id が None の場合:
        CSV登録済みの全チャンネルを返す。

    channel_id が指定された場合:
        CSV登録済みならCSVのチャンネル名を使用する。
        CSV未登録なら指定IDをチャンネル名の代わりに使用する。
    """
    channels = get_channels(CHANNEL_DATAS)

    if channel_id is None:
        return [
            (channel.channel_id, channel.channel_name)
            for channel in channels
        ]

    channel_id = channel_id.strip()

    if not channel_id:
        raise ValueError(
            "channel_id に空文字列は指定できません。"
        )

    for channel in channels:
        if channel.channel_id == channel_id:
            return [
                (channel.channel_id, channel.channel_name)
            ]

    # CSVに登録されていないチャンネルもIDで指定できるようにする。
    return [(channel_id, channel_id)]


def process_historical_channels(
    start_date,
    end_date,
    channel_id: str | None = None,
) -> dict[str, int]:
    """指定期間の過去動画情報を更新する。

    channel_id が None の場合はCSV登録済みの全チャンネルを処理する。
    channel_id が指定された場合は、そのチャンネルのみ処理する。
    """
    channels = _get_target_channels(channel_id)

    stats = {
        "total": len(channels),
        "completed": 0,
        "failed": 0,
    }

    for target_channel_id, channel_name in channels:
        print()
        print("=" * 60)
        print(
            f"REFRESH: "
            f"{channel_name} "
            f"({target_channel_id})"
        )
        print("=" * 60)

        try:
            success = refresh_historical_channel(
                channel_id=target_channel_id,
                start_date=start_date,
                end_date=end_date,
            )

            if success:
                stats["completed"] += 1
                print(f"COMPLETED: {channel_name}")
            else:
                stats["failed"] += 1
                print(f"FAILED: {channel_name}")

        except Exception as exc:
            stats["failed"] += 1
            print(f"ERROR: {channel_name}: {exc}")

    return stats


def process_current_channels(
    channel_id: str | None = None,
) -> dict[str, int]:
    """最新の動画情報を同期する。

    channel_id が None の場合はCSV登録済みの全チャンネルを処理する。
    channel_id が指定された場合は、そのチャンネルのみ処理する。
    """
    channels = _get_target_channels(channel_id)

    stats = {
        "total": len(channels),
        "completed": 0,
        "failed": 0,
    }

    for target_channel_id, channel_name in channels:
        print()
        print("=" * 60)
        print(
            f"SYNC: "
            f"{channel_name} "
            f"({target_channel_id})"
        )
        print("=" * 60)

        try:
            success = sync_current_channel(
                channel_id=target_channel_id,
            )

            if success:
                stats["completed"] += 1
                print(f"COMPLETED: {channel_name}")
            else:
                stats["failed"] += 1
                print(f"FAILED: {channel_name}")

        except Exception as exc:
            stats["failed"] += 1
            print(f"ERROR: {channel_name}: {exc}")

    return stats
