import { mockGraphNodes } from './graph'
import type { AgentMode, AgentSuggestion, ProjectGroup, WorkspaceStatus } from '../types/workspace'
import { buildProjectGroupsFromNodes } from '../utils/nodeFactory'

/** PoC 默认项目名称，与后端默认项目名对齐；供前端独立演示和旧入口显示。 */
export const mockProjectName = '《咒术回战》涉谷站线'

/** 旧左侧分组数据，真实 graph 已改为从后端加载。 */
export const mockProjectGroups: ProjectGroup[] = buildProjectGroupsFromNodes(mockGraphNodes)

/** Agent 占位建议，供尚未接入真实 LLM 的 UI 状态使用。 */
export const mockAgentSuggestions: Record<AgentMode, AgentSuggestion[]> = {
  inspiration: [
    {
      id: 'idea-ticket-cost',
      title: '给半价月票增加代价',
      body: '当前可以追问一个古怪代价：使用半价月票的人虽然能无限乘车，但每换乘一次，就会忘记一个真实站名。',
    },
    {
      id: 'idea-station-visual',
      title: '强化车站怪谈视觉',
      body: '可以把咒力痕迹统一成发霉的站牌、反向滚动的电子屏、没有出口编号的换乘通道和自动流血的闸机灯。',
    },
    {
      id: 'idea-announcement-choice',
      title: '制造广播选择压力',
      body: '让虎杖检票员在关闭午夜广播和救下被点名乘客之间做选择：广播一旦停止，第零站台也会永久移动到更深一层。',
    },
  ],
  research: [
    {
      id: 'research-zero-platform',
      title: '补齐第零站台规则',
      body: '可以为涉谷地下第零站台补充三层规则：普通乘客能看见什么、咒术师能看见什么、被车站吞掉的人会变成什么。',
    },
    {
      id: 'research-cursed-facilities',
      title: '整理站内咒物设施',
      body: '当前设定适合追加一份车站设施清单，例如闸机、售票机、失物招领处、换乘电梯、报站屏分别寄宿不同类型的咒灵。',
    },
  ],
  structure: [
    {
      id: 'structure-last-train-chain',
      title: '整理末班车链路',
      body: '建议将异常末班车、第零站台显形、半价月票苏醒、午夜广播点名、终点站换乘仪式串成连续剧情节点。',
    },
    {
      id: 'structure-character-relation',
      title: '建立站员关系网',
      body: '虎杖检票员、五条站长和钉崎失物招领员的关系可以从“车站同事”展开，逐步变成共同对抗第零站台的临时咒术班组。',
    },
  ],
}

/** 工作区状态占位；保存状态会在 AppShell 中被真实后端状态覆盖。 */
export const mockWorkspaceStatus: WorkspaceStatus = {
  saveState: '第零站台草稿已保存',
  indexState: '咒物资料索引待构建',
  modelState: '模型：本地咒力占位',
}