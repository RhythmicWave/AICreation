<template>
    <div class="character-library">
        <h3>{{ t('menu.sceneLibrary') }}</h3>

        <!-- 搜索框和新增按钮 -->
        <div class="header-container">
            <div class="search-container">
                <el-input v-model="searchQuery" :placeholder="t('common.search')" :prefix-icon="Search" clearable />
            </div>
            <el-button type="primary" @click="openCreateSceneDialog">
                {{ t('entity.createScene') }}
            </el-button>
        </div>

        <el-table v-loading="loading" :data="filteredCharacters" style="width: 100%" border>
            <el-table-column :label="t('entity.entityName')" prop="name" width="120" align="center">
                <template #default="{ row }">
                    <span class="entity-name">{{ row.name }}</span>
                </template>
            </el-table-column>

            <el-table-column :label="t('entity.description')" min-width="240" align="center">
                <template #default="{ row }">
                    <el-input v-model="row.prompt" type="textarea" :rows="5"
                              :placeholder="t('entity.description')" />
                </template>
            </el-table-column>
            <el-table-column :label="t('common.operations')" width="360" align="center">
                <template #default="{ row }">
                    <div class="operation-buttons">
                        <div class="button-row">

                            <!-- <el-button type="info" @click="openReversePrompt(row)">
                                {{ t('entity.reversePrompt') }}
                            </el-button> -->
                        </div>
                        <div class="button-row">
                            <el-button type="success" @click="savePrompt(row)">
                                {{ t('entity.savePrompt') }}
                            </el-button>
                            <el-button type="danger" @click="deleteEntity(row)">
                                {{ t('entity.delete') }}
                            </el-button>
                        </div>
                    </div>
                </template>
            </el-table-column>
        </el-table>

        <!-- 创建场景对话框 -->
        <el-dialog v-model="createSceneVisible" :title="t('entity.createSceneTitle')" width="600px">
            <div class="create-scene-form">
                <el-form :model="newScene" label-width="120px">
                    <el-form-item :label="t('entity.entityName')" required>
                        <el-input v-model="newScene.name" />
                    </el-form-item>
                    <el-form-item :label="t('entity.description')">
                        <el-input v-model="newScene.prompt" type="textarea" :rows="5" :placeholder="t('entity.description')" />
                    </el-form-item>
                </el-form>
                <div class="dialog-footer">
                    <el-button @click="createSceneVisible = false">
                        {{ t('entity.cancel') }}
                    </el-button>
                    <el-button type="primary" @click="createScene">
                        {{ t('entity.create') }}
                    </el-button>
                </div>
            </div>
        </el-dialog>

        <!-- 反推提示词对话框 -->
        <el-dialog v-model="reversePromptVisible" :title="t('entity.reversePromptTitle')" width="600px">
            <div class="reverse-prompt-dialog">
                <!-- 上传图片区域 -->
                <el-upload class="upload-area" action="#" :auto-upload="false" :show-file-list="false"
                           :on-change="handleImageChange">
                    <div class="upload-content">
                        <el-icon class="upload-icon">
                            <Upload />
                        </el-icon>
                        <div class="upload-text">{{ t('entity.uploadImage') }}</div>
                        <img v-if="selectedImage" :src="selectedImage" class="preview-image" />
                    </div>
                </el-upload>

                <!-- 文本显示区域 -->
                <div class="description-area">
                    {{ reversePromptText }}
                </div>

                <!-- 按钮区域 -->
                <div class="dialog-footer">
                    <el-button @click="reversePromptVisible = false">
                        {{ t('entity.cancel') }}
                    </el-button>
                    <el-button type="primary" @click="confirmReversePrompt">
                        {{ t('entity.confirm') }}
                    </el-button>
                </div>
            </div>
        </el-dialog>
    </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, reactive } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { UploadFile } from 'element-plus'
import { Search, Upload } from '@element-plus/icons-vue'
import { entityApi } from '@/api/entity_api'

const route = useRoute()
const { t } = useI18n()
const projectName = computed(() => route.params.name as string)

interface Scene {
    name: string
    prompt: string
   
}

const loading = ref(false)
const scenes = ref<Scene[]>([])
const searchQuery = ref('')

const reversePromptVisible = ref(false)
const reversePromptText = ref('')
const selectedImage = ref('')
const currentScene = ref<Scene | null>(null)

// 新增场景相关
const createSceneVisible = ref(false)
const newScene = reactive<Scene>({
    name: '',
    prompt: ''
})

// 根据搜索词过滤列表
const filteredCharacters = computed(() => {
    const query = searchQuery.value.toLowerCase().trim()
    if (!query) return scenes.value

    return scenes.value.filter(character =>
        character.name.toLowerCase().includes(query)
    )
})

const fetchSceneList = async () => {
    loading.value = true
    try {
        const res = await entityApi.getSceneList(projectName.value)
        const data=res.scenes
        console.log(data)
        scenes.value = []
        for (const d in data) {
            scenes.value.push({
                name: d,
                prompt: data[d]
            })
        }

    } catch (error) {
        ElMessage.error(String(error))
    } finally {
        loading.value = false
    }
}


const openReversePrompt = (row: Scene) => {
    currentScene.value = row
    reversePromptText.value = ''
    selectedImage.value = ''
    reversePromptVisible.value = true
}

const handleImageChange = (uploadFile: UploadFile) => {
    if (uploadFile.raw) {
        selectedImage.value = URL.createObjectURL(uploadFile.raw)
    }
}

const confirmReversePrompt = () => {
    if (currentScene.value && reversePromptText.value) {
        currentScene.value.prompt = reversePromptText.value
        reversePromptVisible.value = false
        // 自动保存更新后的描述
        savePrompt(currentScene.value)
    }
}

const savePrompt = async (row: Scene) => {
    try {
        const data = await entityApi.updateScene(projectName.value, {
            name: row.name,
            prompt: row.prompt
        })
        if(data)
            ElMessage.success(t('entity.updateSuccess'))
    } catch (error) {
        ElMessage.error(String(error))
    }
}

const deleteEntity = async (row: any) => {
    try {
        await ElMessageBox.confirm(
            t('entity.deleteConfirm'),
            t('common.warning'),
            {
                confirmButtonText: t('entity.confirm'),
                cancelButtonText: t('entity.cancel'),
                type: 'warning',
            }
        )

        const res = await entityApi.deleteScene(projectName.value, row.name)
        if (res) {
            ElMessage.success(t('entity.deleteSuccess'))
            await fetchSceneList()
        } else {
            ElMessage.error(res.data.message || t('entity.deleteError'))
        }
    } catch (error) {
        if (error !== 'cancel') {
            ElMessage.error(t('entity.operationFailed'))
        }
    }
}

const openCreateSceneDialog = () => {
    newScene.name = ''
    newScene.prompt = ''
    createSceneVisible.value = true
}

const createScene = async () => {
    if (!newScene.name.trim()) {
        ElMessage.error(t('entity.nameRequired'))
        return
    }
    
    try {
        
        const data = await entityApi.createScene(projectName.value, {
            name: newScene.name,
            prompt: newScene.prompt
        })
        

        
        if (data) {
            ElMessage.success(t('entity.createSuccess') || '创建成功')
            createSceneVisible.value = false
            await fetchSceneList()
        } else {
            ElMessage.error(t('entity.createError') || '创建失败')
        }
    } catch (error) {
  
        ElMessage.error(typeof error === 'string' ? error : (error.message || t('entity.createError') || '创建失败'))
    }
}

onMounted(() => {
    fetchSceneList()
})
</script>

<style scoped>
.character-library {
    padding: 20px;
}

.header-container {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
}

.search-container {
    max-width: 300px;
}

.operation-buttons {
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.button-row {
    display: flex;
    gap: 8px;
    justify-content: center;
}

.button-row .el-button {
    flex: 1;
    min-width: 110px;
}

.entity-name {
    display: inline-block;
    line-height: 40px;
    height: 40px;
}

.is-locked {
    background-color: #909399;
    border-color: #909399;
}

.is-locked:hover {
    background-color: #a6a9ad;
    border-color: #a6a9ad;
}

.reverse-prompt-dialog {
    display: flex;
    flex-direction: column;
    gap: 20px;
}

.upload-area {
    width: 100%;
    height: 200px;
    border: 2px dashed var(--el-border-color);
    border-radius: 6px;
    cursor: pointer;
    position: relative;
    overflow: hidden;
    display: flex;
    justify-content: center;
    align-items: center;
}

.upload-content {
    height: 100%;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    color: var(--el-text-color-secondary);
}

.upload-icon {
    font-size: 28px;
    margin-bottom: 8px;
}

.upload-text {
    font-size: 14px;
}

.preview-image {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    object-fit: contain;
}

.description-area {
    min-height: 100px;
    padding: 12px;
    background-color: var(--el-fill-color-light);
    border-radius: 4px;
    color: var(--el-text-color-regular);
    font-size: 14px;
    line-height: 1.6;
}

.dialog-footer {
    display: flex;
    justify-content: flex-end;
    gap: 10px;
    margin-top: 20px;
}

:deep(.el-table__cell) {
    padding: 8px 0;
}

:deep(.el-table .cell) {
    white-space: pre-wrap;
    word-break: break-word;
    line-height: 1.5;
}

:deep(.el-table__header .cell) {
    font-weight: bold;
}

.create-scene-form {
    padding: 10px;
}
</style>
