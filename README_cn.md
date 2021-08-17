[English](./README.md) | **中文**

# Task

一个用于统计服务器进行中工程任务的插件

需要 [MCDReforged](https://github.com/Fallen-Breath/MCDReforged) >=2.0.0-beta.1

不再需要 [stext](https://github.com/TISUnion/stext), 不再兼容 [MCDeamon](https://github.com/kafuuchino-desu/MCDaemon) 及 [MCDReforged](https://github.com/Fallen-Breath/MCDReforged) 1.x及以下版本

### 用法

`!!task help` 显示帮助信息

`!!task list` 显示任务列表

`!!task detail <任务名称>` 查看任务详细信息

`!!task add <任务名称> [任务描述]` 添加任务

`!!task del <任务名称]>` 删除任务

`!!task rename <旧任务名称> <新任务名称>` 重命名任务

`!!task change <任务名称> <新任务描述>` 修改任务描述

`!!task done <任务名称>` 标注任务为已完成

`!!task undone <任务名称>` 标注任务为未完成

`!!task deadline <任务名称> <工期:日数>` 为任务设置工期

`!!task player <任务名称>` 查阅玩家任务列表

`!!task res[ponsible] <任务名称> <玩家>` 设置任务的责任人

`!!task unres[ponsible] <任务名称> <玩家>` 移除任务的责任人

`!!task list-res[ponsibles] <任务名称>` 列出该任务的责任人

注: 上述所有 `[任务名称]` 可以用 `[任务名称].[子任务名称]` 的形式来访问子任务

例: `!!task add 女巫塔.铺地板 挂机铺黑色玻璃`