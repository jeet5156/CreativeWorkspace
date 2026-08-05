The engine knows nothing about UI.

Nodes know nothing about storage.

Storage knows nothing about rendering.

The Registry is the single source of truth.

Capabilities replace inheritance.

Future node types require registration, not modification.

Prefer composition over conditionals.

Never add switch statements for node types.
## UI Philosophy

Explorer answers:
"Where do I go?"

Dashboard answers:
"What is happening?"

Inspector answers:
"What can I edit?"

A view should have one primary responsibility.

If a feature blurs responsibilities, redesign the feature rather than expanding the view.

Prefer clarity over density.

Prefer typography over decoration.

Prefer reusable architecture over special cases.

The user should immediately understand what is important before noticing what is possible.