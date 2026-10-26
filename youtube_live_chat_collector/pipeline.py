"""動画同期からライブチャット取得・コメント保存までのパイプライン。"""

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
from myutils.youtube_api import YouTubeAPI, create_youtube_api


_VIDEO_STATS_TEMPLATE = {
    "total": 0,
    "completed": 0,
    "excluded": 0,
    "retry": 0,
}


def _process_videos(
    videos: list[dict],
    keywords: list[str],
    db: CommentsDB,
) -> dict[str, int]:
    """取得済み動画一覧に対して、チャット取得からDB保存まで行う。"""
    db.ensure_jobs(video["video_id"] for video in videos)
    stats = {**_VIDEO_STATS_TEMPLATE, "total": len(videos)}

    for video in videos:
        video_id = video["video_id"]
        title = video.get("title", "")

        if db.is_completed(video_id):
            stats["completed"] += 1
            print(f"SKIP completed: {video_id} {title}")
            continue

        if db.is_excluded(video_id):
            stats["excluded"] += 1
            print(f"SKIP excluded: {video_id} {title}")
            continue

        if not video["is_live_broadcast"]:
            db.mark_excluded(video_id)
            stats["excluded"] += 1
            print(f"EXCLUDE non-live: {video_id} {title}")
            continue

        print(f"PROCESS: {video_id} {title}")
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

            # コメントのDB保存に成功してから、一時JSONとジョブ状態を更新する。
            delete_video_json(video_id, JSON_DIRECTORY)
            db.mark_completed(video_id)
            stats["completed"] += 1
            print(f"COMPLETED: {video_id} comments={len(comments)}")

        except Exception as exc:
            # 保存や抽出に失敗した場合は未完了のままにして次回再試行する。
            stats["retry"] += 1
            print(f"ERROR: {video_id}: {exc}")

    return stats


def process_channel(
    channel_id: str,
    start_date,
    end_date,
    keywords: list[str] | None = None,
    db: CommentsDB | None = None,
    *,
    sync_metadata: bool = True,
    end_date_is_day: bool = True,
    date_bounds_are_utc: bool = False,
    api: YouTubeAPI | None = None,
) -> dict[str, int]:
    """指定チャンネルの動画を取得し、ライブチャットを処理する。

    通常の期間指定収集では sync_metadata=True のまま使用する。
    current のように、先行する同期処理が完了している場合は False を指定し、
    同じ範囲の動画メタデータをもう一度同期しない。
    """
    selected_keywords = (
        keywords if keywords is not None else COMMENT_KEYWORDS
    )
    if db is None:
        db = CommentsDB()

    videos = get_target_videos(
        channel_id=channel_id,
        start_date=start_date,
        end_date=end_date,
        api=api,
        sync_metadata=sync_metadata,
        end_date_is_day=end_date_is_day,
        date_bounds_are_utc=date_bounds_are_utc,
    )
    return _process_videos(videos, selected_keywords, db)


def process_channels(
    channels: list[Channel],
    start_date,
    end_date,
    keywords: list[str] | None = None,
    db: CommentsDB | None = None,
) -> dict[str, int]:
    """複数チャンネルの指定期間の動画を処理する。"""
    if db is None:
        db = CommentsDB()

    total_stats = dict(_VIDEO_STATS_TEMPLATE)

    for channel in channels:
        print("\n" + "=" * 60)
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
    """CSV登録状態とチャンネルID指定に応じて対象チャンネルを返す。"""
    channels = get_channels(CHANNEL_DATAS)

    if channel_id is None:
        return [
            (channel.channel_id, channel.channel_name)
            for channel in channels
        ]

    normalized_id = channel_id.strip()
    if not normalized_id:
        raise ValueError("channel_id に空文字列は指定できません。")

    for channel in channels:
        if channel.channel_id == normalized_id:
            return [(channel.channel_id, channel.channel_name)]

    # CSV未登録チャンネルもIDで指定できるようにする。
    return [(normalized_id, normalized_id)]


def process_historical_channels(
    start_date,
    end_date,
    channel_id: str | None = None,
) -> dict[str, int]:
    """指定したチャンネルの過去動画情報を更新する。"""
    channels = _get_target_channels(channel_id)
    stats = {"total": len(channels), "completed": 0, "failed": 0}

    for target_channel_id, channel_name in channels:
        print("\n" + "=" * 60)
        print(f"REFRESH: {channel_name} ({target_channel_id})")
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
    """最新の動画情報を同期し、その新規同期範囲のライブチャットを保存する。

    チャンネルごとに、メタデータ同期 -> 同じ範囲の動画読み出し ->
    チャット取得 -> コメント抽出 -> DB保存、の順で実行する。
    """
    channels = _get_target_channels(channel_id)
    stats = {
        "total": len(channels),
        "completed": 0,
        "failed": 0,
        "videos_total": 0,
        "videos_completed": 0,
        "videos_excluded": 0,
        "videos_retry": 0,
    }
    db = CommentsDB()

    for target_channel_id, channel_name in channels:
        print("\n" + "=" * 60)
        print(f"CURRENT: {channel_name} ({target_channel_id})")
        print("=" * 60)

        try:
            # 同期に使ったAPIインスタンスを、DBから動画一覧を読む処理にも再利用する。
            api = create_youtube_api()
            sync_result = sync_current_channel(
                channel_id=target_channel_id,
                api=api,
            )

            if not sync_result.success:
                stats["failed"] += 1
                print(
                    f"SYNC FAILED: {channel_name}: "
                    f"{sync_result.reason or 'unknown error'}"
                )
                continue

            if not sync_result.start_date or not sync_result.end_date:
                stats["completed"] += 1
                print(
                    f"NO NEW RANGE: {channel_name}; "
                    "チャット取得をスキップします。"
                )
                continue

            chat_stats = process_channel(
                channel_id=target_channel_id,
                start_date=sync_result.start_date,
                end_date=sync_result.end_date,
                db=db,
                sync_metadata=False,
                date_bounds_are_utc=True,
                api=api,
            )

            stats["completed"] += 1
            stats["videos_total"] += chat_stats["total"]
            stats["videos_completed"] += chat_stats["completed"]
            stats["videos_excluded"] += chat_stats["excluded"]
            stats["videos_retry"] += chat_stats["retry"]

            print(
                f"CURRENT DONE: {channel_name} "
                f"videos={chat_stats['total']} "
                f"completed={chat_stats['completed']} "
                f"excluded={chat_stats['excluded']} "
                f"retry={chat_stats['retry']}"
            )

        except Exception as exc:
            stats["failed"] += 1
            print(f"ERROR: {channel_name}: {exc}")

    return stats
