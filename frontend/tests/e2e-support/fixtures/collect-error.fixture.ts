// sanitizingReporter.integration.test.ts 執行的範例：測試檔最上層（收集階段）丟出帶著機密的錯誤
import { COLLECT_VALUE, EMAIL, JWT, QUERY_VALUE, url } from './leakValues'

throw Object.assign(new Error(`collect failed: ${url(QUERY_VALUE)} ${EMAIL} ${JWT}`), {
  session: COLLECT_VALUE,
  details: { note: `Bearer ${COLLECT_VALUE}` },
})
