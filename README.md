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

初回起動時は、未許可の権限があると「権限設定」画面が開きます。
マイクの「許可する」、各権限の「設定を開く」から設定してください。
許可状況は自動で再確認され、3つの権限がそろうと「完了」で起動を続けられます。
初回設定で「あとで」またはウィンドウを閉じた場合は、録音せずに終了します。
起動後もメニューバーの「権限設定...」から確認できます。

APIキーの設定前に、権限設定だけを開くこともできます:

```bash
.venv/bin/voice-input-app --setup
```

必要な権限は以下の3つです:

1. **マイク**: システム設定 → プライバシーとセキュリティ → マイク
2. **アクセシビリティ**: システム設定 → プライバシーとセキュリティ → アクセシビリティ（自動ペースト機能）
3. **入力監視**: システム設定 → プライバシーとセキュリティ → 入力監視（メニューバーアプリのホットキー検知）

`.app` では Voice Input を、ターミナルからの直接実行では起動元の
ターミナルや Python など、macOSに表示された対象を許可してください。
設定が反映されない場合やmacOSから再起動を求められた場合は、アプリを起動し直してください。
最初の自動ペーストでは「System Events」の操作（オートメーション）の許可も
求められる場合があります。拒否した場合は、システム設定の
「プライバシーとセキュリティ → オートメーション」で確認してください。

新しいPCでも許可操作は必要ですが、設定画面を探す必要はありません。
画面収録の権限は、このツールの音声入力には不要です。

**既存バージョンから更新する場合**: 起動時の確認対象がアクセシビリティだけでなく、
マイク・入力監視にも広がりました。以前は起動できていた環境でも、
これらの権限が未許可であれば設定画面が表示されます。
入力監視は許可した後も再起動まで確認結果が変わらない場合があります。
設定済みなのに「完了」が押せないときは、「あとで」で閉じてから
Voice Inputを終了し、起動し直してください。
「確認できません」と表示される場合は、未許可ではなく状態確認の失敗です。
再起動しても直らない場合はアプリを再インストールしてください。

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

```bash
# 通常起動
.venv/bin/voice-input-app

# デバッグモード（詳細ログ出力）
.venv/bin/voice-input-app --debug
```

`voice-input-app` を起動すると:

- メニューバーに「Voice Input」が表示されます
- 設定したホットキー（デフォルト: **左Control**）を押している間、録音されます
- キーを離すと、自動で文字起こし → ペーストされます
- メニューの「Hotkey」からホットキーを変更できます（設定は自動保存）
- メニューの「Input Device」から入力デバイスを固定できます（System Default でOSのデフォルトに戻ります）
- デバイスの抜き差し後は「Refresh Devices」で一覧を更新できます
- Toggleモードでは長時間録音を防ぐため、デフォルトで120秒で自動停止します（`max_recording_seconds`またはメニューの`Recording Limit`で変更可能）
- メニューの「Show Nekochan」で、画面右下にペットを表示できます（後述）

### ペット機能

メニューの「Show Nekochan」をオンにすると、画面右下にペットが表示され、アプリの状態に合わせて見た目が変わります。

ペットはドラッグして好きな位置に動かせます。位置は保存され、次回起動時も同じ場所に表示されます。メニューの「Reset Nekochan Position」で右下に戻せます。ペットが表示されている範囲は、下にあるウィンドウをクリックできなくなります。

| 状態 | ファイル名 | 画像がないときの表示 |
|---|---|---|
| 待機中 | `idle` | 🐱 |
| 録音中 | `listening` | 👂 |
| 文字起こし中 | `thinking` | 💭 |
| ペースト完了（数秒） | `happy` | 😸 |
| エラー（数秒） | `sad` | 😿 |

画像は `~/.voice-input/pet/` に `<ファイル名>.gif` または `<ファイル名>.png` として置きます（例: `~/.voice-input/pet/idle.png`）。GIF はアニメーション再生され、背景が透過の画像ならキャラだけが表示されます。

ファイル名を変えずに使いたい場合は、`~/.voice-input/config.json` で状態ごとに指定できます。

```json
{
  "pet_images": {
    "idle": "nekochan_smile.png",
    "listening": "nekochan_wave.gif"
  }
}
```

画像はこのリポジトリには含まれていません。たとえば [しかまつさんのネコチャン絵文字](https://note.com/shikamatsu/n/nd217dc0617db) を使う場合は、配布ページからダウンロードし、[利用のおやくそく](https://note.com/shikamatsu/n/n8818bb5ebea1) を守って各自の環境でお使いください。

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

## macOS アプリとしてビルド

スタンドアロンの macOS アプリとしてビルドできます。

```bash
# PyInstaller をインストール
uv pip install pyinstaller

# ビルド実行
uv run pyinstaller VoiceInput.spec -y
```

ビルド後、`dist/VoiceInput.app` が作成されます。`/Applications/` にコピーして使用できます。

詳細は [docs/build.md](docs/build.md) を参照してください。

## コスト

OpenAI Whisper APIの料金は$0.006/分です。月100分使用しても約$0.60と、非常に低コストで運用できます。
