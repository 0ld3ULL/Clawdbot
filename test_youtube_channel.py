"""
Quick test to verify YouTube OAuth is connected to the correct channel.
Run this after re-authenticating to confirm you're on David Flip's channel.
"""

import sys
sys.path.insert(0, '.')

from tools.youtube_tool import YouTubeTool

def main():
    print("Testing YouTube channel authentication...")
    print("-" * 50)

    yt = YouTubeTool()

    # This will trigger OAuth if not authenticated
    print("\nGetting channel info (may open browser for OAuth)...")

    is_correct, message = yt.verify_channel()

    print(f"\nResult: {message}")
    print("-" * 50)

    if is_correct:
        print("SUCCESS! You're authenticated to the correct channel.")
        print("YouTube uploads will go to David Flip's channel.")

        # Show full channel info
        info = yt.get_channel_info()
        print(f"\nChannel: {info.get('title')}")
        print(f"ID: {info.get('channel_id')}")
        print(f"Videos: {info.get('video_count')}")
        print(f"Subscribers: {info.get('subscriber_count')}")
    else:
        print("FAILED! Wrong channel authenticated.")
        print("\nTo fix:")
        print("1. Delete data/youtube_token.pickle")
        print("2. Run this script again")
        print("3. Sign in with David Flip's Google account ONLY")

if __name__ == "__main__":
    main()
