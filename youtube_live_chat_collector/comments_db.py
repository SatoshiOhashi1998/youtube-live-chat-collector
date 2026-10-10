from __future__ import annotations

import os
import sqlite3
from typing import Iterable


class CommentsDB:
    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or os.getenv("COMMENTS_DB_PATH", "data/comments.db")
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        parent = os.path.dirname(os.path.abspath(self.db_path))
        if parent:
            os.makedirs(parent, exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS live_chat_jobs (
                    video_id TEXT PRIMARY KEY,
                    completed INTEGER NOT NULL DEFAULT 0,
                    excluded INTEGER NOT NULL DEFAULT 0,
                    CHECK (completed IN (0, 1)),
                    CHECK (excluded IN (0, 1))
                )
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS comments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    comment TEXT NOT NULL,
                    author_name TEXT NOT NULL,
                    title TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    url TEXT NOT NULL,
                    date TEXT,
                    UNIQUE(video_id, timestamp, author_name, comment)
                )
                """
            )

            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_jobs_completed "
                "ON live_chat_jobs(completed, excluded)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_comments_video_id "
                "ON comments(video_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_comments_channel "
                "ON comments(channel)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_comments_date "
                "ON comments(date)"
            )

    def ensure_job(self, video_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO live_chat_jobs(video_id, completed, excluded)
                VALUES (?, 0, 0)
                """,
                (video_id,),
            )

    def ensure_jobs(self, video_ids: Iterable[str]) -> None:
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT OR IGNORE INTO live_chat_jobs(video_id, completed, excluded)
                VALUES (?, 0, 0)
                """,
                ((video_id,) for video_id in video_ids),
            )

    def get_job(self, video_id: str) -> sqlite3.Row | None:
        with self._connect() as conn:
            return conn.execute(
                "SELECT * FROM live_chat_jobs WHERE video_id = ?",
                (video_id,),
            ).fetchone()

    def is_completed(self, video_id: str) -> bool:
        job = self.get_job(video_id)
        return bool(job and job["completed"])

    def is_excluded(self, video_id: str) -> bool:
        job = self.get_job(video_id)
        return bool(job and job["excluded"])

    def mark_completed(self, video_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO live_chat_jobs(video_id, completed, excluded)
                VALUES (?, 1, 0)
                ON CONFLICT(video_id) DO UPDATE SET
                    completed = 1,
                    excluded = 0
                """,
                (video_id,),
            )

    def mark_excluded(self, video_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO live_chat_jobs(video_id, completed, excluded)
                VALUES (?, 0, 1)
                ON CONFLICT(video_id) DO UPDATE SET
                    completed = 0,
                    excluded = 1
                """,
                (video_id,),
            )

    def save_comments(self, comments: list[dict]) -> None:
        if not comments:
            return

        rows = [
            (
                comment["video_id"],
                comment["timestamp"],
                comment["comment"],
                comment["author_name"],
                comment["title"],
                comment["channel"],
                comment["url"],
                comment.get("date"),
            )
            for comment in comments
        ]

        with self._connect() as conn:
            conn.executemany(
                """
                INSERT OR IGNORE INTO comments(
                    video_id,
                    timestamp,
                    comment,
                    author_name,
                    title,
                    channel,
                    url,
                    date
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

    def search_comments(
        self,
        channel: str | None = None,
        keyword: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[sqlite3.Row]:
        """条件を指定してコメントを検索する。

        Args:
            channel: チャンネル名による絞り込み。
            keyword: コメント本文に含まれるキーワード。
            start_date: 検索開始日（YYYY-MM-DD）。指定日を含む。
            end_date: 検索終了日（YYYY-MM-DD）。指定日を含む。

        Returns:
            条件に一致するコメントのリスト。
            date、id の昇順で返す。
        """
        query = "SELECT * FROM comments WHERE 1=1"
        params: list[str] = []

        if channel:
            query += " AND channel = ?"
            params.append(channel)

        if keyword:
            query += " AND comment LIKE ?"
            params.append(f"%{keyword}%")

        if start_date:
            query += " AND date >= ?"
            params.append(start_date)

        if end_date:
            query += " AND date <= ?"
            params.append(end_date)

        query += " ORDER BY date ASC, id ASC"

        with self._connect() as conn:
            return conn.execute(query, params).fetchall()

    def get_all_comments(self) -> list[sqlite3.Row]:
        with self._connect() as conn:
            return conn.execute(
                "SELECT * FROM comments ORDER BY date ASC, id ASC"
            ).fetchall()

    def debug_summary(self) -> None:
        """DBのパスと、テーブル・処理状態ごとの件数を出力する。"""
        print("\n" + "=" * 60)
        print("DEBUG: CommentsDB Summary")
        print("=" * 60)
        print(f"DB path: {os.path.abspath(self.db_path)}")

        with self._connect() as conn:
            job_count = conn.execute(
                "SELECT COUNT(*) FROM live_chat_jobs"
            ).fetchone()[0]

            comment_count = conn.execute(
                "SELECT COUNT(*) FROM comments"
            ).fetchone()[0]

            print(f"動画ジョブ総数: {job_count}")
            print(f"コメント総数: {comment_count}")

            rows = conn.execute(
                """
                SELECT completed, excluded, COUNT(*) AS count
                FROM live_chat_jobs
                GROUP BY completed, excluded
                ORDER BY completed, excluded
                """
            ).fetchall()

            print("\n--- 処理状態の内訳 ---")
            for row in rows:
                print(
                    f"completed={row['completed']}, "
                    f"excluded={row['excluded']}: "
                    f"{row['count']} 件"
                )

        print("=" * 60)

    def debug_jobs(
        self,
        completed: int | None = None,
        excluded: int | None = None,
        limit: int = 100,
    ) -> None:
        """動画ごとの処理状態を一覧表示する。"""
        query = """
            SELECT video_id, completed, excluded
            FROM live_chat_jobs
            WHERE 1=1
        """
        params = []

        if completed is not None:
            query += " AND completed = ?"
            params.append(completed)

        if excluded is not None:
            query += " AND excluded = ?"
            params.append(excluded)

        query += " ORDER BY video_id LIMIT ?"
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()

        print("\n--- DEBUG: Live Chat Jobs ---")
        print(f"表示件数: {len(rows)}")

        for row in rows:
            print(
                f"video_id={row['video_id']}, "
                f"completed={row['completed']}, "
                f"excluded={row['excluded']}"
            )

    def debug_video(self, video_id: str) -> None:
        """指定動画の処理状態と保存済みコメントを確認する。"""
        print("\n" + "=" * 60)
        print(f"DEBUG: Video {video_id}")
        print("=" * 60)

        with self._connect() as conn:
            job = conn.execute(
                """
                SELECT *
                FROM live_chat_jobs
                WHERE video_id = ?
                """,
                (video_id,),
            ).fetchone()

            comment_count = conn.execute(
                """
                SELECT COUNT(*)
                FROM comments
                WHERE video_id = ?
                """,
                (video_id,),
            ).fetchone()[0]

            if job is None:
                print("ジョブ: DBに登録されていません")
            else:
                print(f"completed: {job['completed']}")
                print(f"excluded:  {job['excluded']}")

            print(f"保存済みコメント数: {comment_count}")

            latest_comments = conn.execute(
                """
                SELECT timestamp, author_name, comment
                FROM comments
                WHERE video_id = ?
                ORDER BY id DESC
                LIMIT 5
                """,
                (video_id,),
            ).fetchall()

            print("\n--- 最新の保存コメント（最大5件） ---")
            for row in latest_comments:
                print(
                    f"[{row['timestamp']}] "
                    f"{row['author_name']}: {row['comment']}"
                )

        print("=" * 60)

    def debug_check_jobs(self) -> None:
        """ジョブとコメントの状態に不整合がないか確認する。"""
        print("\n" + "=" * 60)
        print("DEBUG: Job Consistency Check")
        print("=" * 60)

        with self._connect() as conn:
            # completed と excluded が同時に1のジョブ
            conflicting_jobs = conn.execute(
                """
                SELECT video_id, completed, excluded
                FROM live_chat_jobs
                WHERE completed = 1 AND excluded = 1
                """
            ).fetchall()

            print(
                "\n[1] completed=1 かつ excluded=1:",
                len(conflicting_jobs),
                "件",
            )
            for row in conflicting_jobs:
                print(dict(row))

            # コメントが存在するが、ジョブが存在しない動画
            orphan_comments = conn.execute(
                """
                SELECT c.video_id, COUNT(*) AS comment_count
                FROM comments AS c
                LEFT JOIN live_chat_jobs AS j
                    ON c.video_id = j.video_id
                WHERE j.video_id IS NULL
                GROUP BY c.video_id
                """
            ).fetchall()

            print(
                "\n[2] ジョブ未登録の動画に保存されたコメント:",
                len(orphan_comments),
                "動画",
            )
            for row in orphan_comments:
                print(
                    f"video_id={row['video_id']}, "
                    f"comments={row['comment_count']}"
                )

        print("=" * 60)
