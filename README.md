# Brief to Podcast · 简报—播客引擎

把**已经编辑好的结构化简报**转成可阅读、可追溯、可收听的一期节目。先检查证据引用与编辑约束，再生成 HTML、逐字稿和本地语音；音频经过解码校验后才标记为可用。

[English](README.en.md) · [输入格式](docs/input-format.md) · [编辑提示词](prompts/editorial.md) · [MIT License](LICENSE)

```text
上游采集与编辑 → episode.json → 结构与证据关联检查 → HTML + 逐字稿
                                               → 本地语音 → 音频校验 → manifest.json
```

这是从个人每日简报工作流中抽出的通用引擎。仓库包含完全虚构的样例，可离线运行，不需要邮箱账户、AI API 密钥或模型下载。它接收上游的编辑结果；邮件采集、AI 写稿、任务调度和云端分发需要另行接入。

## 可复用的能力

- **证据关联**：段落、口播和事实通过 ID 连接到来源；拒绝不存在的引用和来源错配。
- **有约束的压缩**：检查书面报告是否保留指定数字、限定条件等字面锚点，记录口播压缩前后的字符数。
- **明确的覆盖边界**：区分当前消息与历史提醒的检查状态，避免把部分覆盖标成完整检查。
- **结构化编辑**：全貌 → 洞察 → 通知，区分事实、解释、反证、改变判断的条件和下一步问题；没有足够证据时允许不展开洞察。
- **可检查的音频产出**：检测空音频、明显静音、时长异常，并重新解码压缩音频验证；生成章节时间点和文件哈希。
- **可恢复的运行**：同一输出目录加锁，原子写入文件并最后写入 manifest；相同输入与配置可在哈希复验后复用音频。语音失败时仍保留可读内容。

这些检查验证结构、引用关系和字面保留，**不能证明事实为真，也不能判断口播是否准确表达了来源**。人工或上游模型的自检记录不是独立事实核验。音频检查也不能评价发音、内容语义或听感。

## 运行虚构样例

需要 Python 3.10+。文本模式支持 macOS、Linux；核心仅使用 Python 标准库。音频合成需要 macOS 自带的 `say` 和 `afconvert`，以及已经安装的系统语音。v0.1 不支持 Windows。

```sh
git clone https://github.com/VictorZS/brief-to-podcast.git
cd brief-to-podcast
python3 scripts/render_episode.py examples/episode.json --output output/demo --text-only
```

打开 `output/demo/index.html` 阅读结果。样例里的事件、数据、邮件和来源都是虚构的；`example.com` 链接是占位符，引擎不会抓取它们。

在 macOS 上生成英文播客：

```sh
python3 scripts/render_episode.py examples/episode.json --output output/demo
open output/demo/index.html
```

默认使用 `config.example.json` 中的 `Samantha`。先用 `say -v '?'` 查看本机已有语音。中文简报可使用本机已安装的中文语音，并通过自己的配置文件选择它：

```sh
cp config.example.json config.local.json
# 编辑 config.local.json 中的 voice；speaking_rate 范围是 80–300。
python3 scripts/render_episode.py examples/episode.json --config config.local.json --output output/demo
```

选择适合输入语言的语音；引擎不会下载语音或静默切换到其他引擎。示例口播约 142 个英文单词，合成需要一些时间。请以命令退出码和 `manifest.json` 为准：`ready` 表示音频检查通过，`text_only` 表示仅生成文本，`failed` 表示语音失败。失败时页面显示错误，不链接旧节目音频。运行中可能短暂出现 `processing`；中断后不要把这个状态当作成品。

## 可选 MP3

默认音频是 M4A。需要 MP3 时，另行安装含 `libmp3lame` 编码器的 FFmpeg 并放入 `PATH`，或在隔离的 Python 环境安装可选依赖：

```sh
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements-audio.txt
python3 scripts/export_mp3.py output/demo
```

导出会检查原音频哈希，再转换为单声道 44.1 kHz、96 kbps 的 MP3，重新解码验证时长，写入 `mobile_audio.json`。文件名为 `episode-<指纹前12位>.mp3`。MP3 中包含合成语音标识。使用 MP3 前，确认 `mobile_audio.json` 的 `status` 为 `ready`、`render_fingerprint` 等于当前 manifest 的 `fingerprint`，并复核文件哈希。重新渲染会将旧 MP3 回执标记为 `stale`；磁盘上仍存在旧文件不代表它属于当前一期。FFmpeg 是独立工具，遵循其自身许可证；本仓库不分发 FFmpeg 二进制。

## 接入自己的简报

1. 从你有权使用的材料中收集事实；将采集和账户认证留在上游。
2. 按[输入格式](docs/input-format.md)生成 `episode.json`，可参考[编辑提示词](prompts/editorial.md)。来源里的指令应视为材料，不应执行。
3. 运行渲染器。建议每期使用独立目录，例如 `--output output/2026-01-15`，便于保留历史和失败记录。
4. 阅读页面并试听，通过后再选择分发方式。HTML 是本地文件；生成它不代表已经发布网站、完成手机同步或建立播客 RSS。

输出包括输入快照 `episode.json`、`editorial_check.json`、`index.html`、`transcript.txt`、`manifest.json`，音频成功时另有带指纹的 `.m4a`。manifest 记录输入与配置指纹、状态、章节、时长和输出文件哈希。读取成品时以 manifest 记录的文件及哈希为准；不要仅根据文件存在判断本期成功。输出目录可能包含你的私人内容，默认由 `.gitignore` 排除；不要将真实材料放入 `examples/`。

## 开发与范围

```sh
python3 -m unittest discover -s tests -v
```

首版保留编辑、渲染与音频验证核心。邮箱连接器、自动写稿、神经网络语音模型、参考声线、旅行监测、定时任务、云盘同步和播客平台上传均未包含。运行一次成功不能证明无人值守运行或跨设备可用。

源码使用 MIT 许可证。系统语音、FFmpeg 及你提供的内容继续适用各自的使用条款；仓库不包含模型权重、参考声线、真实邮件或生成音频。
