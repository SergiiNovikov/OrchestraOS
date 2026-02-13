OrchestraOS/
  artifacts/        # v0 FROZEN
  roles/            # v0 role boundaries (как сейчас) FROZEN
  runtime/          # v0 FROZEN
  specs/            # v0 FROZEN
  tests/            # v0 tests FROZEN (новые тесты — только в новом дереве)
  tools/            # v0 FROZEN
  validation/       # v0 FROZEN

  apps/                     # NEW: точки входа (интерфейс общения)
    front_cli/              # NEW: минимальный CLI Front Manager
      __init__.py
      __main__.py           # python -m apps.front_cli ...
      config.py             # загрузка профиля/настроек (детерминированно)
      io.py                 # stdin/stdout + режим REPL
      adapters.py           # преобразование текста -> request_envelope_v0

  extensions/               # NEW: всё прикладное “поверх v0”
    rolepacks/              # NEW: реальные реализации ролей
      v1_tz/                # NEW: первый rolepack (формирование ТЗ/планов)
        __init__.py
        registry.py         # маппинг role_id -> callable/класс
        intent_interpreter.py
        task_decomposer.py
        prompts/            # шаблоны/инструкции (если LLM)
          intent_interpreter.md
          task_decomposer.md
        fixtures/           # эталонные входы/выходы для golden-тестов rolepack
          cases/

    profiles/               # NEW: профили запуска (без изменения v0 контрактов)
      tz_cli_default.json   # режим, maturity, source, policy knobs, etc.

  tests_ext/                # NEW: тесты поверх v0 (не трогаем tests/)
    e2e_cli/                # прогон "текст -> pipeline -> результат"
    rolepacks/              # golden/determinism для rolepack
    contracts_overlay/      # проверка что envelope формируется строго в v0


2) Дорожная карта реализации (минимально, но “в продакшен-режиме”)

Ниже не “идеальная в теории”, а самая короткая траектория до того состояния, когда ты реально пишешь текстом задачи и получаешь оформленные ТЗ/планы.

Milestone 0 — CLI как тонкий Front Manager (без “умных ролей”)

Цель: запустить end-to-end путь: текст → request_envelope_v0 → runtime → output/manifest.

Deliverables:

apps/front_cli/__main__.py

extensions/profiles/tz_cli_default.json

tests_ext/contracts_overlay/test_cli_envelope_is_v0_valid.py

Критерии готовности:

CLI принимает --text и --repl

CLI формирует request_envelope_v0 строго валидный через ваш validation слой (fail-closed)

один прогон создаёт сохранённый run (куда у вас принято) и печатает assembled result

Это делает систему “разговорной” технически, но смысл ещё будет пустой/заглушечный, пока нет rolepack.

Milestone 1 — Rolepack v1: Intent Interpreter (реальный)

Цель: первый “смысловой” слой: из Scoped Request получить intent_package_v0 (или ваш канонический артефакт для Intent Interpreter) — строго по спецификации, без расширения ответственности.

Deliverables:

extensions/rolepacks/v1_tz/intent_interpreter.py

extensions/rolepacks/v1_tz/prompts/intent_interpreter.md (если LLM)

extensions/rolepacks/v1_tz/registry.py (регистрация реализации)

tests_ext/rolepacks/test_intent_interpreter_golden.py

Критерии готовности:

На вход: только разрешённый upstream-артефакт (как в v0 specs)

На выход: строго валидный intent-артефакт по v0 schema

Golden-тесты: 5–10 кейсов “вопрос пользователя → intent”

Milestone 2 — Rolepack v1: Task Decomposer (реальный)

Цель: превратить intent в task_graph_package_v0 (или ваш канонический выход TD), чтобы дальше pipeline реально строил план работ.

Deliverables:

extensions/rolepacks/v1_tz/task_decomposer.py

extensions/rolepacks/v1_tz/prompts/task_decomposer.md

tests_ext/rolepacks/test_task_decomposer_golden.py

tests_ext/e2e_cli/test_cli_makes_tz_plan.py

Критерии готовности:

Task graph детерминирован в рамках вашего режима (как у вас принято: “deterministic aggregation”, “stable_input_key” и т.п.)

На одинаковый вход CLI выдаёт одинаковый task graph (проверка стабилизации на N прогонов — поверх, не трогая v0 determinism suite)

Milestone 3 — Подключение rolepack в runtime (без правки v0)

Цель: runtime остаётся v0, но получает внешнюю реализацию ролей.

Это делается “поверх” так:

либо через уже существующий механизм “role registry/provider” (если он есть в v0)

либо через инъекцию на уровне CLI: CLI формирует run_context/конфиг так, чтобы runtime при разрешении роли брал её из extensions/rolepacks/...

Deliverables:

apps/front_cli/config.py — выбор rolepack профилем

extensions/rolepacks/v1_tz/registry.py — единая точка маппинга

tests_ext/e2e_cli/test_cli_uses_rolepack.py

Критерии готовности:

Переключение rolepack без изменения v0: --profile tz_cli_default

Невозможность “подсунуть” незарегистрированную роль (fail-closed)

Milestone 4 — “Практическое общение”: шаблоны диалога для ТЗ/планов

Цель: ты реально ведёшь диалог и получаешь:

Draft ТЗ

WBS / план этапов

список рисков/допущений

критерии готовности

Deliverables:

extensions/rolepacks/v1_tz/fixtures/cases/ — набор кейсов (минимум 10)

tests_ext/e2e_cli/test_tz_outputs_sections.py — проверка структуры результата


