**English** | [中文](./README_cn.md)

# Task

A plugin shows tasks of project in progress

Requires [MCDReforged](https://github.com/Fallen-Breath/MCDReforged) >= 2.1.3

[stext](https://github.com/TISUnion/stext) is no longer required. [MCDeamon](https://github.com/kafuuchino-desu/MCDaemon) and [MCDReforged](https://github.com/Fallen-Breath/MCDReforged) 1.x and earlier is no longer supported

### Usage

`!!task help` Show help message

`!!task overview` Show task overview (also the default behavior of `!!task`)

`!!task list` Show task list

`!!task detail <task>` Show task detail

`!!task list-all <task>` Show all tasks and sub-tasks

`!!task list-done <task>` Show tasks which were marked as done

`!!task add <task> [<description>]` Add a task

`!!task remove/rm/delete/del <task>` Remove a task

`!!task rename <old task> <new task>` Rename a task

`!!task change <task> <new description>` Edit a task description 

`!!task done <task>` Mark task as done

`!!task undone <task>` Mark task as undone

`!!task deadline <task> <period: day>` Set deadline for the task

`!!task player <task>` Show player task list

`!!task res[ponsible] <task> <player>` Set responsibles for this task

`!!task unres[ponsible] <task> <player>` Remove responsibles from this task

PS: All the `<task>` above can be replaced by `<task>.<sub-task>` to access sub-task

e.g. `!!task add Witch_Hut.Floor AFK black glass placement`
