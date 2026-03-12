# vibe-mpeg

**Open AI-driven Video Editing — No Cloud Required**

ローカルで完結する、AI駆動のオープンソース動画編集ツール。ffmpeg + Python + LLM。

> プロプライエタリなAPIもクラウドサービスも不要。飛行機の中でもサーバーでも動く。

---

## Features

- **ffmpeg Skills** — 動画結合 / 音声ミキシング / 字幕(SRT/ASS) / トランジション / リフォーマット
- **Project Pipelines** — JSON定義のマルチステップレンダリング、`${prev.output}` チェイニング
- **Browser Editor** — `localhost:3333` でメディアブラウザ / タイムライン / プレビュー
- **Vertical Shorts** — 1080x1920 クロップ＆スケール、TikTok / YouTube Shorts 対応
- **Offline-first** — Ollama + Qwen3 でAI対話。Claude不要、API不要

## Quick Start

```bash
git clone https://github.com/aicuai/vibe-mpeg.git
cd vibe-mpeg

# 対話チュートリアル（環境チェック → 動画結合 → 音声 → 字幕 → トランジション）
python3 tutorial.py

# ブラウザエディタ起動
python3 server.py          # → http://localhost:3333
```

## Skills

| Skill | Description | Example |
|---|---|---|
| `concat` | 動画結合 | `python3 render.py concat --files '["a.mp4","b.mp4"]'` |
| `mix-audio` | 音声ミキシング / 置換 | `python3 render.py mix-audio --video X --audio Y --replace` |
| `subtitles` | SRT/ASS/VTT 字幕焼き込み | `python3 render.py subtitles --video X --sub Y` |
| `transition` | トランジション | `python3 render.py transition --video1 X --video2 Y` |
| `reformat` | クロップ / スケール / トリム / 速度変更 | `python3 render.py reformat --video X --crop '{"w":608,"h":1080}'` |
| `probe` | メディア情報取得 | `python3 render.py probe --file X` |
| `project` | プロジェクトパイプライン実行 | `python3 render.py project --name VerticalShort` |
| `demo` | デモ動画生成 (Playwright) | `python3 render.py demo` |

## Project Pipelines

`projects/*.json` にパイプラインを定義。ステップを順番に実行し、`${prev.output}` で前ステップの出力を次のステップに渡す。

```json
{
  "name": "VerticalShort",
  "description": "Vertical short (1080x1920) — TikTok/Shorts ready",
  "format": { "width": 1080, "height": 1920 },
  "steps": [
    { "skill": "reformat", "params": { "video": "media/source.mp4", "in": 34.0, "out": 64.0, "crop": {"w":608,"h":1080,"x":656,"y":0}, "scale": {"w":1080,"h":1920} }},
    { "skill": "subtitles", "params": { "video": "${prev.output}", "sub": "media/lyrics.ass" }},
    { "skill": "mix-audio", "params": { "video": "${prev.output}", "audio": "media/track.mp3", "replace": true }}
  ]
}
```

出力: `out/{ProjectName}-{MMDD}-{HHMM}.mp4`

## Browser Editor

```
python3 server.py
```

Remotion Studio インスパイアのダークテーマUI:

| Area | Function |
|---|---|
| Left sidebar | メディアブラウザ（アップロード / リネーム / 削除） |
| Center | プレビュープレーヤー |
| Right sidebar | ファイル情報 / スキル一覧 |
| Bottom | タイムライン（ドラッグ＆ドロップ並替 / ステップ編集 / 保存） |

## Architecture

```
User → LLM (Ollama/Qwen3) → Skill JSON → render.py → ffmpeg → MP4
                                              │
                                    skills/*.json (skill definitions)
                                    projects/*.json (pipelines)
                                    server.py (browser editor)
```

## Dependencies

| Component | License | Required |
|---|---|---|
| ffmpeg | GPL/LGPL | Yes (external command only) |
| Python 3.12+ | PSF | Yes |
| Playwright | MIT | Optional (template skills) |
| Ollama | MIT | Optional (AI chat) |
| Qwen3 | Apache 2.0 | Optional (via Ollama) |

## Roadmap

開発中の機能は [Issues](https://github.com/aicuai/vibe-mpeg/issues) で追跡しています。

改善要望・バグ報告は Issue にお寄せください。

## Dev Blog

| Date | Topic |
|---|---|
| 2026-03-12 | Initial release — skills, project pipelines, browser editor, vertical shorts |

## License

MIT

---

Built with ffmpeg, Python, and vibes.
