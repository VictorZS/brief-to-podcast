# Contributing · 参与改进

欢迎分享使用障碍、修正文档、补充虚构样例或提交代码改进。第一次参与可以从指出一句难懂的说明开始。

## 反馈问题

- 使用 [问题报告](https://github.com/VictorZS/brief-to-podcast/issues/new?template=bug_report.yml) 描述可复现的错误、预期结果和实际结果。
- 使用 [使用反馈](https://github.com/VictorZS/brief-to-podcast/issues/new?template=usage_feedback.yml) 说明尝试的任务、完成情况和再次使用的原因或障碍。
- 提交前搜索已有 Issue；已有同类问题时补充新证据，避免重复开帖。

Issue 是公开内容。复现请使用仓库样例或重新编写的虚构材料；不要附上私人邮件、原始简报、音频、认证信息或完整环境日志。必要的错误片段也请先移除个人路径和敏感内容。无须披露原始材料，仍然可以提供有用反馈。

## 修改与验证

当前文本模式面向 Python 3.10+ 的 macOS/Linux，系统语音合成需要 macOS。核心没有第三方 Python 依赖；MP3 导出是可选功能。

```sh
python3 -m unittest discover -s tests -v
python3 scripts/render_episode.py examples/episode.json --output output/contribution-check --text-only
```

请在 Pull Request 中说明具体问题、改动后的行为和实际完成的验证。音频行为有变化时，补充所在系统、所用语音和音频检查结果；没有实际试听就说明尚未试听。文档改动应检查链接和运行命令，行为改动应补充能揭示问题的回归测试。

保持一次改动聚焦一个问题。输入契约、默认语音引擎或输出兼容性若有较大变化，先在 Issue 中解释使用场景与取舍，让维护者能讨论影响。

生成文件放在 `output/`，私人输入留在仓库之外或忽略目录内。提交前检查 Git 差异和文件列表，避免把本地输出或配置带入提交。

## 表达证据与范围

描述经过验证的结果，并区分人工判断和自动检查。不要把结构校验通过写成事实核验通过，也不要把克隆、样例运行或维护者代跑计为独立用户使用。

可复用的经验可以整理成 [Learning note](docs/learnings/README.md)：写明问题、日期、证据、判断变化、适用条件和下一次验证。欢迎补充反例与修正；相同结论的新版本应说明增加了什么证据。
