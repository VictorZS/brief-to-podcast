# 主分支 CI 通过后，为什么发布提交又变红了？

日期：2026-11-08。案例版本：`v0.1.0`，提交 [`efbbff8`](https://github.com/VictorZS/brief-to-podcast/commit/efbbff8d5a1ec00ce8827d4e76c0b0d25d5cc2d4)。本文根据该次发布日志整理。

这次发布暴露了一个验收缺口：确认主分支的自动检查通过后，创建版本标签又触发了一轮检查。第二轮失败，导致同一提交显示红色状态。发布结束前还需要检查标签触发的运行。

## 实际发生了什么

| 证据 | 观察结果 |
|---|---|
| [主分支运行](https://github.com/VictorZS/brief-to-podcast/actions/runs/42468712743) | Python 3.10 和 3.13 的测试与文本样例均通过 |
| [标签运行的原失败任务](https://github.com/VictorZS/brief-to-podcast/actions/runs/42468820282/job/128694526817) | 安装 Python 3.10.22 时，下载连续三次收到 HTTP 504；测试尚未开始 |
| [同一提交的重跑任务](https://github.com/VictorZS/brief-to-podcast/actions/runs/42468820282/job/128695730542) | Python 安装成功，28 项离线测试及虚构文本样例通过 |

HTTP 504 表示请求在某个网关等待上游响应时超时。日志能确定失败发生在环境安装阶段，但不能确定是哪一层网络或服务造成了超时。重跑成功支持这次故障具有暂时性的判断，不能据此保证以后不会再发生。

## 为什么旧的绿色结果不够

自动检查不只由代码变化触发，也可以由推送分支、创建标签等事件触发。本项目的工作流监听 `push`，所以主分支和标签各自启动了运行。

两轮运行检查相同的代码，却在不同的执行环境中重新准备 Python。第一次成功，说明那一次执行完成了检查；它不能证明后面新启动的运行也已成功。此次发布验收只看了前者，因此漏掉了后者。

## 这次如何处理，之后如何验证

1. 先定位失败步骤，确认错误发生在 Python 下载，而非单元测试断言或样例渲染。
2. 保留日志，对同一提交重跑失败任务；没有修改业务代码、跳过测试或移动版本标签。
3. 重跑后确认安装、测试和样例三步都完成，再按完整提交 SHA 核对主分支和标签的最新检查。

该次复核中，两轮运行的四项最新检查全部通过。今后的发布验收会在标签或 release 创建之后再做最后一次核对，并记录提交、标签、运行链接及结果。

重跑应当验证具体假设。如果失败发生在稳定可复现的断言、输入格式或程序异常处，就应定位并修复原因；不能靠反复重跑直到偶然出现绿色结果。

## 这个案例能说明什么

值得迁移的做法是：**把“哪一次执行、检查了什么、留下什么证据”一起记录。** 文件存在、命令退出成功、一次 CI 通过，分别只覆盖部分验收条件。

在简报引擎里也保留这种区分：来源 ID 与事实 ID 检查能发现引用关系错误，不能证明事实为真；音频回解码能检查空文件、静音或时长异常，不能评价发音和听感。通过哪一层检查，就报告哪一层结果。

**English takeaway:** A passing branch run does not cover a later tag-triggered run. Inspect the failing step, retry only when evidence supports a transient failure, and verify all relevant runs for the exact release commit. Structural checks and CI results have explicit limits; neither establishes factual truth or user value.
