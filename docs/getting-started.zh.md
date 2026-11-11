# 从一条中文通知开始

假设你想把已有文字整理成一段早餐时能听完的简报。这份指南用一条**完全虚构的图书室通知**演示准备输入、生成结果和修正错误。先完成小样例，再替换成自己的材料；当前引擎仍需编辑 JSON，尚不提供粘贴普通文字就自动写稿的界面。

## 1. 先得到一份能读的结果

文本输出需要 Python 3.10+；后面的音频步骤请使用 Python 3.12+。先在终端运行 `python3 --version`；版本不足时，安装合适版本，并确认这条命令已经指向新版本再继续。文本输出支持 macOS、Linux，不需要 AI 账户或付费服务。以下命令在仓库目录执行；尚未下载时，先按 [README](../README.md#运行虚构样例) 克隆并进入目录。

```sh
mkdir -p inputs
cp examples/episode.zh.json inputs/episode.zh.json
cp examples/draft.zh.txt inputs/draft.zh.txt
python3 scripts/render_episode.py inputs/episode.zh.json --output output/first-zh --text-only
```

用浏览器打开 `output/first-zh/index.html`。页面应明确标出虚构内容，并保留日期、开放至 20:00、仅当日有效的限制。`inputs/` 和 `output/` 已从 Git 排除；自己的材料放在这里，公开的 `examples/` 只保存虚构样例。

这一步验证样例能运行。它还没有完成你自己的材料准备，也没有生成声音。

## 2. 看懂这条素材怎样进入输入

样例素材是：“虚构演示：图书室在 2026-01-15 开放至 20:00，仅当日有效，不代表长期调整。”没有真实活动或出行建议，`example.com` 链接只是演示占位符。

用文本编辑器打开 `inputs/episode.zh.json`，沿着下表读一遍。JSON 中的字段名、双引号、逗号和方括号需要保留；改自己的材料时，用真实、可核对的内容替换样例。

| 要准备什么 | 写在哪里 | 需要一起核对什么 |
|---|---|---|
| 材料来自哪里、实际读到了什么 | `sources` | 来源 ID `s1`、有效 HTTPS 链接、读取范围；真实材料不能沿用虚构链接 |
| 一条事实及其限制 | `editorial.facts` | 事实 ID `f1`、来源 `s1`；`must_preserve` 中的日期、时间和限制须出现在引用它的书面段落里 |
| 给人看的文字、给人听的文字 | `sections`、`segments` | 两份稿件的事实、来源 ID 对应；分别保留 `inbox → insights → notifications` 三部分，口播里不写网址 |
| 没有证据支持进一步解读 | `editorial.stories: []`、`no_story_reason` | 写出不展开的原因；不要为填满结构编造洞察或待办 |
| 本次实际看过多少材料、还没查什么 | `coverage`、`briefing` | 数量相符，未查历史保持 `not_run`；不能把样例的部分复核改成未经验证的“全部完成” |
| 怎样编辑、哪些内容尚未验证 | `editorial.compression`、`editorial.review` | 保存真实初稿，记录删改与限制；自行核对后才能声明 `review.status: pass`，它不代表独立事实核验 |

样例只用一个来源、一个事实，没有展开洞察或真实待办。实际任务若需要多个事实、通知或研究问题，请按[完整输入格式](input-format.md)补充；不要为了少填字段删掉重要内容。仅有本地文字、没有合适的来源链接时，当前契约未提供直接入口，不要编造链接使其通过。

## 3. 改完口播，重新计算字符数

`inputs/draft.zh.txt` 保存压缩前的口播初稿。换成自己的材料时，先保存自己的实际初稿，再编辑 JSON 中的最终口播；不要把最终稿当作初稿去制造压缩成绩。样例初稿为 213 个字符，最终口播为 169 个字符，数字只描述这个虚构例子。

下面的命令按文件实际内容更新两个计数，不会生成文字或替你审稿：

```sh
python3 - <<'PY'
import json
from pathlib import Path
path = Path("inputs/episode.zh.json")
episode = json.loads(path.read_text(encoding="utf-8"))
draft = Path("inputs/draft.zh.txt").read_text(encoding="utf-8").rstrip("\n")
episode["editorial"]["compression"]["before_chars"] = len(draft)
episode["editorial"]["compression"]["after_chars"] = len("\n\n".join(s["text"] for s in episode["segments"]))
path.write_text(json.dumps(episode, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(episode["editorial"]["compression"])
PY
python3 scripts/render_episode.py inputs/episode.zh.json --output output/first-zh --text-only
```

若出现 `compression.after_chars does not match the actual script`，通常是改了口播却没有重算字符数。检查最终稿、运行上面的计数命令，再渲染即可。其他错误需要修正对应内容，例如缺少事实引用或丢失限定条件；不要关闭编辑检查来绕过它们。再次阅读页面，确认日期、数字和限制没有被改错。

## 4. 在 Mac 上生成中文声音

音频需要 Python 3.12+、macOS 自带的语音工具和已安装的中文语音。较旧的 Python 可能无法读取系统语音生成的 WAV，报 `unknown format: 65534`；这是 Python 3.12 才加入支持的一种 [WAV 格式](https://docs.python.org/3/library/wave.html)。遇到它先检查 `python3 --version`，并让渲染命令使用受支持的解释器。

运行 `say -v '?'` 查看本机列表。只有列表中有 `Tingting` 时，才采用下面示例；否则把命令里的名称换成列表中的合适中文语音。没有中文语音时先停在文本步骤，引擎不会替你下载或换用其他服务。

```sh
python3 - <<'PY'
import json
from pathlib import Path
config = json.loads(Path("config.example.json").read_text(encoding="utf-8"))
config["voice"] = "Tingting"
Path("config.zh.local.json").write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
python3 scripts/render_episode.py inputs/episode.zh.json --config config.zh.local.json --output output/first-zh
```

查看结果状态：

```sh
python3 - <<'PY'
import json
from pathlib import Path
manifest = json.loads(Path("output/first-zh/manifest.json").read_text(encoding="utf-8"))
print(manifest["audio_status"])
print(manifest.get("error", ""))
PY
```

`ready` 表示音频检查通过；`text_only` 表示只有文本；`failed` 表示语音失败，可先阅读页面并按错误排查语音或运行环境；`processing` 表示尚未完成。输入校验失败时可能没有新回执，先看终端错误和退出码，不要把旧文件当作本次成功。

在页面中试听，核对日期、时间、限定条件与发音。若要复制或分享文件，还应复核回执中的文件哈希；这能发现文件是否损坏或被替换：

```sh
python3 - <<'PY'
import hashlib, json
from pathlib import Path
directory = Path("output/first-zh")
manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
assert manifest["audio_status"] == "ready", "本期音频尚未通过检查"
for name, expected in manifest["file_hashes"].items():
    assert hashlib.sha256((directory / name).read_bytes()).hexdigest() == expected, name
print("回执中的文件哈希一致；内容和听感仍需自行核对。")
PY
```

本地文件生成不代表已经同步到手机或发布成播客。后续每期使用不同的输出目录，保留旧结果与失败记录。

## 记录哪里仍然费力

这份指南的目标是减少准备与纠错的负担，效果仍需真实使用者验证。欢迎通过[使用反馈](https://github.com/VictorZS/brief-to-podcast/issues/new?template=usage_feedback.yml)说明卡在哪一步、是否需要帮助，以及准备和校对花了多少时间。首次安装与之后每次使用分开记录；无需上传私人材料。
