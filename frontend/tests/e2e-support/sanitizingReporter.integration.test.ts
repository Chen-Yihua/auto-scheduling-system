// @vitest-environment node
// 真的執行一次 vitest，確認清理用的 reporter 在現在的 vitest 版本仍然有效（#50 需求 11）：
// vitest 升級後改了呼叫 reporter 的方式時，這裡會抓到機密又出現在輸出裡
import { Writable } from 'node:stream'
import { fileURLToPath } from 'node:url'
import { stripVTControlCharacters } from 'node:util'
import { describe, expect, it } from 'vitest'
import { startVitest } from 'vitest/node'
import type { Reporter } from 'vitest/reporters'
import SanitizingReporter from '../e2e/support/sanitizingReporter'
import {
  BEARER_TOKEN,
  BYTES_TEXT,
  COLLECT_VALUE,
  CONSOLE_VALUE,
  COOKIE_VALUE,
  HOOK_TOKEN,
  JWT,
  LONG_COOKIE_VALUES,
  QUERY_VALUE,
  SECRETS,
  UNHANDLED_COOKIE_VALUES,
} from './fixtures/leakValues'

const FIXTURES_DIR = fileURLToPath(new URL('./fixtures', import.meta.url))

async function runFixtures(reporters: (Reporter | string)[]): Promise<string> {
  let output = ''
  const sink = () =>
    new Writable({
      write(chunk, _encoding, callback) {
        output += String(chunk)
        callback()
      },
    })
  const exitCode = process.exitCode
  try {
    const vitest = await startVitest(
      'test',
      [],
      {
        config: false,
        watch: false,
        root: FIXTURES_DIR,
        include: ['leaks.fixture.ts', 'collect-error.fixture.ts'],
        environment: 'node',
        reporters: reporters as never,
        diff: { expand: true },
      },
      {},
      { stdout: sink(), stderr: sink() },
    )
    await vitest.close()
  } finally {
    // 範例本來就會失敗，startVitest 會設定 exitCode；不還原的話外層的 npm run test 會失敗
    process.exitCode = exitCode
  }
  return stripVTControlCharacters(output)
}

const BYTES = [...Buffer.from(BYTES_TEXT)]

// 每個機密在輸出裡可能出現的形式；位元組在訊息與 Serialized Error 裡是同一行，在 diff 裡一行一個
const LEAKS: Record<string, (output: string) => number> = {
  ...Object.fromEntries(
    [
      ...SECRETS,
      QUERY_VALUE,
      JWT,
      BEARER_TOKEN,
      HOOK_TOKEN,
      COOKIE_VALUE,
      CONSOLE_VALUE,
      COLLECT_VALUE,
      ...LONG_COOKIE_VALUES,
      // 沒被接住的錯誤的 diff 只印改動附近的行，前兩個 cookie 的值本來就不會印出
      UNHANDLED_COOKIE_VALUES[2]!,
    ].map((secret) => [secret, (output: string) => output.split(secret).length - 1]),
  ),
  'bytes on one line': (output) => output.split(BYTES.join(', ')).length - 1,
  'bytes one per line': (output) => {
    const lines = output.split('\n').map((line) => line.replace(/^[\s+-]*/, '').trim())
    return lines.join('\n').split(BYTES.map((byte) => `${byte},`).join('\n')).length - 1
  },
}

function countLeaks(output: string) {
  return Object.fromEntries(Object.entries(LEAKS).map(([name, count]) => [name, count(output)]))
}

describe('清理用的 reporter 在真的 vitest 裡', () => {
  it('#50 AC2～AC5：有清理用的 reporter 時，default 與 github-actions 的輸出裡不出現任何機密', async () => {
    const output = await runFixtures([new SanitizingReporter({ secrets: SECRETS }), 'default', 'github-actions'])
    // 確認範例真的跑到：測試失敗、hook 錯誤、收集階段錯誤、沒被接住的錯誤、console、::error 附註都有印出
    expect(output).toContain('string diff')
    expect(output).toContain('afterAll failed')
    expect(output).toContain('collect failed')
    expect(output).toContain('Unhandled')
    expect(output).toContain('console:')
    expect(output).toContain('::error')
    expect(countLeaks(output)).toEqual(Object.fromEntries(Object.keys(LEAKS).map((name) => [name, 0])))
  }, 120_000)

  it('#50 AC2～AC5：沒有清理用的 reporter 時，每個機密至少出現一次（證明範例真的會外洩）', async () => {
    const output = await runFixtures(['default', 'github-actions'])
    for (const [name, count] of Object.entries(countLeaks(output))) {
      expect(count, name).toBeGreaterThan(0)
    }
  }, 120_000)
})
