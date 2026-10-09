import { spawn } from 'node:child_process'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// 页面要的是 Copilot Runtime 的 /info，不是 AG-UI 的 RunAgentInput。
// 开发时随 vite 拉起 runtime.js，再把 /api/copilotkit 转到它。
function copilotRuntime() {
  let child
  return {
    name: 'copilot-runtime',
    configureServer() {
      if (child) return
      child = spawn(process.execPath, ['runtime.js'], {
        cwd: process.cwd(),
        stdio: 'inherit',
        env: process.env,
      })
      child.on('exit', (code) => {
        if (code) console.error(`Copilot Runtime exited with code ${code}`)
        child = undefined
      })
    },
    buildEnd() {
      child?.kill()
    },
  }
}

export default defineConfig({
  plugins: [react(), copilotRuntime()],
  server: {
    port: 5177,
    proxy: {
      '/api/copilotkit': 'http://127.0.0.1:9002',
    },
  },
})

