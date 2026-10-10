from datetime import date, timedelta
import argparse

from youtube_live_chat_collector.comments_db import CommentsDB
from youtube_live_chat_collector.config import (
    FILTERED_DATA,
    get_channels,
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
    """過去のライブチャットに関する処理を実行する。"""
    if end_date is None:
        end_date = (date.today() - timedelta(days=1)).isoformat()

    # 日付の形式を検証する
    date.fromisoformat(start_date)
    date.fromisoformat(end_date)

    if start_date > end_date:
        raise ValueError("開始日は終了日以前の日付を指定してください。")

    # チャンネルIDが指定されている場合はCSV登録済みか検証する
    channels = get_channels()

    if channel_id:
        matched_channels = [
            channel
            for channel in channels
            if channel.channel_id == channel_id
        ]

        if not matched_channels:
            raise ValueError(
                f"チャンネルが見つかりません: {channel_id}"
            )

        target_count = len(matched_channels)
    else:
        target_count = len(channels)

    print("=== 過去のライブチャット収集 ===")
    print(f"開始日: {start_date}")
    print(f"終了日: {end_date}")
    print(f"対象チャンネル数: {target_count}")

    # process_historical_channels は channel_id を受け取る
    process_historical_channels(
        start_date=start_date,
        end_date=end_date,
        channel_id=channel_id,
    )


# ============================================================
# Interactive collection
# ============================================================

def _input_date(prompt, default=None):
    """対話形式で日付を入力する。空欄ならデフォルト値を使う。"""
    while True:
        suffix = f" [{default}]" if default else ""
        value = input(
            f"{prompt} (YYYY-M-D){suffix}: "
        ).strip()

        if not value and default:
            return default

        if not value:
            return None

        try:
            return _parse_date(value).isoformat()
        except ValueError as exc:
            print(f"日付の形式が正しくありません: {exc}")


def interactive_mode():
    """対話形式でチャンネルと期間を指定して収集する。"""
    channels = get_channels()

    print("\n=== チャンネル選択 ===")

    if not channels:
        print("チャンネルが登録されていません。")
        return

    for index, channel in enumerate(channels, start=1):
        print(f"{index}. {channel.channel_name}")

    query = input(
        "\nチャンネル名の一部を入力してください: "
    ).strip()

    if not query:
        print("チャンネル名を入力してください。")
        return

    matched_channels = [
        channel
        for channel in channels
        if query.lower() in channel.channel_name.lower()
    ]

    if not matched_channels:
        print("該当するチャンネルがありません。")
        return

    print("\n=== 検索結果 ===")

    for index, channel in enumerate(matched_channels, start=1):
        print(f"{index}. {channel.channel_name}")

    if len(matched_channels) == 1:
        channel = matched_channels[0]
    else:
        try:
            selected = int(input("番号を選択してください: "))

            if not 1 <= selected <= len(matched_channels):
                raise ValueError

            channel = matched_channels[selected - 1]

        except ValueError:
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

    print("\n=== 収集条件 ===")
    print(f"チャンネル: {channel.channel_name}")
    print(f"チャンネルID: {channel.channel_id}")
    print(f"開始日: {start_date}")
    print(f"終了日: {end_date}")

    process_channel(
        channel_id=channel.channel_id,
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
    channels = get_channels()

    if not channels:
        print("チャンネルが登録されていません。")
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

    print("\n=== 全チャンネル収集 ===")
    print(f"対象チャンネル数: {len(channels)}")
    print(f"開始日: {start_date}")
    print(f"終了日: {end_date}")

    process_channels(
        channels=channels,
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

def _parse_date(value):
    """柔軟な形式の日付文字列を date に変換する。

    対応例:
        2025-1-1
        2025-01-1
        2025-1-01
        2025-01-01

    存在しない日付は ValueError になる。
    """
    parts = value.strip().split("-")

    if len(parts) != 3:
        raise ValueError("日付は YYYY-M-D の形式で入力してください。")

    try:
        year, month, day = map(int, parts)
        return date(year, month, day)
    except ValueError as exc:
        raise ValueError(
            "存在しない日付、または正しくない日付形式です。"
        ) from exc


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
            f"{prompt}（YYYY-M-D、空欄は指定なし）: "
        ).strip()

        if not value:
            return None

        try:
            return _parse_date(value).isoformat()
        except ValueError as exc:
            print(f"日付の形式が正しくありません: {exc}")


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
