// e2e 的清理用 reporter（#50）：在其他 reporter 印出之前，原地清理 vitest 交來的錯誤與 console 輸出，
// 因為這些內容會進公開的 CI log。vitest.e2e.config.ts 要把它排在所有 reporter 的第一個。
import type {
  Reporter,
  RunnerTask as Task,
  RunnerTaskResultPack as TaskResultPack,
  RunnerTestFile as File,
  TestModule,
} from 'vitest/node'
import type { UserConsoleLog } from 'vitest'
import { stripVTControlCharacters } from 'node:util'
import { sanitizeForLog } from './signInWithRetry'

const SENSITIVE_NAMES = ['authorization', 'cookie', 'password', 'token', 'secret', 'apikey', 'api_key', 'jwt', 'session']
const BINARY_TYPES = [
  'Buffer',
  'ArrayBuffer',
  'SharedArrayBuffer',
  'DataView',
  'Int8Array',
  'Uint8Array',
  'Uint8ClampedArray',
  'Int16Array',
  'Uint16Array',
  'Int32Array',
  'Uint32Array',
  'Float32Array',
  'Float64Array',
  'BigInt64Array',
  'BigUint64Array',
]
const REDACTED = '[redacted]'
const BINARY = '[binary]'

const PARTIAL_DIFF_HEADER = /@@ -\d+,\d+ \+\d+,\d+ @@/
const NAME_WITH_SEPARATOR = /["'`]?([A-Za-z0-9_.-]+)["'`]?\s*[:=]\s*/g
const NAME_FIELD = /(?<![A-Za-z0-9_.-])["'`]?name["'`]?\s*[:=]\s*["'`]?([^"'`\s,}]*)/g
const VALUE_FIELD = /(?<![A-Za-z0-9_.-])["'`]?value["'`]?\s*[:=]\s*/g
const BEARER = /(Bearer )\S+/g
const BINARY_START = new RegExp(`(?<![A-Za-z0-9_])(?:${BINARY_TYPES.join('|')})\\s*\\[`, 'g')
const DATA_ARRAY_START = /"data"\s*:\s*\[/g
const DEV_BROWSER_TOKEN = /(?<![A-Za-z0-9_])dvb_[A-Za-z0-9]+/g

function isSensitiveName(name: string): boolean {
  const lower = name.toLowerCase()
  return SENSITIVE_NAMES.some((sensitive) => lower.includes(sensitive))
}

function lineEnd(text: string, from: number): number {
  const end = text.indexOf('\n', from)
  return end === -1 ? text.length : end
}

// 規則 3：同一行裡第一個敏感名稱之後到行尾都遮掉
function redactSensitiveAssignments(line: string): string {
  for (const match of line.matchAll(NAME_WITH_SEPARATOR)) {
    if (isSensitiveName(match[1]!)) return line.slice(0, match.index + match[0].length) + REDACTED
  }
  return line
}

// 規則 4：Playwright cookie 這類 { name, value }，name 敏感時遮掉 value；兩者可能不在同一行
function redactValuesOfSensitiveNames(text: string): string {
  let result = text
  let searchFrom = 0
  for (;;) {
    NAME_FIELD.lastIndex = searchFrom
    const name = NAME_FIELD.exec(result)
    if (!name) return result
    searchFrom = name.index + name[0].length
    if (!isSensitiveName(name[1]!)) continue
    VALUE_FIELD.lastIndex = searchFrom
    const value = VALUE_FIELD.exec(result)
    const closing = result.indexOf('}', searchFrom)
    if (!value || (closing !== -1 && closing < value.index)) continue
    const valueStart = value.index + value[0].length
    result = result.slice(0, valueStart) + REDACTED + result.slice(lineEnd(result, valueStart))
    searchFrom = valueStart + REDACTED.length
  }
}

// 回傳和 text[open] 的 [ 對應的 ] 的位置；找不到時回傳 -1
function matchingBracket(text: string, open: number): number {
  let depth = 0
  for (let i = open; i < text.length; i++) {
    if (text[i] === '[') depth++
    else if (text[i] === ']' && --depth === 0) return i
  }
  return -1
}

// 規則 6：訊息裡的 Buffer[ 1, 2 ]、diff 裡的 Uint8Array [ 底下一行一個數字
function redactBinaryTypes(text: string): string {
  let result = text
  for (;;) {
    BINARY_START.lastIndex = 0
    const match = BINARY_START.exec(result)
    if (!match) return result
    const close = matchingBracket(result, match.index + match[0].length - 1)
    // 找不到對應的 ]（例如內容被截斷）時，遮到字串結尾
    result = result.slice(0, match.index) + BINARY + (close === -1 ? '' : result.slice(close + 1))
  }
}

// 規則 6：Buffer 在 diff 裡是 "data": [ 底下一行一個數字
function redactBufferData(text: string): string {
  let result = text
  let searchFrom = 0
  for (;;) {
    DATA_ARRAY_START.lastIndex = searchFrom
    const match = DATA_ARRAY_START.exec(result)
    if (!match) return result
    const open = match.index + match[0].length - 1
    const close = result.indexOf(']', open)
    searchFrom = open + 1
    if (close === -1) continue
    const inner = result.slice(open + 1, close)
    const integersOnly = inner.split('\n').every((line) => /^[\d,]*$/.test(line.replace(/[+\-\s]/g, '')))
    if (!integersOnly || !/\d/.test(inner)) continue
    result = result.slice(0, open) + BINARY + result.slice(close + 1)
  }
}

export function sanitizeReportText(text: string, secrets: string[]): string {
  const plain = stripVTControlCharacters(text)
  if (plain.split('\n').some((line) => PARTIAL_DIFF_HEADER.test(line))) return '[diff omitted]'
  let result = sanitizeForLog(plain, secrets)
  result = result.split('\n').map(redactSensitiveAssignments).join('\n')
  result = redactValuesOfSensitiveNames(result)
  result = result.replace(BEARER, `$1${REDACTED}`)
  result = redactBinaryTypes(result)
  result = redactBufferData(result)
  return result.replace(DEV_BROWSER_TOKEN, REDACTED)
}

function isSerializedBinary(value: object): boolean {
  const record = value as Record<string, unknown>
  if (record.type === 'Buffer' && Array.isArray(record.data)) return true
  const constructorName = Object.prototype.hasOwnProperty.call(value, 'constructor') ? record.constructor : undefined
  if (typeof constructorName !== 'string') return false
  const match = /^Function<(.+)>$/.exec(constructorName)
  return !!match && BINARY_TYPES.includes(match[1]!)
}

// 原地清理 vitest 交來的資料：後面的 reporter 讀的是同一份
export function sanitizeReportValue(value: unknown, secrets: string[], seen = new WeakSet<object>()): unknown {
  if (typeof value === 'string') return sanitizeReportText(value, secrets)
  if (typeof value !== 'object' || value === null) return value
  // 要在 seen 檢查之前：同一份二進位資料被第二個欄位參照時，也要換掉
  if (isSerializedBinary(value)) return BINARY
  if (seen.has(value)) return value
  seen.add(value)
  if (Array.isArray(value)) {
    for (let i = 0; i < value.length; i++) value[i] = sanitizeReportValue(value[i], secrets, seen)
    return value
  }
  const record = value as Record<string, unknown>
  // 主行程自己的錯誤沒有序列化過，message、stack 不可列舉，Object.keys 拿不到
  if (value instanceof Error) {
    value.message = sanitizeReportText(value.message, secrets)
    if (typeof value.stack === 'string') value.stack = sanitizeReportText(value.stack, secrets)
  }
  const hasSensitiveName = typeof record.name === 'string' && isSensitiveName(record.name)
  for (const key of Object.keys(record)) {
    if (isSensitiveName(key) || (hasSensitiveName && key === 'value')) record[key] = REDACTED
    else record[key] = sanitizeReportValue(record[key], secrets, seen)
  }
  return value
}

function tasksOf(task: Task): Task[] {
  return task.type === 'suite' ? [task, ...task.tasks.flatMap(tasksOf)] : [task]
}

// 每個方法都要同步：vitest 用 Promise.all 依序呼叫每個 reporter，await 之後下一個 reporter 會先印出沒清理的內容
export default class SanitizingReporter implements Reporter {
  private readonly secrets: string[]

  constructor(options: { secrets: string[] }) {
    this.secrets = options.secrets
  }

  private sanitizeErrors(errors: ReadonlyArray<unknown> | undefined) {
    if (errors) sanitizeReportValue(errors, this.secrets)
  }

  private sanitizeFiles(files: File[] | undefined) {
    for (const task of (files ?? []).flatMap(tasksOf)) this.sanitizeErrors(task.result?.errors)
  }

  onCollected(files: File[]) {
    this.sanitizeFiles(files)
  }

  onTaskUpdate(packs: TaskResultPack[]) {
    for (const [, result] of packs) this.sanitizeErrors(result?.errors)
  }

  onUserConsoleLog(log: UserConsoleLog) {
    log.content = sanitizeReportText(log.content, this.secrets)
  }

  onTestRunEnd(modules: ReadonlyArray<TestModule>, errors: ReadonlyArray<unknown>) {
    for (const module of modules) {
      this.sanitizeErrors(module.errors())
      for (const suite of module.children.allSuites()) this.sanitizeErrors(suite.errors())
      for (const test of module.children.allTests()) this.sanitizeErrors(test.result().errors)
    }
    // vitest 傳給每個 reporter 的是同一個陣列，要改這一個，不能複製
    this.sanitizeErrors(errors)
  }

  onFinished(files: File[], errors: unknown[]) {
    this.sanitizeFiles(files)
    this.sanitizeErrors(errors)
  }
}
