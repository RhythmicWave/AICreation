import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      redirect: '/project'
    },
    {
      path: '/setting',
      name: 'Setting',
      component: () => import('@/views/Setting/index.vue')
    },
    {
      path: '/prompt-styler',
      name: 'PromptStyler',
      component: () => import('@/views/PromptStyler/index.vue')
    },
    {
      path: '/project',
      name: 'Project',
      component: () => import('@/views/Project/index.vue')
    },
    {
      path: '/project/:name',
      component: () => import('@/views/ProjectMain/index.vue'),
      children: [
        {
          path: '',
          redirect: to => `/project/${to.params.name}/text-creation`
        },
        {
          path: 'text-creation',
          name: 'TextCreation',
          component: () => import('@/views/ProjectMain/TextCreation/index.vue')
        },
        {
          path: 'library/:entityType',
          name: 'EntityLibrary',
          component: () => import('@/views/ProjectMain/EntityLibrary/index.vue')
        },
        {
          path: 'storyboard-process',
          name: 'StoryboardProcess',
          component: () => import('@/views/ProjectMain/StoryboardProcess/index.vue')
        },
        {
          path: 'video-output',
          name: 'VideoOutput',
          component: () => import('@/views/ProjectMain/VideoOutput/index.vue')
        }
      ]
    },
    {
      path: '/:pathMatch(.*)*',
      name: 'NotFound',
      component: () => import('@/views/NotFound/index.vue')
    }
  ]
})

export default router
