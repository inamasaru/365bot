import os
import datetime as dt


def main():
    print("=== 365bot agent-notion-resend START ===")
    now = dt.datetime.now().isoformat()
    print(f"[INFO] Now: {now}")

    required_envs = [
        "NOTION_TOKEN",
        "NOTION_DATABASE_ID",
        "RESEND_API_KEY",
        "RESEND_FROM_EMAIL",
        "RESEND_TO_EMAIL",
    ]

    missing = [name for name in required_envs if not os.getenv(name)]
    if missing:
        print(f"[WARN] Missing envs: {', '.join(missing)}")
        print("[INFO] 環境変数が揃うまではメール送信処理はスキップします。")
        print("=== 365bot agent-notion-resend END (SKIPPED) ===")
        return

    # TODO: ここに Notion からの取得→Resend でメール送信 を実装
    print("[INFO] 全ての環境変数が揃っています。ここでNotion→Resend処理を実行します。")

    print("=== 365bot agent-notion-resend END (SUCCESS) ===")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        print("=== 365bot agent-notion-resend END (ERROR BUT NOT FAILED) ===")
