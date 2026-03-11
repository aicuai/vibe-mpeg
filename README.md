# vibe-mpeg

**本当にオープンなコーディングAI駆動の動画編集環境**

プロプライエタリなAPIもクラウドサービスも不要。飛行機の中でもサーバーでも動く、ローカルファーストの動画編集ツール。

## コンセプト

- **完全オフライン** — Ollama + Qwen3 で AI駆動の動画編集。Claude不要
- **ライセンスがクリーン** — Remotion等のプロプライエタリ製品を使わない。HTML/CSS + Playwright (MIT) + ffmpeg (外部コマンド)
- **Mac専用** — macOSにインストール済みのツール・フォントを活用
- **スキルベース** — JSON定義のスキルをLLMが呼び出して動画を生成
- **vibe-local連携** — [vibe-local](https://github.com/aicuai/vibe-local) がインストール済みなら自動検出

## アーキテクチャ

```
ユーザー → Qwen3 (Ollama) → スキルJSON → render.py → engine → MP4
                                              │
                                    ┌─────────┼─────────┐
                                    │         │         │
                              HTMLテンプレート  Playwright  ffmpeg
                              (自作/MIT)     (MIT)      (外部コマンド)
```

## セットアップ

```bash
./setup.sh
```

対話的に依存関係をチェック・インストールします：
- Python 3.12+
- ffmpeg (`brew install ffmpeg`)
- Playwright + Chromium
- Ollama + Qwen3（オプション、AI対話用）
- vibe-local（オプション、自動検出）

## 使い方

```bash
# デモ動画をレンダリング
python3 render.py demo

# スライドショーを作成
python3 render.py slideshow --slides '[{"text":"スライド1"},{"text":"スライド2"}]'

# テキストアニメーション
python3 render.py text-overlay --text "タイトル"

# Qwen3と対話しながら動画編集
python3 qwen3-bridge.py

# スキル一覧
python3 render.py --list
```

## テンプレート

HTMLテンプレートが動画の各フレームを描画します。テンプレートには以下のグローバル変数が注入されます：

| 変数 | 説明 |
|---|---|
| `window.__VIBE_FRAME__` | 現在のフレーム番号 |
| `window.__VIBE_FPS__` | フレームレート |
| `window.__VIBE_TOTAL_FRAMES__` | 総フレーム数 |
| `window.__VIBE_PROPS__` | スキルから渡されたプロパティ |

`window.__VIBE_RENDER_FRAME__(frame)` 関数を定義すると、毎フレーム呼び出されます。

## 開発方針

- 動画編集が一通りできるようになったら、vibe-localの外部化を完了しリポジトリを軽量化
- テンプレートは純粋なHTML/CSS/JS — Reactやビルドツール不要
- ffmpegはサブプロセスとして呼び出すのみ（リンク・同梱しない）
- Qwen3以外のOllama対応モデルでも動作可能

## ライセンス

MIT License

### 依存関係のライセンス

| コンポーネント | ライセンス | 利用形態 |
|---|---|---|
| Playwright | MIT (Microsoft) | Pythonパッケージ |
| ffmpeg | GPL/LGPL | 外部コマンド呼び出しのみ |
| Ollama | MIT | 外部サービス（オプション） |
| Qwen3 | Apache 2.0 (Alibaba) | Ollama経由（オプション） |
