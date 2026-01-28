# ROLE_ORCHESTRATOR_SPEC.md

## Статус и роль в системе

**Роль:** Role Orchestrator  
**Тип:** Stateless  
**Статус:** ARCHITECTURALLY CLOSED  
**Upstream:** Task Decomposer  
**Downstream:** Execution Roles  

Role Orchestrator является архитектурной ролью, отвечающей за детерминированное назначение исполнителей задач и фиксацию порядка их выполнения на основе уже сформированного Task Graph. Роль не участвует в интерпретации intent, не изменяет структуру задач и не координирует их выполнение во времени.

---

## Инварианты роли

- Role Orchestrator не изменяет Task Graph ни в одном аспекте.
- Каждая задача получает ровно одного исполнителя.
- Назначение исполнителей детерминировано при идентичном входном артефакте.
- Порядок исполнения задач выводится исключительно из зависимостей графа.
- Отсутствие данных не трактуется как разрешение на гипотезы или догадки.

---

## Границы ответственности

Role Orchestrator отвечает исключительно за:

- сопоставление задач допустимым классам Execution Roles;
- фиксацию порядка выполнения задач;
- формирование Execution Plan;
- подготовку Task Instruction для каждой задачи.

Role Orchestrator не отвечает за интерпретацию intent, изменение задач, их выполнение или runtime-координацию.

---

## Входной контракт (read-only)

### Task Graph Package Schema v0

```yaml
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
Входной артефакт является immutable и используется строго в режиме read-only.

Предусловия запуска
Role Orchestrator запускается только при одновременном выполнении всех условий:

task_graph.tasks не пуст;

граф задач не содержит циклов;

все зависимости depends_on ссылаются на существующие task_id.

При нарушении любого из условий Role Orchestrator обязан завершиться отказом.

Нормативное определение Execution Plan
Execution Plan — канонический артефакт, фиксирующий:

полный перечень задач из Task Graph;

детерминированное назначение Execution Role для каждой задачи;

нормативный порядок исполнения, выведенный из зависимостей.

Execution Plan не содержит логики исполнения и не интерпретирует семантику задач.

Нормативное определение Task Instruction
Task Instruction — производный артефакт, формируемый для каждой отдельной задачи на основе Execution Plan.
Task Instruction предназначен для передачи в соответствующую Execution Role и содержит только информацию, необходимую для исполнения конкретной задачи.

Алгоритм оркестрации
Role Orchestrator обязан выполнить следующие шаги в строгом порядке:

Принять task_graph_package как единственный вход.

Провалидировать предусловия запуска.

Для каждой задачи определить допустимый класс Execution Roles.

Назначить каждой задаче ровно одного исполнителя.

Вывести порядок исполнения задач исключительно из зависимостей depends_on.

Сформировать Execution Plan.

Сформировать Task Instruction для каждой задачи на основе Execution Plan.

Подготовить артефакты к передаче Execution Roles.

Выходные артефакты (Schema v0)
Execution Plan Schema v0
yaml
Копировать код
execution_plan:
  schema_version: "execution_plan_v0"

  identity:
    envelope_id: string
    req_id: string
    trace_id: string
    determinism_key: string?

  tasks:
    - task_id: string
      execution_role: string
      order_index: integer
Task Instruction Schema v0
yaml
Копировать код
task_instruction:
  schema_version: "task_instruction_v0"

  identity:
    envelope_id: string
    req_id: string
    trace_id: string
    task_id: string

  execution_role: string
  task_description: text
  depends_on: list[string]
Отказные и негативные сценарии
Role Orchestrator обязан завершиться отказом при следующих условиях:

пустой task_graph;

обнаружение циклов в графе задач;

невалидные или отсутствующие зависимости;

невозможность сопоставить задачу допустимому Execution Role.

В случае отказа выходные артефакты не формируются.

Граница с Execution Roles
Role Orchestrator:

передаёт Execution Plan и Task Instruction downstream-ролям;

не получает обратную связь о ходе или результате исполнения;

не принимает решений на основе runtime-состояний.

Execution Roles не вправе изменять Execution Plan или Task Instruction.

Статус архитектурной завершённости
ROLE_ORCHESTRATOR_SPEC.md
Version: v0
Status: ARCHITECTURALLY CLOSED

Документ является каноническим и не подлежит пересмотру.