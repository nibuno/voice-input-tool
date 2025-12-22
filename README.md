# Voice Input Tool

音声入力をテキストに変換するCLIツール。OpenAI Whisper APIを使用して高精度な音声認識を実現します。

## 機能

- マイクからの音声録音
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
2. **アクセシビリティ**: システム設定 → プライバシーとセキュリティ → アクセシビリティ（自動ペースト機能を使用する場合）

## 使い方

```bash
# 基本的な使い方（5秒間録音）
voice-input

# 録音時間を指定（例: 10秒）
voice-input -d 10

# クリップボードにコピーのみ（ペーストしない）
voice-input --no-paste
```

### オプション

| オプション | 説明 | デフォルト |
|-----------|------|-----------|
| `-d`, `--duration` | 録音時間（秒） | 5.0 |
| `--no-paste` | 自動ペーストを無効化 | false |

## コスト

OpenAI Whisper APIの料金は$0.006/分です。月100分使用しても約$0.60と、非常に低コストで運用できます。

## ライセンス

MIT License
