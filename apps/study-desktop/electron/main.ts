import { app, BrowserWindow, ipcMain } from 'electron'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { execFile } from 'node:child_process'
import { promisify } from 'node:util'
import {
  buildChatSendMessageArgs,
  buildNotesListArgs,
  buildSourceIngestArgs,
  buildSubjectCreateArgs,
  buildSubjectListArgs,
} from './study-cli'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

function createWindow() {
  const win = new BrowserWindow({
    width: 1100,
    height: 720,
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  })

  const devServerUrl = process.env.HERMES_STUDY_DEV_SERVER
  if (devServerUrl) {
    win.loadURL(devServerUrl)
  } else {
    win.loadFile(path.join(__dirname, '..', 'dist', 'index.html'))
  }
}

const execFileAsync = promisify(execFile)

async function runStudyCli(args: string[]): Promise<unknown> {
  const pythonPath = process.env.HERMES_STUDY_PYTHON
  if (!pythonPath) {
    return { error: 'HERMES_STUDY_PYTHON is not set — launch this app via `hermes study desktop`' }
  }

  try {
    const { stdout } = await execFileAsync(pythonPath, ['-m', 'hermes_cli.main', ...args], {
      env: process.env,
      timeout: 0,
      maxBuffer: 10 * 1024 * 1024,
    })
    return JSON.parse(stdout)
  } catch (err: any) {
    // execFile rejects on a non-zero exit; stdout may still carry the JSON
    // error shape the CLI printed before exiting (e.g. `_require_subject`'s
    // {"error": "..."} + sys.exit(1)). Prefer that parsed shape over the raw
    // execFile rejection message when it's present and valid JSON.
    const stdout = err?.stdout
    if (typeof stdout === 'string' && stdout.trim()) {
      try {
        return JSON.parse(stdout)
      } catch {
        // fall through to the generic error below
      }
    }
    return { error: err?.message || 'hermes study CLI invocation failed' }
  }
}

ipcMain.handle('study:subject:create', (_event, title: string, description?: string) =>
  runStudyCli(buildSubjectCreateArgs(title, description)),
)
ipcMain.handle('study:subject:list', () => runStudyCli(buildSubjectListArgs()))
ipcMain.handle('study:source:ingest', (_event, subjectId: string, type: string, origin: string) =>
  runStudyCli(buildSourceIngestArgs(subjectId, type, origin)),
)
ipcMain.handle('study:notes:list', (_event, subjectId: string) => runStudyCli(buildNotesListArgs(subjectId)))
ipcMain.handle('study:chat:sendMessage', (_event, subjectId: string, message: string) =>
  runStudyCli(buildChatSendMessageArgs(subjectId, message)),
)

app.whenReady().then(() => {
  createWindow()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow()
    }
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})
