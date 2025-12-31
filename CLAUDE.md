# Voice Input Tool

macOS 用の音声入力ツール。OpenAI Whisper API を使用して音声をテキストに変換し、アクティブなアプリケーションにペーストする。

## 設計判断

### ペースト処理に AppleScript を使用

`output.py` では `pyautogui` ではなく `osascript`（AppleScript）を使用してペーストしている。

**背景**: pynput（ホットキー検出）と pyautogui（キー送信）が両方 macOS の Quartz API を使用するため干渉が発生する。

**問題**: pynput のキーボードリスナーが動作中に `pyautogui.hotkey("command", "v")` を実行すると、Cmd キーが無視されて「v」だけが入力される。

**解決**: AppleScript は別プロセス（osascript）で実行されるため、pynput との干渉を回避できる。

参照: Issue #3

### 録音停止時のタイムアウト

`recorder.py` では `stream.abort()` を別スレッドで実行し、1秒のタイムアウトを設定している。

**背景**: sounddevice の `stop()` や `abort()` が稀にハングすることがある。

**問題**: 録音停止時に処理が進まなくなり、アプリが使用不能になる。

**解決**: タイムアウト付きで実行し、ハング時は警告ログを出して強制的に次の処理へ進む。

参照: Issue #9（#7 を統合）

### バッファ管理に queue.Queue を使用

`recorder.py` では `threading.Lock` ではなく `queue.Queue` を使用してオーディオバッファを管理している。

**背景**: オーディオコールバックは別スレッドで実行されるため、スレッドセーフなデータ受け渡しが必要。

**理由**: `queue.Queue` はロックフリーでスレッドセーフであり、コールバック内でのブロッキングを最小化できる。
