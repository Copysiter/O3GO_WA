---
name: ok:project.init
description: Инициализация структуры проектной документации из шаблонов
agent: code
---

Создать рабочее пространство проектной документации путём копирования файлов шаблонов в рабочую директорию.

## Шаги

1. Создать `.opencode/project/`, если директория ещё не существует
2. Создать `.opencode/templates/project/`, если директория ещё не существует
3. Скопировать каждый шаблон в `.opencode/project/` как рабочий документ:
   - `overview.template.md` → `overview.md`
   - `architecture.template.md` → `architecture.md`
   - `stack.template.md` → `stack.md`
   - `structure.template.md` → `structure.md`
   - `conventions.template.md` → `conventions.md`
   - `constraints.template.md` → `constraints.md`
   - `integrations.template.md` → `integrations.md`
   - `changes.template.md` → `changes.md`
4. Сохранить все маркеры `[TEMPLATE_GUIDE]`, `[TEMPLATE_EXAMPLE]` и `{{placeholder}}` без изменений
5. Установить frontmatter `status: empty` в каждом скопированном файле
6. Не анализировать репозиторий и не генерировать контент
7. Если файлы уже существуют в `.opencode/project/`, запросить подтверждение пользователя перед перезаписью

По завершении сообщить, какие файлы были созданы.
