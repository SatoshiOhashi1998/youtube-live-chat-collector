from .config import validate
from .pipeline import process_current_channels


def run_current(
    channel_id: str | None = None,
) -> dict[str, int]:
    """最新の動画情報を同期する。

    Args:
        channel_id:
            指定した場合はそのチャンネルのみ処理する。
            None の場合はCSV登録済みの全チャンネルを処理する。

    Returns:
        処理結果の統計情報。
    """
    validate()

    stats = process_current_channels(
        channel_id=channel_id,
    )

    print()
    print("=== Current sync ===")
    print(f"channel:  {channel_id or 'all'}")
    print(f"success:  {stats['completed']}")
    print(f"failed:   {stats['failed']}")
    print(f"total:    {stats['total']}")

    return stats
