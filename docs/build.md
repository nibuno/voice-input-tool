# macOS アプリのビルド

## ビルド手順

```bash
# PyInstaller をインストール（未インストールの場合）
uv pip install pyinstaller

# ビルド実行
uv run pyinstaller VoiceInput.spec
```

## 出力

ビルド後、`dist/VoiceInput.app` が作成される。

### 起動テスト

```bash
# コンソールから起動（エラー確認用）
dist/VoiceInput.app/Contents/MacOS/VoiceInput

# または Finder から起動
open dist/VoiceInput.app
```

### インストール

```bash
cp -r dist/VoiceInput.app /Applications/
```

## 設計判断

### PyInstaller ビルドに `__main__.py` を使用

`VoiceInput.spec` では `__main__.py` をエントリーポイントとして指定している。

**背景**: voice_input パッケージは相対インポート（`from .config import ...`）を使用している。

**問題**: PyInstaller が `app.py` を直接エントリーポイントに指定すると、パッケージのメンバーとして認識されず、相対インポートが解決できない。

**解決**: `__main__.py` を作成し、絶対インポート（`from voice_input.app import main`）で app.py を呼び出す。PyInstaller はこれをパッケージエントリーポイントとして正しく処理する。
