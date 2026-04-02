<template>
  <div class="min-h-screen flex items-center justify-center bg-gray-900 py-12 px-4 sm:px-6 lg:px-8">
    <div class="max-w-md w-full space-y-8">
      <div>
        <h2 class="mt-6 text-center text-3xl font-extrabold text-white">
          Create your account
        </h2>
        <p class="mt-2 text-center text-sm text-gray-400">
          Or
          <router-link to="/login" class="font-medium text-indigo-400 hover:text-indigo-300">
            sign in to existing account
          </router-link>
        </p>
      </div>
      
      <form class="mt-8 space-y-6" @submit.prevent="handleRegister">
        <div v-if="error" class="bg-red-900/50 border border-red-500 text-red-300 px-4 py-3 rounded">
          {{ error }}
        </div>
        
        <div class="rounded-md shadow-sm space-y-4">
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label for="first_name" class="sr-only">First name</label>
              <input
                id="first_name"
                v-model="form.first_name"
                type="text"
                required
                class="appearance-none relative block w-full px-3 py-2 border border-gray-700 placeholder-gray-500 text-white bg-gray-800 rounded-md focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
                placeholder="First name"
              />
            </div>
            <div>
              <label for="last_name" class="sr-only">Last name</label>
              <input
                id="last_name"
                v-model="form.last_name"
                type="text"
                required
                class="appearance-none relative block w-full px-3 py-2 border border-gray-700 placeholder-gray-500 text-white bg-gray-800 rounded-md focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
                placeholder="Last name"
              />
            </div>
          </div>
          
          <div>
            <label for="email" class="sr-only">Email address</label>
            <input
              id="email"
              v-model="form.email"
              type="email"
              required
              class="appearance-none relative block w-full px-3 py-2 border border-gray-700 placeholder-gray-500 text-white bg-gray-800 rounded-md focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
              placeholder="Email address"
            />
          </div>
          
          <div>
            <label for="username" class="sr-only">Username</label>
            <input
              id="username"
              v-model="form.username"
              type="text"
              required
              class="appearance-none relative block w-full px-3 py-2 border border-gray-700 placeholder-gray-500 text-white bg-gray-800 rounded-md focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
              placeholder="Username"
            />
          </div>
          
          <div>
            <label for="password" class="sr-only">Password</label>
            <input
              id="password"
              v-model="form.password"
              type="password"
              required
              minlength="8"
              class="appearance-none relative block w-full px-3 py-2 border border-gray-700 placeholder-gray-500 text-white bg-gray-800 rounded-md focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
              placeholder="Password (min 8 characters)"
            />
          </div>
          
          <div>
            <label for="confirm_password" class="sr-only">Confirm password</label>
            <input
              id="confirm_password"
              v-model="form.confirm_password"
              type="password"
              required
              class="appearance-none relative block w-full px-3 py-2 border border-gray-700 placeholder-gray-500 text-white bg-gray-800 rounded-md focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
              placeholder="Confirm password"
            />
          </div>
        </div>
        
        <div>
          <button
            type="submit"
            :disabled="loading"
            class="group relative w-full flex justify-center py-2 px-4 border border-transparent text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <span v-if="loading" class="absolute left-0 inset-y-0 flex items-center pl-3">
              <svg class="animate-spin h-5 w-5 text-indigo-300" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
            </span>
            {{ loading ? 'Creating account...' : 'Create account' }}
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const loading = ref(false)
const error = ref('')

const form = reactive({
  first_name: '',
  last_name: '',
  email: '',
  username: '',
  password: '',
  confirm_password: ''
})

async function handleRegister() {
  error.value = ''
  
  // Validate passwords match
  if (form.password !== form.confirm_password) {
    error.value = 'Passwords do not match'
    return
  }
  
  if (form.password.length < 8) {
    error.value = 'Password must be at least 8 characters'
    return
  }
  
  loading.value = true
  
  try {
    const response = await fetch(`${import.meta.env.VITE_API_URL}/api/users/register/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        first_name: form.first_name,
        last_name: form.last_name,
        email: form.email,
        username: form.username,
        password: form.password
      })
    })
    
    const data = await response.json()
    
    if (!response.ok) {
      // Handle validation errors
      if (data.email) {
        error.value = `Email: ${data.email[0]}`
      } else if (data.username) {
        error.value = `Username: ${data.username[0]}`
      } else if (data.password) {
        error.value = `Password: ${data.password[0]}`
      } else {
        error.value = data.error || data.detail || 'Registration failed'
      }
      return
    }
    
    // Auto-login with returned tokens
    if (data.tokens) {
      authStore.setTokens(data.tokens.access, data.tokens.refresh)
      authStore.setUser(data.user)
      router.push('/')
    } else {
      // Redirect to login if no auto-login
      router.push('/login?registered=true')
    }
  } catch (err) {
    error.value = 'Network error. Please try again.'
    console.error('Registration error:', err)
  } finally {
    loading.value = false
  }
}
</script>
