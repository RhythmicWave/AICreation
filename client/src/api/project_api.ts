import request from './request'
import type { ProjectInfo } from '@/types/project'

export default {
    // 获取项目列表
    getProjectList() {
        return request.get<string[]>('/project/list')
    },

    // 创建新项目
    createProject(projectName: string) {
        return request.post<{project_name:string}>('/project/create', { 
            project_name: projectName 
        })
    },

    // 更新项目
    updateProject(oldName: string, newName: string) {
        return request.put<{project_name:string}>('/project/update', { 
            old_name: oldName,
            new_name: newName
        })
    },

    // 删除项目
    deleteProject(projectName: string) {
        return request.delete(`/project/delete/${projectName}`)
    },

    // 获取项目详情
    getProjectInfo(projectName: string) {
        return request.get<ProjectInfo>('/project/info', { 
            project_name: projectName 
        })
    }
}