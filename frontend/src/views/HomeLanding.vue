<script setup lang="ts">
import { useRouter } from 'vue-router'

/**
 * Landing — two entries: chat-driven creation, or the project library.
 */
const router = useRouter()
</script>

<template>
  <main class="home">
    <div class="home__inner">
      <p class="eyebrow home__eyebrow">Original Character Studio</p>
      <h1 class="home__title">OC&nbsp;Creative&nbsp;Suite</h1>
      <p class="home__sub">A calm, paper-quiet workspace for building original characters.</p>

      <div class="home__actions">
        <button type="button" class="home__card" @click="router.push('/chat')">
          <span class="home__card-icon">✦</span>
          <span class="home__card-title">Chat</span>
          <span class="home__card-desc">Think out loud — ideas become nodes.</span>
        </button>
        <button type="button" class="home__card" @click="router.push('/library')">
          <span class="home__card-icon">❏</span>
          <span class="home__card-title">Library</span>
          <span class="home__card-desc">Open or start a project.</span>
        </button>
      </div>
    </div>
  </main>
</template>

<style scoped>
.home {
  height: 100vh;
  display: grid;
  place-items: center;
  background:
    radial-gradient(circle at 50% 18%, rgba(124, 92, 255, 0.06), transparent 55%),
    var(--app-bg);
}
.home__inner {
  text-align: center;
  animation: floatIn 0.5s cubic-bezier(0.22, 1, 0.36, 1) both;
}
.home__eyebrow {
  margin-bottom: 14px;
}
.home__title {
  font-size: clamp(2.4rem, 6vw, 3.6rem);
  font-weight: 500;
  letter-spacing: -0.02em;
  color: var(--text);
}
.home__sub {
  margin: 14px auto 0;
  max-width: 380px;
  color: var(--muted);
  font-size: 0.98rem;
  line-height: 1.6;
}
.home__actions {
  display: flex;
  gap: 18px;
  justify-content: center;
  margin-top: 40px;
}
.home__card {
  width: 220px;
  padding: 26px 22px;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--panel);
  box-shadow: var(--shadow-sm);
  cursor: pointer;
  text-align: left;
  transition: transform 0.2s cubic-bezier(0.34, 1.4, 0.64, 1), box-shadow 0.2s, border-color 0.2s;
}
.home__card:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-md);
  border-color: var(--accent-border);
}
.home__card-icon {
  font-size: 1.5rem;
  color: var(--accent);
}
.home__card-title {
  font-family: var(--font-display);
  font-size: 1.4rem;
  font-weight: 500;
  color: var(--text);
}
.home__card-desc {
  color: var(--muted);
  font-size: 0.85rem;
  line-height: 1.5;
}
.home__card:nth-child(2) .home__card-icon {
  color: var(--warm);
}
</style>
