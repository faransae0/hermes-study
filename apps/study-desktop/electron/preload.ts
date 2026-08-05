import { contextBridge, ipcRenderer } from 'electron'

contextBridge.exposeInMainWorld('hermesStudy', {
  subjectCreate: (title: string, description?: string) =>
    ipcRenderer.invoke('study:subject:create', title, description),
  subjectList: () => ipcRenderer.invoke('study:subject:list'),
  sourceIngest: (subjectId: string, type: string, origin: string) =>
    ipcRenderer.invoke('study:source:ingest', subjectId, type, origin),
  notesList: (subjectId: string) => ipcRenderer.invoke('study:notes:list', subjectId),
  chatSendMessage: (subjectId: string, message: string) =>
    ipcRenderer.invoke('study:chat:sendMessage', subjectId, message),
})
