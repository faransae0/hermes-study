import { contextBridge } from 'electron'

contextBridge.exposeInMainWorld('hermesStudy', {})
