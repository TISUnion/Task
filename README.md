# Task

A plugin shows tasks of project in progress

stext is no longer needed

### Usage

`!!task help` 显示帮助信息

`!!task list` 显示任务列表

`!!task detail [任务名称]` 查看任务详细信息

`!!task add [任务名称] [任务描述]` 添加任务

`!!task del [任务名称]` 删除任务

`!!task rename [旧任务名称] [新任务名称]` 重命名任务

`!!task change [任务名称] [新任务描述]` 修改任务描述

`!!task done [任务名称]` 标注任务为已完成

`!!task undone [任务名称]` 标注任务为未完成

注: 上述所有 `[任务名称]` 可以用 `[任务名称].[子任务名称]` 的形式来访问子任务

例: `!!task add 女巫塔.铺地板 挂机铺黑色玻璃`