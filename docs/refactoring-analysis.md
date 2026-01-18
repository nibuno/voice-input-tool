# リファクタリング分析レポート

作成日: 2026-01-18

## 概要

voice-input-tool のコードベースを分析し、リファクタリングの方針と優先順位をまとめたドキュメント。

## 現状のコード構成

### 基本情報

| 項目 | 値 |
|------|-----|
| 総コード行数 | 864行 |
| モジュール数 | 10 |
| テストカバレッジ | 0% |
| 型ヒントカバレッジ | 約80% |
| Docstringカバレッジ | 約85% |

### モジュール構成

| モジュール | 行数 | 責務 |
|-----------|------|------|
| app.py | 227 | macOSメニューバーアプリ、オーケストレーション |
| recorder.py | 223 | 音声録音、ストリーム管理 |
| hotkey.py | 89 | グローバルホットキー検出 |
| logger.py | 79 | ロギング設定 |
| output.py | 71 | クリップボード、ペースト操作 |
| main.py | 62 | CLIエントリーポイント |
| transcriber.py | 59 | Whisper API通信 |
| config.py | 45 | 設定ファイル管理 |
| \_\_main\_\_.py | 6 | PyInstallerエントリーポイント |
| \_\_init\_\_.py | 3 | パッケージ初期化 |

### 依存関係

```
app.py
├── config.py (設定の読み込み/保存)
├── hotkey.py (HotkeyListener)
├── logger.py (ロギング)
├── output.py (output_text)
├── recorder.py (StreamingRecorder, save_audio, SAMPLE_RATE)
└── transcriber.py (transcribe)

recorder.py
└── logger.py

transcriber.py
└── logger.py

output.py
└── logger.py

hotkey.py
└── (外部: pynput)

main.py
├── output.py
├── recorder.py
└── transcriber.py
```

## 問題点の分析

### 1. テストの欠如（重要度: 高）

- `tests/` ディレクトリが存在しない
- `pyproject.toml` にテスト関連の依存関係がない
- 864行のコードが完全に未テスト

**影響**:
- リファクタリング時に動作保証ができない
- 回帰バグの検出が困難
- スレッド処理やAPI呼び出しの信頼性が不明

### 2. VoiceInputApp の肥大化（重要度: 高）

**場所**: `src/voice_input_tool/app.py`

`VoiceInputApp` クラスが227行あり、以下の責務を全て担当している:

- 録音の開始/停止制御
- 音声処理と検証
- 文字起こしの実行
- テキスト出力
- メニューバーUI管理
- イベントキュー処理
- 設定の読み込み/保存

これは単一責任の原則（SRP）に違反している。

### 3. 依存性注入の欠如（重要度: 高）

**場所**: `src/voice_input_tool/app.py:40-45`

```python
class VoiceInputApp(rumps.App):
    def __init__(self):
        # ...
        self.recorder = StreamingRecorder()  # ハードコード
```

依存オブジェクトが直接インスタンス化されているため:
- モックによるテストが困難
- コンポーネントの差し替えができない

### 4. 文字列ベースのイベントシステム（重要度: 中）

**場所**: `src/voice_input_tool/app.py:100-107`

```python
_event_queue.put("status:Ready")
_event_queue.put(f"error:{e}")
```

文字列のパースに依存しており:
- 型安全性がない
- リファクタリング時にエラーが見つけにくい
- IDE のサポートが効かない

### 5. マジック定数の散在（重要度: 中）

各モジュールに定数が散らばっている:

| 定数 | 値 | 場所 |
|------|-----|------|
| MIN_RECORDING_SECONDS | 0.3 | app.py:19 |
| MIN_RMS_THRESHOLD | 100 | app.py:24 |
| SAMPLE_RATE | 16000 | recorder.py:14 |
| ABORT_TIMEOUT | 1.0 | recorder.py:15 |
| CLOSE_TIMEOUT | 1.0 | recorder.py:16（未使用） |
| PASTE_TIMEOUT | 5.0 | output.py:12 |

### 6. APIリトライロジックの欠如（重要度: 中）

**場所**: `src/voice_input_tool/transcriber.py`

- ネットワークエラー時のリトライがない
- レート制限への対応がない
- 指数バックオフが実装されていない

### 7. その他の問題

| 問題 | 場所 | 説明 |
|------|------|------|
| 未使用定数 | recorder.py:16 | `CLOSE_TIMEOUT` が定義されているが未使用 |
| print文の混在 | app.py:160 | `logger.debug()` ではなく `print()` を使用 |
| 言語のハードコード | transcriber.py:14 | `"ja"` が固定値 |

## UTの追加計画

### 優先度1: スレッド・外部API関連（最優先）

複雑なスレッド処理や外部依存があり、バグのリスクが高い:

| テスト対象 | ファイル | テスト内容 |
|-----------|----------|------------|
| StreamingRecorder.start() | recorder.py | 録音開始、ストリーム初期化 |
| StreamingRecorder.stop() | recorder.py | 録音停止、リソース解放 |
| StreamingRecorder._abort_with_timeout() | recorder.py | タイムアウト処理 |
| transcribe() | transcriber.py | API呼び出し、エラーハンドリング |
| paste() | output.py | AppleScript実行、タイムアウト |

### 優先度2: ビジネスロジック

アプリケーションの主要な動作に関わる:

| テスト対象 | ファイル | テスト内容 |
|-----------|----------|------------|
| _process_audio() | app.py | 音声検証、RMS閾値判定 |
| copy_to_clipboard() | output.py | クリップボード操作 |
| save_audio() | recorder.py | WAVファイル保存 |
| output_text() | output.py | テキスト出力の統合処理 |

### 優先度3: 設定・ユーティリティ

基本的な機能で、テストが比較的容易:

| テスト対象 | ファイル | テスト内容 |
|-----------|----------|------------|
| load_config() | config.py | 設定ファイル読み込み、デフォルト値 |
| save_config() | config.py | 設定ファイル保存 |
| HotkeyListener | hotkey.py | ホットキー検出 |
| get_logger() | logger.py | ロガー初期化 |

### 推奨テストフレームワーク

```toml
# pyproject.toml に追加
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-mock>=3.12.0",
    "pytest-cov>=4.1.0",
]
```

## リファクタリング計画

### Phase 1: テスト基盤の構築

**目標**: 既存コードを変更せずにテストを追加

1. pytest と関連ツールを導入
2. `tests/` ディレクトリ構造を作成
3. 優先度1のテストを実装
4. CI設定（GitHub Actions）を追加

### Phase 2: 依存性注入の導入

**目標**: テスト可能なアーキテクチャへの移行

1. プロトコル（インターフェース）を定義
   ```python
   from typing import Protocol

   class RecorderProtocol(Protocol):
       def start(self) -> None: ...
       def stop(self) -> np.ndarray | None: ...

   class TranscriberProtocol(Protocol):
       def transcribe(self, audio_path: str) -> str: ...
   ```

2. VoiceInputApp のコンストラクタを変更
   ```python
   def __init__(
       self,
       recorder: RecorderProtocol | None = None,
       transcriber: TranscriberProtocol | None = None,
   ):
       self.recorder = recorder or StreamingRecorder()
   ```

### Phase 3: VoiceInputApp の分割

**目標**: 単一責任の原則に従った設計

```
src/voice_input_tool/
├── app.py              # UI とオーケストレーションのみ（~100行）
├── services/
│   ├── __init__.py
│   ├── recording.py    # 録音サービス
│   ├── transcription.py # 文字起こしサービス
│   └── output.py       # 出力サービス
├── events.py           # 型安全なイベント定義
└── constants.py        # 定数の集約
```

### Phase 4: イベントシステムの改善

**目標**: 型安全なイベント駆動アーキテクチャ

```python
# events.py
from dataclasses import dataclass
from typing import Union

@dataclass
class StatusEvent:
    status: str

@dataclass
class ErrorEvent:
    error: Exception
    message: str

@dataclass
class TranscriptionEvent:
    text: str

Event = Union[StatusEvent, ErrorEvent, TranscriptionEvent]
```

## 強み（維持すべき点）

- モジュール間の明確な責務分離
- CLAUDE.md での設計判断の詳細な文書化
- 適切なロギングインフラ
- プラットフォーム固有の最適化（AppleScript、pynput対応）

## 参考: 外部依存関係

| パッケージ | バージョン | 用途 |
|-----------|-----------|------|
| sounddevice | >=0.5.0 | 音声録音 |
| scipy | >=1.15.0 | WAVファイルI/O |
| numpy | >=2.0.0 | 音声データ処理 |
| openai | >=2.0.0 | Whisper APIクライアント |
| pyperclip | >=1.9.0 | クリップボードアクセス |
| python-dotenv | >=1.1.0 | 環境変数読み込み |
| rumps | >=0.4.0 | macOSメニューバーUI |
| pynput | >=1.7.6 | グローバルホットキー検出 |
