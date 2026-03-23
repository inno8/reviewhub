<script setup lang="ts">
import { reactive, ref } from 'vue';
import { useRouter } from 'vue-router';
import Button from '@/components/common/Button.vue';
import Card from '@/components/common/Card.vue';
import Input from '@/components/common/Input.vue';
import logo from '@/assets/logo.svg';
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
  <main class="relative flex min-h-screen items-center justify-center bg-bg-darkest p-4">
    <div class="absolute left-8 top-8 hidden items-center gap-3 lg:flex">
      <img :src="logo" alt="ReviewHub" class="h-9 w-auto" />
      <p class="text-xs font-medium uppercase tracking-[0.18em] text-text-secondary">The Monolith &amp; The Lens</p>
    </div>
    <Card class="login-card w-full max-w-md space-y-6">
      <div>
        <h1 class="text-3xl font-semibold">Welcome back</h1>
        <p class="mt-2 text-sm text-text-secondary">Access your editorial code space</p>
      </div>

      <form class="space-y-4" @submit.prevent="onSubmit">
        <div>
          <label class="field-label">Username or Email</label>
          <Input
            v-model="form.email"
            type="email"
            icon="person"
            required
            placeholder="you@reviewhub.dev"
          />
        </div>
        <div>
          <div class="mb-1.5 flex items-center justify-between">
            <label class="field-label mb-0">Password</label>
            <a href="#" class="text-xs text-primary transition hover:text-primary-hover">Forgot?</a>
          </div>
          <Input
            v-model="form.password"
            type="password"
            icon="lock"
            required
            placeholder="Enter password"
          />
        </div>
        <p v-if="error" class="text-sm text-error">{{ error }}</p>
        <Button type="submit" :disabled="auth.loading" class="w-full justify-center py-3 text-sm">
          {{ auth.loading ? 'Signing in...' : 'Sign In ->' }}
        </Button>
        <p class="pt-1 text-center text-sm text-text-secondary">
          New to the hub? <a href="#" class="font-medium text-primary hover:text-primary-hover">Request Access</a>
        </p>
      </form>

      <div class="space-y-2 border-t border-border pt-4">
        <button class="w-full rounded-lg border border-border bg-bg-elevated px-4 py-2 text-sm font-medium text-text-primary transition hover:border-primary">
          Continue with GitHub
        </button>
        <button class="w-full rounded-lg border border-border bg-bg-elevated px-4 py-2 text-sm font-medium text-text-primary transition hover:border-primary">
          Continue with SSO
        </button>
      </div>
    </Card>
    <footer class="absolute bottom-4 left-1/2 w-full -translate-x-1/2 px-4 text-center text-xs text-text-muted">
      © 2024 ReviewHub | Documentation | System Status | Privacy
    </footer>
  </main>
</template>
