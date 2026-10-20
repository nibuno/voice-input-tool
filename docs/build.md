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

権限設定画面だけを確認する場合は、APIキーを設定せずに起動できる。
録音や権限の要求は、起動しただけでは行わない。

```bash
dist/VoiceInput.app/Contents/MacOS/VoiceInput --setup
```

ログの `Permission setup shown` で `visible=True` と3つの権限の状態を確認する。
`UNKNOWN` やフレームワークの読み込みエラーが出た場合は、
依存関係と同梱設定を修正してから配布する。

署名時に `resource fork, Finder information, or similar detritus not allowed`
が出る場合は、出力先の拡張属性が署名を妨げている。
別のフォルダへ書き出してビルドと署名検証を行う。

```bash
uv run pyinstaller VoiceInput.spec -y --distpath /private/tmp/voice-input-build-check
codesign --verify --deep --strict /private/tmp/voice-input-build-check/VoiceInput.app
/private/tmp/voice-input-build-check/VoiceInput.app/Contents/MacOS/VoiceInput --setup
```

上記はローカルのビルド・起動確認であり、Developer ID署名や公証の確認は含まない。

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
