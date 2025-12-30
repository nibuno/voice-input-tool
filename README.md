# Voice Input Tool

音声入力をテキストに変換するツール。OpenAI Whisper APIを使用して高精度な音声認識を実現します。

## 機能

- **メニューバーアプリ**: 設定したホットキーを押している間だけ録音（デフォルト: 左Control）
- **CLI**: 指定秒数の録音
- OpenAI Whisper APIによる音声→テキスト変換
- 変換したテキストをクリップボードにコピー＆自動ペースト

## 必要要件

- Python 3.13以上
- macOS（アクセシビリティ権限が必要）
- OpenAI APIキー

## インストール

```bash
# リポジトリをクローン
git clone https://github.com/nibuno/voice-input-tool.git
cd voice-input-tool

# 依存関係をインストール（uvを使用）
uv sync

# または pip を使用
pip install -e .
```

## 設定

### 環境変数

`.env.example` をコピーして `.env` を作成し、APIキーを設定します。

```bash
cp .env.example .env
```

`.env` ファイルを編集:

```
OPENAI_API_KEY=sk-your-api-key-here
```

### macOSの権限設定

このツールを使用するには、以下の権限が必要です:

1. **マイク**: システム設定 → プライバシーとセキュリティ → マイク
2. **アクセシビリティ**: システム設定 → プライバシーとセキュリティ → アクセシビリティ（自動ペースト機能）
3. **入力監視**: システム設定 → プライバシーとセキュリティ → 入力監視（メニューバーアプリのホットキー検知）

## 使い方

### 起動方法

#### 方法1: 直接実行（推奨）

仮想環境を有効化せずに、直接コマンドを実行できます:

```bash
# メニューバーアプリを起動
.venv/bin/voice-input-app

# CLIを起動
.venv/bin/voice-input
```

#### 方法2: 仮想環境を有効化してから実行

```bash
source .venv/bin/activate
voice-input-app  # または voice-input
```

#### シェルエイリアスの設定（任意）

毎回パスを入力するのが手間な場合、シェルエイリアスを設定すると便利です。

`~/.zshrc`（または `~/.bashrc`）に以下を追加:

```bash
alias voice="/path/to/voice-input-tool/.venv/bin/voice-input-app"
```

設定後、ターミナルを再起動するか `source ~/.zshrc` を実行すると、`voice` コマンドで起動できます。

### メニューバーアプリの使い方

`voice-input-app` を起動すると:

- メニューバーに「Voice Input」が表示されます
- 設定したホットキー（デフォルト: **左Control**）を押している間、録音されます
- キーを離すと、自動で文字起こし → ペーストされます
- メニューの「Hotkey」からホットキーを変更できます（設定は自動保存）

### CLIの使い方

`voice-input` コマンドは指定した秒数だけ録音し、テキストに変換します。

```bash
# 基本的な使い方（5秒間録音）
.venv/bin/voice-input

# 録音時間を指定（例: 10秒）
.venv/bin/voice-input -d 10

# クリップボードにコピーのみ（ペーストしない）
.venv/bin/voice-input --no-paste
```

### CLIオプション

| オプション | 説明 | デフォルト |
|-----------|------|-----------|
| `-d`, `--duration` | 録音時間（秒） | 5.0 |
| `--no-paste` | 自動ペーストを無効化 | false |

## コスト

OpenAI Whisper APIの料金は$0.006/分です。月100分使用しても約$0.60と、非常に低コストで運用できます。
