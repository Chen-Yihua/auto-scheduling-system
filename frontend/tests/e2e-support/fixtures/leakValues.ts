// 範例測試檔用的機密：都在執行時才組出來，vitest 印的原始碼節錄裡就不會出現完整的值
const join = (...parts: string[]) => parts.join('')

export const EMAIL = join('fixture-user', '@example.com')
export const SECRET_KEY = join('sk_test_', 'FIXTURESECRET')
export const PASSWORD = join('fixture-', 'password')
export const SECRETS = [EMAIL, SECRET_KEY, PASSWORD]

export const QUERY_VALUE = join('QUERY', 'VALUE42')
export const JWT = join('eyJ', 'hbGciOiJIUzI1NiJ9', '.', 'eyJzdWIiOiJ', 'JWTPAYLOAD', '.', 'JWT', 'SIGNATURE')
export const BEARER_TOKEN = join('opaque', 'BEARER77')
export const HOOK_TOKEN = join('hook', 'BEARER88')
export const COOKIE_VALUE = join('dvb_', 'COOKIE', 'VALUE1')
export const CONSOLE_VALUE = join('dvb_', 'CONSOLE', 'VALUE2')
export const COLLECT_VALUE = join('dvb_', 'COLLECT', 'VALUE3')
// 改動只在長陣列尾端時，前面沒改動的 cookie 值也會被印出
export const LONG_COOKIE_VALUES = [join('dvb_', 'LONG', 'A1'), join('dvb_', 'LONG', 'B2'), join('dvb_', 'LONG', 'C3')]
export const UNHANDLED_COOKIE_VALUES = [join('dvb_', 'UNH', 'A1'), join('dvb_', 'UNH', 'B2'), join('dvb_', 'UNH', 'C3')]
export const BYTES_TEXT = join('TOKEN', 'XYZ')

export const url = (value: string) => join('https://example.com/cb?code=', value)

// 只有最後一個 cookie 的 name 不同：diff 只印改動附近的行時，前一個 cookie 的 value 會印出、name 不會
export function cookies(values: string[], lastName: string) {
  const names = ['__clerk_db_jwt', '__session', '__client_uat', lastName]
  return [...values, join('dvb_', 'LAST')].map((value, index) => ({ domain: 'localhost', name: names[index]!, path: '/', value }))
}

// 位元組在尾端以外都相同，diff 只會改到最後一個位元組
export function longBuffer(last: number) {
  return Buffer.from([...Buffer.from(BYTES_TEXT), ...new Array<number>(20).fill(46), last])
}
