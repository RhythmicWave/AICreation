import request from './request'
import type { VideoSettings, VideoProgress } from '@/types/video'

class VideoApi {
  generateVideo(settings: VideoSettings) {
    return request.post<null>('/video/generate_video', settings)
  }

  getGenerationProgress() {
    return request.get<VideoProgress>('/video/generation_progress')
  }

  cancelGeneration() {
    return request.post<null>('/video/cancel_generation')
  }
}

export const videoApi = new VideoApi()