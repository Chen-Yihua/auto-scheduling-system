// sanitizingReporter.integration.test.ts 執行的範例：每種會被 vitest 印出的錯誤與 console 輸出都帶著機密
import { afterAll, describe, expect, it } from 'vitest'
import {
  BEARER_TOKEN,
  CONSOLE_VALUE,
  COOKIE_VALUE,
  EMAIL,
  HOOK_TOKEN,
  JWT,
  LONG_COOKIE_VALUES,
  PASSWORD,
  QUERY_VALUE,
  SECRET_KEY,
  UNHANDLED_COOKIE_VALUES,
  cookies,
  longBuffer,
  url,
} from './leakValues'

describe('leaks', () => {
  afterAll(() => {
    throw new Error(`afterAll failed: Bearer ${HOOK_TOKEN} ${EMAIL}`)
  })

  it('string diff', () => {
    expect(`${url(QUERY_VALUE)} ${EMAIL} ${JWT}`).toBe('x')
  })

  it('object diff', () => {
    expect({
      who: EMAIL,
      callback: url(QUERY_VALUE),
      headers: { authorization: `Bearer ${BEARER_TOKEN}` },
      cookies: [{ name: '__clerk_db_jwt', value: COOKIE_VALUE }],
    }).toEqual({ who: 'x' })
  })

  it('error with extra properties and cause', () => {
    const error = new Error(`request to ${url(QUERY_VALUE)} failed for ${EMAIL}`, {
      cause: new Error(`cause: ${PASSWORD}`),
    })
    Object.assign(error, {
      headers: { Authorization: `Bearer ${BEARER_TOKEN}` },
      body: longBuffer(1),
      errors: [new Error(`nested: ${SECRET_KEY} ${JWT}`)],
      items: [{ name: '__session', value: COOKIE_VALUE }],
    })
    throw error
  })

  it('long cookie array differs only at the end', () => {
    expect(cookies(LONG_COOKIE_VALUES, '__actual')).toEqual(cookies(LONG_COOKIE_VALUES, '__expected'))
  })

  it('long Buffer differs only at the end', () => {
    expect(longBuffer(1)).toEqual(longBuffer(2))
  })

  it('unhandled assertion and console output', async () => {
    console.log(`console: ${EMAIL} ${url(QUERY_VALUE)} ${JWT} ${CONSOLE_VALUE} Bearer ${BEARER_TOKEN}`)
    // 沒有 await：assertion 錯誤變成沒被接住的 Promise 錯誤
    void Promise.resolve().then(() => {
      expect(cookies(UNHANDLED_COOKIE_VALUES, '__actual')).toEqual(cookies(UNHANDLED_COOKIE_VALUES, '__expected'))
    })
    void Promise.reject(new Error(`unhandled: ${SECRET_KEY} ${EMAIL}`))
    await new Promise((resolve) => setTimeout(resolve, 50))
  })
})
