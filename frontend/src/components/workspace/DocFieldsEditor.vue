<script setup lang="ts">
/** Borderless key/value field blocks (shared by world notes and character attributes). */
export interface DocFieldRow {
  key: string
  value: string
}

const rows = defineModel<DocFieldRow[]>({ required: true })

const emit = defineEmits<{ blur: [] }>()

function addField() {
  rows.value.push({ key: '', value: '' })
}

function onBlur() {
  emit('blur')
}
</script>

<template>
  <div class="doc-fields">
    <section
      v-for="(row, index) in rows"
      :key="index"
      class="doc-fields__block"
    >
      <input
        v-model="row.key"
        class="doc-fields__name"
        type="text"
        placeholder="Field name"
        spellcheck="false"
        @blur="onBlur"
      />
      <textarea
        v-model="row.value"
        class="doc-fields__value"
        rows="3"
        placeholder="Write content…"
        spellcheck="true"
        @blur="onBlur"
      />
    </section>

    <button type="button" class="doc-fields__add" @click="addField">
      + Add field
    </button>
  </div>
</template>

<style scoped>
.doc-fields {
  display: flex;
  flex-direction: column;
  gap: 28px;
}

.doc-fields__block {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.doc-fields__name {
  border: none;
  background: transparent;
  font-family: var(--font-ui);
  font-size: 0.68rem;
  font-weight: 600;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--muted);
  padding: 0;
}

.doc-fields__name:focus {
  outline: none;
  color: var(--text-soft);
}

.doc-fields__name::placeholder {
  color: rgba(138, 133, 125, 0.65);
  text-transform: none;
  letter-spacing: 0.02em;
  font-weight: 500;
}

.doc-fields__value {
  width: 100%;
  margin: 0;
  padding: 0;
  border: none;
  background: transparent;
  font-family: var(--font-ui);
  font-size: 0.95rem;
  line-height: 1.65;
  color: var(--text-soft);
  resize: vertical;
  min-height: 4.5rem;
}

.doc-fields__value:focus {
  outline: none;
  color: var(--text);
}

.doc-fields__add {
  align-self: flex-start;
  border: none;
  background: none;
  padding: 0;
  font-size: 13px;
  font-weight: 600;
  color: var(--accent-deep);
  cursor: pointer;
}

.doc-fields__add:hover {
  text-decoration: underline;
  text-underline-offset: 3px;
}
</style>
