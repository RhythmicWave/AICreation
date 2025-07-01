import { ref, reactive, onBeforeUnmount, readonly } from 'vue';
import { ElMessage } from 'element-plus';
import { mediaApi } from '@/api/media_api';
import { useI18n } from 'vue-i18n';

export interface GenerationPrompt {
    id: string;
    prompt: string;
}

/**
 * @description 一个用于处理通用异步生成任务的Vue组合式函数
 */
export function useGeneration() {
    const { t } = useI18n();

    // 内部状态
    const _isGenerating = ref(false);
    const _submittedPrompts = ref<GenerationPrompt[]>([]);
    const _generationProgress = reactive({
        current: 0,
        total: 0,
        status: '', // 'running', 'completed', 'error', 'cancelled'
        taskId: '',
        errors: [] as string[],
        completedIds: [] as string[],
    });
    let _progressTimer: ReturnType<typeof setInterval> | null = null;

    /**
     * @description 重置所有与生成相关的状态
     */
    const resetProgress = () => {
        if (_progressTimer) {
            clearInterval(_progressTimer);
            _progressTimer = null;
        }
        _isGenerating.value = false;
        _submittedPrompts.value = [];
        _generationProgress.current = 0;
        _generationProgress.total = 0;
        _generationProgress.status = '';
        _generationProgress.taskId = '';
        _generationProgress.errors = [];
        _generationProgress.completedIds = [];
    };

    /**
     * @description 检查生成进度
     */
    const checkProgress = async () => {
        if (!_generationProgress.taskId) {
            resetProgress();
            return;
        }

        try {
            const response = await mediaApi.getProgress(_generationProgress.taskId);
            console.log(response)
            const { status, current, total, errors } = response;
            
            // 更新进度
            const newCompletedCount = current;
            const alreadyKnownCompletedCount = _generationProgress.completedIds.length;
            if (newCompletedCount > alreadyKnownCompletedCount) {
                const newIds = _submittedPrompts.value.slice(alreadyKnownCompletedCount, newCompletedCount).map(p => p.id);
                _generationProgress.completedIds.push(...newIds);
            }

            _generationProgress.status = status;
            _generationProgress.current = current;
            _generationProgress.total = total;
            _generationProgress.errors = errors || [];

            if (status === 'completed' || status === 'error' || status === 'cancelled' || status === 'not_found') {
                // 立即停止轮询，防止重复提示
                if (_progressTimer) {
                    clearInterval(_progressTimer);
                    _progressTimer = null;
                }

                if (status === 'completed') {
                    ElMessage.success(t('common.success'));
                } else if (status === 'cancelled') {
                    ElMessage.info(t('storyboardProcess.generationCancelled'));
                } else if (status === 'error') {
                    ElMessage.error(errors?.join('\\n') || t('common.error'));
                }
                
                // 延迟重置，让UI可以显示最终状态
                setTimeout(() => {
                    resetProgress();
                }, 1500);
            }
        } catch (error) {
            console.error('Failed to check generation progress:', error);
            ElMessage.error(t('common.error'));
            resetProgress();
        }
    };

    /**
     * @description 启动一个生成任务
     * @param prompts 包含id和prompt的数组
     * @param apiCall 一个返回Promise的函数，该Promise解析为{task_id: string, total: number}
     */
    const start = async (
        prompts: GenerationPrompt[],
        apiCall: () => Promise<{ task_id: string; total: number }>
    ) => {
        if (!prompts || prompts.length === 0) {
            ElMessage.warning(t('storyboardProcess.noPrompts'));
            return;
        }

        if (_isGenerating.value) {
            ElMessage.warning(t('storyboardProcess.generationInProgress'));
            return;
        }

        try {
            _isGenerating.value = true;
            _submittedPrompts.value = [...prompts]; // 保存提交的prompts副本
            _generationProgress.completedIds = []; // 清空上次的记录

            const data = await apiCall();

            _generationProgress.taskId = data.task_id;
            _generationProgress.total = data.total;
            _generationProgress.current = 0;
            _generationProgress.status = 'running';

            if (_progressTimer) clearInterval(_progressTimer);
            _progressTimer = setInterval(checkProgress, 1000);
        } catch (error) {
            console.error('Failed to start generation:', error);
            ElMessage.error(t('common.operationFailed'));
            resetProgress();
        }
    };
    
    /**
     * @description 停止当前生成任务
     */
    const stop = async () => {
        if (!_generationProgress.taskId) return;
        try {
            await mediaApi.cancelTask(_generationProgress.taskId);
            ElMessage.success(t('storyboardProcess.stopGenerationSuccess'));
            // checkProgress会处理后续的状态重置
        } catch (error) {
            console.error('Failed to stop generation:', error);
            ElMessage.error(t('common.error'));
            resetProgress();
        }
    };

    // 组件卸载时确保清除定时器
    onBeforeUnmount(() => {
        if (_progressTimer) {
            clearInterval(_progressTimer);
        }
    });
    
    // 返回只读的状态和可调用的方法
    return {
        isGenerating: readonly(_isGenerating),
        generationProgress: readonly(_generationProgress),
        start,
        stop,
    };
} 