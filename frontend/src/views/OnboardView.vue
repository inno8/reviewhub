<script setup lang="ts">
import { ref, nextTick, onUnmounted } from 'vue';
import { useRouter } from 'vue-router';
import { api } from '@/composables/useApi';

const router = useRouter();

const step = ref<'email' | 'otp' | 'password' | 'success'>('email');
const email = ref('');
const username = ref('');
const otpDigits = ref(['', '', '', '', '']);
const password = ref('');
const confirmPassword = ref('');
const error = ref('');
const loading = ref(false);
const onboardToken = ref('');
const resendCooldown = ref(0);

let resendTimer: ReturnType<typeof setInterval> | null = null;
let redirectTimer: ReturnType<typeof setTimeout> | null = null;

onUnmounted(() => {
  if (resendTimer) clearInterval(resendTimer);
  if (redirectTimer) clearTimeout(redirectTimer);
});

function startResendCooldown() {
  resendCooldown.value = 60;
  resendTimer = setInterval(() => {
    resendCooldown.value--;
    if (resendCooldown.value <= 0 && resendTimer) {
      clearInterval(resendTimer);
      resendTimer = null;
    }
  }, 1000);
}

async function handleCheckEmail() {
  error.value = '';
  loading.value = true;
  try {
    const { data } = await api.onboard.checkEmail(email.value);
    if (!data.found) {
      error.value = 'No account found with this email address.';
    } else if (data.alreadyOnboarded) {
      error.value = 'This account is already set up. Please sign in instead.';
    } else {
      username.value = data.username;
      step.value = 'otp';
      startResendCooldown();
    }
  } catch (e: any) {
    error.value = e.response?.data?.error || 'Something went wrong. Please try again.';
  } finally {
    loading.value = false;
  }
}

function handleOtpInput(index: number, event: Event) {
  const input = event.target as HTMLInputElement;
  const value = input.value.replace(/\D/g, '');
  otpDigits.value[index] = value.slice(-1);
  input.value = otpDigits.value[index];

  if (value && index < 4) {
    nextTick(() => {
      const next = document.getElementById(`otp-${index + 1}`);
      next?.focus();
    });
  }
}

function handleOtpKeydown(index: number, event: KeyboardEvent) {
  if (event.key === 'Backspace' && !otpDigits.value[index] && index > 0) {
    nextTick(() => {
      const prev = document.getElementById(`otp-${index - 1}`);
      prev?.focus();
    });
  }
}

function handleOtpPaste(event: ClipboardEvent) {
  event.preventDefault();
  const pasted = (event.clipboardData?.getData('text') || '').replace(/\D/g, '').slice(0, 5);
  for (let i = 0; i < 5; i++) {
    otpDigits.value[i] = pasted[i] || '';
  }
  const focusIndex = Math.min(pasted.length, 4);
  nextTick(() => {
    document.getElementById(`otp-${focusIndex}`)?.focus();
  });
}

async function handleVerifyCode() {
  const code = otpDigits.value.join('');
  if (code.length !== 5) {
    error.value = 'Please enter the full 5-digit code.';
    return;
  }
  error.value = '';
  loading.value = true;
  try {
    const { data } = await api.onboard.verifyCode(email.value, code);
    if (data.valid) {
      onboardToken.value = data.token;
      step.value = 'password';
    } else {
      error.value = data.error || 'Invalid or expired code.';
    }
  } catch (e: any) {
    error.value = e.response?.data?.error || 'Verification failed. Please try again.';
  } finally {
    loading.value = false;
  }
}

async function handleResendCode() {
  if (resendCooldown.value > 0) return;
  error.value = '';
  loading.value = true;
  try {
    await api.onboard.checkEmail(email.value);
    startResendCooldown();
  } catch {
    error.value = 'Failed to resend code.';
  } finally {
    loading.value = false;
  }
}

async function handleSetPassword() {
  if (password.value.length < 8) {
    error.value = 'Password must be at least 8 characters.';
    return;
  }
  if (password.value !== confirmPassword.value) {
    error.value = 'Passwords do not match.';
    return;
  }
  error.value = '';
  loading.value = true;
  try {
    const { data } = await api.onboard.setPassword(onboardToken.value, password.value);
    if (data.success) {
      step.value = 'success';
      redirectTimer = setTimeout(() => {
        router.push('/login');
      }, 3000);
    }
  } catch (e: any) {
    error.value = e.response?.data?.error || 'Failed to set password. Please try again.';
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="min-h-screen flex flex-col items-center justify-center p-6 tonal-stacking-bg">
    <main class="w-full max-w-md">
      <!-- Brand Identity -->
      <div class="flex flex-col items-center mb-10">
        <div class="mb-4 bg-surface-container-highest p-4 rounded-xl">
          <span class="material-symbols-outlined text-primary text-4xl">terminal</span>
        </div>
        <h1 class="text-3xl font-extrabold tracking-tight text-on-surface">
          Review<span class="text-primary-container">Hub</span>
        </h1>
        <p class="text-on-surface-variant mt-2 text-sm tracking-wide">THE MONOLITH & THE LENS</p>
      </div>

      <!-- Onboard Card -->
      <div class="bg-surface-container-low rounded-xl border border-outline-variant/15 p-8 shadow-2xl relative overflow-hidden">
        <!-- Asymmetric Glow Accent -->
        <div class="absolute -top-24 -right-24 w-48 h-48 bg-primary/10 blur-[64px] rounded-full"></div>

        <div class="relative z-10">
          <!-- Step 1: Email -->
          <div v-if="step === 'email'">
            <header class="mb-8">
              <h2 class="text-xl font-bold text-on-surface">Set up your account</h2>
              <p class="text-on-surface-variant text-sm mt-1">Enter your email to get started</p>
            </header>

            <div v-if="error" class="mb-6 p-3 bg-error/10 border border-error/20 rounded-lg">
              <p class="text-error text-sm">{{ error }}</p>
            </div>

            <form @submit.prevent="handleCheckEmail" class="space-y-6">
              <div class="space-y-2">
                <label class="block text-xs font-semibold uppercase tracking-widest text-outline ml-1">
                  Email
                </label>
                <div class="relative">
                  <span class="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-outline text-xl">mail</span>
                  <input
                    v-model="email"
                    type="email"
                    placeholder="your_email@reviewhub.io"
                    class="w-full bg-surface-container-lowest border border-outline-variant/30 text-on-surface rounded-lg py-3 pl-10 pr-4 focus:outline-none focus:ring-1 focus:ring-primary/50 focus:border-primary transition-all placeholder:text-outline/40"
                    required
                  />
                </div>
              </div>

              <button
                type="submit"
                :disabled="loading"
                class="w-full primary-gradient text-on-primary font-bold py-3.5 rounded-lg active:scale-[0.98] transition-transform flex items-center justify-center gap-2 group disabled:opacity-50"
              >
                <span>{{ loading ? 'Checking...' : 'Continue' }}</span>
                <span class="material-symbols-outlined text-sm transition-transform group-hover:translate-x-1">arrow_forward</span>
              </button>
            </form>

            <div class="mt-8 pt-6 border-t border-outline-variant/10 text-center">
              <p class="text-sm text-on-surface-variant">
                Already have a password?
                <router-link to="/login" class="text-primary-container font-semibold hover:underline ml-1">Sign in</router-link>
              </p>
            </div>
          </div>

          <!-- Step 2: OTP -->
          <div v-if="step === 'otp'">
            <header class="mb-8">
              <h2 class="text-xl font-bold text-on-surface">Welcome, {{ username }}!</h2>
              <p class="text-on-surface-variant text-sm mt-1">We sent a 5-digit code to {{ email }}</p>
            </header>

            <div v-if="error" class="mb-6 p-3 bg-error/10 border border-error/20 rounded-lg">
              <p class="text-error text-sm">{{ error }}</p>
            </div>

            <form @submit.prevent="handleVerifyCode" class="space-y-6">
              <div class="flex justify-center gap-3" @paste="handleOtpPaste">
                <input
                  v-for="(_, i) in 5"
                  :key="i"
                  :id="`otp-${i}`"
                  type="text"
                  inputmode="numeric"
                  maxlength="1"
                  :value="otpDigits[i]"
                  @input="handleOtpInput(i, $event)"
                  @keydown="handleOtpKeydown(i, $event)"
                  class="w-14 h-14 text-center text-2xl font-bold bg-surface-container-lowest border border-outline-variant/30 text-on-surface rounded-lg focus:outline-none focus:ring-1 focus:ring-primary/50 focus:border-primary transition-all"
                />
              </div>

              <button
                type="submit"
                :disabled="loading"
                class="w-full primary-gradient text-on-primary font-bold py-3.5 rounded-lg active:scale-[0.98] transition-transform flex items-center justify-center gap-2 group disabled:opacity-50"
              >
                <span>{{ loading ? 'Verifying...' : 'Verify Code' }}</span>
                <span class="material-symbols-outlined text-sm transition-transform group-hover:translate-x-1">check</span>
              </button>
            </form>

            <div class="mt-6 text-center">
              <button
                @click="handleResendCode"
                :disabled="resendCooldown > 0 || loading"
                class="text-sm text-primary-container font-semibold hover:underline disabled:opacity-50 disabled:no-underline"
              >
                {{ resendCooldown > 0 ? `Resend code in ${resendCooldown}s` : 'Resend code' }}
              </button>
            </div>
          </div>

          <!-- Step 3: Password -->
          <div v-if="step === 'password'">
            <header class="mb-8">
              <h2 class="text-xl font-bold text-on-surface">Set your password</h2>
              <p class="text-on-surface-variant text-sm mt-1">Choose a secure password for your account</p>
            </header>

            <div v-if="error" class="mb-6 p-3 bg-error/10 border border-error/20 rounded-lg">
              <p class="text-error text-sm">{{ error }}</p>
            </div>

            <form @submit.prevent="handleSetPassword" class="space-y-6">
              <div class="space-y-2">
                <label class="block text-xs font-semibold uppercase tracking-widest text-outline ml-1">
                  Password
                </label>
                <div class="relative">
                  <span class="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-outline text-xl">lock</span>
                  <input
                    v-model="password"
                    type="password"
                    placeholder="••••••••"
                    class="w-full bg-surface-container-lowest border border-outline-variant/30 text-on-surface rounded-lg py-3 pl-10 pr-4 focus:outline-none focus:ring-1 focus:ring-primary/50 focus:border-primary transition-all placeholder:text-outline/40"
                    required
                  />
                </div>
              </div>

              <div class="space-y-2">
                <label class="block text-xs font-semibold uppercase tracking-widest text-outline ml-1">
                  Confirm Password
                </label>
                <div class="relative">
                  <span class="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-outline text-xl">lock_reset</span>
                  <input
                    v-model="confirmPassword"
                    type="password"
                    placeholder="••••••••"
                    class="w-full bg-surface-container-lowest border border-outline-variant/30 text-on-surface rounded-lg py-3 pl-10 pr-4 focus:outline-none focus:ring-1 focus:ring-primary/50 focus:border-primary transition-all placeholder:text-outline/40"
                    required
                  />
                </div>
              </div>

              <p class="text-xs text-outline ml-1">Minimum 8 characters</p>

              <button
                type="submit"
                :disabled="loading"
                class="w-full primary-gradient text-on-primary font-bold py-3.5 rounded-lg active:scale-[0.98] transition-transform flex items-center justify-center gap-2 group disabled:opacity-50"
              >
                <span>{{ loading ? 'Setting password...' : 'Set Password' }}</span>
                <span class="material-symbols-outlined text-sm transition-transform group-hover:translate-x-1">arrow_forward</span>
              </button>
            </form>
          </div>

          <!-- Step 4: Success -->
          <div v-if="step === 'success'" class="text-center py-4">
            <div class="mb-6 bg-primary/10 p-5 rounded-full inline-block">
              <span class="material-symbols-outlined text-primary text-5xl">check_circle</span>
            </div>
            <h2 class="text-xl font-bold text-on-surface mb-2">You're all set!</h2>
            <p class="text-on-surface-variant text-sm mb-8">Your password has been created. Redirecting to login...</p>
            <router-link
              to="/login"
              class="inline-flex items-center gap-2 primary-gradient text-on-primary font-bold py-3 px-8 rounded-lg active:scale-[0.98] transition-transform"
            >
              <span>Go to Login</span>
              <span class="material-symbols-outlined text-sm">arrow_forward</span>
            </router-link>
          </div>
        </div>
      </div>
    </main>

    <!-- Footer -->
    <footer class="mt-auto py-8 w-full max-w-4xl flex flex-col md:flex-row justify-between items-center px-6 gap-4">
      <div class="text-[10px] uppercase tracking-[0.2em] text-outline font-medium">
        &copy; 2024 ReviewHub
      </div>
      <div class="flex gap-6">
        <a href="#" class="text-[10px] uppercase tracking-[0.2em] text-outline hover:text-primary transition-colors">Documentation</a>
        <a href="#" class="text-[10px] uppercase tracking-[0.2em] text-outline hover:text-primary transition-colors">System Status</a>
        <a href="#" class="text-[10px] uppercase tracking-[0.2em] text-outline hover:text-primary transition-colors">Privacy</a>
      </div>
    </footer>

    <!-- Decorative Elements -->
    <div class="fixed top-0 left-0 w-full h-full pointer-events-none z-[-1] opacity-20 overflow-hidden">
      <div class="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-primary/20 blur-[120px] rounded-full"></div>
      <div class="absolute bottom-[-10%] right-[-10%] w-[30%] h-[30%] bg-secondary/10 blur-[100px] rounded-full"></div>
    </div>
  </div>
</template>
