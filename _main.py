from myutils.youtube_api import YouTubeDB

from modules.config import FILTERED_DATA, validate
from modules.exporter import export_comments_to_csv
from modules.pipeline import process_historical_channels


def inspect_youtube_database():
    db = YouTubeDB()

    db.print_table("channels")
    db.print_table("channel_sync_state")
    db.print_channel_video_summary()


def run_historical():
    validate()

    start_date = "2018-01-01"
    end_date = "2026-09-30"

    stats = process_historical_channels(
        start_date=start_date,
        end_date=end_date,
    )

    print()
    print("=== Historical refresh ===")
    print(f"success: {stats['completed']}")
    print(f"failed:  {stats['failed']}")
    print(f"total:   {stats['total']}")


def main():
    export_comments_to_csv(FILTERED_DATA)


if __name__ == "__main__":
    # main()
    run_historical()
    # inspect_youtube_database()