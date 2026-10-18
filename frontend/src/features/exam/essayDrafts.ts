/** 還沒存的申論草稿：交卷前、換題（元件卸載）時要先送出，不然停止輸入不到 1 秒的內容會遺失。
 * key 是「測驗 id-題號」，值是把那一題草稿送出的函式（EssayAnswer 掛上、卸載時移除）。 */
export const essayDraftFlushers = new Map<string, () => Promise<void>>()

/** 交卷前呼叫：把這次測驗所有還沒存的申論草稿送出 */
export async function flushEssayDrafts(sessionId: number) {
  const pending = [...essayDraftFlushers]
    .filter(([key]) => key.startsWith(`${sessionId}-`))
    .map(([, flush]) => flush())
  await Promise.all(pending)
}
