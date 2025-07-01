import config from '@/config'

/**
 * 生成资源访问路径
 * @param projectName 项目名称
 * @param chapterName 章节名称
 * @param spanIndex span索引
 * @param type 资源类型 ('image' | 'audio')
 * @returns 完整的资源访问路径
 */
export const getResourcePath = (
  projectName: string,
  chapterName: string,
  spanId?: string,
  type: 'image' | 'audio' |'video'= 'image'
): string => {
  const timestamp = Date.now()
  let endpoint=''
  switch (type) {
    case 'image':
      endpoint = '/media/get_image'
      break;
    case 'audio':
      endpoint = '/media/get_audio'
      break;
    case 'video':
      endpoint='/video/get_video'
      break;
  }
  if(type!=='video')
    return `${config.baseApi}${endpoint}?project_name=${projectName}&chapter_name=${chapterName}&span_id=${spanId}&_t=${timestamp}`
  else
    return `${config.baseApi}${endpoint}?project_name=${projectName}&chapter_name=${chapterName}&_t=${timestamp}`
}
