<template>
    <div class="setting-container">
        <el-card :title="t('setting.title')" v-loading="loading" class="setting-card">
            <template #header>
                <div class="card-header">
                    <span class="header-title">{{ t('setting.title') }}</span>
                    <el-button type="primary" :loading="saving" @click="handleSave">
                        <el-icon><Check /></el-icon>
                        {{ t('setting.save') }}
                    </el-button>
                </div>
            </template>
            
            <el-form 
                :model="configForm"
                label-position="top"
                class="setting-form"
            >
                <!-- ComfyUI 配置 -->
                <div class="setting-section">
                    <h3 class="section-title">ComfyUI</h3>
                    <el-form-item :label="t('setting.comfyui.apiUrl')" prop="comfyui.api_url">
                        <el-input 
                            v-model="configForm.comfyui.api_url" 
                            :placeholder="t('setting.comfyui.apiUrlPlaceholder')"
                            clearable
                        >
                            <template #prefix>
                                <el-icon><Link /></el-icon>
                            </template>
                        </el-input>
                    </el-form-item>
                    <el-form-item :label="t('setting.comfyui.referenceImageMode')" prop="comfyui.reference_image_mode">
                        <el-switch v-model="configForm.comfyui.reference_image_mode" />
                    </el-form-item>
                </div>

                <!-- 默认工作流配置 -->
                <div class="setting-section">
                    <h3 class="section-title">{{ t('setting.defaultWorkflow.name') }}</h3>
                    <el-form-item prop="default_workflow.name">
                        <el-select 
                            v-model="configForm.default_workflow.name"
                            :placeholder="t('setting.defaultWorkflow.namePlaceholder')"
                            style="width: 100%"
                            clearable
                        >
                            <el-option
                                v-for="workflow in allWorkflows"
                                :key="workflow"
                                :label="workflow"
                                :value="workflow"
                            />
                        </el-select>
                    </el-form-item>
                </div>

                <!-- LLM配置 -->
                <div class="setting-section">
                    <h3 class="section-title">{{ t('setting.llm.title') }}</h3>
                    <el-form-item :label="t('setting.llm.apiUrl')" prop="llm.api_url">
                        <el-input 
                            v-model="configForm.llm.api_url" 
                            :placeholder="t('setting.llm.apiUrlPlaceholder')"
                            clearable
                        >
                            <template #prefix>
                                <el-icon><Link /></el-icon>
                            </template>
                        </el-input>
                    </el-form-item>
                    <el-form-item :label="t('setting.llm.modelName')" prop="llm.model_name">
                        <el-input 
                            v-model="configForm.llm.model_name" 
                            :placeholder="t('setting.llm.modelNamePlaceholder')"
                            clearable
                        >
                            <template #prefix>
                                <el-icon><Monitor /></el-icon>
                            </template>
                        </el-input>
                    </el-form-item>
                    <el-form-item :label="t('setting.llm.apiKey')" prop="llm.api_key">
                        <el-input 
                            v-model="configForm.llm.api_key" 
                            :placeholder="t('setting.llm.apiKeyPlaceholder')"
                            clearable
                        >
                            <template #prefix>
                                <el-icon><Key /></el-icon>
                            </template>
                        </el-input>
                    </el-form-item>
                    <el-form-item :label="t('setting.llm.windowSize')" prop="llm.window_size">
                        <el-input-number 
                            v-model="configForm.llm.window_size" 
                            :min="-1"
                            :step="1"
                            style="width: 180px"
                        />
                    </el-form-item>
                </div>


                <!-- 路径配置 -->
                <div class="setting-section">
                    <h3 class="section-title">{{ t('setting.path.title') }}</h3>
                    <el-form-item :label="t('setting.path.projectsPath')" prop="relative_projects_path">
                        <el-input 
                            v-model="configForm.relative_projects_path" 
                            :placeholder="t('setting.path.projectsPathPlaceholder')"
                            clearable
                        >
                            <template #prefix>
                                <el-icon><Folder /></el-icon>
                            </template>
                        </el-input>
                    </el-form-item>
                    <el-form-item :label="t('setting.path.promptsPath')" prop="relative_prompts_path">
                        <el-input 
                            v-model="configForm.relative_prompts_path" 
                            :placeholder="t('setting.path.promptsPathPlaceholder')"
                            clearable
                        >
                            <template #prefix>
                                <el-icon><Folder /></el-icon>
                            </template>
                        </el-input>
                    </el-form-item>
                    <el-form-item :label="t('setting.path.workflowPath')" prop="relative_workflow_path">
                        <el-input 
                            v-model="configForm.relative_workflow_path" 
                            :placeholder="t('setting.path.workflowPathPlaceholder')"
                            clearable
                        >
                            <template #prefix>
                                <el-icon><Folder /></el-icon>
                            </template>
                        </el-input>
                    </el-form-item>
                </div>
            </el-form>
        </el-card>
    </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { Check, Link, Monitor, Folder,Key } from '@element-plus/icons-vue'
import adminApi from '@/api/admin_api'

const { t } = useI18n()
const loading = ref(false)
const saving = ref(false)
const allWorkflows = ref<string[]>([])
const configForm = ref({
    comfyui: {
        api_url: '',
        reference_image_mode: true
    },
    default_workflow: {
        name: ''
    },
    llm: {
        api_url: '',
        api_key: '',
        model_name: '',
        window_size: 4
    },
    relative_projects_path: '',
    relative_prompts_path: '',
    relative_workflow_path: ''
})

// 获取配置信息
const fetchConfig = async () => {
    loading.value = true
    try {
        const data  = await adminApi.getConfig()
        console.log(data)
        // 保存工作流列表
        allWorkflows.value = data.all_workflow || []
        // 更新配置表单
        configForm.value = {
            comfyui: data.comfyui,
            default_workflow: data.default_workflow,
            llm: data.llm,
            relative_projects_path: data.relative_projects_path,
            relative_prompts_path: data.relative_prompts_path,
            relative_workflow_path: data.relative_workflow_path
        }
    } catch (error) {
        ElMessage.error(t('setting.loadError'))
        console.error(error)
    } finally {
        loading.value = false
    }
}

// 保存配置
const handleSave = async () => {
    saving.value = true
    try {
        await adminApi.updateConfig(configForm.value)
        ElMessage.success(t('setting.saveSuccess'))
    } catch (error) {
        ElMessage.error(t('setting.saveError'))
        console.error(error)
    } finally {
        saving.value = false
    }
}

onMounted(() => {
    fetchConfig()
})
</script>

<style scoped lang="scss">
.setting-container {
    padding: 24px;
    max-width: 90vw;
    margin: 0 auto;
    background-color: var(--el-bg-color);

    .setting-card {
        border-radius: 8px;
        background-color: var(--el-bg-color);
        border: 1px solid var(--el-border-color-light);

        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--el-border-color-light);
            padding: 16px 20px;
            background-color: var(--el-bg-color);

            .header-title {
                font-size: 18px;
                font-weight: 600;
                color: var(--el-text-color-primary);
            }

            .el-button {
                padding: 8px 20px;

                .el-icon {
                    margin-right: 4px;
                }
            }
        }

        .setting-form {
            padding: 20px;

            .setting-section {
                margin-bottom: 32px;
                padding: 24px;
                background-color: var(--el-bg-color-page);
                border: 1px solid var(--el-border-color-lighter);
                border-radius: 8px;
                transition: all 0.3s ease;

                &:hover {
                    border-color: var(--el-border-color);
                    box-shadow: 0 0 8px var(--el-border-color);
                }

                .section-title {
                    margin: 0 0 20px 0;
                    font-size: 16px;
                    font-weight: 600;
                    color: var(--el-text-color-primary);
                    border-bottom: 1px solid var(--el-border-color-light);
                    padding-bottom: 12px;
                }
            }
        }
    }
}

:deep() {
    .el-form-item__label {
        font-weight: 500;
        color: var(--el-text-color-regular);
    }

    .el-input__wrapper {
        background-color: var(--el-bg-color-overlay);
        border-color: var(--el-border-color);
        box-shadow: 0 0 0 1px var(--el-border-color) inset;

        &:hover {
            box-shadow: 0 0 0 1px var(--el-border-color-hover) inset;
        }

        &.is-focus {
            box-shadow: 0 0 0 1px var(--el-color-primary) inset !important;
        }
    }

    .el-select {
        width: 100%;

        .el-input__wrapper {
            background-color: var(--el-bg-color-overlay);
        }
    }

    .el-input-number {
        width: 180px;
        background-color: var(--el-bg-color-overlay);

        .el-input__wrapper {
            background-color: transparent;
        }
    }
}

/* 暗黑主题特定样式 */
:deep(.dark) {
    .setting-section {
        background-color: var(--el-bg-color);
        border-color: var(--el-border-color-darker);

        &:hover {
            border-color: var(--el-border-color);
            box-shadow: 0 0 8px rgba(0, 0, 0, 0.3);
        }
    }

    .el-input__wrapper,
    .el-select .el-input__wrapper,
    .el-input-number {
        background-color: var(--el-bg-color-overlay);
    }
}
</style>