<script setup lang="ts">
import { reactive, ref } from 'vue';
import { useRouter } from 'vue-router';
import Button from '@/components/common/Button.vue';
import Card from '@/components/common/Card.vue';
import { useAuthStore } from '@/stores/auth';

const auth = useAuthStore();
const router = useRouter();
const error = ref('');
const form = reactive({ email: '', password: '' });

async function onSubmit() {
  error.value = '';
  try {
    await auth.login(form.email, form.password);
    await router.push('/');
  } catch (err: any) {
    error.value = err?.response?.data?.error || 'Invalid credentials.';
  }
}
</script>

<template>
  <main class="flex min-h-screen items-center justify-center bg-dark-bg p-4">
    <Card class="w-full max-w-md space-y-4">
      <h1 class="text-2xl font-semibold">Sign in to ReviewHub</h1>
      <p class="text-sm text-text-secondary">Use your intern or admin account to continue.</p>

      <form class="space-y-4" @submit.prevent="onSubmit">
        <div>
          <label class="mb-1 block text-sm text-text-secondary">Email</label>
          <input
            v-model="form.email"
            type="email"
            required
            class="w-full rounded-lg border border-dark-border bg-dark-bg px-3 py-2 text-white outline-none ring-primary focus:ring-2"
          />
        </div>
        <div>
          <label class="mb-1 block text-sm text-text-secondary">Password</label>
          <input
            v-model="form.password"
            type="password"
            required
            class="w-full rounded-lg border border-dark-border bg-dark-bg px-3 py-2 text-white outline-none ring-primary focus:ring-2"
          />
        </div>
        <p v-if="error" class="text-sm text-error">{{ error }}</p>
        <Button type="submit" :disabled="auth.loading" class="w-full">
          {{ auth.loading ? 'Signing in...' : 'Login' }}
        </Button>
      </form>
    </Card>
  </main>
</template>
