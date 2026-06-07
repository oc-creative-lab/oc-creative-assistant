import { onBeforeUnmount, ref } from 'vue'

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value))

/**
 * Horizontal drag-resize for workspace side panels.
 * Attaches document-level listeners on mousedown and cleans up on mouseup.
 */
export function usePanelResize(options: {
  min: number
  max: number
  getWidth: () => number
  setWidth: (width: number) => void
  /** +1 when dragging right increases width; -1 when dragging right decreases width. */
  direction: 1 | -1
}) {
  const isDragging = ref(false)
  let removeListeners: (() => void) | null = null

  function stopDrag() {
    isDragging.value = false
    document.body.style.cursor = ''
    document.body.style.userSelect = ''
    removeListeners?.()
    removeListeners = null
  }

  function startDrag(event: MouseEvent) {
    event.preventDefault()
    isDragging.value = true
    const startX = event.clientX
    const startWidth = options.getWidth()

    const onMove = (moveEvent: MouseEvent) => {
      const delta = (moveEvent.clientX - startX) * options.direction
      options.setWidth(clamp(startWidth + delta, options.min, options.max))
    }

    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
    document.addEventListener('mousemove', onMove)
    document.addEventListener('mouseup', stopDrag, { once: true })
    removeListeners = () => {
      document.removeEventListener('mousemove', onMove)
    }
  }

  onBeforeUnmount(stopDrag)

  return { isDragging, startDrag, stopDrag }
}
