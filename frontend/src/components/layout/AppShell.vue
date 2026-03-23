<script setup lang="ts">
import Header from './Header.vue';
import Sidebar from './Sidebar.vue';
</script>

<template>
  <div class="min-h-screen bg-background text-on-surface">
    <Header />
    <Sidebar />
    <main class="ml-64 pt-16 min-h-screen flex flex-col">
      <slot />
    </main>
  </div>
</template>
