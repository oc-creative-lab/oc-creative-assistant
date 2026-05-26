import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

interface DockPosition {
  x: number
  y: number
}

interface DragState {
  mode: 'bar' | 'ball'
  pointerStartX: number
  pointerStartY: number
  initialX: number
  initialY: number
  moved: boolean
}

interface Options {
  /**
   * 悬浮球被"点击但未拖动"时触发 (如折叠 / 展开聊天栏); 拖动结束 (moved=true)
   * 不调, 避免误触。
   */
  onBallClick: () => void
}

const BAR_POSITION_KEY = 'oc-creative.chat-dock-bar-position'
const BALL_POSITION_KEY = 'oc-creative.chat-dock-ball-position'
const DRAG_THRESHOLD_PX = 5
const VIEWPORT_MARGIN = 8
const BAR_SIZE = { width: 720, height: 64 }
const BALL_SIZE = { width: 56, height: 56 }

/**
 * 把"输入栏 / 悬浮球的拖动 + 视窗约束 + localStorage 位置持久化"
 * 收成一个 composable, 让宿主组件只关心对话语义。
 *
 * 拖动结束后, 位置写入 localStorage; 下一次挂载时从 localStorage 恢复。
 * 球的 click vs drag 由位移阈值区分: 鼠标按下到松开的位移 < 5px 视为 click。
 */
export function useDraggableDock(options: Options) {
  const barPosition = ref<DockPosition | null>(null)
  const ballPosition = ref<DockPosition | null>(null)

  let dragState: DragState | null = null

  const barStyle = computed(() => {
    if (barPosition.value) {
      return {
        left: `${barPosition.value.x}px`,
        top: `${barPosition.value.y}px`,
        transform: 'none',
      }
    }
    return {
      left: '50%',
      top: '50%',
      transform: 'translate(-50%, -50%)',
    }
  })

  const ballStyle = computed(() => {
    if (ballPosition.value) {
      return {
        left: `${ballPosition.value.x}px`,
        top: `${ballPosition.value.y}px`,
        right: 'auto',
        bottom: 'auto',
      }
    }
    return {}
  })

  function clampToViewport(x: number, y: number, width: number, height: number): DockPosition {
    return {
      x: Math.max(VIEWPORT_MARGIN, Math.min(x, window.innerWidth - width - VIEWPORT_MARGIN)),
      y: Math.max(VIEWPORT_MARGIN, Math.min(y, window.innerHeight - height - VIEWPORT_MARGIN)),
    }
  }

  function readInitialPosition(mode: 'bar' | 'ball', el: HTMLElement): DockPosition {
    const stored = mode === 'bar' ? barPosition.value : ballPosition.value
    if (stored) return stored
    const rect = el.getBoundingClientRect()
    return { x: rect.left, y: rect.top }
  }

  function readStored<T>(key: string): T | null {
    const raw = localStorage.getItem(key)
    if (!raw) return null
    try {
      return JSON.parse(raw) as T
    } catch {
      return null
    }
  }

  function onBarMouseDown(event: MouseEvent) {
    const target = event.target as HTMLElement
    /* 输入框 / 按钮 / 上下浮层都不应该触发拖动, 让交互归交互 */
    if (target.closest('input, textarea, button, .bar-dock__reply, .bar-dock__staging-pop')) {
      return
    }
    const dockEl = event.currentTarget as HTMLElement
    const initial = readInitialPosition('bar', dockEl)
    dragState = {
      mode: 'bar',
      pointerStartX: event.clientX,
      pointerStartY: event.clientY,
      initialX: initial.x,
      initialY: initial.y,
      moved: false,
    }
    event.preventDefault()
  }

  function onBallMouseDown(event: MouseEvent) {
    const ballEl = event.currentTarget as HTMLElement
    const initial = readInitialPosition('ball', ballEl)
    dragState = {
      mode: 'ball',
      pointerStartX: event.clientX,
      pointerStartY: event.clientY,
      initialX: initial.x,
      initialY: initial.y,
      moved: false,
    }
    event.preventDefault()
  }

  function onMouseMove(event: MouseEvent) {
    if (!dragState) return
    const dx = event.clientX - dragState.pointerStartX
    const dy = event.clientY - dragState.pointerStartY
    if (!dragState.moved && Math.hypot(dx, dy) > DRAG_THRESHOLD_PX) {
      dragState.moved = true
    }
    if (dragState.mode === 'ball' && !dragState.moved) return

    const size = dragState.mode === 'bar' ? BAR_SIZE : BALL_SIZE
    const next = clampToViewport(
      dragState.initialX + dx,
      dragState.initialY + dy,
      size.width,
      size.height,
    )
    if (dragState.mode === 'bar') {
      barPosition.value = next
    } else {
      ballPosition.value = next
    }
  }

  function onMouseUp() {
    if (!dragState) return
    const { mode, moved } = dragState
    dragState = null

    if (mode === 'bar' && barPosition.value) {
      localStorage.setItem(BAR_POSITION_KEY, JSON.stringify(barPosition.value))
      return
    }
    if (mode === 'ball') {
      if (ballPosition.value) {
        localStorage.setItem(BALL_POSITION_KEY, JSON.stringify(ballPosition.value))
      }
      if (!moved) options.onBallClick()
    }
  }

  onMounted(() => {
    barPosition.value = readStored<DockPosition>(BAR_POSITION_KEY)
    ballPosition.value = readStored<DockPosition>(BALL_POSITION_KEY)
    /* 监听挂在 window 上, 拖动过程鼠标离开 dock 也仍能跟手 */
    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', onMouseUp)
  })

  onBeforeUnmount(() => {
    window.removeEventListener('mousemove', onMouseMove)
    window.removeEventListener('mouseup', onMouseUp)
  })

  return {
    barStyle,
    ballStyle,
    onBarMouseDown,
    onBallMouseDown,
  }
}