# vibe-mpeg

**本当にオープンなコーディングAI駆動の動画編集環境**

プロプライエタリなAPIもクラウドサービスも不要。飛行機の中でもサーバーでも動く、ローカルファーストの動画編集ツール。

## Quick Start

```bash
# 初回チュートリアル（環境チェック→動画結合→音声ミキシング→字幕→トランジション）
python3 tutorial.py
```

チュートリアルが対話的にガイドします：

1. 環境チェック（Python, ffmpeg, Playwright, Ollama, vibe-local）
2. 不足ツールのインストール
3. 動画ファイルの結合
4. メディアソースの指定
5. タイムスタンプ付きレンダリング (`YYYY-MM-DD-HHmm.mp4`)
6. MP3の追加とオーディオミキシング
7. SRT字幕の作成と焼き込み
8. トランジションエフェクト

## コンセプト

- **完全オフライン** — Ollama + Qwen3 で AI駆動の動画編集。Claude不要
- **ライセンスがクリーン** — プロプライエタリ製品を使わない。ffmpegを外部コマンドとして呼び出すのみ
- **Mac専用** — macOSにインストール済みのツール・フォントを活用
- **スキルベース** — ffmpegの機能をJSON定義のスキルとしてLLMから呼び出し

## スキル一覧

| スキル | 説明 | ffmpegコマンド |
|---|---|---|
| `concat` | 動画ファイルの結合 | `-f concat` |
| `mix-audio` | 音声ミキシング（BGM追加） | `amix` / `volume` |
| `subtitles` | SRT字幕の焼き込み | `subtitles` filter |
| `transition` | トランジションエフェクト | `xfade` / `acrossfade` |
| `demo` | デモ動画生成 | Playwright + ffmpeg |
| `slideshow` | スライドショー生成 | Playwright + ffmpeg |
| `text-overlay` | テキストアニメーション | Playwright + ffmpeg |

## 使い方

```bash
# 動画を結合
python3 render.py concat --files '["a.mp4", "b.mp4"]'

# BGMを追加（音量0.3）
python3 render.py mix-audio --video input.mp4 --audio bgm.mp3 --volume 0.3

# 字幕を焼き込み
python3 render.py subtitles --video input.mp4 --srt captions.srt

# トランジション（2つの動画をフェードで繋ぐ）
python3 render.py transition --video1 a.mp4 --video2 b.mp4 --effect fade --duration 1

# Qwen3と対話しながら編集
python3 qwen3-bridge.py

# スキル一覧
python3 render.py --list
```

## アーキテクチャ

```
ユーザー → Qwen3 (Ollama) → スキルJSON → render.py → ffmpeg → MP4
                                              │
                                    スキル定義 (skills/*.json)
                                    ffmpegコマンドのラッパー
```

## 依存関係

| コンポーネント | ライセンス | 利用形態 | 必須 |
|---|---|---|---|
| ffmpeg | GPL/LGPL | 外部コマンド呼び出しのみ | Yes |
| Python 3.12+ | PSF | ランタイム | Yes |
| Playwright | MIT (Microsoft) | HTMLテンプレート用 | Optional |
| Ollama | MIT | AI対話用 | Optional |
| Qwen3 | Apache 2.0 (Alibaba) | Ollama経由 | Optional |
| vibe-local | MIT | 自動検出 | Optional |

## 開発方針

- ffmpegのコマンドを順次スキル化していく
- 動画編集が一通りできたら vibe-local の外部化を完了しリポジトリを軽量化
- テンプレート系スキル（Playwright依存）は段階的にffmpegのdrawtext等に移行検討
- Qwen3以外のOllama対応モデルでも動作可能

## License

MIT
