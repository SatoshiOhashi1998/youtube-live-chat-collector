"""CLIなどから呼び出す実行入口。"""

from .config import validate
from .pipeline import process_current_channels


def run_current(
    channel_id: str | None = None,
) -> dict[str, int]:
    """最新動画の同期と、その新規同期範囲のライブチャット取得を実行する。

    Args:
        channel_id: 指定した場合はそのチャンネルのみ処理する。
            None の場合はCSV登録済みの全チャンネルを処理する。

    Returns:
        チャンネル単位の同期状況と動画単位のチャット処理統計。
    """
    validate()
    stats = process_current_channels(channel_id=channel_id)

    print("\n=== Current sync and live-chat collection ===")
    print(f"channels:        {channel_id or 'all'}")
    print(f"channel success: {stats['completed']}")
    print(f"channel failed:  {stats['failed']}")
    print(f"channel total:   {stats['total']}")
    print(f"videos found:    {stats['videos_total']}")
    print(f"videos complete: {stats['videos_completed']}")
    print(f"videos excluded: {stats['videos_excluded']}")
    print(f"videos retry:    {stats['videos_retry']}")

    return stats
