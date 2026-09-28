package com.wenqing.feenote.util

/**
 * 通用的「快照栈」：记一步、撤销、恢复。
 *
 * 为什么不直接写进 `Repository`：`Repository` 依赖 Android 的 `SQLiteDatabase`，
 * JVM 单元测试跑不起来。把栈抽出来之后，边界行为（撤销后按钮该亮、
 * 做了新动作后 redo 该清掉、栈深有上限）就能直接测了 ——
 * 这几个地方恰恰是纸糊的 bug 最爱待的地方。
 *
 * 语义：
 * - [push] 记下「动作发生**之前**的状态」，label 描述的是即将发生的那个动作；
 * - [undo] 把当前状态交回来（调用方拿去 restore），同时把它收进 redo 栈；
 * - [redo] 反过来再来一遍。
 *
 * @param limit 最多记多少步，超了丢最老的
 */
class SnapshotStack<T>(private val limit: Int = 30) {

    /** 一步：label 给人看，value 是那一刻的完整状态 */
    data class Entry<T>(val label: String, val value: T)

    /** 撤销/恢复的产物：把 [value] 换回去，[label] 用来说人话 */
    data class Restore<T>(val label: String, val value: T)

    private val undoStack = ArrayDeque<Entry<T>>()
    private val redoStack = ArrayDeque<Entry<T>>()

    val canUndo: Boolean get() = undoStack.isNotEmpty()
    val canRedo: Boolean get() = redoStack.isNotEmpty()

    /** 还能撤销几步 */
    val size: Int get() = undoStack.size

    val undoLabel: String? get() = undoStack.lastOrNull()?.label
    val redoLabel: String? get() = redoStack.lastOrNull()?.label

    fun clear() {
        undoStack.clear()
        redoStack.clear()
    }

    /**
     * 记一步（[value] = 动作发生之前的状态）。
     *
     * **新动作会清掉 redo 栈** —— 和所有编辑器的行为一致：
     * 撤销两步之后又做了新动作，那两条撤销掉的旧路就不该还能"重做"回来。
     */
    fun push(label: String, value: T) {
        undoStack.addLast(Entry(label, value))
        while (undoStack.size > limit) undoStack.removeFirst()
        redoStack.clear()
    }

    /** 撤销一步。返回需要换回去的状态；没得撤返回 null */
    fun undo(current: T): Restore<T>? {
        val e = undoStack.removeLastOrNull() ?: return null
        redoStack.addLast(Entry(e.label, current))
        while (redoStack.size > limit) redoStack.removeFirst()
        return Restore(e.label, e.value)
    }

    /** 恢复（重做）刚撤销掉的那一步 */
    fun redo(current: T): Restore<T>? {
        val e = redoStack.removeLastOrNull() ?: return null
        undoStack.addLast(Entry(e.label, current))
        while (undoStack.size > limit) undoStack.removeFirst()
        return Restore(e.label, e.value)
    }
}
