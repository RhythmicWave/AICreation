<template>
  <div class="video-output">
    <h3>{{ t('videoOutput.title') }}</h3>
    
    <!-- 章节选择 -->
    <div class="section">
      <el-select 
        v-model="selectedChapter" 
        :placeholder="t('videoOutput.chapterSelect')"
        @change="handleChapterChange"
      >
        <el-option
          v-for="chapter in chapters"
          :key="chapter"
          :label="chapter"
          :value="chapter"
        />
      </el-select>
    </div>

    <!-- 视频配置表单 -->
    <div class="config-section">
      <el-form :model="videoSettings" label-width="180px">
        <!-- 淡入淡出设置 -->
        <el-form-item :label="t('videoOutput.fadeDuration')">
          <el-input-number 
            v-model="videoSettings.fade_duration" 
            :min="0" 
            :max="2"
          />
        </el-form-item>
        <!-- 画面平移设置 -->
        <el-form-item :label="t('videoOutput.usePan')">
          <el-switch v-model="videoSettings.use_pan" />
        </el-form-item>
        
        <template v-if="videoSettings.use_pan">
          <el-form-item :label="t('videoOutput.panRangeX')">
            <el-slider 
              v-model="videoSettings.pan_range[0]" 
              :min="0" 
              :max="1" 
              :step="0.1" 
            />
          </el-form-item>
          
          <el-form-item :label="t('videoOutput.panRangeY')">
            <el-slider 
              v-model="videoSettings.pan_range[1]" 
              :min="0" 
              :max="1" 
              :step="0.1" 
            />
          </el-form-item>
        </template>

        <!-- 帧率设置 -->
        <el-form-item :label="t('videoOutput.fps')">
          <el-input-number 
            v-model="videoSettings.fps" 
            :min="1" 
            :max="60"
          />
        </el-form-item>
        
        <!-- 源图片分辨率 -->
        <el-form-item :label="t('videoOutput.imageResolution')">
          <el-input-number 
            v-model="imageResolution[0]" 
            :min="100" 
            :max="4000"
            :step="16"
            :placeholder="t('videoOutput.imageWidth')"
            style="margin-right: 10px"
          />
          <el-input-number 
            v-model="imageResolution[1]" 
            :min="100" 
            :max="4000"
            :step="16"
            :placeholder="t('videoOutput.imageHeight')"
          />
        </el-form-item>

        <!-- 分辨率设置 -->
        <el-form-item :label="t('videoOutput.resolution')">
          <el-input-number 
            v-model="videoSettings.resolution[0]" 
            :min="100" 
            :max="4000"
            :step="16"
            :placeholder="t('videoOutput.width')"
            style="margin-right: 10px"
          />
          <el-input-number 
            v-model="videoSettings.resolution[1]" 
            :min="100" 
            :max="4000"
            :step="16"
            :placeholder="t('videoOutput.height')"
          />
          <el-button @click="calculateRecommendedResolution" class="calc-btn">
            {{ t('videoOutput.calculateRecommended') }}
          </el-button>
        </el-form-item>
      </el-form>
    </div>

    <!-- 操作按钮和视频区域 -->
    <div class="action-section">
      <el-button 
        type="primary" 
        :loading="isGenerating"
        @click="handleGenerateVideo"
      >
        {{ t('videoOutput.generateVideo') }}
      </el-button>
      
      <el-button 
        v-if="isGenerating"
        type="danger" 
        @click="handleCancelGeneration"
      >
        {{ t('videoOutput.cancelGeneration') }}
      </el-button>
    </div>
    
    <!-- 进度条 -->
    <div v-if="isGenerating" class="progress-section">
      <div class="progress-info">
        <span>{{ progressInfo }}</span>
      </div>
      <el-progress 
        :percentage="progressPercentage" 
        :status="progressStatus"
      />
    </div>

    <div class="video-preview" v-if="videoUrl">
      <video 
        controls
        :src="videoUrl"
        class="video-player"
      >
        {{ t('videoOutput.browserNotSupport') }}
      </video>
    </div>

    <div v-if="errorMessage" class="error-message">
      {{ errorMessage }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, onBeforeUnmount } from 'vue'
import { useRoute } from 'vue-router'
import { chapterApi } from '@/api/chapter_api'
import { videoApi } from '@/api/video_api'
import type { VideoSettings, VideoProgress } from '@/types/video'
import { getResourcePath } from '@/utils/resourcePath'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'

const route = useRoute()
const projectName = route.params.name as string

const { t } = useI18n()

// 章节相关
const chapters = ref<string[]>([])
const selectedChapter = ref('')
const imageResolution = ref<[number, number]>([512, 768])

// 视频设置
const videoSettings = ref<VideoSettings>({
  project_name: projectName,
  chapter_name:'',
  fade_duration:1,
  use_pan: true,
  pan_range: [0.3, 0],
  fps: 20,
  resolution:[768,768]
})

// 状态管理
const isGenerating = ref(false)
const videoUrl = ref('')
const errorMessage = ref('')

// 进度相关
const progressData = ref<VideoProgress>({
  progress: 0,
  total: 0,
  percentage: 0,
  current_task: null
})
const progressInterval = ref<number | null>(null)
const progressPercentage = computed(() => progressData.value.percentage)
const progressInfo = computed(() => {
  if (!progressData.value.current_task) return ''
  return `${progressData.value.current_task} (${progressData.value.progress}/${progressData.value.total})`
})
const progressStatus = computed(() => {
  if (progressData.value.percentage >= 100) return 'success'
  return ''
})

// 开始定时获取进度
const startProgressTracking = () => {
  // 立即获取一次进度
  fetchProgress()
  
  // 设置定时器每秒获取一次进度
  progressInterval.value = window.setInterval(() => {
    fetchProgress()
  }, 1000)
}

// 停止进度跟踪
const stopProgressTracking = () => {
  if (progressInterval.value) {
    clearInterval(progressInterval.value)
    progressInterval.value = null
    progressData.value = {
      progress: 0,
      total: 0,
      percentage: 0,
      current_task: null
    }
  }
}

// 获取进度
const fetchProgress = async () => {
  try {
    const res = await videoApi.getGenerationProgress()
  
    if (res) {
      
      progressData.value = res as VideoProgress
      
      // 如果进度已完成并且当前正在生成，更新状态并停止跟踪
      if (progressData.value.percentage >= 100 && isGenerating.value) {
        isGenerating.value = false
        stopProgressTracking()
        handleChapterChange() // 刷新视频
        ElMessage.success(t('videoOutput.generationComplete'))
      }
    }
  } catch (error) {
    console.error('获取进度失败', error)
  }
}

// 获取章节列表
// 在组件中修改视频生成处理逻辑
const handleGenerateVideo = async () => {
  try {
    videoSettings.value.chapter_name = selectedChapter.value;
    
    isGenerating.value = true;
    // 开始跟踪进度
    startProgressTracking()
    
    // 发起视频生成请求
    await videoApi.generateVideo(videoSettings.value)
  } catch (error) {
    // 错误处理
    console.log(error)
    isGenerating.value = false;
    stopProgressTracking()
    ElMessage.error(t('error.generateFailed'))
  }
}

// 取消视频生成
const handleCancelGeneration = async () => {
  try {
    await videoApi.cancelGeneration()
    ElMessage.info(t('videoOutput.generationCancelled'))
    isGenerating.value = false
    stopProgressTracking()
  } catch (error) {
    console.error('取消生成失败', error)
    ElMessage.error(t('videoOutput.cancelFailed'))
  }
}

// 修改后的章节获取逻辑
const fetchChapters = async () => {
  try {
    const res = await chapterApi.getChapterList(projectName)
    
    chapters.value = res as unknown as string[]

    if (chapters.value.length > 0) {
      selectedChapter.value = chapters.value[0]
      videoUrl.value = getResourcePath(projectName, selectedChapter.value, '0', 'video')
    }
    
  } catch (error) {
    errorMessage.value = t('error.fetchChapterListFailed')
  }
}

// 章节变更处理
const handleChapterChange = () => {
  videoUrl.value = getResourcePath(projectName, selectedChapter.value, '0', 'video')
}

// 计算推荐分辨率
const calculateRecommendedResolution = () => {
  const [imgW, imgH] = imageResolution.value
  const [panX, panY] = videoSettings.value.pan_range
  const [outW, outH] = videoSettings.value.resolution

  const roundToMultipleOf4 = (value: number) => Math.round(value / 4) * 4;

  if (panX > 0) {
    const recommendedW = roundToMultipleOf4((outH * (imgW / imgH)) / (1 + panX));
    videoSettings.value.resolution[0] = recommendedW;
  } else if (panY > 0) {
    const recommendedH = roundToMultipleOf4((outW * (imgH / imgW)) / (1 + panY));
    videoSettings.value.resolution[1] = recommendedH;
  } else {
    const recommendedW = roundToMultipleOf4(outH * (imgW / imgH));
    videoSettings.value.resolution[0] = recommendedW;
  }
  
  ElMessage.success(t('videoOutput.resolutionUpdated'))
}

// 组件卸载前清理定时器
onBeforeUnmount(() => {
  stopProgressTracking()
})

// 初始化
onMounted(() => {
  fetchChapters()
})
</script>

<style scoped>
.video-output {
  padding: 20px;
  max-width: 70vw;
  margin: 0 auto;
}

.section {
  margin-bottom: 24px;
}

.config-section {
  margin: 24px 0;
  padding: 20px;
  border: 1px solid var(--el-border-color);
  border-radius: 4px;
}

.progress-section {
  margin: 20px 0;
  padding: 15px;
  border: 1px solid var(--el-border-color);
  border-radius: 4px;
  background-color: var(--el-fill-color-light);
}

.progress-info {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 14px;
  color: var(--el-text-color-secondary);
}

.video-preview {
  margin-top: 24px;
}

.video-player {
  width: 100%;
  max-width: 70vw;
  border-radius: 4px;
  background: #000;
}

.error-message {
  color: #f56c6c;
  margin-top: 12px;
}

.action-section {
  margin: 16px 0;
  display: flex;
  gap: 10px;
}

.calc-btn {
  margin-left: 10px;
}
</style>