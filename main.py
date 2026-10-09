from datetime import date, timedelta

from youtube_live_chat_collector.config import FILTERED_DATA, validate
from youtube_live_chat_collector.exporter import export_comments_to_csv
from youtube_live_chat_collector.pipeline import (
process_current_channels,
process_historical_channels,
)

START_DATE = "2018-01-01"

def run_historical(
    channel_id: str | None = None,
    start_date: str = START_DATE,
    end_date: str | None = None,
    ) -> None:
    """過去動画の情報を更新する。

    Args:
        channel_id: 指定した場合はそのチャンネルのみ処理する。
                    None の場合はCSV登録済みの全チャンネルを処理する。
        start_date: 取得対象期間の開始日。デフォルトは2018-01-01。
        end_date: 取得対象期間の終了日。省略時は今日の前日。
    """
    validate()

    if end_date is None:
        end_date = (date.today() - timedelta(days=1)).isoformat()

    stats = process_historical_channels(
        start_date=start_date,
        end_date=end_date,
        channel_id=channel_id,
    )

    print()
    print("=== Historical refresh ===")
    print(f"period:   {start_date} - {end_date}")
    print(f"channel:  {channel_id or 'all'}")
    print(f"success:  {stats['completed']}")
    print(f"failed:   {stats['failed']}")
    print(f"total:    {stats['total']}")

def run_current(channel_id: str | None = None) -> None:
    """最新の動画情報を同期する。

    Args:
        channel_id: 指定した場合はそのチャンネルのみ処理する。
                    None の場合はCSV登録済みの全チャンネルを処理する。
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

def main():
    export_comments_to_csv(FILTERED_DATA)

if __name__ == "main":
    # CSV登録済みの全チャンネルを同期
    # run_current()

    # チャンネルIDを指定して同期
    # run_current("UCxxxxxxxxxxxxxxxxxxxxxx")

    # CSV登録済みの全チャンネルの過去情報を更新
    # run_historical()

    # チャンネルIDを指定して過去情報を更新
    # run_historical("UCxxxxxxxxxxxxxxxxxxxxxx")

    # 期間も指定して更新
    # run_historical(
    #     channel_id="UCxxxxxxxxxxxxxxxxxxxxxx",
    #     start_date="2024-01-01",
    #     end_date="2025-12-31",
    # )

    main()
