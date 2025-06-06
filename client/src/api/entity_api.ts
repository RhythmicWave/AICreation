import request from './request'


export interface CharacterAttributes {
  role?: string
  description?: string
  [key: string]: any
}

export interface UpdateCharacterParams {
  name: string
  attributes: CharacterAttributes
}

export interface UpdateSceneParams {
  name: string
  prompt: string
}

export interface CreateCharacterParams {
  name: string
  attributes: CharacterAttributes
}

export interface CreateSceneParams {
  name: string
  prompt: string
}

export const entityApi = {
  // 获取角色列表
  getCharacterList(projectName: string) {
    return request.get('entity/character/list', { project_name: projectName })
  },
  
  // 创建角色
  createCharacter(projectName: string, params: CreateCharacterParams) {
    return request.post('entity/character/create', { 
      project_name: projectName,
      name: params.name,
      attributes: params.attributes
    })
  },
  
  // 更新角色
  updateCharacter(projectName: string, params: UpdateCharacterParams) {
    return request.post('entity/character/update', { 
      project_name: projectName,
      name: params.name,
      attributes: params.attributes
    })
  },
  
  // 切换锁定状态
  toggleLock(projectName: string, entityName: string) {
    return request.post('entity/character/toggle_lock', { 
      project_name: projectName,
      entity_name: entityName
    })
  },

  // 删除角色
  deleteCharacter(projectName: string, entityName: string) {
    return request.delete(`entity/character/${entityName}`, { project_name: projectName })
  },

  // 获取场景列表
  getSceneList(projectName: string) {
    return request.get('entity/scene/list', { project_name: projectName })
  },
  
  // 创建场景
  createScene(projectName: string, params: CreateSceneParams) {
    return request.post('entity/scene/create', { 
      project_name: projectName,
      name: params.name,
      prompt: params.prompt
    })
  },
  
  // 更新场景
  updateScene(projectName: string, params: UpdateSceneParams) {
    return request.post('entity/scene/update', { 
      project_name: projectName,
      name: params.name,
      prompt: params.prompt
    })
  },

  // 删除场景
  deleteScene(projectName: string, entityName: string) {
    return request.delete(`entity/scene/${entityName}`, { project_name: projectName })
  }
}
