import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'

import WeeklyBarChart from '~/components/productivity/WeeklyBarChart.vue'

const weeks = [
  { week_start: '2026-10-26', completed: 2, completed_minutes: 90 },
  { week_start: '2026-11-02', completed: 4, completed_minutes: 30 },
]

describe('WeeklyBarChart', () => {
  it('每週一根柱子，高度依完成數比例，柱頂標數值、下方標週一日期', () => {
    const wrapper = mount(WeeklyBarChart, { props: { weeks } })

    const bars = wrapper.findAll('[data-testid="bar"]')
    expect(bars).toHaveLength(2)
    const heights = bars.map((bar) => Number(bar.attributes('data-height')))
    expect(heights[0]).toBeCloseTo(heights[1]! / 2)

    const text = wrapper.text()
    expect(text).toContain('10/26')
    expect(text).toContain('11/02')
    expect(wrapper.findAll('[data-testid="bar-value"]').map((v) => v.text())).toEqual(['2', '4'])
  })

  it('全部為 0 時不畫柱子也不會除以 0，數值仍標 0', () => {
    const wrapper = mount(WeeklyBarChart, {
      props: { weeks: weeks.map((w) => ({ ...w, completed: 0, completed_minutes: 0 })) },
    })

    expect(wrapper.findAll('[data-testid="bar"]')).toHaveLength(0)
    expect(wrapper.findAll('[data-testid="bar-value"]').map((v) => v.text())).toEqual(['0', '0'])
    expect(wrapper.html()).not.toContain('NaN')
  })

  it('附表格版本，讀屏和看不清顏色的人也能讀到每週數字與工時', () => {
    const wrapper = mount(WeeklyBarChart, { props: { weeks } })

    const rows = wrapper.findAll('tbody tr').map((row) => row.findAll('td').map((td) => td.text()))
    expect(rows).toEqual([
      ['10/26', '2', '1 小時 30 分'],
      ['11/02', '4', '30 分'],
    ])
  })
})
