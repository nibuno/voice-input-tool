# VoiceInput Local

WhisperをMac内で実行する音声入力アプリです。APIキーや従量課金は不要です。
初回に音声認識モデルをダウンロードすると、その後はオフラインで使えます。
ネコチャンの表示は含みません。

## 動作環境

- Apple Silicon（M1以降）のMac
- macOS 15以降（今回同梱するMLXバイナリの最低OSに合わせています）
- モデルの保存容量：標準モデル約481 MB、large-v3-turbo約1.61 GB

利用者がPython、Homebrew、ffmpegをインストールする必要はありません。
Intel MacとWindowsには対応していません。

## インストールと初回設定

1. ZIPを展開し、`VoiceInputLocal.app`を「アプリケーション」へ移動します。
2. アプリを開き、モデルを選んで「ダウンロード」を押します。
3. 続いて表示される権限設定で、マイク・アクセシビリティ・入力監視を許可します。
4. 入力監視が反映されない場合は、アプリを終了して開き直します。

現在の試用ビルドはアドホック署名で、Appleの公証は未実施です。
インターネット経由で受け取ったMacではGatekeeperによって起動を止められる場合があります。
一般公開する版には、配布者がDeveloper ID署名と公証を行います。

## 音声入力

テキストを入力するアプリにカーソルを置き、左Controlを押したまま話します。
キーを離すと文字起こしが始まり、完了後にテキストを貼り付けます。
Escapeを押すと、その録音を破棄します。

メニューバーの`Hotkey`でキー、`Mode`で押すたびに録音を切り替える方式を選べます。
モデルは「音声認識モデル」から変更できます。処理中の重複入力を避けるため、
文字起こしが完了するまでは次の録音を始められません。

録音中の字幕表示は、この版では対応していません。
標準モデルとlarge-v3-turboでは、精度・処理時間・メモリ使用量が異なります。
まず標準モデルで試し、誤認識が多ければlarge-v3-turboと比較してください。

## 通信と保存データ

通信するのは、利用者がモデルの取得を選んだときだけです。
Hugging Faceから固定リビジョンのモデルを取得し、サイズとSHA-256を確認します。
キャンセルや失敗では未完成のファイルを使わず、再試行できます。
認識に失敗しても、クラウドAPIには切り替えません。

録音はメモリ内で処理し、音声ファイルと文字起こし履歴は保存しません。
ログにも文字起こし本文やクリップボードの内容を記録しません。
貼り付けたテキストは入力先アプリとクリップボードに残ります。
入力先アプリやOSのクリップボード共有機能が行う通信は、このアプリの管理対象外です。

| データ | 保存先 |
| --- | --- |
| 設定 | `~/Library/Application Support/VoiceInputLocal/config.json` |
| モデル | `~/Library/Application Support/VoiceInputLocal/models/` |
| 動作ログ | `~/Library/Logs/VoiceInputLocal/` |

削除する場合はアプリを終了し、アプリ本体と上記のフォルダを削除します。
既存API版の`~/.voice-input/`とは設定を分離しています。
同じショートカットの競合を避けるため、試用時はAPI版を終了してください。

## 開発環境での起動

```bash
uv sync --extra local --extra dev --extra build --frozen
uv run --no-sync voice-input-local
```

モデル設定だけを開く場合は`--models`、権限設定だけなら`--setup`を指定します。
16 kHz・モノラルのWAVは、マイクや貼り付けを使わずに検証できます。

```bash
uv run --no-sync voice-input-local --download-model --model small
uv run --no-sync voice-input-local --transcribe sample.wav
```

## 配布ビルド

Apple SiliconのMacで次を実行します。

```bash
bash scripts/build_local.sh
```

`dist/VoiceInputLocal.app`と`dist/VoiceInputLocal-arm64.zip`を生成します。
Python、MLX、音声入出力ライブラリ、トークナイザーのデータ、依存ライブラリの
ライセンス表記を同梱します。モデルの重みはZIPには含めません。

Developer ID証明書を用意した配布者は、署名するビルドに切り替えられます。

```bash
CODESIGN_IDENTITY='Developer ID Application: 名前 (TEAMID)' bash scripts/build_local.sh
```

公証用の認証情報をKeychainプロファイルに登録したうえで、Appleに提出します。
秘密情報をリポジトリやコマンド例へ書き込まないでください。

```bash
xcrun notarytool submit dist/VoiceInputLocal-arm64.zip --keychain-profile VoiceInputLocal --wait
xcrun stapler staple dist/VoiceInputLocal.app
xcrun stapler validate dist/VoiceInputLocal.app
spctl --assess --type execute --verbose dist/VoiceInputLocal.app
ditto -c -k --sequesterRsrc --keepParent dist/VoiceInputLocal.app dist/VoiceInputLocal-arm64.zip
```

公証結果がAcceptedであることを確認してからstapleします。
署名・公証後は、新しいMacでダウンロードから初回起動、権限設定、録音、貼り付けまで確認します。
詳細は[Appleの公証ガイド](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution)を参照してください。

## 採用ライブラリ

認識には[MLX Whisper](https://github.com/ml-explore/mlx-examples/tree/main/whisper)を使います。
モデルは[Whisper small](https://huggingface.co/mlx-community/whisper-small-mlx)と
[large-v3-turbo](https://huggingface.co/mlx-community/whisper-large-v3-turbo)を選べます。
Whisperのライセンスは`packaging/Whisper-LICENSE.txt`に収録しています。
モデル選択・ダウンロードはアプリの処理とし、推論には保存済みのローカルパスだけを渡します。

## 今回の検証結果（2026年11月1日）

M1 Pro・メモリ16 GB・macOS 15.7.1で確認しました。

- 全134件のテストが成功。ローカル認識の出力、モデル破損・通信失敗・キャンセル、設定画面の状態遷移と実際のモーダルループの終了を含みます。
- APIキーなしでローカル版のメニューを構築し、ネコチャンの項目がないことを確認しました。
- 標準モデル約481 MBを実際に取得し、サイズとSHA-256の検証が成功しました。
- ZIPから別のフォルダに展開したアプリの署名検証が成功しました。
- APIキー・Pythonの開発用環境変数を外し、OSで通信を禁止した状態でも、日本語WAVの文字起こしに成功しました。
- 配布物の確認で見つかったMLX内部モジュールの同梱漏れと、補助プロセスの引数エラーを修正し、同じ検証が通ることを確認しました。

オフライン検証は次のコマンドで再実行できます。引数には絶対パスを指定します。

```bash
bash scripts/verify_local_bundle.sh /path/to/models /path/to/16khz-mono.wav
```

音声はmacOSの日本語読み上げから作成した約9秒のサンプルです。
標準モデルは文全体を認識しましたが、「インターネット」を「インパーネット」と誤認識しました。
日常利用の日本語精度や雑音耐性、large-v3-turboの精度・速度は、この検証からは判断できません。

画面操作ツールが応答しなかったため、画面の目視確認と実マイクから貼り付けまでの操作は未確認です。
設定画面は実際のAppKitコントロールを生成するテストで確認しています。
Developer ID署名・Apple公証・別のMacでの初回起動も未実施です。
