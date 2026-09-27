/** 主交易页面：极光玻璃态背景 + 三栏布局（市场列表 | K 线图 | 交易面板）+ 底部标签页。
 *  仅视觉重构：数据流与业务逻辑保持不变。极光背景由 App 全局层提供。 */

import BottomTabs from './BottomTabs'
import KlineChart from './KlineChart'
import MarketList from './MarketList'
import OrderPanel from './OrderPanel'
import GlassCard from './ui/GlassCard'

export default function TradingPage() {
  return (
    <div className="relative flex flex-col gap-3 px-1 pb-3" style={{ height: 'calc(100vh - 106px)' }}>
      <div className="flex min-h-0 flex-1 gap-3">
        <GlassCard className="w-[264px] shrink-0 overflow-auto" noLift>
          <MarketList />
        </GlassCard>

        <GlassCard className="min-w-0 flex-1" noLift>
          <KlineChart />
        </GlassCard>

        <GlassCard className="w-[304px] shrink-0 overflow-auto" noLift>
          <OrderPanel />
        </GlassCard>
      </div>

      <GlassCard className="h-[248px] shrink-0 overflow-hidden" noLift>
        <BottomTabs />
      </GlassCard>
    </div>
  )
}
