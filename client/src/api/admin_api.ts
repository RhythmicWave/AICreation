import request from './request'

interface Config {
  [key: string]: any
}

export const adminApi = {
  // 获取配置信息
  getConfig() {
    return request.get('/admin/config')
 },

 // 更新配置信息
 updateConfig(config: Record<string, any>) {
    return request.post('/admin/config', config)
 },

  /**
   * 获取提示词样式列表
   */
  getPromptStyles() {
    return request.get('/admin/prompt_styles')
  },

  /**
   * 保存提示词样式列表
   * @param styles 提示词样式数组
   */
  savePromptStyles(styles: any[]) {
    return request.post('/admin/prompt_styles', { styles })
  }
}

export default adminApi 