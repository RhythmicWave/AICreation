<script setup lang="ts">
import { Setting, Moon, Sunny, Notebook } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import type { Language } from '../locales'
import { useI18n } from 'vue-i18n'
import { ref } from 'vue'

const emit = defineEmits<{
  (e: 'theme-change', dark: boolean): void
}>()

const { t, locale } = useI18n()
const isDark = ref(false)

// 语言切换，true 表示英文，false 表示中文
const isEnglish = ref(locale.value === 'en-US')

const handleLanguageChange = (value: boolean) => {
  const lang = value ? 'en-US' : 'zh-CN'
  locale.value = lang as Language
  ElMessage.success(t('common.languageChanged'))
}

const toggleTheme = () => {
  isDark.value = !isDark.value
  emit('theme-change', isDark.value)
  ElMessage.success(t(isDark.value ? 'common.darkMode' : 'common.lightMode'))
}
</script>

<template>
  <div class="header-content">
    <router-link to="/" style="text-decoration: none;">
      <div class="logo">{{ t('header.logo') }}</div>
    </router-link>
    <div class="right-section">
      <el-button @click="toggleTheme">
        <el-icon><component :is="isDark ? Sunny : Moon" /></el-icon>
      </el-button>
      <div class="lang-switch">
        <span class="lang-label">中文</span>
        <el-switch
          v-model="isEnglish"
          @change="handleLanguageChange"
          inline-prompt
          style="--el-switch-on-color: #409EFF"
        />
        <span class="lang-label">English</span>
      </div>
      <router-link to="/prompt-styler" style="text-decoration: none;">
        <el-button type="primary" class="settings-btn">
          <el-icon class="el-icon--left"><Notebook /></el-icon>
          {{ t('promptStyler.title') }}
        </el-button>
      </router-link>
      <router-link to="/setting" style="text-decoration: none;">
        <el-button type="primary" class="settings-btn">
          <el-icon class="el-icon--left"><Setting /></el-icon>
          {{ t('common.settings') }}
        </el-button>
      </router-link>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 20px;
  height: 60px;
  background-color: var(--el-bg-color);
  border-bottom: 1px solid var(--el-border-color-light);

  .logo {
    font-size: 24px;
    font-weight: bold;
    color: var(--el-text-color-primary);
  }

  .right-section {
    display: flex;
    align-items: center;
    gap: 16px;

    .lang-switch {
      display: flex;

      align-items: center;
      gap: 8px;

      .lang-label {
        font-size: 14px;
        color: var(--el-text-color-regular);
      }
    }

    .settings-btn {
      display: flex;
      align-items: center;
      justify-content: center;
      min-width: 100px;
    }
  }
}
</style>
