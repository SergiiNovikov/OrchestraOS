Appendix A
ERROR_CODE_DICTIONARY_v0.md
1. Статус документа

Document: ERROR_CODE_DICTIONARY_v0.md
Version: v0
Status: SUBORDINATE TO ARCHITECTURE (non-canonical)
Scope: единый нормативный словарь кодов ошибок рантайма для всех ролей и стадий исполнения.

Данный словарь:

MUST использоваться всеми ролями и инфраструктурными компонентами;

MUST NOT изменять архитектурные контракты;

MUST обеспечивать детерминированную классификацию отказов.

2. Общая структура ошибки

Каждый отказ в рантайме MUST быть представлен в структурированном виде и включать:

error:
  error_code: string
  error_class: enum
  role_id: string
  artifact_expected: string
  determinism_key: string
  message: text

3. Классы ошибок (error_class)
CONTRACT_VIOLATION

Нарушение межрольного или артефактного контракта.

INVALID_INPUT

Некорректный или неполный входной артефакт.

RUNTIME_FAILURE

Инфраструктурная или исполнительская ошибка.

UNSUPPORTED_VERSION

Несовместимая версия артефакта, spec’а или политики.

4. Словарь кодов ошибок (v0)
4.1. Общие (GLOBAL)
error_code	error_class	Описание
GLOBAL_MISSING_INPUT	INVALID_INPUT	Отсутствует обязательный входной артефакт
GLOBAL_SCHEMA_INVALID	CONTRACT_VIOLATION	Артефакт не соответствует схеме
GLOBAL_UNSUPPORTED_VERSION	UNSUPPORTED_VERSION	Версия артефакта/спека не поддерживается
GLOBAL_DETERMINISM_MISMATCH	CONTRACT_VIOLATION	Нарушена детерминированность исполнения
4.2. Scope / Intent / Planning
error_code	error_class	Описание
INTENT_NOT_RESOLVED	CONTRACT_VIOLATION	Intent не имеет статуса RESOLVED
SCOPE_VIOLATION	CONTRACT_VIOLATION	Нарушены allowed / disallowed contours
TASK_GRAPH_INVALID	CONTRACT_VIOLATION	Некорректный Task Graph (циклы, зависимости)
4.3. Orchestration
error_code	error_class	Описание
NO_EXECUTION_ROLE	CONTRACT_VIOLATION	Невозможно назначить Execution Role
MULTIPLE_EXECUTORS	CONTRACT_VIOLATION	Нарушение правила “одна задача — один исполнитель”
EXECUTION_PLAN_INVALID	CONTRACT_VIOLATION	Execution Plan невалиден
4.4. Execution
error_code	error_class	Описание
TASK_EXECUTION_FAILED	RUNTIME_FAILURE	Ошибка при выполнении задачи
TASK_INPUT_INSUFFICIENT	INVALID_INPUT	Недостаточно данных для выполнения задачи
TASK_NON_DETERMINISTIC	CONTRACT_VIOLATION	Выявлен недетерминированный результат
4.5. Aggregation / Finalization
error_code	error_class	Описание
RESULT_SET_INCOMPLETE	CONTRACT_VIOLATION	Неполный набор task_result
RESULT_IDENTITY_MISMATCH	CONTRACT_VIOLATION	Несогласованные identity поля
FINAL_ASSEMBLY_FAILED	RUNTIME_FAILURE	Ошибка при формировании финального артефакта
5. Инварианты словаря

error_code MUST быть стабильным внутри версии v0.

error_code MUST NOT интерпретироваться семантически (строка — это идентификатор).

Новые коды ошибок допускаются только в v1+.

Роль MUST NOT генерировать произвольные error_code.

6. Статус завершённости

ERROR_CODE_DICTIONARY_v0.md считается зафиксированным и обязательным к использованию для всех ролей и инфраструктурных компонентов системы.