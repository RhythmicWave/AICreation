import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { adminApi } from '@/api/admin_api'
import { useI18n } from 'vue-i18n'

export interface PromptStyle {
  name: string
  chinese_name: string
  prompt: string
  negative_prompt: string
}

export const usePromptStyleStore = defineStore('promptStyle', () => {
  const { locale } = useI18n()
  const styles = ref<PromptStyle[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  // 获取所有样式
  const fetchStyles = async () => {
    if (styles.value.length > 0) return // 如果已经有数据，不重复加载
    
    loading.value = true
    error.value = null
    
    try {
      const res = await adminApi.getPromptStyles()
      if (res && res.styles) {
        styles.value = res.styles
      } else {
        error.value = '获取样式列表失败'
      }
    } catch (err) {
      console.error('获取样式列表出错:', err)
      error.value = '网络错误，请稍后重试'
    } finally {
      loading.value = false
    }
  }

  // 保存样式列表
  const saveStyles = async (updatedStyles: PromptStyle[]) => {
    loading.value = true
    error.value = null
    
    try {
      const res = await adminApi.savePromptStyles(updatedStyles)
      if (res) {
        styles.value = updatedStyles
        return true
      } else {
        error.value = '保存失败'
        return false
      }
    } catch (err) {
      console.error('保存样式出错:', err)
      error.value = '网络错误，请稍后重试'
      return false
    } finally {
      loading.value = false
    }
  }

  // 格式化后的样式列表，用于下拉选择框
  const styleOptions = computed(() => {
    return styles.value.map(style => ({
      label: locale.value === 'zh-CN' ? style.chinese_name : style.name,
      value: style.name
    }))
  })

  // 根据名称获取样式
  const getStyleByName = (name: string) => {
    return styles.value.find(style => style.name === name)
  }

  // 添加新样式
  const addStyle = async (style: PromptStyle) => {
    const updatedStyles = [...styles.value, style]
    return await saveStyles(updatedStyles)
  }

  // 更新样式
  const updateStyle = async (style: PromptStyle) => {
    const index = styles.value.findIndex(s => s.name === style.name)
    if (index === -1) return false
    
    const updatedStyles = [...styles.value]
    updatedStyles[index] = style
    return await saveStyles(updatedStyles)
  }

  // 删除样式
  const deleteStyle = async (name: string) => {
    const updatedStyles = styles.value.filter(s => s.name !== name)
    return await saveStyles(updatedStyles)
  }

  return {
    styles,
    loading,
    error,
    fetchStyles,
    styleOptions,
    getStyleByName,
    addStyle,
    updateStyle,
    deleteStyle,
    saveStyles
  }
}) 