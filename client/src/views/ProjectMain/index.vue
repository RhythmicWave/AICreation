<template>
  <div class="project-main">
    <el-container>
      <!-- 侧边栏 -->
      <el-aside width="210px">
        <el-menu :default-active="activeRoute" class="project-menu" router>
          <el-menu-item index="/project">
            <el-icon>
              <Back />
            </el-icon>
            <span>{{ t('common.back') }}</span>
          </el-menu-item>
          <el-menu-item :index="`/project/${projectName}/text-creation`">
            <el-icon>
              <EditPen />
            </el-icon>
            <span>{{ t('projectMain.textCreation') }}</span>
          </el-menu-item>
          <el-menu-item :index="`/project/${projectName}/library/character`">
            <el-icon>
              <User />
            </el-icon>
            <span>{{ t('projectMain.characterLibrary') }}</span>
          </el-menu-item>
          <el-menu-item :index="`/project/${projectName}/library/scene`">
            <el-icon>
              <OfficeBuilding />
            </el-icon>
            <span>{{ t('projectMain.sceneLibrary') }}</span>
          </el-menu-item>
          <el-menu-item :index="`/project/${projectName}/storyboard-process`">
            <el-icon>
              <PictureFilled />
            </el-icon>
            <span>{{ t('projectMain.storyboardProcess') }}</span>
          </el-menu-item>
          <el-menu-item :index="`/project/${projectName}/video-output`">
            <el-icon>
              <VideoPlay />
            </el-icon>
            <span>{{ t('projectMain.videoOutput') }}</span>
          </el-menu-item>
        </el-menu>
      </el-aside>

      <!-- 主要内容区域 -->
      <el-container>
        <el-main>
          <div v-if="error" class="error-message">
            {{ error }}
          </div>
          <el-loading :value="loading" />

          <router-view v-if="!loading && !error" />
        </el-main>
      </el-container>
    </el-container>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { EditPen, User, PictureFilled, VideoPlay, Back,OfficeBuilding } from '@element-plus/icons-vue'

import type { ProjectInfo } from '@/types/project'
import projectApi from '@/api/project_api'


const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const projectInfo = ref<ProjectInfo | null>(null)
const loading = ref(true)
const error = ref('')

const projectName = computed(() => route.params.name as string)
const activeRoute = computed(() => route.path)


const fetchProjectInfo = async () => {
  if (!projectName.value) {
    router.push('/404')
    return
  }

  try {
    loading.value = true
    error.value = ''
    projectInfo.value = await projectApi.getProjectInfo(projectName.value)
  } catch (e: any) {
    error.value = e.message || t('project.fetchError')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchProjectInfo()
})
</script>

<style scoped>
.project-main {
  display: flex;
  height: 100%;
}

.el-container {
  height: 100%;
}

.el-aside {
  background-color: var(--el-menu-bg-color);
  border-right: solid 1px var(--el-border-color-light);

}

.project-menu {
  border-right: none;
  width: 200px;
  height: 100%;
}

.error-message {
  color: var(--el-color-danger);
  text-align: center;
  margin-top: 20px;
}

:deep(.el-menu-item) {
  display: flex;
  align-items: center;
  gap: 8px;
}

:deep(.el-menu-item .el-icon) {
  margin-right: 0;
}

.operation-bar {
  padding: 10px 20px;
  border-top: 1px solid var(--el-border-color);
  background-color: var(--el-bg-color);
  display: flex;
  justify-content: flex-end;
  align-items: center;
}
</style>
