import request from './request'

interface GenerateImageParams {
  project_name: string
  chapter_name: string
  imageSettings: {
    width: number
    height: number
    style: string
  }
  reference_image_infos?: {
    character1: string
    character2: string
    scene: string
  }[]
  prompts: {
    id?: string
    prompt: string
  }[]
}

interface GenerateAudioParams {
  project_name: string
  chapter_name: string
  audioSettings: {
    voice: string
    rate: string
  }
  prompts: {
    id: string
    prompt: string
  }[]
}

interface GenerationProgressResponse {
  status: string
  current: number
  total: number
  errors: string[]
}

export const mediaApi = {
  generateImages(params: GenerateImageParams) {
    return request.post('/media/generate_images', params)
  },

  generateAudio(params: GenerateAudioParams) {
    return request.post('/media/generate-audio', params)
  },

  getProgress(taskId: string) {
    return request.get<GenerationProgressResponse>('/media/progress', { task_id: taskId })
  },

  cancelTask(taskId: string) {
    return request.post('/media/cancel', { task_id: taskId })
  },

  uploadReferenceImage(project_name: string, chapter_name: string, span_id: string, file: File) {
    const form = new FormData()
    form.append('project_name', project_name)
    form.append('chapter_name', chapter_name)
    form.append('span_id', span_id)
    form.append('file', file)
    return request.post('/media/upload_image', form, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  }
}

export default mediaApi
