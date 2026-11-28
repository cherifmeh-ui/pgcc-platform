# Action Plan API Safety — Test Plan

## Lifecycle checks
- New action creation is rejected if status is not `À faire`.
- Transition to `En cours` is allowed.
- Transition to `Bloqué` is allowed and logged.
- Transition to `Terminé` requires a non-empty completion description.
- A partial update setting status to `Terminé` validates the existing effective description.
- A completed action cannot be reopened through the current API (409).
- A completed action cannot be hard-deleted through the current API (409).
- Deleting an unfinished action is logged and permitted under existing RBAC.
- Action creation rejects nonexistent risks.
- Unauthorized users cannot read/create/update/delete actions.
- Updates preserve omitted fields.

## Follow-up requirements
The current description is only a temporary completion record. A formal evidence attachment, validation user/date, comments/history, archival status, linked controls, notifications and overdue reporting require dedicated models and migrations. Until those exist, the API must not claim evidence-based validation.
