/** Grow a textarea's height to fit its content. */
export function autoResizeTextarea(el: HTMLTextAreaElement | null | undefined) {
  if (!el) return
  el.style.height = 'auto'
  el.style.height = `${el.scrollHeight}px`
}

/** Grow an input's width to fit its text (capped by the parent). */
export function autoResizeInput(el: HTMLInputElement | null | undefined) {
  if (!el) return
  el.style.width = '0'
  el.style.width = `${el.scrollWidth}px`
}
