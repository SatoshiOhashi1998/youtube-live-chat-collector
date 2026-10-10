from datetime import date, timedelta
import argparse

from youtube_live_chat_collector.comments_db import CommentsDB
from youtube_live_chat_collector.config import (
    CHANNEL_DATAS,
    FILTERED_DATA,
)
from youtube_live_chat_collector.exporter import export_comments_to_csv
from youtube_live_chat_collector.pipeline import (
    process_channel,
    process_channels,
    process_historical_channels,
)

from youtube_live_chat_collector.runner import run_current

# ============================================================
# Historical collection
# ============================================================

START_DATE = "2018-01-01"


def run_historical(
    channel_id=None,
    start_date=START_DATE,
    end_date=None,
):
    """過去のライブチャットを収集する。"""
    if end_date is None:
        end_date = (date.today() - timedelta(days=1)).isoformat()

    date.fromisoformat(start_date)
    date.fromisoformat(end_date)

    if start_date > end_date:
        raise ValueError("開始日は終了日以前の日付を指定してください。")

    channels = CHANNEL_DATAS

    if channel_id:
        channels = [
            channel
            for channel in CHANNEL_DATAS
            if channel.channel_id == channel_id
        ]

        if not channels:
            raise ValueError(
                f"チャンネルが見つかりません: {channel_id}"
            )

    print("=== 過去のライブチャット収集 ===")
    print(f"開始日: {start_date}")
    print(f"終了日: {end_date}")
    print(f"対象チャンネル数: {len(channels)}")

    process_historical_channels(
        channels=channels,
        start_date=start_date,
        end_date=end_date,
    )


# ============================================================
# Interactive collection
# ============================================================

def _input_date(prompt, default=None):
    """対話形式で日付を入力する。空欄ならデフォルト値を使う。"""
    while True:
        suffix = f" [{default}]" if default else ""
        value = input(
            f"{prompt} (YYYY-MM-DD){suffix}: "
        ).strip()

        if not value and default:
            return default

        if not value:
            return None

        try:
            date.fromisoformat(value)
            return value
        except ValueError:
            print("日付の形式が正しくありません。")


def interactive_mode():
    """対話形式でチャンネルと期間を指定して収集する。"""
    print("\n=== チャンネル選択 ===")

    for index, channel in enumerate(CHANNEL_DATAS, start=1):
        print(f"{index}. {channel.channel_name}")

    query = input(
        "\nチャンネル名の一部を入力してください: "
    ).strip()

    matched_channels = [
        channel
        for channel in CHANNEL_DATAS
        if query.lower() in channel.channel_name.lower()
    ]

    if not matched_channels:
        print("該当するチャンネルがありません。")
        return

    for index, channel in enumerate(matched_channels, start=1):
        print(f"{index}. {channel.channel_name}")

    if len(matched_channels) == 1:
        channel = matched_channels[0]
    else:
        try:
            selected = int(input("番号を選択してください: "))
            channel = matched_channels[selected - 1]
        except (ValueError, IndexError):
            print("選択が正しくありません。")
            return

    start_date = _input_date(
        "開始日",
        default=START_DATE,
    )
    end_date = _input_date(
        "終了日",
        default=(date.today() - timedelta(days=1)).isoformat(),
    )

    if not start_date or not end_date:
        print("開始日と終了日を指定してください。")
        return

    if start_date > end_date:
        print("開始日は終了日以前の日付を指定してください。")
        return

    process_channel(
        channel=channel,
        start_date=start_date,
        end_date=end_date,
    )

    export_comments_to_csv(
        output_csv=FILTERED_DATA,
        channel=channel.channel_name,
        start_date=start_date,
        end_date=end_date,
    )


def run_all_channels():
    """全チャンネルを指定期間で収集する。"""
    start_date = _input_date(
        "開始日",
        default=START_DATE,
    )
    end_date = _input_date(
        "終了日",
        default=(date.today() - timedelta(days=1)).isoformat(),
    )

    if not start_date or not end_date:
        print("開始日と終了日を指定してください。")
        return

    if start_date > end_date:
        print("開始日は終了日以前の日付を指定してください。")
        return

    process_channels(
        channels=CHANNEL_DATAS,
        start_date=start_date,
        end_date=end_date,
    )

    export_comments_to_csv(
        output_csv=FILTERED_DATA,
        start_date=start_date,
        end_date=end_date,
    )


# ============================================================
# CSV export
# ============================================================

def _parse_list(value):
    """
    カンマ区切り文字列をリストに変換する。

    例:
        "A"       -> ["A"]
        "A,B"     -> ["A", "B"]
        None      -> None
    """
    if value is None:
        return None

    if isinstance(value, list):
        values = value
    else:
        values = value.split(",")

    result = [
        item.strip()
        for item in values
        if item and item.strip()
    ]

    return result or None


def _input_list(prompt):
    """カンマ区切りで複数の値を入力する。"""
    value = input(
        f"{prompt}（複数指定はカンマ区切り、空欄は指定なし）: "
    ).strip()

    return _parse_list(value)


def _input_export_date(prompt):
    """CSV出力用の日付入力。空欄は指定なし。"""
    while True:
        value = input(
            f"{prompt}（YYYY-MM-DD、空欄は指定なし）: "
        ).strip()

        if not value:
            return None

        try:
            date.fromisoformat(value)
            return value
        except ValueError:
            print("日付の形式が正しくありません。")


def export_csv(
    output_csv=FILTERED_DATA,
    channel=None,
    keyword=None,
    start_date=None,
    end_date=None,
):
    """指定条件に一致するコメントをCSV出力する。"""
    channel = _parse_list(channel)
    keyword = _parse_list(keyword)

    if start_date:
        date.fromisoformat(start_date)

    if end_date:
        date.fromisoformat(end_date)

    if start_date and end_date and start_date > end_date:
        raise ValueError("開始日は終了日以前の日付を指定してください。")

    export_comments_to_csv(
        output_csv=output_csv,
        channel=channel,
        keyword=keyword,
        start_date=start_date,
        end_date=end_date,
    )


def interactive_export():
    """対話形式で条件を指定してCSV出力する。"""
    print("\n=== コメントの条件指定出力 ===")

    channels = _input_list("チャンネル名")
    keywords = _input_list("コメントのキーワード")
    start_date = _input_export_date("開始日")
    end_date = _input_export_date("終了日")

    output_csv = input(
        f"出力先（空欄は {FILTERED_DATA}）: "
    ).strip() or FILTERED_DATA

    if start_date and end_date and start_date > end_date:
        print("開始日は終了日以前の日付を指定してください。")
        return

    print("\n=== 出力条件 ===")
    print(f"チャンネル: {channels or '指定なし'}")
    print(f"キーワード: {keywords or '指定なし'}")
    print(f"開始日: {start_date or '指定なし'}")
    print(f"終了日: {end_date or '指定なし'}")
    print(f"出力先: {output_csv}")

    confirm = input(
        "この条件で出力しますか？ (y/N): "
    ).strip().lower()

    if confirm != "y":
        print("出力をキャンセルしました。")
        return

    export_csv(
        output_csv=output_csv,
        channel=channels,
        keyword=keywords,
        start_date=start_date,
        end_date=end_date,
    )


def export_all_csv(output_csv="comments_all.csv"):
    """条件を指定せず、DB内の全コメントをCSV出力する。"""
    export_comments_to_csv(
        output_csv=output_csv,
    )


# ============================================================
# Database debug
# ============================================================

def debug_db():
    """DBの状態を確認する。"""
    db = CommentsDB()

    print("\n=== DB Summary ===")
    db.debug_summary()

    print("\n=== Job Summary ===")
    db.debug_jobs()

    print("\n=== Job Consistency Check ===")
    db.debug_check_jobs()


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="YouTube Live Chat Collector"
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    # --------------------------------------------------------
    # Current collection
    # --------------------------------------------------------
    current_parser = subparsers.add_parser(
        "current",
        help="現在のライブチャットを収集する",
    )
    current_parser.add_argument(
        "--channel-id",
        help="対象チャンネルID",
    )

    # --------------------------------------------------------
    # Historical collection
    # --------------------------------------------------------
    historical_parser = subparsers.add_parser(
        "historical",
        help="過去のライブチャットを収集する",
    )
    historical_parser.add_argument(
        "--channel-id",
        help="対象チャンネルID。省略時は全チャンネル",
    )
    historical_parser.add_argument(
        "--start-date",
        default=START_DATE,
        help="開始日 YYYY-MM-DD",
    )
    historical_parser.add_argument(
        "--end-date",
        help="終了日 YYYY-MM-DD。省略時は昨日",
    )

    # --------------------------------------------------------
    # Interactive collection
    # --------------------------------------------------------
    subparsers.add_parser(
        "interactive",
        help="対話形式でチャンネルと期間を指定して収集する",
    )

    # --------------------------------------------------------
    # All-channel collection
    # --------------------------------------------------------
    subparsers.add_parser(
        "all",
        help="全チャンネルを対話形式で収集する",
    )

    # --------------------------------------------------------
    # Filtered CSV export
    # --------------------------------------------------------
    export_parser = subparsers.add_parser(
        "export",
        help="条件を指定してコメントをCSV出力する",
    )
    export_parser.add_argument(
        "--channel",
        action="append",
        help="チャンネル名。複数指定・カンマ区切りに対応",
    )
    export_parser.add_argument(
        "--keyword",
        action="append",
        help="コメントのキーワード。複数指定・カンマ区切りに対応",
    )
    export_parser.add_argument(
        "--start-date",
        help="開始日 YYYY-MM-DD",
    )
    export_parser.add_argument(
        "--end-date",
        help="終了日 YYYY-MM-DD",
    )
    export_parser.add_argument(
        "--output",
        default=FILTERED_DATA,
        help="出力先CSVファイル",
    )
    export_parser.add_argument(
        "--interactive",
        action="store_true",
        help="対話形式で条件を指定する",
    )

    # --------------------------------------------------------
    # Export all comments
    # --------------------------------------------------------
    export_all_parser = subparsers.add_parser(
        "export-all",
        help="DB内の全コメントをCSV出力する",
    )
    export_all_parser.add_argument(
        "--output",
        default="comments_all.csv",
        help="出力先CSVファイル",
    )

    # --------------------------------------------------------
    # Database debug
    # --------------------------------------------------------
    subparsers.add_parser(
        "debug",
        help="DBの状態を確認する",
    )

    args = parser.parse_args()

    if args.command == "current":
        if args.channel_id:
            run_current(args.channel_id)
        else:
            run_current()

    elif args.command == "historical":
        run_historical(
            channel_id=args.channel_id,
            start_date=args.start_date,
            end_date=args.end_date,
        )

    elif args.command == "interactive":
        interactive_mode()

    elif args.command == "all":
        run_all_channels()

    elif args.command == "export":
        if args.interactive:
            interactive_export()
        else:
            channels = _parse_list(args.channel)
            keywords = _parse_list(args.keyword)

            export_csv(
                output_csv=args.output,
                channel=channels,
                keyword=keywords,
                start_date=args.start_date,
                end_date=args.end_date,
            )

    elif args.command == "export-all":
        export_all_csv(
            output_csv=args.output,
        )

    elif args.command == "debug":
        debug_db()


if __name__ == "__main__":
    main()
