# バージョンとリリース

## バージョン番号の定義

`src/voice_input/__init__.py` の `__version__` を唯一の定義とします。
Pythonパッケージ、メニュー、CLI、PyInstallerとpy2appのアプリ情報は、
すべてこの値を参照します。`uv.lock` は `uv lock` で更新します。

番号は `MAJOR.MINOR.PATCH` の3つの整数にします。
当面は開発中の `0.x.y` とし、不具合修正は `0.1.0 → 0.1.1`、
機能追加や互換性に影響する変更は `0.1.0 → 0.2.0` とします。
安定版としての互換性を保証する段階で `1.0.0` にします。

初回は既存の `0.1.0` を維持しています。公開するまでは更新履歴を
「未リリース」に置き、初回公開時に `v0.1.0` タグを作成します。
以後、配布物を変更して公開するときは必ず番号を上げます。

## 日々の変更

変更内容はルートの `CHANGELOG.md` の「未リリース」に追記します。
公開済みの項目は残し、新しいリリースを上に追加します。
バージョンはメニュー末尾、または次のコマンドで確認できます。

```bash
uv run voice-input --version
uv run voice-input-app --version
```

## リリース手順

以下はリポジトリのルートで実行します。

1. リリースする変更を統合し、`__version__` を決めます。
2. `CHANGELOG.md` の「未リリース」を `## [0.1.0] - YYYY-MM-DD` のような
   見出しに変更し、実際の公開日を入れます。その上に空の「未リリース」を残します。
3. 依存関係とテストを確認します。`uv.lock` の差分も確認し、バージョンとともに記録します。

```bash
uv lock
uv sync --locked --extra dev
uv run --locked pytest
uv build
```

4. [ビルド手順](build.md) に従って `.app` をビルドします。
   メニューの番号、権限設定、録音、文字起こし、ペーストを確認します。
   ローカル認識には別途、モデルを設定済みの `VoiceInputLocal.app` が必要です。
5. 変更をコミットし、配布するコミットに注釈付きタグを付けます。
   以下の番号は実際のリリースに合わせて変更します。

```bash
git status --short
# 確認したリリース対象のファイルを git add してコミットする
git commit -m "Release v0.1.0"
# 未コミットの変更がないことを確認する
git status --short
git tag -a v0.1.0 -m "Release v0.1.0"
```

6. ビルド済みアプリを番号付きのZIPにまとめます。
   別の出力先でビルドした場合は入力パスも変更します。

```bash
ditto -c -k --sequesterRsrc --keepParent dist/VoiceInput.app dist/VoiceInput-0.1.0-macos.zip
```

7. リリース対象のブランチとタグをGitHubにpushします。
   GitHub Releasesでそのタグを選び、該当バージョンの更新履歴とZIPを登録します。
   配布物には対応CPU、ローカル認識の前提、署名・公証の有無を記載します。

タグは `v` + バージョン番号に統一し、一度公開したタグは移動・上書きしません。
修正が必要なら番号を上げて新しいリリースを作成します。

## 以前の版を確認する

タグ一覧は `git tag --list 'v*' --sort=-v:refname` で確認できます。
変更内容は `git log --oneline v0.1.0..v0.1.1` のように比較できます。
過去のソースは別の作業ディレクトリに取り出せます。

```bash
git worktree add --detach ../voice-input-v0.1.0 v0.1.0
```

配布済みアプリを戻す場合は、GitHub Releasesから該当するZIPを取得します。
ユーザー設定や外部のローカル認識モデルは、このリポジトリのタグでは復元されません。
