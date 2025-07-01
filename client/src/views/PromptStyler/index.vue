<template>
  <div class="prompt-styler-container">
    <div class="header">
      <h2>{{ t('promptStyler.title') }}</h2>
      <el-button type="primary" @click="openAddDialog" :icon="Plus">{{ t('promptStyler.addStyle') }}</el-button>
    </div>

    <el-input
      v-model="searchQuery"
      :placeholder="t('promptStyler.searchPlaceholder')"
      prefix-icon="Search"
      clearable
      class="search-input"
    />

    <div v-if="loading" class="loading-container">
      <el-skeleton :rows="3" animated />
      <el-skeleton :rows="3" animated />
      <el-skeleton :rows="3" animated />
    </div>
    
    <div v-else-if="filteredStyles.length === 0" class="empty-container">
      <el-empty :description="t('promptStyler.emptyDescription')" />
    </div>
    
    <el-row :gutter="20" v-else class="style-cards">
      <el-col :span="8" v-for="(item, idx) in filteredStyles" :key="item.name" class="style-card-col">
        <el-card class="style-card" shadow="hover">
          <div class="style-card-header">
            <h3>{{ item.name || item.chinese_name }}</h3>
            <div class="style-card-name">{{ item.chinese_name||item.name }}</div>
          </div>
          <div class="style-card-content">
            <div class="prompt-item">
              <span class="label">{{ t('promptStyler.positivePrompt') }}：</span>
              <p class="value">{{ item.prompt }}</p>
            </div>
            <div class="prompt-item">
              <span class="label">{{ t('promptStyler.negativePrompt') }}：</span>
              <p class="value">{{ item.negative_prompt }}</p>
            </div>
          </div>
          <div class="style-card-actions">
            <el-button size="small" type="primary" @click="openEditDialog(idx)" :icon="Edit">
              {{ t('promptStyler.editButton') }}
            </el-button>
            <el-button size="small" type="danger" @click="deletePrompt(idx)" :icon="Delete">
              {{ t('promptStyler.deleteButton') }}
            </el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 编辑/新增对话框 -->
    <el-dialog 
      :title="isEditing ? t('promptStyler.editStyleTitle') : t('promptStyler.addStyleTitle')" 
      v-model="dialogVisible"
      width="50%"
      destroy-on-close
    >
      <el-form :model="editForm" label-width="130px" :rules="formRules" ref="formRef">
        <el-form-item :label="t('promptStyler.englishName')" prop="name">
          <el-input v-model="editForm.name" :placeholder="t('promptStyler.englishNamePlaceholder')" />
        </el-form-item>
        <el-form-item :label="t('promptStyler.chineseName')" prop="chinese_name">
          <el-input v-model="editForm.chinese_name" :placeholder="t('promptStyler.chineseNamePlaceholder')" />
        </el-form-item>
        <el-form-item :label="t('promptStyler.positivePrompt')" prop="prompt">
          <el-input 
            v-model="editForm.prompt" 
            type="textarea" 
            :rows="4"
            :placeholder="t('promptStyler.positivePromptPlaceholder')"
          />
        </el-form-item>
        <el-form-item :label="t('promptStyler.negativePrompt')" prop="negative_prompt">
          <el-input 
            v-model="editForm.negative_prompt" 
            type="textarea" 
            :rows="4"
            :placeholder="t('promptStyler.negativePromptPlaceholder')"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="dialogVisible = false">{{ t('promptStyler.cancelButton') }}</el-button>
          <el-button type="primary" @click="savePrompt" :loading="saving">{{ t('promptStyler.saveButton') }}</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, reactive } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Edit, Delete, Plus } from '@element-plus/icons-vue'
import type { FormInstance, FormRules } from 'element-plus'
import { adminApi } from '@/api/admin_api'

interface PromptStyle {
  name: string
  chinese_name: string
  prompt: string
  negative_prompt: string
}

const { t } = useI18n()
const loading = ref(true)
const saving = ref(false)
const promptStyles = ref<PromptStyle[]>([])
const searchQuery = ref('')

// 过滤样式
const filteredStyles = computed(() => {
  if (!searchQuery.value) return promptStyles.value
  
  const query = searchQuery.value.toLowerCase()
  return promptStyles.value.filter(style => 
    style.name.toLowerCase().includes(query) || 
    (style.chinese_name && style.chinese_name.includes(query)) ||
    style.prompt.toLowerCase().includes(query) ||
    style.negative_prompt.toLowerCase().includes(query)
  )
})

// 表单相关
const dialogVisible = ref(false)
const editForm = reactive<PromptStyle>({
  name: '',
  chinese_name: '',
  prompt: '',
  negative_prompt: ''
})
const editIndex = ref(-1)
const isEditing = computed(() => editIndex.value !== -1)
const formRef = ref<FormInstance>()

const formRules: FormRules = {
  name: [
    { required: true, message: t('promptStyler.nameRequired'), trigger: 'blur' },
    { min: 2, max: 50, message: t('promptStyler.nameLength'), trigger: 'blur' }
  ],
  chinese_name: [
    { required: true, message: t('promptStyler.chineseNameRequired'), trigger: 'blur' },
    { min: 1, max: 50, message: t('promptStyler.chineseNameLength'), trigger: 'blur' }
  ],
  prompt: [
    { required: true, message: t('promptStyler.promptRequired'), trigger: 'blur' }
  ]
}

// 获取所有提示词样式
const fetchPromptStyles = async () => {
  loading.value = true
  try {
    const res = await adminApi.getPromptStyles()
    if (res) {
      promptStyles.value = res.styles || []
    } else {
      ElMessage.error(t('promptStyler.fetchFailed'))
    }
  } catch (error) {
    console.error('获取样式列表出错:', error)
    ElMessage.error(t('promptStyler.networkError'))
  } finally {
    loading.value = false
  }
}

// 打开编辑对话框
const openEditDialog = (idx: number) => {
  editIndex.value = idx
  Object.assign(editForm, promptStyles.value[idx])
  dialogVisible.value = true
}

// 打开新增对话框
const openAddDialog = () => {
  editIndex.value = -1
  editForm.name = ''
  editForm.chinese_name = ''
  editForm.prompt = ''
  editForm.negative_prompt = ''
  dialogVisible.value = true
}

// 保存提示词样式
const savePrompt = async () => {
  if (!formRef.value) return
  
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    
    saving.value = true
    
    try {
      // 深拷贝当前样式列表
      const updatedStyles = JSON.parse(JSON.stringify(promptStyles.value))
      
      if (editIndex.value === -1) {
        // 新增样式
        updatedStyles.push({
          name: editForm.name,
          chinese_name: editForm.chinese_name,
          prompt: editForm.prompt,
          negative_prompt: editForm.negative_prompt
        })
      } else {
        // 编辑现有样式
        updatedStyles[editIndex.value] = {
          name: editForm.name,
          chinese_name: editForm.chinese_name,
          prompt: editForm.prompt,
          negative_prompt: editForm.negative_prompt
        }
      }
      
      // 保存到服务器
      const res = await adminApi.savePromptStyles(updatedStyles)
      console.log(res)
      if (res) {
        promptStyles.value = updatedStyles
        ElMessage.success(isEditing.value ? t('promptStyler.updateSuccess') : t('promptStyler.addSuccess'))
        dialogVisible.value = false
      } else {
        ElMessage.error(t('promptStyler.saveFailed'))
      }
    } catch (error) {
      console.error('保存样式出错:', error)
      ElMessage.error(t('promptStyler.networkError'))
    } finally {
      saving.value = false
    }
  })
}

// 删除提示词样式
const deletePrompt = (idx: number) => {
  ElMessageBox.confirm(
    t('promptStyler.deleteConfirmContent'),
    t('promptStyler.deleteConfirmTitle'),
    {
      confirmButtonText: t('common.confirm'),
      cancelButtonText: t('common.cancel'),
      type: 'warning'
    }
  ).then(async () => {
    try {
      // 深拷贝当前样式列表并删除指定项
      const updatedStyles = JSON.parse(JSON.stringify(promptStyles.value))
      updatedStyles.splice(idx, 1)
      
      // 保存到服务器
      const res = await adminApi.savePromptStyles(updatedStyles)
      
      if (res) {
        promptStyles.value = updatedStyles
        ElMessage.success(t('promptStyler.deleteSuccess'))
      } else {
        ElMessage.error(t('promptStyler.saveFailed'))
      }
    } catch (error) {
      console.error('删除样式出错:', error)
      ElMessage.error(t('promptStyler.networkError'))
    }
  }).catch(() => {
    // 用户取消删除，不做任何操作
  })
}

onMounted(fetchPromptStyles)
</script>

<style scoped>
.prompt-styler-container {
  padding: 20px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.header h2 {
  margin: 0;
  font-size: 1.5rem;
  color: var(--el-text-color-primary);
}

.search-input {
  margin-bottom: 20px;
  max-width: 400px;
}

.loading-container {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
}

.empty-container {
  display: flex;
  justify-content: center;
  padding: 40px 0;
}

.style-cards {
  margin-top: 20px;
}

.style-card-col {
  margin-bottom: 20px;
}

.style-card {
  height: 100%;
  display: flex;
  flex-direction: column;
  transition: all 0.3s;
}

.style-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 10px 15px rgba(0, 0, 0, 0.1);
}

.style-card-header {
  margin-bottom: 15px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  padding-bottom: 10px;
}

.style-card-header h3 {
  margin: 0;
  font-size: 1.2rem;
  color: var(--el-color-primary);
}

.style-card-name {
  font-size: 0.85rem;
  color: var(--el-text-color-secondary);
  margin-top: 5px;
}

.style-card-content {
  flex-grow: 1;
  margin-bottom: 15px;
}

.prompt-item {
  margin-bottom: 10px;
}

.prompt-item .label {
  font-weight: bold;
  color: var(--el-text-color-regular);
  display: block;
  margin-bottom: 5px;
}

.prompt-item .value {
  margin: 0;
  color: var(--el-text-color-primary);
  word-break: break-word;
  background-color: var(--el-fill-color-lighter);
  padding: 8px;
  border-radius: 4px;
  font-size: 0.9rem;
  max-height: 100px;
  overflow-y: auto;
}

.style-card-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
}
</style>