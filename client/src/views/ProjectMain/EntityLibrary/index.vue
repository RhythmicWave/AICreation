<template>
  <div class="entity-library">
    <h3>{{ config.title }}</h3>
    
    <!-- 设置区域 -->
    <el-row :gutter="24" class="settings-row">
      <el-col :span="24">
        <ImageSettingsControl v-model="imageSettings" />
      </el-col>
    </el-row>

    <!-- 操作栏 -->
    <div class="header-container">
      <el-button type="primary" @click="openCreateDialog">
        {{ config.createButtonText }}
      </el-button>
      <el-button
        type="success"
        @click="generateImagesForSelected"
        :loading="isGenerating"
        :disabled="selectedEntities.length === 0"
      >
        {{ t('storyboardProcess.generateSelectedImages') }}
      </el-button>
      <div class="search-container">
        <el-input
          v-model="searchQuery"
          :placeholder="t('common.search')"
          :prefix-icon="Search"
          clearable
        />
      </div>
    </div>

    <!-- 进度显示 -->
    <el-row v-if="generationProgress.taskId" :gutter="24" class="progress-row">
      <el-col :span="24">
        <div class="settings-group">
          <div class="settings-title">{{ t('storyboardProcess.generationProgress') }}</div>
          <div class="progress-container">
            <el-progress
              :percentage="generationProgress.total > 0 ? Math.floor((generationProgress.current / generationProgress.total) * 100) : 0"
              :format="() => `${generationProgress.current}/${generationProgress.total}`"
              :status="generationProgress.status === 'error' ? 'exception' : generationProgress.status === 'completed' ? 'success' : ''"
              :duration="1"
            />
            <el-button type="danger" @click="stop" style="margin-left: 10px; margin-top: 5px;">
              {{ t('storyboardProcess.stopGeneration') }}
            </el-button>
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- 实体表格 -->
    <el-table
      v-loading="loading"
      :data="filteredEntities"
      @selection-change="handleSelectionChange"
      style="width: 100%"
      border
    >
      <el-table-column type="selection" width="55" align="center" />
      <el-table-column
        :label="t('entity.entityName')"
        prop="name"
        width="120"
        align="center"
      >
        <template #default="{ row }">
          <span class="entity-name">{{ row.name }}</span>
        </template>
      </el-table-column>
      
      <!-- 动态列 -->
      <el-table-column v-if="entityType === 'character'" :label="t('entity.role')" width="150" align="center">
        <template #default="{ row }">
          <el-input v-model="row.attributes.role" type="textarea" :rows="2" :placeholder="t('entity.role')" :disabled="isLocked(row.name)"/>
        </template>
      </el-table-column>
      <el-table-column :label="t('entity.description')" min-width="240" align="center">
        <template #default="{ row }">
          <el-input v-model="row.attributes.description" type="textarea" :rows="5" :placeholder="t('entity.description')" :disabled="isLocked(row.name)"/>
        </template>
      </el-table-column>

      <el-table-column :label="t('entity.referenceImage')" width="260" align="center">
        <template #default="{ row }">
          <div>
            <el-image v-if="row.reference_image" :src="row.reference_image" fit="contain" :preview-src-list="[row.reference_image]" :initial-index="0" preview-teleported height="90%">
              <template #error><div class="no-image">{{ t('common.loadError') }}</div></template>
            </el-image>
            <div style="display:flex; gap:8px; justify-content:center; margin-top:10px;">
              <el-button 
                type="primary" 
                style="min-width: 120px;" 
                @click="generateImage(row)"
                :loading="isGenerating"
                :disabled="isGenerating"
              >{{ t('entity.generateImage') }}</el-button>
              <el-button 
                type="warning" 
                style="min-width: 120px;" 
                @click="() => onClickUpload(row)"
              >{{ t('common.upload') || '上传图片' }}</el-button>
            </div>
          </div>
        </template>
      </el-table-column>
      
      <el-table-column :label="t('common.operations')" width="360" align="center">
        <template #default="{ row }">
          <div class="operation-buttons">
            <div class="button-row" v-if="entityType === 'character'">
              <el-button :type="isLocked(row.name) ? 'warning' : 'primary'" @click="handleLockClick(row)">
                {{ isLocked(row.name) ? t('entity.unlockPrompt') : t('entity.lockPrompt') }}
              </el-button>
            </div>
            <div class="button-row">
              <el-button type="success" :disabled="isLocked(row.name)" @click="saveEntity(row)">
                {{ t('entity.savePrompt') }}
              </el-button>
              <el-button type="danger" :disabled="isLocked(row.name)" @click="deleteEntity(row)">
                {{ t('entity.delete') }}
              </el-button>
            </div>
          </div>
        </template>
      </el-table-column>
    </el-table>

    <!-- 创建实体对话框 -->
    <el-dialog v-model="createDialogVisible" :title="config.createDialogTitle" width="600px">
      <div class="create-entity-form">
        <el-form :model="newEntity" label-width="120px">
          <el-form-item :label="t('entity.entityName')" required>
            <el-input v-model="newEntity.name" />
          </el-form-item>
          <el-form-item v-if="entityType === 'character'" :label="t('entity.role')">
            <el-input v-model="newEntity.attributes.role" type="textarea" :rows="2" :placeholder="t('entity.role')"/>
          </el-form-item>
          <el-form-item :label="t('entity.description')">
            <el-input v-model="newEntity.attributes.description" type="textarea" :rows="5" :placeholder="t('entity.description')"/>
          </el-form-item>
        </el-form>
        <div class="dialog-footer">
          <el-button @click="createDialogVisible = false">{{ t('entity.cancel') }}</el-button>
          <el-button type="primary" @click="createEntity">{{ t('entity.create') }}</el-button>
        </div>
      </div>
    </el-dialog>

    <!-- 隐藏文件选择器，用于上传参考图 -->
    <input ref="fileInputRef" type="file" accept="image/*" style="display:none" @change="onFileSelected" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, reactive, watch } from 'vue';
import { useRoute } from 'vue-router';
import { useI18n } from 'vue-i18n';
import { ElMessage, ElMessageBox } from 'element-plus';
import { Search } from '@element-plus/icons-vue';
import { entityApi } from '@/api/entity_api';
import { mediaApi } from '@/api/media_api';
import { getResourcePath } from '@/utils/resourcePath';
import { useGeneration } from '@/composables/useGeneration';
import { usePromptStyleStore } from '@/store/usePromptStyleStore';
import type { ImageSettings } from '@/types/imageSettings';
import ImageSettingsControl from '@/components/ImageSettingsControl.vue';

const route = useRoute();
const { t } = useI18n();

const entityType = computed(() => route.params.entityType as 'character' | 'scene');
const projectName = computed(() => route.params.name as string);

// --- 组合式函数 ---
const { isGenerating, generationProgress, start, stop } = useGeneration();
const promptStyleStore = usePromptStyleStore();

// --- 接口定义 ---
interface Entity {
  name: string;
  attributes: {
    role?: string;
    description?: string;
    [key: string]: any;
  };
  reference_image?: string;
}

// --- 组件状态 ---
const loading = ref(false);
const entities = ref<Entity[]>([]);
const selectedEntities = ref<Entity[]>([]);
const lockedEntities = ref<string[]>([]);
const searchQuery = ref('');
const createDialogVisible = ref(false);

const newEntity = reactive<Entity>({
  name: '',
  attributes: { role: '', description: '' },
});

const imageSettings = ref<ImageSettings>({
  width: 512,
  height: 768,
  style: 'sai-anime'
});

// 上传参考图状态
const fileInputRef = ref<HTMLInputElement | null>(null);
const pendingUploadRow = ref<Entity | null>(null);

// --- 根据实体类型动态配置 ---
const config = computed(() => {
  const isCharacter = entityType.value === 'character';
  return {
    title: isCharacter ? t('menu.characterLibrary') : t('menu.sceneLibrary'),
    createButtonText: isCharacter ? t('entity.createCharacter') : t('entity.createScene'),
    createDialogTitle: isCharacter ? t('entity.createCharacterTitle') : t('entity.createSceneTitle'),
    fetchApi: isCharacter ? entityApi.getCharacterList : entityApi.getSceneList,
    createApi: isCharacter ? entityApi.createCharacter : entityApi.createScene,
    updateApi: isCharacter ? entityApi.updateCharacter : entityApi.updateScene,
    deleteApi: isCharacter ? entityApi.deleteCharacter : entityApi.deleteScene,
    imageChapter: isCharacter ? 'Character' : 'Scene',
  };
});

// --- 数据获取与处理 ---
const fetchEntities = async () => {
  loading.value = true;
  try {
    const data = await config.value.fetchApi(projectName.value);
    if (entityType.value === 'character') {
      entities.value = data.characters.map((char: any) => ({
        ...char,       
        reference_image: getResourcePath(projectName.value, config.value.imageChapter, char.name, 'image')
      }));
      lockedEntities.value = data.locked_entities || [];
    } else {
      entities.value = Object.entries(data.scenes).map(([name, prompt]) => ({
        name,
        attributes: { description: prompt as string },
        reference_image: getResourcePath(projectName.value, config.value.imageChapter, name, 'image')
      }));
    }
  } catch (error) {
    ElMessage.error(String(error));
  } finally {
    loading.value = false;
  }
};

const filteredEntities = computed(() => {
  const query = searchQuery.value.toLowerCase().trim();
  if (!query) return entities.value;
  return entities.value.filter(e => e.name.toLowerCase().includes(query));
});

const handleSelectionChange = (selection: Entity[]) => {
  selectedEntities.value = selection;
};

// --- 增删改查操作 ---
const openCreateDialog = () => {
  Object.assign(newEntity, { name: '', attributes: { role: '', description: '' } });
  createDialogVisible.value = true;
};

const createEntity = async () => {
  if (!newEntity.name.trim()) {
    ElMessage.error(t('entity.nameRequired'));
    return;
  }
  try {
    const payload = entityType.value === 'character'
      ? newEntity
      : { name: newEntity.name, prompt: newEntity.attributes.description || '' };

    await config.value.createApi(projectName.value, payload as any);
    ElMessage.success(t('entity.createSuccess'));
    createDialogVisible.value = false;
    await fetchEntities();
  } catch (error) {
    ElMessage.error(String(error) || t('entity.createError'));
  }
};

const saveEntity = async (row: Entity) => {
  try {
    const payload = entityType.value === 'character'
      ? { name: row.name, attributes: row.attributes }
      : { name: row.name, prompt: row.attributes.description || '' };

    await config.value.updateApi(projectName.value, payload as any);
    ElMessage.success(t('entity.updateSuccess'));
  } catch (error) {
    ElMessage.error(String(error));
  }
};

const deleteEntity = async (row: Entity) => {
  try {
    await ElMessageBox.confirm(t('entity.deleteConfirm'), t('common.warning'), { type: 'warning' });
    await config.value.deleteApi(projectName.value, row.name);
    ElMessage.success(t('entity.deleteSuccess'));
    await fetchEntities();
  } catch (error) {
    if (error !== 'cancel') ElMessage.error(t('entity.operationFailed'));
  }
};

// --- 角色专属逻辑 ---
const isLocked = (name: string) => {
  return entityType.value === 'character' && lockedEntities.value.includes(name);
};

const handleLockClick = async (row: Entity) => {
  if (entityType.value !== 'character') return;
  const action = () => entityApi.toggleLock(projectName.value, row.name).then(response => {
    if (response.is_locked) {
      ElMessage.success(t('entity.lockSuccess'));
    } else {
      ElMessage.success(t('entity.unlockSuccess'));
    }
    fetchEntities();
  }).catch(() => ElMessage.error(t('entity.operationFailed')));
  
  if (!isLocked(row.name)) {
    ElMessageBox.confirm(t('entity.lockConfirmContent'), t('entity.lockConfirmTitle'), { type: 'warning' }).then(action);
  } else {
    action();
  }
};

// --- 图像生成 ---
const generateImage = async (row: Entity) => {
  let prompts = [];
  //增强提示词
  if (entityType.value === 'character') {
    prompts = [{
      id: row.name,
      prompt: (row.attributes.description || '') +
        ", full body, facing forward, front view, standing in a neutral pose, camera at a far distance, entire figure visible, plain light gray monochromatic background, minimalist environment, subtle shadow, no close-up, no text, no logo, no watermark"
    }];
  } else {
    prompts = [{ id: row.name, prompt: (row.attributes.description || '') + "no human,wide-angle lens, establishing shot, vast environment, depth of field, cinematic scale" }];
  }
  start(prompts, () => mediaApi.generateImages({
    project_name: projectName.value,
    chapter_name: config.value.imageChapter,
    imageSettings: imageSettings.value,
    prompts,
  }));
};

// 上传逻辑
const onClickUpload = (row: Entity) => {
  pendingUploadRow.value = row;
  fileInputRef.value?.click();
};

const onFileSelected = async (e: Event) => {
  const input = e.target as HTMLInputElement;
  const file = input.files && input.files[0];
  if (!file || !pendingUploadRow.value) return;
  try {
    await mediaApi.uploadReferenceImage(
      projectName.value,
      config.value.imageChapter,
      pendingUploadRow.value.name,
      file
    );
    ElMessage.success(t('common.uploadSuccess') || '上传成功');
    await fetchEntities();
  } catch (err) {
    ElMessage.error(String(err));
  } finally {
    // 清理 input 值，便于下次选择同名文件也能触发 change
    if (fileInputRef.value) fileInputRef.value.value = '';
    pendingUploadRow.value = null;
  }
};

const generateImagesForSelected = () => {
  const prompts = selectedEntities.value
    .filter(e => e.attributes.description)
    .map(e => ({ id: e.name, prompt: e.attributes.description || '' }));
  
  start(prompts, () => mediaApi.generateImages({
    project_name: projectName.value,
    chapter_name: config.value.imageChapter,
    imageSettings: imageSettings.value,
    prompts,
  }));
};

watch(isGenerating, (newValue, oldValue) => {
  if (oldValue === true && newValue === false) {
    setTimeout(() => fetchEntities(), 1000);
  }
});

// 监听单个图片完成事件
watch(() => [...generationProgress.completedIds], (newIds, oldIds) => {
  if (newIds.length > oldIds.length) {
    const lastCompletedId = newIds[newIds.length - 1];
    const entity = entities.value.find(e => e.name === lastCompletedId);
    if (entity) {
      entity.reference_image = getResourcePath(projectName.value, config.value.imageChapter, entity.name, 'image');
    }
  }
});

watch(entityType, () => {
    fetchEntities();
    if(entityType.value === 'scene'){
    imageSettings.value.width=768;
    imageSettings.value.height=768;
   
  }else{
     imageSettings.value.width=512;
    imageSettings.value.height=768;
  }
});

// --- 生命周期钩子 ---
onMounted(() => {
  fetchEntities();
  promptStyleStore.fetchStyles();
  
});
</script>

<style scoped>
.entity-library { padding: 20px; }
.header-container { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; flex-wrap: wrap; gap: 10px; }
.search-container { max-width: 300px; margin-left: auto; }
.progress-row { margin-bottom: 20px; }
.settings-group { background-color: var(--el-fill-color-light); border-radius: 4px; padding: 16px; }
.settings-title { font-size: 14px; color: var(--el-text-color-primary); margin-bottom: 16px; font-weight: bold; }
.progress-container { display: flex; align-items: center; gap: 10px; }
.progress-container :deep(.el-progress) { flex: 1; }
.operation-buttons { display: flex; flex-direction: column; gap: 8px; }
.button-row { display: flex; gap: 8px; justify-content: center; }
.button-row .el-button { flex: 1; min-width: 110px; }
.entity-name { display: inline-block; line-height: 40px; height: 40px; }
.dialog-footer { display: flex; justify-content: flex-end; gap: 10px; margin-top: 20px; }
.create-entity-form { padding: 10px; }
:deep(.el-table__cell) { padding: 8px 0; }
:deep(.el-table .cell) { white-space: pre-wrap; word-break: break-word; line-height: 1.5; }
:deep(.el-table__header .cell) { font-weight: bold; }
.settings-row {
  margin-bottom: 20px;
}
</style> 