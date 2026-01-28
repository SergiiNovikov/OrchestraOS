# TASK_DECOMPOSER_SPEC.md

## Статус и роль в системе

**Роль:** Task Decomposer  
**Тип роли:** Stateless  
**Архитектурный уровень:** Deterministic Planning Layer  
**Upstream:** Intent Interpreter  
**Downstream:** Role Orchestrator  

Task Decomposer является архитектурно изолированной ролью, отвечающей исключительно за детерминированную декомпозицию разрешённого намерения в структуру задач без интерпретации, оптимизации или исполнения.

---

## Инварианты роли

- Декомпозиция не добавляет новый смысл.
- Все задачи выводятся строго из `intent_goal`.
- Результат детерминирован при идентичном входе.
- Отсутствие данных не допускает гипотез или домысливаний.
- Каждая задача:
  - атомарна;
  - проверяема;
  - исполнима независимо.
- Границы intent не изменяются.

---

## Границы ответственности

Task Decomposer **обязан**:
- разложить `intent_goal` на минимально необходимые задачи;
- выявить логические зависимости между задачами;
- зафиксировать порядок выполнения;
- сформировать Task Graph без исполнения и оптимизации.

Task Decomposer **не имеет права**:
- интерпретировать или переосмысливать intent;
- изменять `intent_goal` или intent-constraints;
- назначать роли;
- выполнять задачи;
- оптимизировать или упрощать план;
- добавлять шаги, не вытекающие из `intent_goal`.

---

## Входной контракт (Intent Package, read-only)

**Schema:** `intent_package_v0`  
**Режим доступа:** immutable, read-only  

```yaml
intent_package:
  schema_version: "intent_package_v0"

  identity:
    envelope_id: string
    req_id: string
    trace_id: string
    determinism_key: string?

  source_fingerprint:
    baseline_norm_hash: string

  intent_definition:
    intent_status: enum  # RESOLVED | AMBIGUOUS | BLOCKED
    intent_label: enum?
    intent_goal: text?
    constraints:
      allowed_contours: list[enum]
      required_by_contract: list[text]

  ambiguity_report:
    ambiguous: boolean
    ambiguity_reason: list[text]?

  conflict_report:
    conflicts_present: boolean
    conflict_summary: list[text]?

  handoff:
    target_role: "task_decomposer"
    notes_for_downstream: list[text]
Предусловия запуска
Task Decomposer запускается только если:

intent_status == RESOLVED

При AMBIGUOUS или BLOCKED:

декомпозиция не выполняется;

роль завершает работу с отказным статусом.

Нормативное определение Task
Task — это минимальная логическая единица действия, строго выведенная из intent_goal, обладающая следующими свойствами:

атомарность (не подлежит дальнейшей декомпозиции в рамках данного intent);

проверяемость результата;

независимая исполнимость при соблюдении зависимостей.

Task не содержит указаний на исполнителя, способ реализации или оптимизацию.

Алгоритм декомпозиции
Принять intent_package в неизменном виде.

Проверить предусловие intent_status == RESOLVED.

Извлечь intent_goal как единственный источник смысла.

Детерминированно разложить intent_goal на минимальный набор задач.

Определить логические зависимости между задачами.

Зафиксировать порядок выполнения задач.

Сформировать Task Graph.

Никакие дополнительные источники смысла не используются.

Правила формирования Task Graph
Task Graph представляет собой направленный ациклический граф (DAG).

Узлы графа — задачи.

Рёбра графа — строгие логические зависимости выполнения.

Граф не содержит:

циклов;

альтернативных ветвлений, не вытекающих из intent;

оптимизационных или эвристических связей.

Порядок выполнения полностью определяется зависимостями.

Выходной артефакт
Task Graph Package — Schema v0
Единственный допустимый выходной артефакт Task Decomposer.

yaml
Копировать код
task_graph_package:
  schema_version: "task_graph_v0"

  identity:
    envelope_id: string
    req_id: string
    trace_id: string
    determinism_key: string?

  source_fingerprint:
    baseline_norm_hash: string

  task_graph:
    tasks:
      - task_id: string
        description: text
        depends_on: list[string]

  handoff:
    target_role: "role_orchestrator"
Отказные и негативные сценарии
Task Decomposer обязан завершиться отказом при следующих условиях:

intent_status != RESOLVED;

отсутствует intent_goal;

выявлена невозможность сформировать задачи без добавления нового смысла;

обнаружена неоднозначность, не отражённая upstream.

В отказном сценарии Task Graph не формируется.

Граница с Role Orchestrator
Task Decomposer передаёт только task_graph_package.

Не передаёт:

интерпретации;

приоритеты;

указания по ролям или исполнению.

Role Orchestrator не имеет права запрашивать дополнительный контекст вне выходного артефакта.

Статус архитектурной завершённости
Документ TASK_DECOMPOSER_SPEC.md является канонической архитектурной спецификацией роли Task Decomposer.

Статус: CLOSED

Изменения, расширения или интерпретации вне данного документа недопустимы.