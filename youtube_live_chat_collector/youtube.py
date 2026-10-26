"""YouTube動画メタデータの同期と対象動画の取得。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from myutils.youtube_api import YouTubeAPI, create_youtube_api, to_utc_z


@dataclass(frozen=True)
class CurrentSyncResult:
    """最新動画情報の同期結果。

    start_date / end_date は今回同期対象とした UTC の境界時刻。
    新しい同期範囲がない場合は、success=True かつ両方 None になる。
    """

    success: bool
    start_date: str | None = None
    end_date: str | None = None
    reason: str | None = None


def _build_video_records(
    channel_id: str,
    start: str,
    end: str,
    api: YouTubeAPI,
) -> list[dict]:
    """DB内の動画レコードを、チャット処理用の辞書に変換する。

    この関数は動画メタデータの同期を行わない。
    """
    rows = api.db.get_videos_by_channel_and_date(
        channel_id,
        start,
        end,
    )

    video_ids = [row[0] for row in rows]
    live_broadcast_video_ids = set(
        api.get_live_broadcast_video_ids(video_ids)
    )

    videos: list[dict] = []
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
                "is_live_broadcast": video_id in live_broadcast_video_ids,
                "url": f"https://www.youtube.com/watch?v={video_id}",
            }
        )

    return videos


def get_target_videos(
    channel_id: str,
    start_date: str | date | datetime,
    end_date: str | date | datetime,
    api: YouTubeAPI | None = None,
    *,
    sync_metadata: bool = True,
    end_date_is_day: bool = True,
    date_bounds_are_utc: bool = False,
) -> list[dict]:
    """指定期間の動画を取得する。

    Args:
        channel_id: 対象チャンネルID。
        start_date: 取得期間の開始。
        end_date: 取得期間の終了。
        api: 再利用する YouTubeAPI。省略時は新規作成する。
        sync_metadata: True の場合は、先に動画メタデータを同期する。
            current 同期後に同じ範囲の動画を処理するときは False を指定し、
            メタデータの二重同期を防ぐ。
        end_date_is_day: 日付形式の end_date を指定日の終端として扱う。
        date_bounds_are_utc: True の場合、start_date / end_date を既に正規化済みの
            UTC文字列としてそのまま使用する。同期処理で決まった範囲を再利用する
            current の経路で指定し、境界時刻の再変換や丸めを避ける。
    """
    if api is None:
        api = create_youtube_api()

    if date_bounds_are_utc:
        start = str(start_date)
        end = str(end_date)
    else:
        start = to_utc_z(start_date)
        end = to_utc_z(end_date, end_date=end_date_is_day)

    if sync_metadata:
        api.sync_channel_videos(
            channel_id,
            start_date=start,
            end_date=end,
        )

    return _build_video_records(
        channel_id=channel_id,
        start=start,
        end=end,
        api=api,
    )


def refresh_historical_channel(
    channel_id: str,
    start_date: str | date | datetime,
    end_date: str | date | datetime,
    api: YouTubeAPI | None = None,
) -> bool:
    """指定期間の動画情報をAPIから再取得してDBへ保存する。

    既存の同期状態は取得判定に使用しない。
    """
    if api is None:
        api = create_youtube_api()

    start = to_utc_z(start_date)
    end = to_utc_z(end_date, end_date=True)

    return api.refresh_channel_videos(
        channel_id,
        start_date=start,
        end_date=end,
    )


def sync_current_channel(
    channel_id: str,
    api: YouTubeAPI | None = None,
) -> CurrentSyncResult:
    """未同期の最新期間の動画情報を同期し、同期範囲を返す。

    同期状態がない場合は失敗を返す。同期対象期間がすでに空の場合は
    成功扱いとし、start_date / end_date を None にしてチャット処理を省く。
    """
    if api is None:
        api = create_youtube_api()

    state = api.db.get_channel_sync_state(channel_id)
    if not state:
        return CurrentSyncResult(
            success=False,
            reason="同期状態がDBにありません。先に過去動画情報を同期してください。",
        )

    newest_synced_at = state[3]
    if not newest_synced_at:
        return CurrentSyncResult(
            success=False,
            reason="最新の同期時刻がDBにありません。",
        )

    start = to_utc_z(newest_synced_at)
    end = to_utc_z(datetime.now(UTC) - timedelta(days=1))

    # 取得対象がない場合は、同期成功として扱うがチャット処理は行わない。
    if start >= end:
        return CurrentSyncResult(
            success=True,
            reason="新しく同期する期間はありません。",
        )

    success = api.sync_channel_videos(
        channel_id,
        start_date=start,
        end_date=end,
    )

    return CurrentSyncResult(
        success=bool(success),
        start_date=start,
        end_date=end,
        reason=None if success else "動画メタデータの同期に失敗しました。",
    )
