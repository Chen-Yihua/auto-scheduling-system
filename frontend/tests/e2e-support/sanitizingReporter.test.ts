// @vitest-environment node
// e2e 清理用 reporter 的文字規則、結構規則與設定（#50）；reporter 在真的 vitest 裡是否有效由 sanitizingReporter.integration.test.ts 負責
import { afterEach, describe, expect, it, vi } from 'vitest'
import { sanitizeReportText, sanitizeReportValue } from '../e2e/support/sanitizingReporter'
import { e2eSecrets } from '../e2e/support/e2eSecrets'

const SECRETS = ['fixture-user@example.com', 'sk_test_FIXTURESECRET', 'fixture-password']
const text = (input: string) => sanitizeReportText(input, SECRETS)
const value = (input: unknown) => sanitizeReportValue(input, SECRETS)

describe('vitest.e2e.config.ts 的設定', () => {
  afterEach(() => {
    vi.unstubAllEnvs()
  })

  // 每次 resetModules 後兩個都要重新 import，否則 instanceof 比對的是不同次載入的類別
  async function loadConfig() {
    vi.resetModules()
    const { default: config } = await import('../../vitest.e2e.config')
    const { default: SanitizingReporter } = await import('../e2e/support/sanitizingReporter')
    return { test: config.test!, SanitizingReporter }
  }

  it("#50 AC1：GITHUB_ACTIONS 是 'true' 時，reporter 依序是清理用的 reporter、default、github-actions", async () => {
    vi.stubEnv('GITHUB_ACTIONS', 'true')
    const { test, SanitizingReporter } = await loadConfig()
    const reporters = test.reporters as unknown[]
    expect(reporters).toHaveLength(3)
    expect(reporters[0]).toBeInstanceOf(SanitizingReporter)
    expect(reporters.slice(1)).toEqual(['default', 'github-actions'])
  })

  it("#50 AC1：GITHUB_ACTIONS 不是 'true' 時，reporter 依序是清理用的 reporter、default", async () => {
    vi.stubEnv('GITHUB_ACTIONS', '')
    const { test, SanitizingReporter } = await loadConfig()
    const reporters = test.reporters as unknown[]
    expect(reporters).toHaveLength(2)
    expect(reporters[0]).toBeInstanceOf(SanitizingReporter)
    expect(reporters[1]).toBe('default')
  })

  it('#50 AC18：test.diff.expand 是 true', async () => {
    const { test } = await loadConfig()
    expect(test.diff).toEqual({ expand: true })
  })
})

describe('sanitizeReportText：文字規則', () => {
  it('#50 AC6：先拿掉 ANSI 色碼再套用 sanitizeForLog', () => {
    expect(text('\x1b[32m+   "url": "/cb?code=abc",\x1b[39m')).toBe('+   "url": "/cb",')
    expect(text('+   "who": "fixture-user@example.com",')).toBe('+   "who": "[redacted]",')
  })

  it('#50 AC7：敏感名稱後面接 : 或 = 時，分隔符號之後到行尾換成 [redacted]', () => {
    expect(text('+     "authorization": "Bearer opaqueTOKEN9",')).toBe('+     "authorization": [redacted]')
    expect(text('x?token=1')).toBe('x?token=[redacted]')
    expect(text('apiKey=abc; theme=dark')).toBe('apiKey=[redacted]')
    expect(text('+     "theme": "dark",')).toBe('+     "theme": "dark",')
  })

  it('#50 AC8：name 含敏感名稱時，之後到 } 之前的 value 照 AC7 處理', () => {
    expect(text('+     "name": "__clerk_db_jwt",\n+     "path": "/",\n+     "value": "dvb_X",\n+   },')).toBe(
      '+     "name": "__clerk_db_jwt",\n+     "path": "/",\n+     "value": [redacted]\n+   },',
    )
    expect(text("expected [ { name: '__clerk_db_jwt', value: 'dvb_X' } ] to deeply equal []")).toBe(
      "expected [ { name: '__clerk_db_jwt', value: [redacted]",
    )
    expect(text('+     "name": "__refresh_AbCd",\n+     "path": "/",\n+     "value": "opaqueREFRESH99",\n+   },')).toBe(
      '+     "name": "__refresh_AbCd",\n+     "path": "/",\n+     "value": [redacted]\n+   },',
    )
    expect(text('+     "name": "theme",\n+     "value": "dark",\n+   },')).toBe(
      '+     "name": "theme",\n+     "value": "dark",\n+   },',
    )
    expect(text("{ name: 'theme', value: 'dark' }")).toBe("{ name: 'theme', value: 'dark' }")
  })

  it('#50 AC9：Bearer 後面接的非空白字串換成 [redacted]', () => {
    expect(text('request failed with Bearer abc.def-ghi')).toBe('request failed with Bearer [redacted]')
  })

  it('#50 AC10：二進位類型的名稱接著 [ 到對應的 ]，整段換成 [binary]', () => {
    expect(text('expected Buffer[ 47, 99, 98, …(-86) ] to deeply equal Buffer[ 120 ]')).toBe(
      'expected [binary] to deeply equal [binary]',
    )
    expect(text('  Uint8Array [\n-   1,\n+   47,\n  ]')).toBe('  [binary]')
    expect(text('  Float32Array [\n+   1.5,\n  ]')).toBe('  [binary]')
  })

  it('#50 AC11："data": [ 底下只有整數時，從 [ 到 ] 換成 [binary]', () => {
    expect(text('    "data": [\n-     120,\n+     47,\n    ],')).toBe('    "data": [binary],')
    expect(text('    "data": [\n      "a",\n    ],')).toBe('    "data": [\n      "a",\n    ],')
  })

  it('#50 AC19：前面不是英數字或 _ 的 dvb_ 和後面的英數字換成 [redacted]', () => {
    expect(text("expected 'dvb_2abcXYZ' to be 'x'")).toBe("expected '[redacted]' to be 'x'")
  })

  it('#50 AC20：登入後診斷經過清理後不變', () => {
    const diagnostics =
      '{\n  "clerkState": {\n    "hasClerkSid": true\n  },\n  "browserStorageNames": [\n    "__clerk_db_jwt",\n    "__session"\n  ]\n}'
    expect(text(diagnostics)).toBe(diagnostics)
  })

  it('#50 AC21：有 diff 只印出一部分的標頭時，整個字串換成 [diff omitted]', () => {
    expect(text('- Expected\n+ Received\n\n@@ -18,8 +18,16 @@\n+     84,\n+     79,\n    ],')).toBe('[diff omitted]')
    expect(text('  Uint8Array [\n+   1,\n  ]')).toBe('  [binary]')
  })
})

describe('sanitizeReportValue：結構規則', () => {
  it('#50 AC12：欄位名稱是敏感名稱時，值整個換成 [redacted]', () => {
    expect(
      value({ headers: { Authorization: 'Bearer abc' }, token: 123, note: '/cb?code=abc fixture-user@example.com' }),
    ).toEqual({ headers: { Authorization: '[redacted]' }, token: '[redacted]', note: '/cb [redacted]' })
    expect(value({ cookies: [{ name: 'theme', value: 'dark' }] })).toEqual({ cookies: '[redacted]' })
  })

  it('#50 AC13：name 含敏感名稱時，同一個物件的 value 換成 [redacted]', () => {
    expect(
      value({ items: [{ name: '__clerk_db_jwt', value: 'dvb_X' }, { name: 'theme', value: 'dark' }] }),
    ).toEqual({ items: [{ name: '__clerk_db_jwt', value: '[redacted]' }, { name: 'theme', value: 'dark' }] })
    expect(value({ items: [{ name: '__refresh_AbCd', value: 'opaque' }] })).toEqual({
      items: [{ name: '__refresh_AbCd', value: '[redacted]' }],
    })
  })

  it('#50 AC14：序列化後的二進位資料整個換成 [binary]', () => {
    expect(
      value({
        body: { type: 'Buffer', data: [104, 105] },
        u8: { '0': 1, '1': 2, constructor: 'Function<Uint8Array>', length: 2 },
      }),
    ).toEqual({ body: '[binary]', u8: '[binary]' })
  })

  it('#50 AC15：循環參照時清理會結束、參照關係保留；同一份二進位資料被多個欄位參照時都換掉', () => {
    const a: Record<string, unknown> = { note: '/cb?code=abc' }
    a.self = a
    const result = value(a) as Record<string, unknown>
    expect(result.note).toBe('/cb')
    expect(result.self).toBe(result)

    const u8 = { '0': 1, constructor: 'Function<Uint8Array>' }
    expect(value({ a: u8, b: { c: u8 } })).toEqual({ a: '[binary]', b: { c: '[binary]' } })
  })
})

describe('e2eSecrets', () => {
  it('#50 AC16：清理清單取自三個環境變數，沒設定或是空字串的不放進清單', () => {
    expect(
      e2eSecrets({
        E2E_CLERK_TEST_EMAIL: 'a@example.com',
        NUXT_CLERK_SECRET_KEY: 'sk_test_x',
        E2E_CLERK_TEST_PASSWORD: 'p',
      }),
    ).toEqual(['a@example.com', 'sk_test_x', 'p'])
    expect(e2eSecrets({ E2E_CLERK_TEST_EMAIL: 'a@example.com', NUXT_CLERK_SECRET_KEY: '' })).toEqual(['a@example.com'])
  })
})
