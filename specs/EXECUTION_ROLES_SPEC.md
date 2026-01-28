# EXECUTION_ROLES_SPEC.md

## 1. Статус и роль в системе

Execution Roles — архитектурный класс ролей системы исполнения.

Тип: Stateless (per invocation)

Upstream: Role Orchestrator

Downstream: Result Assembler

Назначение: строгое исполнение одной назначенной задачи на основе переданного Task Instruction.

Execution Roles не участвуют в интерпретации намерений, формировании планов или координации выполнения. Их единственная функция — детерминированное исполнение задачи.

---

## 2. Инварианты класса Execution Roles

Для всех Execution Roles обязательны следующие инварианты:

* Роль исполняет ровно одну задачу за один запуск.
* Роль является полностью stateless.
* Роль не хранит память между вызовами.
* Роль не знает о существовании других задач.
* Роль не имеет представления о полном execution plan.
* Роль не интерпретирует intent.
* Роль не изменяет входные данные.
* Результат детерминирован при идентичном входе.
* Отсутствие данных не допускает гипотез, догадок или обобщений.

---

## 3. Границы ответственности

Execution Role отвечает исключительно за:

* Исполнение задачи, описанной в `task_description`.
* Формирование единственного выходного артефакта — Task Result.

Execution Role не отвечает за:

* Проверку зависимостей.
* Контроль порядка выполнения.
* Координацию с другими ролями.
* Обработку пользовательского контекста.
* Агрегацию или интерпретацию результатов.

---

## 4. Входной контракт (Task Instruction, read-only)

Execution Role получает ровно один входной артефакт.

### Task Instruction Schema v0

```yaml
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
```

Контракт является immutable и read-only.

Execution Role не имеет доступа к:

* execution_plan целиком;
* другим task_instruction;
* upstream-артефактам;
* пользовательскому контексту.

---

## 5. Нормативное определение Execution Role

Execution Role — это изолированная исполняющая сущность, которая:

* запускается исключительно по инициативе Role Orchestrator;
* получает один валидный Task Instruction;
* исполняет задачу строго в рамках `task_description`;
* формирует один Task Result;
* завершает выполнение.

Никакая дополнительная ответственность Execution Role не допускается.

---

## 6. Алгоритм исполнения задачи

Execution Role обязан следовать следующему нормативному алгоритму:

1. Принять Task Instruction Schema v0.
2. Зафиксировать identity как идентификатор текущего исполнения.
3. Исполнить задачу, описанную в `task_description`, без расширения или интерпретации.
4. Сформировать Task Result в соответствии со Schema v0.
5. Завершить выполнение.

Никакие дополнительные шаги не допускаются.

---

## 7. Выходной артефакт (Task Result)

Task Result является единственным допустимым выходом Execution Role.

### Task Result Schema v0

```yaml
task_result:
  schema_version: "task_result_v0"

  identity:
    envelope_id: string
    req_id: string
    trace_id: string
    task_id: string

  execution_role: string

  status: one_of ["success", "failure"]

  output:
    type: one_of ["text", "structured", "empty"]
    payload: any

  errors:
    - code: string
      message: text
```

### Инварианты Task Result

* `schema_version` обязателен.
* `identity` полностью копируется из Task Instruction.
* `execution_role` соответствует входному значению.
* `status` отражает факт выполнения задачи.
* `output` присутствует только при `status = success`.
* `errors` присутствует только при `status = failure`.
* Task Result не содержит интерпретаций, выводов или мета-оценок.

---

## 8. Отказные и негативные сценарии

Execution Role формирует Task Result со статусом `failure`, если:

* выполнение задачи невозможно в рамках `task_description`;
* входные данные недостаточны для исполнения без гипотез;
* возникает внутренняя ошибка исполнения.

Execution Role не:

* предпринимает попыток восстановления;
* запрашивает дополнительный контекст;
* повторяет выполнение.

---

## 9. Граница с Result Assembler

Execution Role:

* передаёт Task Result downstream;
* не знает о правилах агрегации;
* не адаптирует формат под итоговый ответ;
* не взаимодействует с Result Assembler напрямую.

Result Assembler рассматривает Task Result как атомарный, завершённый факт исполнения.

---

## 10. Статус архитектурной завершённости

Данный документ является архитектурно закрытым.

Все определения Execution Roles, их границы ответственности, входные и выходные контракты зафиксированы окончательно.

Изменения допускаются только через выпуск новой версии спецификации.
