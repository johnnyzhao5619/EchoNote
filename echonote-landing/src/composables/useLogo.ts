import { ref, computed } from 'vue'

// 预定义的fallback图片
const FALLBACK_IMAGES = {
  logo: 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMzIiIGhlaWdodD0iMzIiIHZpZXdCb3g9IjAgMCAzMiAzMiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHJlY3Qgd2lkdGg9IjMyIiBoZWlnaHQ9IjMyIiByeD0iNCIgZmlsbD0iIzM5ODJmNiIvPgo8dGV4dCB4PSIxNiIgeT0iMjAiIGZvbnQtZmFtaWx5PSJBcmlhbCIgZm9udC1zaXplPSIxNCIgZm9udC13ZWlnaHQ9ImJvbGQiIGZpbGw9IndoaXRlIiB0ZXh0LWFuY2hvcj0ibWlkZGxlIj5FPC90ZXh0Pgo8L3N2Zz4K',
  image:
    'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDAwIiBoZWlnaHQ9IjMwMCIgdmlld0JveD0iMCAwIDQwMCAzMDAiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CjxyZWN0IHdpZHRoPSI0MDAiIGhlaWdodD0iMzAwIiBmaWxsPSIjZjNmNGY2Ii8+Cjx0ZXh0IHg9IjIwMCIgeT0iMTUwIiBmb250LWZhbWlseT0iQXJpYWwiIGZvbnQtc2l6ZT0iMTYiIGZpbGw9IiM2YjczODAiIHRleHQtYW5jaG9yPSJtaWRkbGUiPkltYWdlIG5vdCBhdmFpbGFibGU8L3RleHQ+Cjwvc3ZnPgo=',
} as const

/**
 * 通用图片处理组合式函数
 */
export function useImage(
  imagePath: string,
  alt: string,
  fallbackType: keyof typeof FALLBACK_IMAGES = 'image',
) {
  const imageSrc = ref(imagePath)
  const isLoading = ref(true)
  const hasError = ref(false)

  const handleImageError = () => {
    hasError.value = true
    imageSrc.value = FALLBACK_IMAGES[fallbackType]
    isLoading.value = false
  }

  const handleImageLoad = () => {
    isLoading.value = false
    hasError.value = false
  }

  const imageAlt = computed(() => {
    if (hasError.value) {
      return `${alt} (fallback)`
    }
    return alt
  })

  return {
    imageSrc,
    isLoading,
    hasError,
    imageAlt,
    handleImageError,
    handleImageLoad,
  }
}

/**
 * Logo专用组合式函数 - 基于通用图片函数
 */
export function useLogo(defaultPath = '/Logo.png') {
  const {
    imageSrc: logoSrc,
    isLoading,
    hasError,
    imageAlt,
    handleImageError,
    handleImageLoad,
  } = useImage(defaultPath, 'EchoNote - Modern Open Source Note-Taking App Logo', 'logo')

  return {
    logoSrc,
    isLoading,
    hasError,
    altText: imageAlt,
    handleLogoError: handleImageError,
    handleLogoLoad: handleImageLoad,
  }
}

/**
 * 响应式图片处理组合式函数 - 基于通用图片函数
 */
export function useResponsiveImage(imagePath: string, alt: string) {
  return useImage(imagePath, alt, 'image')
}
