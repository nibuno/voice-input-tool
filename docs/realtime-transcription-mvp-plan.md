# Realtime transcription overlay MVP plan

## Goal

録音中の発話を、macOS上の小さなフローティングパネルへ逐次表示する。
録音終了後の確定文字列とペースト処理は既存のWhisper処理を残し、MVP導入による
既存機能の品質低下を避ける。

## MVP scope

- 録音開始時に字幕パネルを表示する。
- `sounddevice` の音声コールバックで得た16 kHz / mono / int16 PCMを、
  録音用キューとは別の購読経路からRealtime文字起こしへ送る。
- Realtime APIから届く暫定テキストと確定テキストを字幕パネルに反映する。
- 録音終了時にRealtime接続を閉じ、既存の `whisper-1` による最終文字起こしと
  ペーストを継続する。
- Realtime接続に失敗しても録音、最終文字起こし、ペーストは継続する。

## Out of scope

- Realtime結果を最終ペースト結果として使うこと。
- 入力中のアプリケーションやキャレット位置にパネルを追従させること。
- 字幕履歴、設定画面、表示位置のカスタマイズ。
- オフライン文字起こし、話者分離、翻訳。
- PyInstallerビルドの更新（MVP動作確認後の別段階とする）。

## Design

```text
sounddevice callback
    |-- existing recording queue --> stop --> WAV --> whisper-1 --> paste
    `-- realtime subscriber queue --> Realtime API --> transcript state
                                                   --> NSPanel overlay
```

### Threading rules

- 音声コールバックではコピーとノンブロッキングなキュー投入だけを行う。
- ネットワーク送受信は専用ワーカースレッドで行う。
- AppKit UIの生成・更新・破棄はrumpsのタイマーが動くメインスレッドで行う。
- ワーカーからUIへは既存のアプリイベントキューを経由する。

### Failure behavior

- APIキー未設定、接続失敗、送受信エラー時は字幕を利用不可として隠す。
- Realtime側のエラーで録音を停止しない。
- 字幕イベントが遅れて別録音へ混入しないよう、録音セッションIDで破棄する。

## Work log

- [x] 専用ブランチ `feat/realtime-transcription-overlay` を作成。
- [x] 現行の録音・文字起こし経路を確認。
- [x] OpenAI Python SDKのRealtime接続口と不足依存を確認。
- [x] 録音チャンク購読APIとテストを追加。
- [x] Realtime文字起こしワーカー、字幕状態管理、テストを追加。
- [x] 最小限のAppKit字幕パネルを追加。
- [x] `VoiceInputApp`へライフサイクルを接続。
- [x] `openai[realtime]` のWebSocket依存をTakumi Guard経由で導入。
- [x] 全65件のユニットテストが成功。
- [x] cmux上でMVP版アプリが起動・常駐することを確認。
- [x] 接続スモークテストで専用モデル直指定が利用不可と判明し、
  transcription intent + `gpt-4o-mini-transcribe` 方式へ修正。
- [x] 修正したtranscription sessionで `session.created` / `session.updated` を確認。
- [x] 24kHz日本語合成音声でdelta列とcompleted全文を確認。
- [ ] 実マイク操作で字幕パネルの表示と更新を目視確認。
- [ ] `uv.lock` の既存ローカル変更と依存追加を分離して整理。
- [x] 初回実マイク試験で接続待ち中に小チャンク用キューが飽和する問題を特定。
- [ ] 100ms送信バッチ化・接続待ちバッファ拡張後に実マイクで再確認。
- [x] バッチ化後はキュー飽和がなく、Realtime接続成功を実マイクで確認。
- [x] 無音確定前の録音停止で結果を受け取れない問題を特定。
- [ ] 約1秒ごとの手動commitと停止後猶予を実マイクで再確認。
- [x] Realtime delta/completedは実マイクで継続的に受信できることを確認。
- [x] 字幕が見えない問題を表示レイヤーに限定。
- [ ] アクティブディスプレイ・高ウィンドウレベル版のパネルを目視確認。
- [x] 高ウィンドウレベル版パネルがユーザー環境で見えることを確認。
- [x] 1秒分割では「イラストリング」「Nein」など文脈不足の誤認識を確認。
- [ ] 2秒commit + `gpt-4o-transcribe` で精度と遅延を再評価。
- [x] 2秒版でも未発話の「バカだ」「ご視聴ありがとうございました」等を確認。
- [ ] 4秒文脈・RMS無音除外・推測禁止プロンプト版を再評価。
- [x] `gpt-realtime-whisper` へ切り替え、固定秒数commitを廃止。
- [x] 100ms単位で連続送信し、録音停止時に一度だけcommitする構成へ変更。
- [ ] `gpt-realtime-whisper` 連続ストリーミング版を実マイクで再評価。
- [x] 実マイク試験で `prompt` 非対応エラーを確認し、未対応設定を削除。
- [x] Realtime確定結果を最終入力に使用し、失敗・空・タイムアウト時のみ
  `whisper-1` へフォールバックする構成へ変更。
- [x] 長文でもパネルが止まって見えないよう、全文は保持したまま表示だけを
  最新約4行へ追従させる。

## Acceptance criteria

- 録音開始から数秒以内に字幕パネルへ文字が現れる。
- 暫定文字列の更新で同じ文章が無制限に重複しない。
- 録音停止後は従来どおり最終文字列が対象アプリへ入力される。
- ネットワークを切った状態でも従来の録音処理がクラッシュしない。
- 既存テストと新規ユニットテストが通る。

## Follow-up candidates

1. Realtimeモデルと従来Whisperの精度・遅延・コストを比較する。
3. パネルの表示位置、サイズ、表示可否をメニュー設定に追加する。
4. PyInstallerへWebSocket依存とAppKit利用クラスを明示的に含める。
