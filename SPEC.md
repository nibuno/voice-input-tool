# Voice Input Tool - プロジェクト仕様書

## 概要

Aqua Voice（$9.99/月）の代替として、音声入力→テキスト変換ツールを自作する。

## 要件

### 機能要件

- ホットキーを押している間、マイクから音声を録音
- ホットキーを離したら、音声をテキストに変換
- 変換されたテキストをアクティブなアプリケーションにペースト

### 非機能要件

- **日本語精度**: 高精度が必須（Whisper large-v3相当）
- **セキュリティ**: 会社利用を想定。APIデータがモデル学習に使われないこと
- **コスト**: 月額$9.99より大幅に安く抑える
- **ローカル完結**: 不要（クラウドAPI利用OK）

## 技術選定

### 音声認識API

**第一候補: OpenAI Whisper API**

- 料金: $0.006/分（月100分使っても$0.60）
- 日本語精度: 非常に高い
- セキュリティ: APIデータはモデル学習に不使用（利用規約に明記）

**代替候補**（会社のセキュリティポリシーで必要な場合）

- Google Cloud Speech-to-Text
- Azure Speech
- Amazon Transcribe

### 技術スタック

| 用途 | ライブラリ |
|------|-----------|
| メニューバー常駐（macOS） | rumps |
| グローバルホットキー | pynput |
| 音声録音 | sounddevice |
| 音声ファイル処理 | scipy (wav書き出し) |
| API通信 | openai |
| テキスト出力 | pyperclip + pyautogui |

## アーキテクチャ

```
┌─────────────────────────────────────────────────────┐
│  macOS Menu Bar App (rumps)                         │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────┐ │
│  │   pynput    │───▶│ sounddevice │───▶│  .wav   │ │
│  │  (hotkey)   │    │ (recording) │    │  file   │ │
│  └─────────────┘    └─────────────┘    └────┬────┘ │
│                                              │      │
│                                              ▼      │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────┐ │
│  │  pyautogui  │◀───│   openai    │◀───│ Whisper │ │
│  │  (paste)    │    │   (API)     │    │   API   │ │
│  └─────────────┘    └─────────────┘    └─────────┘ │
│                                                     │
└─────────────────────────────────────────────────────┘
```

## 処理フロー

1. アプリ起動 → メニューバーに常駐
2. ユーザーがホットキー（例: `Cmd+Shift+V`）を押下
3. マイクから音声録音を開始
4. ユーザーがホットキーを離す
5. 録音を停止、一時ファイル（.wav）に保存
6. OpenAI Whisper APIに音声ファイルを送信
7. 返却されたテキストをクリップボードにコピー
8. `Cmd+V` をシミュレートしてペースト（またはタイプ入力）

## ファイル構成（案）

```
voice-input-tool/
├── README.md
├── pyproject.toml
├── src/
│   └── voice_input/
│       ├── __init__.py
│       ├── app.py          # メインアプリ（rumps）
│       ├── recorder.py     # 音声録音
│       ├── transcriber.py  # Whisper API通信
│       └── output.py       # テキスト出力
└── tests/
```

## 設定項目

環境変数または設定ファイルで管理:

- `OPENAI_API_KEY`: OpenAI APIキー
- `HOTKEY`: トリガーとなるホットキー（デフォルト: `cmd+shift+v`）
- `LANGUAGE`: 認識言語（デフォルト: `ja`）

## 開発の進め方

### Phase 1: 最小限のプロトタイプ

- [ ] 音声録音 → ファイル保存の動作確認
- [ ] Whisper APIへの送信と結果取得
- [ ] クリップボードへのコピー＆ペースト

### Phase 2: 常駐アプリ化

- [ ] rumpsでメニューバーアプリ化
- [ ] グローバルホットキーの実装
- [ ] 録音中のビジュアルフィードバック（アイコン変更など）

### Phase 3: 品質向上

- [ ] エラーハンドリング
- [ ] 設定UI（ホットキー変更など）
- [ ] ログ出力

## 注意事項

- macOSではマイクとアクセシビリティの権限が必要
- pyautoguiを使う場合、システム環境設定でアクセシビリティ許可が必要
- 会社利用時はOpenAI APIの利用規約を確認し、必要に応じて代替APIに切り替え

## 参考リンク

- [OpenAI Whisper API](https://platform.openai.com/docs/guides/speech-to-text)
- [rumps](https://github.com/jaredks/rumps)
- [pynput](https://pynput.readthedocs.io/)
- [sounddevice](https://python-sounddevice.readthedocs.io/)
