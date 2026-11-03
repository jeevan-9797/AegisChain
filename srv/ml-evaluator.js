import { execFile } from 'node:child_process'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const repositoryRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const defaultTimeoutMs = 15_000
const maxOutputBytes = 2 * 1024 * 1024

export class MlCliError extends Error {
  constructor(status, message) {
    super(message)
    this.name = 'MlCliError'
    this.status = status
  }
}

function executeCli(command, args, request, options) {
  return new Promise(resolve => {
    let child
    try {
      child = execFile(command, args, options, (error, stdout, stderr) => {
        resolve({ error, stdout: stdout ?? '', stderr: stderr ?? '' })
      })
      if (!child.stdin) {
        resolve({ error: new Error('ML process stdin is unavailable'), stdout: '', stderr: '' })
        return
      }
      child.stdin.end(JSON.stringify(request))
    } catch (error) {
      resolve({ error, stdout: '', stderr: '' })
    }
  })
}

/** Create an isolated stdin/stdout evaluator for the existing Python CLI. */
export function createMlCliEvaluator({
  command = process.env.AEGISCHAIN_PYTHON || (process.platform === 'win32' ? 'python' : 'python3'),
  timeoutMs = Number(process.env.AEGISCHAIN_ML_TIMEOUT_MS) || defaultTimeoutMs,
  execute = executeCli
} = {}) {
  return async request => {
    const { error, stdout, stderr } = await execute(command, ['-m', 'ml.cli'], request, {
      cwd: repositoryRoot,
      encoding: 'utf8',
      timeout: timeoutMs,
      maxBuffer: maxOutputBytes,
      windowsHide: true
    })

    if (error) {
      if (error.code === 'ETIMEDOUT' || error.killed) {
        throw new MlCliError(504, `ML evaluation timed out after ${timeoutMs} ms`)
      }
      if (error.code === 'ENOENT') {
        throw new MlCliError(503, 'Python runtime was not found; configure AEGISCHAIN_PYTHON')
      }
      const inputError = String(stderr).match(/evaluation error: ValueError: ([^\r\n]*)/)
      if (inputError) throw new MlCliError(400, `ML evaluator rejected the input: ${inputError[1]}`)
      throw new MlCliError(502, `ML evaluator process failed${error.code ? ` (exit ${error.code})` : ''}`)
    }

    try {
      return JSON.parse(String(stdout).trim())
    } catch {
      throw new MlCliError(502, 'ML evaluator returned malformed JSON')
    }
  }
}

/** Create a bounded HTTP client for the standalone Python evaluator service. */
export function createMlRemoteEvaluator({
  url = process.env.AEGISCHAIN_ML_URL,
  timeoutMs = Number(process.env.AEGISCHAIN_ML_TIMEOUT_MS) || defaultTimeoutMs,
  authToken = process.env.AEGISCHAIN_ML_TOKEN,
  fetchImpl = globalThis.fetch
} = {}) {
  if (!url) throw new MlCliError(503, 'AEGISCHAIN_ML_URL is required when AEGISCHAIN_ML_MODE=remote')
  let endpoint
  try {
    endpoint = new URL(url)
  } catch {
    throw new MlCliError(503, 'AEGISCHAIN_ML_URL must be a valid HTTP(S) URL')
  }
  if (!['http:', 'https:'].includes(endpoint.protocol)) {
    throw new MlCliError(503, 'AEGISCHAIN_ML_URL must use HTTP or HTTPS')
  }
  if (endpoint.username || endpoint.password) {
    throw new MlCliError(503, 'AEGISCHAIN_ML_URL must not contain embedded credentials')
  }
  const loopbackHosts = new Set(['localhost', '127.0.0.1', '[::1]'])
  if (endpoint.protocol !== 'https:' && !loopbackHosts.has(endpoint.hostname)) {
    throw new MlCliError(503, 'Remote ML credentials require HTTPS except for loopback development URLs')
  }
  if (typeof authToken !== 'string' || Buffer.byteLength(authToken, 'utf8') < 32 || /[\r\n]/.test(authToken)) {
    throw new MlCliError(503, 'AEGISCHAIN_ML_TOKEN must be at least 32 UTF-8 bytes and contain no line breaks when AEGISCHAIN_ML_MODE=remote')
  }
  if (typeof fetchImpl !== 'function') {
    throw new MlCliError(503, 'Remote ML mode requires a runtime with the Fetch API')
  }

  return async request => {
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), timeoutMs)
    try {
      let response
      try {
        response = await fetchImpl(endpoint, {
          method: 'POST',
          headers: {
            'content-type': 'application/json',
            accept: 'application/json',
            authorization: `Bearer ${authToken}`
          },
          body: JSON.stringify(request),
          signal: controller.signal
        })
      } catch (error) {
        if (error?.name === 'AbortError' || controller.signal.aborted) {
          throw new MlCliError(504, `Remote ML evaluation timed out after ${timeoutMs} ms`)
        }
        throw new MlCliError(503, 'Remote ML evaluator is unavailable')
      }

      let body
      try {
        body = await response.text()
      } catch (error) {
        if (error?.name === 'AbortError' || controller.signal.aborted) {
          throw new MlCliError(504, `Remote ML evaluation timed out after ${timeoutMs} ms`)
        }
        throw new MlCliError(502, 'Remote ML evaluator response could not be read')
      }
      if (!response.ok) {
        if (response.status === 401 || response.status === 403) {
          throw new MlCliError(502, 'Remote ML evaluator authentication failed')
        }
        let message = `Remote ML evaluator returned HTTP ${response.status}`
        try {
          const parsed = JSON.parse(body)
          if (typeof parsed?.error?.message === 'string' && parsed.error.message.trim()) {
            message = parsed.error.message.trim().slice(0, 500)
          }
        } catch { /* Keep the bounded status-only message. */ }
        if (response.status === 400 || response.status === 422) {
          throw new MlCliError(400, `ML evaluator rejected the input: ${message}`)
        }
        throw new MlCliError(502, message)
      }

      try {
        return JSON.parse(body)
      } catch {
        throw new MlCliError(502, 'Remote ML evaluator returned malformed JSON')
      }
    } finally {
      clearTimeout(timeout)
    }
  }
}

/** Select an explicit mode; remote configuration errors never fall back locally. */
export function createMlEvaluator({
  env = process.env,
  cliOptions = {},
  remoteOptions = {}
} = {}) {
  const mode = env.AEGISCHAIN_ML_MODE || 'local'
  if (mode === 'local') return createMlCliEvaluator(cliOptions)
  if (mode === 'remote') {
    return createMlRemoteEvaluator({
      url: env.AEGISCHAIN_ML_URL,
      timeoutMs: Number(env.AEGISCHAIN_ML_TIMEOUT_MS) || defaultTimeoutMs,
      authToken: env.AEGISCHAIN_ML_TOKEN,
      ...remoteOptions
    })
  }
  throw new MlCliError(503, 'AEGISCHAIN_ML_MODE must be either local or remote')
}
