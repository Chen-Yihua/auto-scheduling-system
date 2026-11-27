// E2E 用的假 Google 日曆伺服器：回應後端用到的 calendarList、FreeBusy、事件的新增／讀取／刪除、OAuth token，
// 並記錄收到的請求，測試從 GET /__e2e/requests 讀回。後端用 GOOGLE_API_BASE_URL 指向它。
// 不呼叫 console：E2E 的程式只有 createDiagnosticLogger 可以呼叫（e2e-playwright AC15），啟動訊息改寫 stdout。
import { createServer } from 'node:http'

const port = Number(process.argv[2])
const PRIMARY_CALENDAR_ID = 'e2e-primary-calendar'
const requests = []

function readBody(req) {
  return new Promise((resolve) => {
    const chunks = []
    req.on('data', (chunk) => chunks.push(chunk))
    req.on('end', () => resolve(Buffer.concat(chunks).toString()))
  })
}

function parseJson(text) {
  try {
    return JSON.parse(text)
  } catch {
    return {}
  }
}

function send(res, status, body) {
  if (body === undefined) {
    res.writeHead(status).end()
    return
  }
  res.writeHead(status, { 'content-type': 'application/json' }).end(JSON.stringify(body))
}

const server = createServer(async (req, res) => {
  const { pathname } = new URL(req.url ?? '/', 'http://localhost')
  const method = req.method ?? 'GET'

  if (method === 'GET' && pathname === '/__e2e/requests') {
    send(res, 200, requests)
    return
  }
  // 只記路徑，不記 header 與 body：請求帶著 token、client secret
  requests.push({ method, path: pathname })
  const body = parseJson(await readBody(req))

  if (method === 'POST' && pathname === '/token') {
    send(res, 200, { access_token: 'e2e-fake-access-token', expires_in: 3600, token_type: 'Bearer' })
  } else if (method === 'GET' && pathname === '/calendar/v3/users/me/calendarList') {
    send(res, 200, { items: [{ id: PRIMARY_CALENDAR_ID, summary: 'E2E', primary: true, accessRole: 'owner' }] })
  } else if (method === 'POST' && pathname === '/calendar/v3/freeBusy') {
    const calendarId = body.items?.[0]?.id ?? PRIMARY_CALENDAR_ID
    send(res, 200, { timeMin: body.timeMin, timeMax: body.timeMax, calendars: { [calendarId]: { busy: [] } } })
  } else if (method === 'POST' && /^\/calendar\/v3\/calendars\/[^/]+\/events$/.test(pathname)) {
    send(res, 200, { id: `e2e-event-${requests.length}`, summary: body.summary, start: body.start, end: body.end })
  } else if (method === 'GET' && /^\/calendar\/v3\/calendars\/[^/]+\/events\/[^/]+$/.test(pathname)) {
    send(res, 200, { id: pathname.split('/').pop(), status: 'confirmed' })
  } else if (method === 'DELETE' && /^\/calendar\/v3\/calendars\/[^/]+\/events\/[^/]+$/.test(pathname)) {
    send(res, 204)
  } else {
    send(res, 404, { error: { code: 404, message: 'not found' } })
  }
})

// 只聽 127.0.0.1：不讓區網的其他機器連到
server.listen(port, '127.0.0.1', () => process.stdout.write(`假的 Google 日曆伺服器已啟動：http://127.0.0.1:${port}\n`))

for (const signal of ['SIGINT', 'SIGTERM']) {
  process.on(signal, () => server.close(() => process.exit(0)))
}
