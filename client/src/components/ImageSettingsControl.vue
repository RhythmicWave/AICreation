<template>
  <div class="settings-group">
    <div class="settings-title">{{ t('storyboardProcess.imageSettings') }}</div>
    <el-row :gutter="12">
      <el-col :span="8">
        <div class="input-with-label">
          <span class="input-label">{{ t('storyboardProcess.imageWidth') }}</span>
          <el-input-number
            :model-value="modelValue.width"
            @update:model-value="update('width', $event)"
            :min="64" :max="2048" :step="64"
            controls-position="right"
          />
        </div>
      </el-col>
      <el-col :span="8">
        <div class="input-with-label">
          <span class="input-label">{{ t('storyboardProcess.imageHeight') }}</span>
          <el-input-number
            :model-value="modelValue.height"
            @update:model-value="update('height', $event)"
            :min="64" :max="2048" :step="64"
            controls-position="right"
          />
        </div>
      </el-col>
      <el-col :span="8">
        <div class="input-with-label">
          <span class="input-label">{{ t('storyboardProcess.imageStyle') }}</span>
          <el-select
            :model-value="modelValue.style"
            @update:model-value="update('style', $event)"
            class="style-select"
          >
            <el-option
              v-for="style in styleOptions"
              :key="style.value"
              :label="style.label"
              :value="style.value"
            />
          </el-select>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { usePromptStyleStore } from '@/store/usePromptStyleStore';
import type { ImageSettings } from '@/types/imageSettings';

const { t } = useI18n();

// v-model an object
const props = defineProps<{
  modelValue: ImageSettings;
}>();

const emit = defineEmits(['update:modelValue']);

const update = (key: keyof ImageSettings, value: any) => {
  emit('update:modelValue', { ...props.modelValue, [key]: value });
};

// Prompt Style Store
const promptStyleStore = usePromptStyleStore();
const styleOptions = computed(() => promptStyleStore.styleOptions);

onMounted(() => {
  if (styleOptions.value.length === 0) {
    promptStyleStore.fetchStyles();
  }
});
</script>

<style scoped>
.settings-group {
  background-color: var(--el-fill-color-light);
  border-radius: 4px;
  padding: 16px;
}
.settings-title {
  font-size: 14px;
  color: var(--el-text-color-primary);
  margin-bottom: 16px;
  font-weight: bold;
}
.input-with-label {
  display: flex;
  align-items: center;
  gap: 8px;
}
.input-label {
  white-space: nowrap;
  color: var(--el-text-color-regular);
}
.el-input-number {
  width: 120px;
}
.style-select {
  width: 100%;
}
</style> 